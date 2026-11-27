"""Editorial rules for the hand-written content in ``content/``."""

from __future__ import annotations

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
