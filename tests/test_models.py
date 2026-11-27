from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from roadmap.config import load_config
from roadmap.models import CronogramaTotals, Issue, Link, WeeklyPoint

ROOT = Path(__file__).resolve().parent.parent


def test_issue_format_with_row() -> None:
    issue = Issue(tab="Cronograma", row=12, rule="Q3", message="bad date")
    assert issue.format() == "[Q3] Cronograma row 12: bad date"


def test_issue_format_without_row() -> None:
    issue = Issue(tab="Cronograma", row=None, rule="Q3", message="bad date")
    assert issue.format() == "[Q3] Cronograma: bad date"


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        CronogramaTotals(planned=1, done=1, missed=0, unknown=1)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        Link(label="a", url="b", extra="x")  # type: ignore[call-arg]


def test_frozen() -> None:
    point = WeeklyPoint(week_start=datetime.date(2026, 11, 16), hours_done_cum=4.0)
    with pytest.raises(ValidationError):
        point.hours_done_cum = 5.0  # type: ignore[misc]


def test_load_config() -> None:
    cfg = load_config(ROOT / "config" / "site.yaml")
    assert cfg.start_year == 2026
    assert cfg.chart_min_weeks == 4
    assert all(isinstance(link, Link) for link in cfg.links)
