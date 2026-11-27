"""Editorial rules for the hand-written content in ``content/``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = sorted((ROOT / "content/cases").glob("*.md"))


def test_there_is_at_least_one_case() -> None:
    assert CASES


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.stem)
def test_cases_do_not_name_job_platforms(case: Path) -> None:
    # Case studies describe sources generically; job platforms are not named (slug included).
    text = f"{case.stem}\n{case.read_text(encoding='utf-8')}".lower()
    assert "linkedin" not in text


PUBLIC_DIAGRAMS = sorted((ROOT / "diagrams").glob("*.json")) + sorted(
    (ROOT / "static/diagrams").glob("*.svg")
)


@pytest.mark.parametrize("path", PUBLIC_DIAGRAMS, ids=lambda p: p.name)
def test_diagrams_follow_case_rules(path: Path) -> None:
    # Same editorial rule as the cases (R8): no job platform names, no links to private code.
    text = path.read_text(encoding="utf-8")
    assert "linkedin" not in text.lower()
    if path.suffix == ".json":
        spec = json.loads(text)
        assert "repository" not in spec["meta"]
        assert all("sources" not in c for c in spec["components"])
