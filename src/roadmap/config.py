"""Site configuration loaded from ``config/site.yaml``."""

from __future__ import annotations

import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from roadmap.models import Link


class SiteConfig(BaseModel):
    """Keys of ``config/site.yaml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    headline: str
    summary: str
    links: list[Link]
    start_year: int
    chart_min_weeks: int
    base_url: str
    repo_url: str
    # Decorative "platform" strip in the hero (tools used in production). Optional.
    platform: list[str] = []
    # Overrides the "studying since" KPI (courses taken before the Cronograma existed).
    studying_since: datetime.date | None = None


def load_config(path: Path) -> SiteConfig:
    """Load and validate the site configuration from a YAML file."""
    with Path(path).open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return SiteConfig.model_validate(data)
