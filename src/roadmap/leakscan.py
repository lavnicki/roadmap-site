"""Leak scanner for rendered output, the live site and the repository (RNF-Q 8, defense in depth).

Layers, all reported as Q8 issues that name only *where* and *what kind*, never the match:
1. forbidden terms (secret list, see ``confidentiality``);
2. secret-like patterns (keys, tokens, service-account emails, sheet URLs, CPF, phones, emails);
3. sensitive literals known at run time (sheet id, service-account email/project/key id);
4. private vocabulary that only exists in non-public parts of the sheet;
5. link allowlist and published file types.

HTML is scanned as text after unescaping entities and stripping tags, *plus* every attribute
value, so ``Nu<b>bank</b>``, ``&#78;ubank`` or a term hidden in ``title=""`` are still caught.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from roadmap.confidentiality import _AFTER, _BEFORE, find_forbidden, normalize
from roadmap.models import Issue

# Patterns are deliberately broad: a false positive only blocks a deploy, a miss leaks.
SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\"private_key\"\s*:"),
    "google api key": re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    "google oauth token": re.compile(r"ya29\.[0-9A-Za-z_\-]{20,}"),
    "github token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),
    "openai key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}"),
    "aws access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "service account email": re.compile(r"[\w.\-]+@[\w\-]+\.iam\.gserviceaccount\.com"),
    "google sheet url": re.compile(r"docs\.google\.com/spreadsheets", re.I),
    "cpf": re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)"),
    "phone number": re.compile(r"(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9\d{4}[\s\-]?\d{4}(?!\d)"),
    # Local part must start with a letter/digit: "+@pytest.mark" (a diff line) is not an email.
    "email address": re.compile(
        r"(?<![\w.%+\-])[A-Za-z0-9][A-Za-z0-9._%+\-]*@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+"
    ),
}

# Emails that are fine to appear in the repository (bot and attribution addresses).
ALLOWED_EMAILS = re.compile(
    r"noreply@anthropic\.com|[\w.+\-\[\]]+@users\.noreply\.github\.com", re.I
)

_SAFE_DATA_URI = re.compile(r"^data:image/svg\+xml[,;]", re.I)


@dataclass(frozen=True)
class Guardrails:
    private_vocabulary: list[str] = field(default_factory=list)
    allowed_link_hosts: list[str] = field(default_factory=list)
    allowed_file_suffixes: list[str] = field(default_factory=lambda: [".html", ".css", ""])


def load_guardrails(path: Path) -> Guardrails:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Guardrails(
        private_vocabulary=list(data.get("private_vocabulary", [])),
        allowed_link_hosts=[h.lower() for h in data.get("allowed_link_hosts", [])],
        allowed_file_suffixes=list(data.get("allowed_file_suffixes", [".html", ".css", ""])),
    )


class _Collector(HTMLParser):
    """Collects visible text, every attribute value and link targets."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.joined: list[str] = []  # text with tags removed (catches Nu<b>bank</b>)
        self.spaced: list[str] = []  # text with tags as spaces (keeps word boundaries)
        self.attrs: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.spaced.append(" ")
        for name, value in attrs:
            if value is None:
                continue
            self.attrs.append(value)
            if name in ("href", "src", "action", "srcset", "poster", "data"):
                self.links.append(value.strip())

    def handle_endtag(self, tag: str) -> None:
        self.spaced.append(" ")

    def handle_data(self, data: str) -> None:
        self.joined.append(data)
        self.spaced.append(data)

    def handle_comment(self, data: str) -> None:
        # Comments are shipped to every visitor even though they are not rendered.
        self.attrs.append(data)


def html_to_scan_text(markup: str) -> tuple[str, list[str]]:
    """Return (text to scan, link targets) for an HTML document."""
    parser = _Collector()
    parser.feed(markup)
    parser.close()
    text = "\n".join(
        ["".join(parser.joined), "".join(parser.spaced), *(html.unescape(a) for a in parser.attrs)]
    )
    return text, parser.links


def _issue(location: str, kind: str) -> Issue:
    return Issue(tab="Content", row=None, rule="Q8", message=f"{kind} found in {location}")


def _vocab_regex(word: str) -> re.Pattern[str]:
    parts = [re.escape(p) for p in normalize(word).split()]
    return re.compile(_BEFORE + r"\s+".join(parts) + _AFTER)


def scan_text(
    location: str,
    text: str,
    terms: list[str],
    guardrails: Guardrails,
    literals: list[str] | None = None,
    *,
    check_vocabulary: bool = True,
    allowed_emails: re.Pattern[str] | None = None,
) -> list[Issue]:
    """Scan one text blob; one issue per (location, kind)."""
    issues: list[Issue] = []
    if find_forbidden([(location, text)], terms):
        issues.append(_issue(location, "forbidden term"))
    for name, pattern in SECRET_PATTERNS.items():
        matches = pattern.findall(text)
        if name == "email address" and allowed_emails is not None:
            matches = [m for m in matches if not allowed_emails.fullmatch(m)]
        if matches:
            issues.append(_issue(location, f"secret-like pattern '{name}'"))
    norm = normalize(text)
    for literal in literals or []:
        if literal and normalize(literal) in norm:
            issues.append(_issue(location, "sensitive literal"))
            break
    if check_vocabulary and any(
        _vocab_regex(w).search(norm) for w in guardrails.private_vocabulary
    ):
        issues.append(_issue(location, "private vocabulary"))
    return issues


def check_link(location: str, target: str, guardrails: Guardrails) -> Issue | None:
    """Allow relative links, in-page anchors, inline SVG data URIs and https to allowed hosts."""
    t = target.strip()
    if not t or t.startswith("#"):
        return None
    if _SAFE_DATA_URI.match(t):
        return None
    parts = urlsplit(t)
    if not parts.scheme and not parts.netloc:
        return None  # relative path
    host = (parts.hostname or "").lower()
    if parts.scheme == "https" and host in guardrails.allowed_link_hosts:
        return None
    return Issue(
        tab="Content",
        row=None,
        rule="Q8",
        message=f"link to a non-allowed destination ({parts.scheme or 'no scheme'}://"
        f"{host or '?'}) in {location}",
    )


def scan_document(
    location: str,
    content: str,
    suffix: str,
    terms: list[str],
    guardrails: Guardrails,
    literals: list[str] | None = None,
) -> list[Issue]:
    """Scan one published file by type."""
    if suffix == ".html":
        text, links = html_to_scan_text(content)
        issues = scan_text(location, text, terms, guardrails, literals)
        for link in links:
            bad = check_link(location, link, guardrails)
            if bad is not None and bad not in issues:
                issues.append(bad)
        return issues
    issues = scan_text(location, content, terms, guardrails, literals)
    if suffix == ".css":
        for url in re.findall(r"url\(\s*['\"]?([^'\")]+)", content):
            bad = check_link(location, url, guardrails)
            if bad is not None and bad not in issues:
                issues.append(bad)
    return issues


def scan_site_dir(
    site_dir: Path, terms: list[str], guardrails: Guardrails, literals: list[str] | None = None
) -> list[Issue]:
    """Scan every file that would be published from ``site_dir``."""
    issues: list[Issue] = []
    for path in sorted(p for p in Path(site_dir).rglob("*") if p.is_file()):
        rel = path.relative_to(site_dir).as_posix()
        if path.suffix not in guardrails.allowed_file_suffixes:
            issues.append(_issue(rel, f"unexpected file type '{path.suffix}'"))
            continue
        content = path.read_text(encoding="utf-8")
        issues += scan_document(rel, content, path.suffix, terms, guardrails, literals)
    return issues
