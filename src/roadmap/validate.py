"""Data-quality checks (RNF-Q) that block publication."""

from __future__ import annotations

import datetime
import re
from typing import Literal

from roadmap.models import (
    CronogramaRow,
    CronogramaTotals,
    Issue,
    ModuleRow,
    PublicoRow,
    PublishedData,
)

_SLUG = re.compile(r"^[a-z0-9-]+$")
_PUBLICO = "Publico"

Rule = Literal["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]


def check_future_dates(rows: list[CronogramaRow], today: datetime.date) -> list[Issue]:
    """Q2: a non-planned row may not be dated more than one day after ``today``."""
    limit = today + datetime.timedelta(days=1)
    return [
        Issue(
            tab="Cronograma",
            row=r.row,
            rule="Q2",
            message=f"date {r.date.isoformat()} is in the future but status is not Planned",
        )
        for r in rows
        if r.date > limit and r.status != "Planned"
    ]


def check_publico(rows: list[PublicoRow], case_ids: set[str]) -> list[Issue]:
    """Q5/Q6: uniqueness and referential integrity of the Publico tab."""
    issues: list[Issue] = []

    def add(row: PublicoRow, rule: Rule, msg: str) -> None:
        issues.append(Issue(tab=_PUBLICO, row=row.row, rule=rule, message=msg))

    competencia_ids = {r.id for r in rows if r.tipo == "competencia"}
    curso_ids = {r.id for r in rows if r.tipo == "curso"}

    seen: set[tuple[str, str]] = set()
    seen_keys: dict[str, str] = {}
    for r in rows:
        key = (r.tipo, r.id)
        if key in seen:
            add(r, "Q6", f"duplicate (tipo, id): ({r.tipo}, '{r.id}')")
        seen.add(key)
        if not _SLUG.fullmatch(r.id):
            add(r, "Q6", f"id '{r.id}' must match ^[a-z0-9-]+$")
        if r.tipo == "curso" and r.cronograma_key:
            if r.cronograma_key in seen_keys:
                add(
                    r,
                    "Q6",
                    f"cronograma_key repeated in courses '{seen_keys[r.cronograma_key]}' "
                    f"and '{r.id}'",
                )
            else:
                seen_keys[r.cronograma_key] = r.id

    for r in rows:
        if not r.publicar:
            continue
        label = f"{r.tipo} '{r.id}'"
        if not r.nome_en.strip():
            add(r, "Q5", f"{label} has empty nome_en")
        if r.tipo in ("competencia", "projeto") and not (r.descricao_en or "").strip():
            add(r, "Q5", f"{label} has empty descricao_en")
        if r.tipo in ("curso", "projeto"):
            if not r.competencias:
                add(r, "Q5", f"{label} has no competencias")
            for c in r.competencias:
                if c not in competencia_ids:
                    add(r, "Q5", f"{label} references unknown competencia '{c}'")
        if r.tipo == "projeto" and not r.url and r.id not in case_ids:
            add(r, "Q5", f"projeto '{r.id}' has no url and no case file")
        for col, val in (("url", r.url), ("credencial_url", r.credencial_url)):
            if val and not val.startswith("https://"):
                add(r, "Q5", f"{label} {col} must start with https://")
        if r.horas_manual_total is not None and (
            r.status_manual != "In progress" or r.horas_manual > r.horas_manual_total  # type: ignore[operator]
        ):
            add(r, "Q5", f"{label} horas_manual 'done/total' needs In progress and done <= total")
        in_progress = r.status_manual == "In progress"
        if in_progress and r.horas_manual is not None and r.horas_manual_total is None:
            add(r, "Q5", f"{label} in progress needs horas_manual as 'done/total' or empty")
        if r.tipo == "modulo":
            if r.pai is None or r.pai not in curso_ids:
                add(r, "Q5", f"modulo '{r.id}' has unknown pai '{r.pai or ''}'")
            elif not re.fullmatch(rf"{re.escape(r.pai)}-m\d+", r.id):
                add(r, "Q5", f"modulo id '{r.id}' must match '{r.pai}-m<N>'")
    return issues


def check_modules_mapped(publico: list[PublicoRow], modules: list[ModuleRow]) -> list[Issue]:
    """Q5: a public modulo must point to a module number present in the modules tab."""
    numbers = {m.number for m in modules}
    issues: list[Issue] = []
    for r in publico:
        if r.tipo != "modulo" or not r.publicar or r.pai is None:
            continue
        m = re.fullmatch(rf"{re.escape(r.pai)}-m(\d+)", r.id)
        if m and int(m.group(1)) not in numbers:
            issues.append(
                Issue(
                    tab=_PUBLICO,
                    row=r.row,
                    rule="Q5",
                    message=f"modulo '{r.id}' refers to module {int(m.group(1))}, "
                    "which is not in the modules tab",
                )
            )
    return issues


def check_vanished_courses(
    publico: list[PublicoRow],
    rows: list[CronogramaRow],
    previous: PublishedData | None,
) -> list[Issue]:
    """Q5 (K3): a course with published hours whose cronograma_key no longer matches."""
    if previous is None:
        return []
    prev_hours = {c.id: c.hours_done for c in previous.courses}
    present = {r.course for r in rows}
    return [
        Issue(
            tab=_PUBLICO,
            row=p.row,
            rule="Q5",
            message=f"course '{p.id}' had published hours but its cronograma_key "
            "matches no Cronograma row",
        )
        for p in publico
        if p.tipo == "curso"
        and p.publicar
        and p.cronograma_key
        and p.status_manual is None
        and prev_hours.get(p.id, 0) > 0
        and p.cronograma_key not in present
    ]


def check_reconciliation(
    rows: list[CronogramaRow], totals: CronogramaTotals, tol: float = 0.1
) -> list[Issue]:
    """Q7: parsed hours must match the sheet's own totals (rows 1-3), before any filter.

    planned = sum of all rows (confirmed against real data, design K1), done = Done rows,
    missed = Missed rows. A mismatch means the parsing is wrong, so publication is blocked.
    """
    computed = {
        "Horas planejadas": (sum(r.hours for r in rows), totals.planned),
        "Horas concluídas": (sum(r.hours for r in rows if r.status == "Done"), totals.done),
        "Horas não feitas": (sum(r.hours for r in rows if r.status == "Missed"), totals.missed),
    }
    return [
        Issue(
            tab="Cronograma",
            row=None,
            rule="Q7",
            message=f"'{label}' is {expected:.1f} in the sheet but rows sum to {got:.1f}",
        )
        for label, (got, expected) in computed.items()
        if abs(got - expected) > tol + 1e-9
    ]
