"""Tests for the weekly SVG chart."""

from __future__ import annotations

from datetime import date

from roadmap.chart import render_weekly_svg
from roadmap.models import WeeklyPoint

POINTS = [
    WeeklyPoint(week_start=date(2026, 12, 28), hours_done_cum=5.0),
    WeeklyPoint(week_start=date(2027, 1, 4), hours_done_cum=9.0),
    WeeklyPoint(week_start=date(2027, 1, 11), hours_done_cum=10.5),
    WeeklyPoint(week_start=date(2027, 1, 18), hours_done_cum=13.0),
]


def test_empty_returns_empty_string() -> None:
    assert render_weekly_svg([]) == ""


def test_four_points() -> None:
    svg = render_weekly_svg(POINTS)
    assert "<title" in svg
    assert svg.count("<circle") == 4
    assert "Dec 28" in svg
    assert "Jan 18" in svg
    assert "13.0 h" in svg
    assert 'fill="none"' in svg


def test_deterministic() -> None:
    assert render_weekly_svg(POINTS) == render_weekly_svg(POINTS)


def test_single_point_centered() -> None:
    svg = render_weekly_svg(POINTS[:1])
    assert svg.count("<circle") == 1
    assert 'cx="320.0"' in svg


def test_all_zero_hours() -> None:
    pts = [WeeklyPoint(week_start=date(2027, 1, 4), hours_done_cum=0.0)]
    assert "0.0 h" in render_weekly_svg(pts)
