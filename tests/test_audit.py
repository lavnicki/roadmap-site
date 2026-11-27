"""Live-site crawler and repository/history audits (no network, temporary git repos)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from roadmap.audit import audit_live, audit_repo, commit_author_emails
from roadmap.leakscan import load_guardrails

ROOT = Path(__file__).resolve().parents[1]
GUARD = load_guardrails(ROOT / "config/guardrails.yaml")
TERMS = ["acme-corp"]
BASE = "https://lavnicki.github.io/roadmap-site/"


def _site(pages: dict[str, tuple[str, str]]):
    fetched: list[str] = []

    def fetch(url: str) -> tuple[str, str]:
        fetched.append(url)
        if url not in pages:
            raise AssertionError(f"unexpected fetch {url}")
        return pages[url]

    return fetch, fetched


def test_crawls_same_site_pages_and_css_only() -> None:
    fetch, fetched = _site(
        {
            BASE: (
                "text/html",
                '<link rel="stylesheet" href="style.css"><a href="cases/a.html#x">a</a>'
                '<a href="https://github.com/lavnicki">gh</a>',
            ),
            BASE + "style.css": ("text/css", "body{color:#fff}"),
            BASE + "cases/a.html": ("text/html", '<a href="../index.html">back</a>'),
            BASE + "index.html": ("text/html", "<p>home</p>"),
        }
    )
    issues, audited = audit_live(BASE, TERMS, GUARD, fetch=fetch)
    assert issues == []
    assert set(audited) == {BASE, BASE + "style.css", BASE + "cases/a.html", BASE + "index.html"}
    assert not any("github.com" in u for u in fetched)


def test_leak_on_a_linked_page_is_reported() -> None:
    fetch, _ = _site(
        {
            BASE: ("text/html", '<a href="cases/a.html">a</a>'),
            BASE + "cases/a.html": ("text/html", "<p>built for ACME-CORP</p>"),
        }
    )
    issues, _ = audit_live(BASE, TERMS, GUARD, fetch=fetch)
    assert [i.message for i in issues] == ["forbidden term found in cases/a.html"]


def test_live_audit_requires_https() -> None:
    with pytest.raises(ValueError):
        audit_live(
            "http://lavnicki.github.io/roadmap-site/", TERMS, GUARD, fetch=lambda u: ("", "")
        )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Bot")
    _git(tmp_path, "config", "user.email", "1+bot@users.noreply.github.com")
    (tmp_path / "README.md").write_text("clean\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_clean_repo(repo: Path) -> None:
    issues, n = audit_repo(repo, TERMS, GUARD)
    assert issues == [] and n == 1
    assert commit_author_emails(repo) == []


def test_term_deleted_later_is_still_found_in_history(repo: Path) -> None:
    (repo / "notes.md").write_text("client: acme-corp\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add notes")
    (repo / "notes.md").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "remove notes")
    issues, _ = audit_repo(repo, TERMS, GUARD)
    assert [i.message for i in issues] == ["forbidden term found in git history (patches)"]


def test_term_in_commit_message_and_secret_in_file(repo: Path) -> None:
    (repo / "k.txt").write_text("-----BEGIN " + "PRIVATE KEY-----\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "work for acme-corp")
    messages = {i.message for i in audit_repo(repo, TERMS, GUARD)[0]}
    assert "forbidden term found in git history (commit messages)" in messages
    assert "secret-like pattern 'private key' found in k.txt" in messages


def test_personal_author_email_is_detected(repo: Path) -> None:
    personal = "person" + "@" + "example.org"  # built from parts: the repo audit stays clean
    _git(repo, "config", "user.email", personal)
    (repo / "x.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "x")
    assert commit_author_emails(repo) == [personal]
