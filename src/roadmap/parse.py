"""Parsing of raw sheet values (pt-BR numbers, dd/mm dates, statuses, Publico tab)."""

from __future__ import annotations

import datetime
import re

from roadmap.models import (
    CronogramaRow,
    CronogramaTotals,
    Issue,
    ModuleRow,
    ParsedSheets,
    PublicoRow,
    RawSheets,
    Status,
)

PUBLICO_HEADER = [
    "tipo",
    "id",
    "publicar",
    "ordem",
    "nome_en",
    "descricao_en",
    "competencias",
    "provedor",
    "cronograma_key",
    "url",
    "credencial_url",
    "stack",
    "pai",
    "status_manual",
    "horas_manual",
]
_TOTALS_LABELS = ["Horas planejadas", "Horas concluídas", "Horas não feitas"]
_TAB_CRONOGRAMA = "Cronograma"
_TAB_MODULES = "Spark & Databricks"
_TAB_PUBLICO = "Publico"
_NUMBER_RE = re.compile(r"^\d+(,\d+)?$")
_DDMM_RE = re.compile(r"^\d{2}/\d{2}$")
_TIPOS = ("competencia", "curso", "projeto", "modulo")
_MAX_HOURS = 12.0


def parse_ptbr_number(s: str) -> float:
    """Parse a pt-BR number such as ``"2,0"`` or ``"14"``; raise ValueError otherwise."""
    t = s.strip()
    if not _NUMBER_RE.match(t):
        raise ValueError(f"invalid pt-BR number: {s!r}")
    return float(t.replace(",", "."))


def parse_status(s: str) -> Status:
    """Map ``Feito``/``A fazer``/``Não feito`` (case-insensitive) to a Status."""
    t = s.strip().lower()
    if t == "feito":
        return "Done"
    if t == "a fazer":
        return "Planned"
    if t == "não feito":
        return "Missed"
    raise ValueError(f"invalid status: {s!r}")


def _advance_year(year: int, prev_month: int | None, month: int) -> int:
    return year + 1 if prev_month is not None and month < prev_month else year


def infer_dates(ddmm: list[str], start_year: int) -> list[datetime.date]:
    """Infer full dates from ``dd/mm`` strings; the year grows when the month decreases."""
    out: list[datetime.date] = []
    year = start_year
    prev_month: int | None = None
    for i, text in enumerate(ddmm):
        if not _DDMM_RE.match(text):
            raise ValueError(f"index {i}: invalid date format")
        day, month = int(text[:2]), int(text[3:])
        if not 1 <= month <= 12:
            raise ValueError(f"index {i}: invalid date")
        year = _advance_year(year, prev_month, month)
        prev_month = month
        try:
            out.append(datetime.date(year, month, day))
        except ValueError:
            raise ValueError(f"index {i}: invalid date") from None
    return out


def _pad(row: list[str], width: int) -> list[str]:
    return list(row) + [""] * (width - len(row))


def _is_empty(row: list[str]) -> bool:
    return all(c.strip() == "" for c in row)


def _opt(s: str) -> str | None:
    t = s.strip()
    return t or None


def _split(s: str) -> list[str]:
    return [p.strip() for p in s.split(";") if p.strip()]


def _parse_totals(raw: list[list[str]], issues: list[Issue]) -> CronogramaTotals:
    values = [0.0, 0.0, 0.0]
    for i, label in enumerate(_TOTALS_LABELS):
        row = _pad(raw[i], 2) if i < len(raw) else ["", ""]
        if row[0] != label:
            issues.append(
                Issue(
                    tab=_TAB_CRONOGRAMA,
                    row=None,
                    rule="Q1",
                    message=f"totals label {i + 1} expected {label!r}",
                )
            )
            continue
        try:
            values[i] = parse_ptbr_number(row[1])
        except ValueError:
            issues.append(
                Issue(
                    tab=_TAB_CRONOGRAMA,
                    row=None,
                    rule="Q1",
                    message=f"total {label!r} is not a valid number",
                )
            )
    return CronogramaTotals(planned=values[0], done=values[1], missed=values[2])


def _parse_cronograma(raw: RawSheets, start_year: int, issues: list[Issue]) -> list[CronogramaRow]:
    left, right = list(raw.cronograma_left), list(raw.cronograma_right)
    if (
        not left
        or left[0] != ["Data", "Dia", "Curso"]
        or not right
        or right[0] != ["Horas", "Status"]
    ):
        issues.append(
            Issue(
                tab=_TAB_CRONOGRAMA,
                row=None,
                rule="Q1",
                message="unexpected header (expected Data, Dia, Curso | Horas, Status)",
            )
        )
        return []
    size = max(len(left), len(right))
    left += [[] for _ in range(size - len(left))]
    right += [[] for _ in range(size - len(right))]

    rows: list[CronogramaRow] = []
    year = start_year
    prev_month: int | None = None
    for idx in range(1, size):
        data, _dia, curso = _pad(left[idx], 3)[:3]
        horas, status = _pad(right[idx], 2)[:2]
        if all(c.strip() == "" for c in (data, curso, horas, status)):
            continue
        rownum = idx + 4
        problems: list[Issue] = []

        date: datetime.date | None = None
        d = data.strip() if _DDMM_RE.match(data) else None
        month = int(d[3:]) if d and 1 <= int(d[3:]) <= 12 else None
        if d is None or month is None:
            problems.append(
                Issue(
                    tab=_TAB_CRONOGRAMA,
                    row=rownum,
                    rule="Q2",
                    message=f"invalid date {data!r} (expected dd/mm)",
                )
            )
        else:
            # The month is valid, so it takes part in the year inference.
            year = _advance_year(year, prev_month, month)
            prev_month = month
            try:
                date = datetime.date(year, month, int(d[:2]))
            except ValueError:
                problems.append(
                    Issue(
                        tab=_TAB_CRONOGRAMA,
                        row=rownum,
                        rule="Q2",
                        message=f"invalid calendar date {data!r} for year {year}",
                    )
                )
        hours = 0.0
        try:
            hours = parse_ptbr_number(horas)
            if not 0 <= hours <= _MAX_HOURS:
                raise ValueError("out of range")
        except ValueError:
            problems.append(
                Issue(
                    tab=_TAB_CRONOGRAMA,
                    row=rownum,
                    rule="Q3",
                    message=f"invalid hours {horas!r} (expected 0 to 12)",
                )
            )
        st: Status = "Done"
        try:
            st = parse_status(status)
        except ValueError:
            problems.append(
                Issue(
                    tab=_TAB_CRONOGRAMA,
                    row=rownum,
                    rule="Q4",
                    message=f"invalid status {status!r}",
                )
            )
        issues.extend(problems)
        if not problems and date is not None:
            rows.append(
                CronogramaRow(row=rownum, date=date, course=curso.strip(), hours=hours, status=st)
            )
    return rows


def _parse_modules(raw: list[list[str]], issues: list[Issue]) -> list[ModuleRow]:
    if not raw or raw[0][:4] != ["Módulo", "Tema", "Horas", "Status"]:
        issues.append(
            Issue(
                tab=_TAB_MODULES,
                row=None,
                rule="Q1",
                message="unexpected header (expected Módulo, Tema, Horas, Status)",
            )
        )
        return []
    out: list[ModuleRow] = []
    for idx in range(1, len(raw)):
        if _is_empty(raw[idx]):
            continue
        cells = _pad(raw[idx], 4)
        rownum = idx + 1
        ok = True
        number = 0
        try:
            number = int(cells[0].strip())
        except ValueError:
            issues.append(
                Issue(tab=_TAB_MODULES, row=rownum, rule="Q5", message="invalid module number")
            )
            ok = False
        status: str = ""
        try:
            status = parse_status(cells[3])
            if status == "Missed":
                raise ValueError("not allowed")
        except ValueError:
            issues.append(
                Issue(
                    tab=_TAB_MODULES,
                    row=rownum,
                    rule="Q4",
                    message=f"invalid status {cells[3]!r} (expected Feito or A fazer)",
                )
            )
            ok = False
        if ok and (status == "Done" or status == "Planned"):
            out.append(ModuleRow(row=rownum, number=number, status=status))
    return out


def _parse_publico(raw: list[list[str]], issues: list[Issue]) -> list[PublicoRow]:
    if not raw or raw[0] != PUBLICO_HEADER:
        issues.append(Issue(tab=_TAB_PUBLICO, row=None, rule="Q1", message="unexpected header"))
        return []
    out: list[PublicoRow] = []
    for idx in range(1, len(raw)):
        if _is_empty(raw[idx]):
            continue
        c = dict(zip(PUBLICO_HEADER, _pad(raw[idx], len(PUBLICO_HEADER)), strict=False))
        rownum = idx + 1
        problems: list[Issue] = []

        def bad(
            rule: str, msg: str, rownum: int = rownum, problems: list[Issue] = problems
        ) -> None:
            problems.append(
                Issue(tab=_TAB_PUBLICO, row=rownum, rule=rule, message=msg)  # type: ignore[arg-type]
            )

        tipo = c["tipo"].strip()
        if tipo not in _TIPOS:
            bad("Q5", f"invalid tipo {c['tipo']!r}")
        ordem = 0
        try:
            ordem = int(c["ordem"].strip())
        except ValueError:
            bad("Q5", f"invalid ordem {c['ordem']!r}")
        horas_manual: float | None = None
        horas_manual_total: float | None = None
        raw_hours = c["horas_manual"].strip()
        if raw_hours:
            try:
                if "/" in raw_hours:  # "done/total", for courses in progress
                    done_s, total_s = raw_hours.split("/", 1)
                    horas_manual = parse_ptbr_number(done_s.strip())
                    horas_manual_total = parse_ptbr_number(total_s.strip())
                else:
                    horas_manual = parse_ptbr_number(raw_hours)
            except ValueError:
                bad("Q3", f"invalid horas_manual {c['horas_manual']!r}")
        sm = c["status_manual"].strip()
        if sm not in ("", "Done", "In progress"):
            bad("Q5", f"invalid status_manual {c['status_manual']!r}")
        issues.extend(problems)
        if not problems:
            out.append(
                PublicoRow(
                    row=rownum,
                    tipo=tipo,  # type: ignore[arg-type]
                    id=c["id"].strip(),
                    publicar=c["publicar"].strip().lower() == "sim",
                    ordem=ordem,
                    nome_en=c["nome_en"].strip(),
                    descricao_en=_opt(c["descricao_en"]),
                    competencias=_split(c["competencias"]),
                    provedor=_opt(c["provedor"]),
                    cronograma_key=_opt(c["cronograma_key"]),
                    url=_opt(c["url"]),
                    credencial_url=_opt(c["credencial_url"]),
                    stack=_split(c["stack"]),
                    pai=_opt(c["pai"]),
                    status_manual=sm or None,  # type: ignore[arg-type]
                    horas_manual=horas_manual,
                    horas_manual_total=horas_manual_total,
                )
            )
    return out


def parse_sheets(raw: RawSheets, start_year: int) -> tuple[ParsedSheets, list[Issue]]:
    """Parse all sheets; every problem becomes an Issue and the offending row is dropped."""
    issues: list[Issue] = []
    totals = _parse_totals(raw.cronograma_totals, issues)
    cronograma = _parse_cronograma(raw, start_year, issues)
    modules = _parse_modules(raw.modules, issues)
    publico = _parse_publico(raw.publico, issues)
    parsed = ParsedSheets(totals=totals, cronograma=cronograma, modules=modules, publico=publico)
    return parsed, issues
