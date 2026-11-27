"""Pydantic models: raw sheet data, parsed rows, validation issues and the published snapshot."""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Status = Literal["Done", "Planned", "Missed"]


class _Model(BaseModel):
    """Base class: immutable, rejects unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class RawSheets(_Model):
    """Raw cell values of each extracted range."""

    publico: list[list[str]]
    cronograma_totals: list[list[str]]
    cronograma_left: list[list[str]]
    cronograma_right: list[list[str]]
    modules: list[list[str]]


class Issue(_Model):
    """A validation problem found in the sheet."""

    tab: str
    row: int | None
    rule: Literal["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]
    message: str

    def format(self) -> str:
        """Render as ``[Q3] Cronograma row 12: message`` (row omitted when None)."""
        where = self.tab if self.row is None else f"{self.tab} row {self.row}"
        return f"[{self.rule}] {where}: {self.message}"


class CronogramaTotals(_Model):
    """Totals block of the Cronograma tab."""

    planned: float
    done: float
    missed: float


class CronogramaRow(_Model):
    """One schedule row."""

    row: int
    date: datetime.date
    course: str
    hours: float
    status: Status


class ModuleRow(_Model):
    """One module row of the Spark & Databricks tab."""

    row: int
    number: int
    status: Literal["Done", "Planned"]


class PublicoRow(_Model):
    """One row of the Publico tab."""

    row: int
    tipo: Literal["competencia", "curso", "projeto", "modulo"]
    id: str
    publicar: bool
    ordem: int
    nome_en: str
    descricao_en: str | None
    competencias: list[str]
    provedor: str | None
    cronograma_key: str | None
    url: str | None
    credencial_url: str | None
    stack: list[str]
    pai: str | None
    status_manual: Literal["Done", "In progress"] | None
    horas_manual: float | None
    horas_manual_total: float | None = None  # In progress: 'done/total'


class ParsedSheets(_Model):
    """Typed contents of all sheets."""

    totals: CronogramaTotals
    cronograma: list[CronogramaRow]
    modules: list[ModuleRow]
    publico: list[PublicoRow]


class Link(_Model):
    """A labelled external link."""

    label: str
    url: str


class Profile(_Model):
    """Public profile shown on the site."""

    name: str
    headline: str
    summary: str
    links: list[Link]


class Kpis(_Model):
    """Headline numbers."""

    hours_done: float
    hours_planned_total: float
    pct_plan: float
    courses_done: int
    courses_total: int
    study_start: datetime.date


class Competency(_Model):
    """A published competency with aggregated progress."""

    id: str
    name: str
    description: str
    order: int
    status: Literal["Not started", "In progress", "Done", "Planned"]
    pct: float | None
    hours_done: float
    hours_planned: float
    courses: list[str]
    projects: list[str]


class Module(_Model):
    """A course module."""

    id: str
    name: str
    status: Literal["Done", "Planned"]


class Course(_Model):
    """A published course."""

    id: str
    name: str
    provider: str
    competencies: list[str]
    status: Literal["Planned", "In progress", "Done"]
    hours_done: float
    hours_planned: float
    credential_url: str | None
    modules: list[Module]


class Project(_Model):
    """A published project."""

    id: str
    title: str
    description: str
    stack: list[str]
    competencies: list[str]
    repo_url: str | None
    case_path: str | None


class WeeklyPoint(_Model):
    """Cumulative done hours at the start of an ISO week."""

    week_start: datetime.date
    hours_done_cum: float


class PublishedData(_Model):
    """The snapshot stored in ``data/published.json``."""

    schema_version: Literal[1] = 1
    data_updated_at: datetime.date
    profile: Profile
    kpis: Kpis
    competencies: list[Competency]
    courses: list[Course]
    projects: list[Project]
    weekly: list[WeeklyPoint]
