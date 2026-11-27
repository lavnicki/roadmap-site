"""Tests for roadmap.validate (T5)."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from roadmap.extract import load_fixture
from roadmap.models import CronogramaRow, ParsedSheets, PublicoRow
from roadmap.parse import parse_sheets
from roadmap.validate import check_future_dates, check_modules_mapped, check_publico

FIXTURE = Path(__file__).parent / "fixtures" / "valid.json"
CASES = {"private-proj"}


@pytest.fixture
def parsed() -> ParsedSheets:
    p, issues = parse_sheets(load_fixture(FIXTURE), 2026)
    assert issues == []
    return p


def mutate(rows: list[PublicoRow], id_: str, **kw: object) -> list[PublicoRow]:
    return [r.model_copy(update=kw) if r.id == id_ else r for r in rows]


def where(issues: list) -> list[tuple[str, int | None]]:
    return [(i.rule, i.row) for i in issues]


def test_fixture_clean(parsed: ParsedSheets) -> None:
    assert check_publico(parsed.publico, CASES) == []
    assert check_modules_mapped(parsed.publico, parsed.modules) == []
    assert check_future_dates(parsed.cronograma, datetime.date(2027, 2, 1)) == []


def test_future_dates(parsed: ParsedSheets) -> None:
    today = datetime.date(2027, 1, 5)
    issues = check_future_dates(parsed.cronograma, today)
    expected = [
        r.row
        for r in parsed.cronograma
        if r.date > today + datetime.timedelta(days=1) and r.status != "Planned"
    ]
    assert expected  # the fixture has Done rows after 2027-01-06
    assert [i.row for i in issues] == expected
    assert all(i.rule == "Q2" and i.tab == "Cronograma" for i in issues)


def test_future_dates_tolerates_one_day() -> None:
    row = CronogramaRow(row=5, date=datetime.date(2027, 1, 2), course="X", hours=1.0, status="Done")
    assert check_future_dates([row], datetime.date(2027, 1, 1)) == []
    assert len(check_future_dates([row], datetime.date(2026, 12, 31))) == 1


def test_future_dates_planned_allowed() -> None:
    row = CronogramaRow(
        row=5, date=datetime.date(2030, 1, 2), course="X", hours=1.0, status="Planned"
    )
    assert check_future_dates([row], datetime.date(2027, 1, 1)) == []


def test_duplicate_id(parsed: ParsedSheets) -> None:
    dup = parsed.publico[0].model_copy(update={"row": 99})
    assert where(check_publico([*parsed.publico, dup], CASES)) == [("Q6", 99)]


def test_bad_slug(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "alpha", id="Alpha_1"), CASES)
    assert ("Q6", 5) in where(issues)


def test_empty_id(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "hidden-proj", id=""), CASES)
    assert ("Q6", 11) in where(issues)


def test_repeated_cronograma_key(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "beta", cronograma_key="Curso Alpha"), CASES)
    assert where(issues) == [("Q6", 6)]


def test_empty_nome_en(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "alpha", nome_en=""), CASES)
    assert where(issues) == [("Q5", 5)]


def test_missing_descricao(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "public-proj", descricao_en=None), CASES)
    assert where(issues) == [("Q5", 9)]
    issues = check_publico(mutate(parsed.publico, "data-platforms", descricao_en=None), CASES)
    assert where(issues) == [("Q5", 2)]


def test_no_competencias(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "alpha", competencias=[]), CASES)
    assert where(issues) == [("Q5", 5)]


def test_unknown_competencia(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "alpha", competencias=["nope"]), CASES)
    assert where(issues) == [("Q5", 5)]
    assert "nope" in issues[0].message


def test_unpublished_competencia_is_valid_reference(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "alpha", competencias=["secret-comp"]), CASES)
    assert issues == []


def test_project_without_url_or_case(parsed: ParsedSheets) -> None:
    assert where(check_publico(parsed.publico, set())) == [("Q5", 10)]


def test_non_https_urls(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "public-proj", url="http://x.example"), CASES)
    assert where(issues) == [("Q5", 9)]
    issues = check_publico(mutate(parsed.publico, "delta", credencial_url="ftp://x"), CASES)
    assert where(issues) == [("Q5", 7)]


def test_manual_done_without_hours_is_allowed(parsed: ParsedSheets) -> None:
    assert check_publico(mutate(parsed.publico, "delta", horas_manual=None), CASES) == []


def test_manual_in_progress_hours(parsed: ParsedSheets) -> None:
    rows = mutate(parsed.publico, "delta", status_manual="In progress")
    assert where(check_publico(rows, CASES)) == [("Q5", 7)]  # plain number is ambiguous
    assert check_publico(mutate(rows, "delta", horas_manual=None), CASES) == []
    ok = mutate(rows, "delta", horas_manual=105.0, horas_manual_total=384.0)
    assert check_publico(ok, CASES) == []
    over = mutate(rows, "delta", horas_manual=400.0, horas_manual_total=384.0)
    assert where(check_publico(over, CASES)) == [("Q5", 7)]
    done_with_total = mutate(ok, "delta", status_manual="Done")
    assert where(check_publico(done_with_total, CASES)) == [("Q5", 7)]


def test_modulo_unknown_pai(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "alpha-m1", pai="zzz"), CASES)
    assert where(issues) == [("Q5", 12)]


def test_modulo_pai_not_a_course(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "alpha-m1", pai="data-platforms"), CASES)
    assert where(issues) == [("Q5", 12)]


def test_modulo_bad_id(parsed: ParsedSheets) -> None:
    issues = check_publico(mutate(parsed.publico, "alpha-m1", id="alpha-x1"), CASES)
    assert where(issues) == [("Q5", 12)]


def test_unpublished_rows_skip_q5(parsed: ParsedSheets) -> None:
    rows = mutate(parsed.publico, "gamma", nome_en="", competencias=[], url="http://x")
    assert check_publico(rows, CASES) == []


def test_modules_mapped(parsed: ParsedSheets) -> None:
    rows = mutate(parsed.publico, "alpha-m2", id="alpha-m9")
    issues = check_modules_mapped(rows, parsed.modules)
    assert [(i.tab, i.rule, i.row) for i in issues] == [("Publico", "Q5", 13)]


def test_modules_mapped_skips_nonmatching_ids(parsed: ParsedSheets) -> None:
    rows = mutate(parsed.publico, "alpha-m2", id="weird")
    assert check_modules_mapped(rows, parsed.modules) == []
