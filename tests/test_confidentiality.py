from __future__ import annotations

import pytest

from roadmap.confidentiality import find_forbidden, load_terms, parse_terms

TERMS = ["acme-corp", "Cliente Fictício"]


def _hit(text: str, terms: list[str] = TERMS) -> bool:
    return bool(find_forbidden([("loc", text)], terms))


@pytest.mark.parametrize(
    "text",
    [
        "Worked with ACME-CORP data",
        "acme-corp",
        "see github.com/acme-corp/repo",
        "built for cliente ficticio last year",
        "CLIENTE FICTÍCIO",
        "Cliente\n  Fictício",
        "(acme-corp)",
        "acme corp",
        "acme_corp",
        "Cliente-Ficticio",
    ],
)
def test_matches_case_accent_and_punctuation(text: str) -> None:
    assert _hit(text)


@pytest.mark.parametrize(
    "text",
    [
        "acme-corporation",
        "megaacme-corp",
        "pre-acme-corp",
        "acmecorp",
        "Cliente Ficticios",
        "nothing to see",
        "",
    ],
)
def test_partial_words_do_not_match(text: str) -> None:
    assert not _hit(text)


def test_message_names_location_never_the_term() -> None:
    issues = find_forbidden(
        [("projects[p1].description", "about Acme-Corp"), ("ok", "clean")], TERMS
    )
    assert len(issues) == 1
    issue = issues[0]
    assert issue.rule == "Q8"
    assert "projects[p1].description" in issue.message
    rendered = issue.format().casefold()
    assert "acme" not in rendered
    assert "fict" not in rendered


def test_one_issue_per_location_even_with_many_terms() -> None:
    issues = find_forbidden([("x", "acme-corp and Cliente Fictício")], TERMS)
    assert len(issues) == 1


def test_empty_terms_never_match() -> None:
    assert find_forbidden([("x", "anything")], []) == []
    assert find_forbidden([("x", "anything")], ["   "]) == []


def test_parse_and_load_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = "acme-corp\n\n# comment\n  Cliente Fictício  \n"
    assert parse_terms(raw) == ["acme-corp", "Cliente Fictício"]
    monkeypatch.setenv("FORBIDDEN_TERMS", raw)
    assert load_terms() == ["acme-corp", "Cliente Fictício"]
    monkeypatch.delenv("FORBIDDEN_TERMS")
    assert load_terms() == []
