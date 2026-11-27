"""Deterministic inline SVG line chart of cumulative study hours per week."""

from __future__ import annotations

import datetime

from roadmap.models import WeeklyPoint

_MARGIN = 32
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _date_label(day: datetime.date) -> str:
    """Format a date as ``Dec 28`` without relying on the locale."""
    return f"{_MONTHS[day.month - 1]} {day.day}"


def render_weekly_svg(points: list[WeeklyPoint], width: int = 640, height: int = 200) -> str:
    """Render the weekly cumulative hours as an SVG string ("" when there are no points)."""
    if not points:
        return ""

    plot_w = width - 2 * _MARGIN
    plot_h = height - 2 * _MARGIN
    max_hours = max(p.hours_done_cum for p in points) or 1.0
    last_index = len(points) - 1

    coords: list[tuple[float, float]] = []
    for i, p in enumerate(points):
        x = _MARGIN + plot_w / 2 if last_index == 0 else _MARGIN + plot_w * i / last_index
        y = _MARGIN + plot_h * (1 - p.hours_done_cum / max_hours)
        coords.append((x, y))

    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    label_y = height - _MARGIN / 2
    last_x, last_y = coords[-1]

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title" '
        'xmlns="http://www.w3.org/2000/svg">',
        '<title id="chart-title">Cumulative study hours per week</title>',
        f'<polyline class="line" fill="none" stroke="currentColor" stroke-width="2" '
        f'points="{poly}"/>',
    ]
    parts.extend(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="currentColor"/>' for x, y in coords
    )

    first_x = coords[0][0]
    parts.append(
        f'<text x="{first_x:.1f}" y="{label_y:.1f}" text-anchor="middle" fill="currentColor">'
        f"{_date_label(points[0].week_start)}</text>"
    )
    if last_index > 0:
        parts.append(
            f'<text x="{last_x:.1f}" y="{label_y:.1f}" text-anchor="middle" fill="currentColor">'
            f"{_date_label(points[-1].week_start)}</text>"
        )
    parts.append(
        f'<text x="{last_x:.1f}" y="{max(last_y - 8, 12):.1f}" text-anchor="middle" '
        f'fill="currentColor">{points[-1].hours_done_cum:.1f} h</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)
