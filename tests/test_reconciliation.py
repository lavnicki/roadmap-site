from __future__ import annotations

from pathlib import Path

import pytest

from roadmap.extract import load_fixture
from roadmap.models import ParsedSheets
from roadmap.parse import parse_sheets
from roadmap.validate import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def parsed() -> ParsedSheets:
    result, issues = parse_sheets(load_fixture(ROOT / "tests/fixtures/valid.json"), 2026)
    assert issues == []
    return result


def test_fixture_reconciles(parsed: ParsedSheets) -> None:
    assert check_reconciliation(parsed.cronograma, parsed.totals) == []


def test_within_tolerance(parsed: ParsedSheets) -> None:
    totals = parsed.totals.model_copy(update={"done": parsed.totals.done + 0.1})
    assert check_reconciliation(parsed.cronograma, totals) == []


@pytest.mark.parametrize("field", ["planned", "done", "missed"])
def test_mismatch_blocks(parsed: ParsedSheets, field: str) -> None:
    value = getattr(parsed.totals, field) + 0.2
    totals = parsed.totals.model_copy(update={field: value})
    issues = check_reconciliation(parsed.cronograma, totals)
    assert len(issues) == 1
    assert issues[0].rule == "Q7"
    assert issues[0].row is None


def test_dropped_row_is_detected(parsed: ParsedSheets) -> None:
    issues = check_reconciliation(parsed.cronograma[1:], parsed.totals)
    assert {i.rule for i in issues} == {"Q7"}
    assert len(issues) == 2  # planned and done both drift (first row is Done)
