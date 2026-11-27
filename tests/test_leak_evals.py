"""The labelled leak eval suite must pass in full and stay meaningful."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from roadmap.evals import load_cases, run_leak_evals
from roadmap.leakscan import SECRET_PATTERNS

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals/leak_cases.yaml"


def test_all_cases_pass() -> None:
    result = run_leak_evals(CASES, ROOT / "config/guardrails.yaml")
    assert result.failures == [], "\n".join(result.failures)
    assert result.fn == 0  # no missed leak


def test_suite_covers_every_category_both_ways() -> None:
    _, _, cases = load_cases(CASES)
    assert len(cases) >= 50
    categories = Counter(c.category for c in cases)
    for cat in ("forbidden-term", "obfuscation", "secret", "pii", "vocabulary", "link"):
        assert categories[cat] >= 4, cat
    assert categories["false-positive"] >= 8
    assert {c.expect for c in cases} == {"block", "allow"}


def test_eval_file_itself_contains_no_secret_like_strings() -> None:
    raw = CASES.read_text(encoding="utf-8")
    hits = [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(raw)]
    assert hits == []


def test_published_case_counts_match_the_suite() -> None:
    # The diagram and its SVG quote the suite size; they must not drift from it (T28).
    import re

    _, _, cases = load_cases(CASES)
    for rel in ("diagrams/roadmap-site.architecture.json", "static/diagrams/roadmap-site.svg"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        counts = {int(n) for n in re.findall(r"(\d+) (?:labelled )?cases", text)}
        assert counts == {len(cases)}, (rel, counts)
