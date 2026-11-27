"""Checks build_published against tests/fixtures/EXPECTED.md."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from roadmap.config import load_config
from roadmap.extract import load_fixture
from roadmap.models import ParsedSheets, PublishedData
from roadmap.parse import parse_sheets
from roadmap.transform import _competency_status, build_published

ROOT = Path(__file__).resolve().parents[1]
TODAY = datetime.date(2027, 2, 1)


@pytest.fixture(scope="module")
def parsed() -> ParsedSheets:
    result, issues = parse_sheets(load_fixture(ROOT / "tests/fixtures/valid.json"), 2026)
    assert issues == []
    return result


def _build(parsed: ParsedSheets, **kw: object) -> PublishedData:
    args: dict[str, object] = {
        "config": load_config(ROOT / "tests/fixtures/site.yaml"),
        "case_ids": {"private-proj"},
        "today": TODAY,
        "previous": None,
        "min_weeks": 4,
    }
    args.update(kw)
    return build_published(parsed, **args)  # type: ignore[arg-type]


def test_courses(parsed: ParsedSheets) -> None:
    data = _build(parsed)
    courses = {c.id: c for c in data.courses}
    assert list(courses) == ["alpha", "beta", "delta"]
    a, b, d = courses["alpha"], courses["beta"], courses["delta"]
    assert (a.hours_done, a.hours_planned, a.status) == (6.5, 9.5, "In progress")
    assert [(m.id, m.status) for m in a.modules] == [("alpha-m1", "Done"), ("alpha-m2", "Planned")]
    assert (b.hours_done, b.hours_planned, b.status) == (6.5, 8.5, "In progress")
    assert (d.hours_done, d.hours_planned, d.status) == (10.0, 10.0, "Done")
    assert d.credential_url == "https://example.com/cred/delta"
    assert a.credential_url is None


def test_competencies(parsed: ParsedSheets) -> None:
    comps = {c.id: c for c in _build(parsed).competencies}
    assert list(comps) == ["data-platforms", "llm-engineering"]
    dp, llm = comps["data-platforms"], comps["llm-engineering"]
    assert (dp.hours_done, dp.hours_planned, dp.pct, dp.status) == (23.0, 28.0, 82.1, "In progress")
    assert dp.courses == ["alpha", "beta", "delta"]
    assert dp.projects == ["public-proj"]
    # No course hours, but a public project: hands-on work in progress, still no % bar.
    assert (llm.status, llm.pct, llm.courses) == ("In progress", None, [])
    assert llm.projects == ["private-proj"]


def test_projects(parsed: ParsedSheets) -> None:
    projects = {p.id: p for p in _build(parsed).projects}
    assert list(projects) == ["public-proj", "private-proj"]
    assert projects["public-proj"].repo_url == "https://github.com/example/public-proj"
    assert projects["public-proj"].case_path is None
    assert projects["private-proj"].repo_url is None
    assert projects["private-proj"].case_path == "cases/private-proj.html"
    assert projects["public-proj"].stack == ["Python", "Airflow"]


def test_kpis(parsed: ParsedSheets) -> None:
    k = _build(parsed).kpis
    assert (k.hours_done, k.hours_planned_total, k.pct_plan) == (23.0, 28.0, 82.1)
    assert (k.courses_done, k.courses_total) == (1, 3)
    assert k.study_start == datetime.date(2026, 12, 28)


def test_weekly(parsed: ParsedSheets) -> None:
    weekly = [(p.week_start.isoformat(), p.hours_done_cum) for p in _build(parsed).weekly]
    assert weekly == [
        ("2026-12-28", 5.0),
        ("2027-01-04", 9.0),
        ("2027-01-11", 10.5),
        ("2027-01-18", 13.0),
    ]
    assert _build(parsed, min_weeks=5).weekly == []


def test_nothing_private_leaks(parsed: ParsedSheets) -> None:
    dumped = _build(parsed).model_dump_json()
    hidden_values = ("secret-comp", "Secret Competency", "hidden-proj", "gamma", "Interno X")
    for hidden in hidden_values:
        assert hidden not in dumped


def test_deterministic(parsed: ParsedSheets) -> None:
    assert _build(parsed).model_dump_json() == _build(parsed).model_dump_json()


def test_data_updated_at_kept_when_unchanged(parsed: ParsedSheets) -> None:
    first = _build(parsed)
    later = _build(parsed, today=TODAY + datetime.timedelta(days=3), previous=first)
    assert later.data_updated_at == TODAY
    assert later == first


def test_data_updated_at_moves_when_changed(parsed: ParsedSheets) -> None:
    first = _build(parsed)
    changed = parsed.model_copy(update={"cronograma": parsed.cronograma[:-2]})
    later_day = TODAY + datetime.timedelta(days=3)
    later = _build(changed, today=later_day, previous=first)
    assert later.data_updated_at == later_day


@pytest.mark.parametrize(
    ("done", "planned", "courses", "projects", "expected"),
    [
        (0.0, 0.0, [], False, "Planned"),
        (0.0, 0.0, [], True, "In progress"),
        (0.0, 0.0, ["Planned"], False, "Planned"),
        (0.0, 0.0, ["In progress"], False, "In progress"),
        (0.0, 0.0, ["Done", "In progress"], False, "In progress"),
        (0.0, 0.0, ["Done"], False, "Done"),
        (10.0, 10.0, ["Done", "In progress"], False, "In progress"),
        (10.0, 10.0, ["Done"], False, "Done"),
        (0.0, 8.0, ["Planned"], False, "Not started"),
        (2.0, 8.0, ["In progress"], False, "In progress"),
    ],
)
def test_competency_status_rules(
    done: float, planned: float, courses: list[str], projects: bool, expected: str
) -> None:
    assert _competency_status(done, planned, courses, projects) == expected
