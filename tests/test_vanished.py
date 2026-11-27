"""Tests for check_vanished_courses (T7)."""

from __future__ import annotations

import datetime
from pathlib import Path

from roadmap.extract import load_fixture
from roadmap.models import Course, Kpis, ParsedSheets, Profile, PublishedData
from roadmap.parse import parse_sheets
from roadmap.validate import check_vanished_courses

FIXTURE = Path(__file__).parent / "fixtures" / "valid.json"


def previous(hours: float = 6.5) -> PublishedData:
    return PublishedData(
        data_updated_at=datetime.date(2027, 1, 1),
        profile=Profile(name="N", headline="H", summary="S", links=[]),
        kpis=Kpis(
            hours_done=hours,
            hours_planned_total=hours,
            pct_plan=100.0,
            courses_done=0,
            courses_total=1,
            study_start=datetime.date(2026, 12, 28),
        ),
        competencies=[],
        courses=[
            Course(
                id="alpha",
                name="Alpha Course",
                provider="Provider A",
                competencies=[],
                status="In progress",
                hours_done=hours,
                hours_planned=hours,
                credential_url=None,
                modules=[],
            )
        ],
        projects=[],
        weekly=[],
    )


def parsed() -> ParsedSheets:
    p, _ = parse_sheets(load_fixture(FIXTURE), 2026)
    return p


def test_previous_none() -> None:
    p = parsed()
    rows = [r for r in p.cronograma if r.course != "Curso Alpha"]
    assert check_vanished_courses(p.publico, rows, None) == []


def test_course_present() -> None:
    p = parsed()
    assert check_vanished_courses(p.publico, p.cronograma, previous()) == []


def test_course_vanished() -> None:
    p = parsed()
    rows = [r for r in p.cronograma if r.course != "Curso Alpha"]
    issues = check_vanished_courses(p.publico, rows, previous())
    assert len(issues) == 1
    i = issues[0]
    assert (i.tab, i.rule, i.row) == ("Publico", "Q5", 5)
    assert i.message == (
        "course 'alpha' had published hours but its cronograma_key matches no Cronograma row"
    )


def test_course_without_published_hours_not_flagged() -> None:
    p = parsed()
    rows = [r for r in p.cronograma if r.course != "Curso Alpha"]
    assert check_vanished_courses(p.publico, rows, previous(0.0)) == []
