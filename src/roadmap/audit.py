"""Post-deploy and repository audits (``roadmap audit-live`` / ``roadmap audit-repo``)."""

from __future__ import annotations

import subprocess
import urllib.request
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlsplit, urlunsplit

from roadmap.leakscan import (
    ALLOWED_EMAILS,
    Guardrails,
    html_to_scan_text,
    scan_document,
    scan_text,
)
from roadmap.models import Issue

Fetcher = Callable[[str], tuple[str, str]]  # url -> (content type, body)

_USER_AGENT = "roadmap-site-audit/1.0"


def http_fetch(url: str) -> tuple[str, str]:
    req = urllib.request.Request(
        url, headers={"User-Agent": _USER_AGENT, "Cache-Control": "no-cache"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 (https only, see caller)
        ctype = resp.headers.get_content_type()
        return ctype, resp.read().decode("utf-8", errors="replace")


def _strip_fragment(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def audit_live(
    base_url: str,
    terms: list[str],
    guardrails: Guardrails,
    literals: list[str] | None = None,
    fetch: Fetcher = http_fetch,
    max_pages: int = 50,
) -> tuple[list[Issue], list[str]]:
    """Crawl every same-site page and stylesheet under ``base_url`` and scan it.

    Returns (issues, audited urls). Only https URLs under ``base_url`` are fetched.
    """
    if not base_url.startswith("https://"):
        raise ValueError("base_url must be https")
    root = base_url if base_url.endswith("/") else base_url + "/"
    queue, seen, audited = [root], set(), []
    issues: list[Issue] = []
    while queue and len(audited) < max_pages:
        url = _strip_fragment(queue.pop(0))
        if url in seen:
            continue
        seen.add(url)
        ctype, body = fetch(url)
        audited.append(url)
        path = urlsplit(url).path
        location = path[len(urlsplit(root).path) :] or "index.html"
        suffix = PurePosixPath(path).suffix or (".html" if ctype == "text/html" else "")
        if ctype == "text/html":
            suffix = ".html"
        elif ctype == "text/css":
            suffix = ".css"
        issues += scan_document(location, body, suffix, terms, guardrails, literals)
        if suffix == ".html":
            _, links = html_to_scan_text(body)
            for link in links:
                absolute = _strip_fragment(urljoin(url, link))
                if absolute.startswith(root) and absolute not in seen:
                    queue.append(absolute)
    return issues, audited


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=True,
        encoding="utf-8",
        errors="replace",
    )
    return out.stdout


def audit_repo(
    repo: Path, terms: list[str], guardrails: Guardrails, literals: list[str] | None = None
) -> tuple[list[Issue], int]:
    """Scan tracked files and every patch in the history (all refs) for terms and secrets.

    Private vocabulary is not checked here: the specs legitimately describe the private sheet.
    Returns (issues, number of files scanned).
    """
    issues: list[Issue] = []
    files = [f for f in _git(repo, "ls-files", "-z").split("\0") if f]
    for rel in files:
        path = repo / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        issues += scan_text(
            rel,
            text,
            terms,
            guardrails,
            literals,
            check_vocabulary=False,
            allowed_emails=ALLOWED_EMAILS,
        )
    # Patches only (format= drops author lines and messages; metadata is reported separately).
    history = _git(repo, "log", "--all", "-p", "--no-color", "--format=")
    issues += scan_text(
        "git history (patches)",
        history,
        terms,
        guardrails,
        literals,
        check_vocabulary=False,
        allowed_emails=ALLOWED_EMAILS,
    )
    messages = _git(repo, "log", "--all", "--format=%B")
    issues += scan_text(
        "git history (commit messages)",
        messages,
        terms,
        guardrails,
        literals,
        check_vocabulary=False,
        allowed_emails=ALLOWED_EMAILS,
    )
    return issues, len(files)


def commit_author_emails(repo: Path) -> list[str]:
    """Distinct author/committer emails that are not GitHub noreply addresses."""
    raw = _git(repo, "log", "--all", "--format=%ae%n%ce")
    emails = sorted({e.strip() for e in raw.splitlines() if e.strip()})
    return [e for e in emails if not ALLOWED_EMAILS.fullmatch(e)]
