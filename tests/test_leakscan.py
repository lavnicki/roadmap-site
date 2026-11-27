"""Unit tests for the rendered-output leak scanner."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from roadmap.confidentiality import load_terms
from roadmap.leakscan import (
    Guardrails,
    check_link,
    html_to_scan_text,
    load_guardrails,
    scan_document,
    scan_site_dir,
    scan_text,
)

ROOT = Path(__file__).resolve().parents[1]
GUARD = load_guardrails(ROOT / "config/guardrails.yaml")
TERMS = ["acme-corp", "Banco Exemplo", "QZX"]


def test_production_guardrails_have_no_forbidden_terms() -> None:
    # The guardrails file is public; real client names live only in the FORBIDDEN_TERMS secret.
    # Runs for real in the audit workflow, where the secret is set.
    terms = load_terms()
    text = (ROOT / "config/guardrails.yaml").read_text(encoding="utf-8")
    assert scan_text("guardrails.yaml", text, terms, Guardrails(), check_vocabulary=False) == []


def test_html_text_includes_attributes_and_comments() -> None:
    text, links = html_to_scan_text(
        '<a href="x.html" title="T1">A<b>B</b></a><!-- C1 --><img src="i.svg" alt="ALT">'
    )
    for piece in ("AB", "T1", "C1", "ALT"):
        assert piece in text
    assert links == ["x.html", "i.svg"]


@pytest.mark.parametrize(
    ("target", "ok"),
    [
        ("cases/a.html", True),
        ("../index.html", True),
        ("#top", True),
        ("https://github.com/lavnicki", True),
        ("https://www.linkedin.com/in/x", True),
        ("data:image/svg+xml,%3Csvg%3E", True),
        ("http://github.com/lavnicki", False),
        ("https://evil.example.net/", False),
        ("https://github.com.evil.net/", False),
        ("//cdn.example.net/x.js", False),
        ("mailto:a", False),
        ("javascript:alert(1)", False),
        ("data:text/html,x", False),
    ],
)
def test_link_allowlist(target: str, ok: bool) -> None:
    assert (check_link("loc", target, GUARD) is None) is ok


def test_messages_never_contain_the_match() -> None:
    issues = scan_text("page.html", "acme-corp Observação", TERMS, GUARD, ["SECRETLITERAL123"])
    issues += scan_text("page.html", "id SECRETLITERAL123", TERMS, GUARD, ["SECRETLITERAL123"])
    assert {i.rule for i in issues} == {"Q8"}
    rendered = " ".join(i.format() for i in issues).lower()
    for leaked in ("acme", "observa", "secretliteral"):
        assert leaked not in rendered


def test_literals_ignore_case_and_accents() -> None:
    assert scan_text("x", "sheet abcdefghij", [], GUARD, ["ABCDEFGHIJ"])


def test_vocabulary_can_be_disabled_for_repo_scans() -> None:
    assert scan_text("x", "DevSpeak", [], GUARD)
    assert not scan_text("x", "DevSpeak", [], GUARD, check_vocabulary=False)


def test_site_dir_rejects_unexpected_files(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<p>ok</p>", encoding="utf-8")
    (tmp_path / "dump.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".nojekyll").write_text("", encoding="utf-8")
    issues = scan_site_dir(tmp_path, TERMS, GUARD)
    assert [i.message for i in issues] == ["unexpected file type '.json' found in dump.json"]


def test_css_urls_are_link_checked() -> None:
    css = "body{background:url('https://tracker.example.net/p.gif')}"
    assert scan_document("style.css", css, ".css", [], GUARD)
    assert not scan_document("style.css", "body{background:url(bg.svg)}", ".css", [], GUARD)


def test_fuzzed_obfuscation_is_always_caught() -> None:
    """Random case, zero-width/soft-hyphen injection, tag splitting and entity encoding."""
    rng = random.Random(20261127)
    invisible = ["​", "‌", "‍", "­", "﻿"]
    for _ in range(300):
        term = rng.choice(TERMS)
        chars = []
        for ch in term:
            ch = ch.upper() if rng.random() < 0.5 else ch.lower()
            if ch.isalpha() and rng.random() < 0.2:
                ch = f"&#{ord(ch)};"
            chars.append(ch)
            if rng.random() < 0.15:
                chars.append(rng.choice(invisible + ["<b></b>", "<span></span>"]))
        html = f"<p>worked with {''.join(chars)} on pipelines</p>"
        assert scan_document("fuzz.html", html, ".html", TERMS, GUARD), html


def test_empty_guardrails_still_check_terms_and_secrets() -> None:
    empty = Guardrails()
    assert scan_text("x", "acme-corp", TERMS, empty)
    assert not scan_text("x", "DevSpeak", TERMS, empty)
