"""Allowlist filtering and progress calculations (R1-R4, R8; design "Regras de cálculo", ADR-08).

Input is already validated (T5-T7). Anything not reachable from a public competency is dropped.
"""

from __future__ import annotations

import datetime
import re
from collections import defaultdict

from roadmap.config import SiteConfig
from roadmap.models import (
    Competency,
    Course,
    CronogramaRow,
    Kpis,
    Module,
    ParsedSheets,
    Profile,
    Project,
    PublicoRow,
    PublishedData,
    WeeklyPoint,
)


def _r1(x: float) -> float:
    return round(x + 0.0, 1)


def _sort_key(row: PublicoRow) -> tuple[int, str]:
    return (row.ordem, row.id)


def _pct(done: float, planned: float) -> float | None:
    return _r1(100 * done / planned) if planned > 0 else None


def _course_status(done: float, planned_left: float) -> str:
    if done > 0 and planned_left > 0:
        return "In progress"
    if planned_left == 0 and done > 0:
        return "Done"
    return "Planned"


def _competency_status(
    done: float, planned: float, course_statuses: list[str], has_projects: bool
) -> str:
    """Hours come from courses; started courses and public projects count as progress (R1)."""
    if course_statuses and all(s == "Done" for s in course_statuses) and done >= planned:
        return "Done"
    if done > 0 or has_projects or any(s != "Planned" for s in course_statuses):
        return "In progress"
    if planned <= 0:
        return "Planned"
    return "Not started"


def _week_start(d: datetime.date) -> datetime.date:
    return d - datetime.timedelta(days=d.weekday())


def _weekly(rows: list[CronogramaRow], min_weeks: int) -> list[WeeklyPoint]:
    done = [r for r in rows if r.status == "Done"]
    if not done:
        return []
    per_week: dict[datetime.date, float] = defaultdict(float)
    for r in done:
        per_week[_week_start(r.date)] += r.hours
    first, last = min(per_week), max(per_week)
    n_weeks = (last - first).days // 7 + 1
    if n_weeks < min_weeks:
        return []
    points: list[WeeklyPoint] = []
    cum = 0.0
    for i in range(n_weeks):
        week = first + datetime.timedelta(weeks=i)
        cum += per_week.get(week, 0.0)
        points.append(WeeklyPoint(week_start=week, hours_done_cum=_r1(cum)))
    return points


def build_published(
    parsed: ParsedSheets,
    config: SiteConfig,
    case_ids: set[str],
    today: datetime.date,
    previous: PublishedData | None,
    min_weeks: int,
) -> PublishedData:
    """Build the public snapshot from validated sheets."""
    by_tipo: dict[str, list[PublicoRow]] = defaultdict(list)
    for row in parsed.publico:
        if row.publicar:
            by_tipo[row.tipo].append(row)

    comps = sorted(by_tipo["competencia"], key=_sort_key)
    comp_ids = {c.id for c in comps}

    def public_comps(row: PublicoRow) -> list[str]:
        return [c for c in row.competencias if c in comp_ids]

    courses_rows = sorted(
        (c for c in by_tipo["curso"] if public_comps(c)), key=_sort_key
    )
    projects_rows = sorted(
        (p for p in by_tipo["projeto"] if public_comps(p)), key=_sort_key
    )
    course_ids = {c.id for c in courses_rows}

    # Public Cronograma rows: course text matches the cronograma_key of a public course.
    # Missed rows never count (ADR-08).
    key_to_course = {c.cronograma_key: c.id for c in courses_rows if c.cronograma_key}
    public_rows = [
        r for r in parsed.cronograma if r.course in key_to_course and r.status != "Missed"
    ]
    done_by: dict[str, float] = defaultdict(float)
    todo_by: dict[str, float] = defaultdict(float)
    for r in public_rows:
        cid = key_to_course[r.course]
        if r.status == "Done":
            done_by[cid] += r.hours
        else:
            todo_by[cid] += r.hours

    # Modules: id "<pai>-m<N>", status from the module tab.
    module_status = {m.number: m.status for m in parsed.modules}
    modules_by_course: dict[str, list[Module]] = defaultdict(list)
    for m in sorted(by_tipo["modulo"], key=_sort_key):
        if m.pai not in course_ids:
            continue
        match = re.fullmatch(rf"{re.escape(m.pai)}-m(\d+)", m.id)
        if not match or int(match.group(1)) not in module_status:
            continue
        modules_by_course[m.pai].append(
            Module(id=m.id, name=m.nome_en, status=module_status[int(match.group(1))])
        )

    courses: list[Course] = []
    for c in courses_rows:
        if c.status_manual is not None:
            # Courses tracked outside the Cronograma. Done: total hours (optional).
            # In progress: "done/total" (optional).
            done = c.horas_manual or 0.0
            planned = c.horas_manual_total if c.horas_manual_total is not None else done
            status = c.status_manual
        else:
            done = done_by.get(c.id, 0.0)
            planned = done + todo_by.get(c.id, 0.0)
            status = _course_status(done, todo_by.get(c.id, 0.0))
        courses.append(
            Course(
                id=c.id,
                name=c.nome_en,
                provider=c.provedor or "",
                competencies=public_comps(c),
                status=status,  # type: ignore[arg-type]
                hours_done=_r1(done),
                hours_planned=_r1(planned),
                credential_url=c.credencial_url,
                modules=modules_by_course.get(c.id, []),
            )
        )

    projects = [
        Project(
            id=p.id,
            title=p.nome_en,
            description=p.descricao_en or "",
            stack=p.stack,
            competencies=public_comps(p),
            repo_url=p.url,
            case_path=f"cases/{p.id}.html" if p.url is None and p.id in case_ids else None,
        )
        for p in projects_rows
    ]

    competencies: list[Competency] = []
    for comp in comps:
        linked = [c for c in courses if comp.id in c.competencies]
        done = sum(c.hours_done for c in linked)
        planned = sum(c.hours_planned for c in linked)
        linked_projects = [p.id for p in projects if comp.id in p.competencies]
        competencies.append(
            Competency(
                id=comp.id,
                name=comp.nome_en,
                description=comp.descricao_en or "",
                order=comp.ordem,
                status=_competency_status(
                    done, planned, [c.status for c in linked], bool(linked_projects)
                ),  # type: ignore[arg-type]
                pct=_pct(done, planned),
                hours_done=_r1(done),
                hours_planned=_r1(planned),
                courses=[c.id for c in linked],
                projects=linked_projects,
            )
        )

    # KPIs over distinct public courses (a course in two competencies counts once).
    total_done = sum(c.hours_done for c in courses)
    total_planned = sum(c.hours_planned for c in courses)
    done_dates = [r.date for r in public_rows if r.status == "Done"]
    any_dates = [r.date for r in public_rows]
    kpis = Kpis(
        hours_done=_r1(total_done),
        hours_planned_total=_r1(total_planned),
        pct_plan=_pct(total_done, total_planned) or 0.0,
        courses_done=sum(1 for c in courses if c.status == "Done"),
        courses_total=len(courses),
        study_start=config.studying_since or min(done_dates or any_dates or [today]),
    )

    candidate = PublishedData(
        data_updated_at=today,
        profile=Profile(
            name=config.name,
            headline=config.headline,
            summary=config.summary,
            links=config.links,
        ),
        kpis=kpis,
        competencies=competencies,
        courses=courses,
        projects=projects,
        weekly=_weekly(public_rows, min_weeks),
    )
    # ADR-07: keep the previous date when the published content did not change.
    if previous is not None:
        exclude = {"data_updated_at"}
        if previous.model_dump(exclude=exclude) == candidate.model_dump(exclude=exclude):
            return candidate.model_copy(update={"data_updated_at": previous.data_updated_at})
    return candidate
