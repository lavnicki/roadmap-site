"""Tests for roadmap.parse."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from roadmap.models import RawSheets
from roadmap.parse import infer_dates, parse_ptbr_number, parse_sheets, parse_status

FIXTURE = Path(__file__).parent / "fixtures" / "valid.json"


def load() -> dict[str, list[list[str]]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("s", "expected"), [("2,0", 2.0), ("2", 2.0), (" 1,5 ", 1.5), ("14", 14.0)]
)
def test_number_ok(s: str, expected: float) -> None:
    assert parse_ptbr_number(s) == expected


@pytest.mark.parametrize("s", ["", "1.5", "abc", "1,2,3"])
def test_number_rejects(s: str) -> None:
    with pytest.raises(ValueError):
        parse_ptbr_number(s)


@pytest.mark.parametrize(
    ("s", "expected"),
    [
        ("Feito", "Done"),
        ("A fazer", "Planned"),
        ("Não feito", "Missed"),
        (" feito ", "Done"),
        ("A FAZER", "Planned"),
        ("NÃO FEITO", "Missed"),
    ],
)
def test_status_ok(s: str, expected: str) -> None:
    assert parse_status(s) == expected


def test_status_rejects() -> None:
    with pytest.raises(ValueError):
        parse_status("talvez")


def test_infer_dates_year_rollover() -> None:
    got = infer_dates(["28/12", "05/01", "06/01", "01/12"], 2026)
    assert got == [
        datetime.date(2026, 12, 28),
        datetime.date(2027, 1, 5),
        datetime.date(2027, 1, 6),
        datetime.date(2027, 12, 1),
    ]


@pytest.mark.parametrize("bad", ["31/02", "1/1", "aa/bb", "10/13", "00/01"])
def test_infer_dates_invalid(bad: str) -> None:
    with pytest.raises(ValueError, match="index 1"):
        infer_dates(["01/01", bad], 2026)


def test_infer_dates_leap_year() -> None:
    assert infer_dates(["29/02"], 2028) == [datetime.date(2028, 2, 29)]
    with pytest.raises(ValueError):
        infer_dates(["29/02"], 2027)


def test_valid_fixture() -> None:
    parsed, issues = parse_sheets(RawSheets(**load()), 2026)
    assert issues == []
    assert len(parsed.cronograma) == 10
    assert len(parsed.modules) == 2
    assert len(parsed.publico) == 12
    assert (parsed.totals.planned, parsed.totals.done, parsed.totals.missed) == (22.0, 15.0, 1.0)
    dates = [r.date for r in parsed.cronograma]
    assert dates[0] == datetime.date(2026, 12, 28)
    assert dates[2] == datetime.date(2026, 12, 30)
    assert dates[3] == datetime.date(2027, 1, 5)
    assert dates[-1] == datetime.date(2027, 1, 28)
    assert parsed.cronograma[0].row == 5
    assert parsed.cronograma[1].status == "Missed"
    delta = next(p for p in parsed.publico if p.id == "delta")
    assert delta.status_manual == "Done"
    assert delta.horas_manual == 10.0
    assert delta.descricao_en is None
    pub = next(p for p in parsed.publico if p.id == "public-proj")
    assert pub.stack == ["Python", "Airflow"]
    assert next(p for p in parsed.publico if p.id == "secret-comp").publicar is False


def test_bad_headers_each_one_issue() -> None:
    d = load()
    d["cronograma_left"][0] = ["X", "Dia", "Curso"]
    d["modules"][0] = ["Mod", "Tema", "Horas", "Status"]
    d["publico"][0] = d["publico"][0][:-1]
    parsed, issues = parse_sheets(RawSheets(**d), 2026)
    assert [(i.tab, i.rule) for i in issues] == [
        ("Cronograma", "Q1"),
        ("Spark & Databricks", "Q1"),
        ("Publico", "Q1"),
    ]
    assert parsed.cronograma == []
    assert parsed.modules == []
    assert parsed.publico == []


def test_bad_totals_label_and_value() -> None:
    d = load()
    d["cronograma_totals"][0][0] = "Foo"
    d["cronograma_totals"][1][1] = "x"
    parsed, issues = parse_sheets(RawSheets(**d), 2026)
    assert [i.rule for i in issues] == ["Q1", "Q1"]
    assert parsed.totals.planned == 0.0
    assert parsed.totals.done == 0.0
    assert parsed.totals.missed == 1.0


def test_cronograma_row_problems() -> None:
    d = load()
    d["cronograma_left"][1][0] = "31/02"  # row 5
    d["cronograma_right"][2] = ["13,0", "talvez"]  # row 6: Q3 + Q4
    d["cronograma_left"].append(["", "", ""])  # empty row ignored
    d["cronograma_right"].append(["", ""])
    parsed, issues = parse_sheets(RawSheets(**d), 2026)
    assert [(i.row, i.rule) for i in issues] == [(5, "Q2"), (6, "Q3"), (6, "Q4")]
    assert len(parsed.cronograma) == 8


def test_cronograma_misaligned_lengths_and_blank() -> None:
    d = load()
    d["cronograma_right"] = d["cronograma_right"][:-1]  # last row loses right half
    d["cronograma_left"].append(["", "", "Curso Z"])
    parsed, issues = parse_sheets(RawSheets(**d), 2026)
    assert sorted((i.row, i.rule) for i in issues) == [
        (14, "Q3"),
        (14, "Q4"),
        (15, "Q2"),
        (15, "Q3"),
        (15, "Q4"),
    ]
    assert len(parsed.cronograma) == 9


def test_leap_day_depends_on_inferred_year() -> None:
    d = load()
    d["cronograma_left"] = [["Data", "Dia", "Curso"], ["29/02", "", "A"]]
    d["cronograma_right"] = [["Horas", "Status"], ["1", "Feito"]]
    _, issues = parse_sheets(RawSheets(**d), 2027)
    assert [i.rule for i in issues] == ["Q2"]
    parsed, issues = parse_sheets(RawSheets(**d), 2028)
    assert issues == []
    assert parsed.cronograma[0].date == datetime.date(2028, 2, 29)


def test_bad_date_excluded_from_year_sequence() -> None:
    d = load()
    d["cronograma_left"] = [
        ["Data", "Dia", "Curso"],
        ["10/12", "", "A"],
        ["xx", "", "A"],
        ["05/01", "", "A"],
    ]
    d["cronograma_right"] = [["Horas", "Status"], ["1", "Feito"], ["1", "Feito"], ["1", "Feito"]]
    parsed, issues = parse_sheets(RawSheets(**d), 2026)
    assert [(i.row, i.rule) for i in issues] == [(6, "Q2")]
    assert [r.date for r in parsed.cronograma] == [
        datetime.date(2026, 12, 10),
        datetime.date(2027, 1, 5),
    ]


def test_modules_problems() -> None:
    d = load()
    d["modules"] += [
        ["x", "T", "1", "Feito"],
        ["3", "T", "1", "Não feito"],
        ["4", "T", "1", "A fazer"],
    ]
    parsed, issues = parse_sheets(RawSheets(**d), 2026)
    assert [(i.tab, i.row, i.rule) for i in issues] == [
        ("Spark & Databricks", 4, "Q5"),
        ("Spark & Databricks", 5, "Q4"),
    ]
    assert [m.number for m in parsed.modules] == [1, 2, 4]


def test_publico_problems() -> None:
    d = load()
    base = d["publico"][1]
    for col, val in [(0, "outro"), (3, "um"), (13, "Planned"), (14, "abc")]:
        row = list(base)
        row[col] = val
        d["publico"].append(row)
    parsed, issues = parse_sheets(RawSheets(**d), 2026)
    assert [(i.row, i.rule) for i in issues] == [(14, "Q5"), (15, "Q5"), (16, "Q5"), (17, "Q3")]
    assert len(parsed.publico) == 12


def test_issue_messages_do_not_leak_other_columns() -> None:
    d = load()
    d["cronograma_left"][1] = ["zz", "SecretDia", "SecretCurso"]
    _, issues = parse_sheets(RawSheets(**d), 2026)
    assert issues
    assert all("SecretDia" not in i.message for i in issues)


@pytest.mark.parametrize(
    ("raw", "done", "total", "ok"),
    [("70", 70.0, None, True), ("105/384", 105.0, 384.0, True), ("10,5 / 20", 10.5, 20.0, True),
     ("105/", None, None, False), ("a/384", None, None, False)],
)
def test_horas_manual_forms(raw: str, done: float | None, total: float | None, ok: bool) -> None:
    d = load()
    row = list(d["publico"][1])
    row[1], row[13], row[14] = "manual-x", "In progress", raw
    d["publico"].append(row)
    parsed, issues = parse_sheets(RawSheets(**d), 2026)
    if ok:
        got = next(p for p in parsed.publico if p.id == "manual-x")
        got_hours = (got.status_manual, got.horas_manual, got.horas_manual_total)
        assert got_hours == ("In progress", done, total)
    else:
        assert [i.rule for i in issues] == ["Q3"]
