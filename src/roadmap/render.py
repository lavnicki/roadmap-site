"""Render the static site (HTML + CSS) from the published snapshot."""

from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markdown_it import MarkdownIt

from roadmap.chart import render_weekly_svg
from roadmap.config import SiteConfig
from roadmap.models import PublishedData


def _repo_root() -> Path:
    """Templates live in the repo, not in the package: prefer the source checkout, else the CWD.

    With a non-editable install the module sits in site-packages, so ``parents[2]`` has no
    ``templates/``; the pipeline always runs from the repo root, so the CWD is the fallback.
    """
    source_root = Path(__file__).resolve().parents[2]
    return source_root if (source_root / "templates").is_dir() else Path.cwd()


REPO_ROOT = _repo_root()
TEMPLATES_DIR = REPO_ROOT / "templates"
STATIC_DIR = REPO_ROOT / "static"

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _hours(value: float) -> str:
    return f"{value:.1f}"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def _month_year(value: datetime.date) -> str:
    return f"{_MONTHS[value.month - 1]} {value.year}"


def _slug(value: str) -> str:
    return value.lower().replace(" ", "-")


def _make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["hours"] = _hours
    env.filters["pct"] = _pct
    env.filters["month_year"] = _month_year
    env.filters["slug"] = _slug
    return env


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def render_site(
    data: PublishedData, config: SiteConfig, content_dir: Path, out_dir: Path
) -> list[Path]:
    """Write the whole site into ``out_dir`` (recreated) and return the sorted written paths."""
    env = _make_env()
    md = MarkdownIt("commonmark", {"html": False})
    content_dir = Path(content_dir)
    out_dir = Path(out_dir)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    about_html = md.render((content_dir / "about.md").read_text(encoding="utf-8"))
    written: list[Path] = []

    index = env.get_template("index.html").render(
        data=data,
        config=config,
        courses={c.id: c for c in data.courses},
        projects={p.id: p for p in data.projects},
        chart_svg=render_weekly_svg(data.weekly),
        about_html=about_html,
    )
    path = out_dir / "index.html"
    _write(path, index)
    written.append(path)

    case_template = env.get_template("case.html")
    for project in data.projects:
        if project.case_path is None:
            continue
        case_md = (content_dir / "cases" / f"{project.id}.md").read_text(encoding="utf-8")
        path = out_dir / "cases" / f"{project.id}.html"
        _write(
            path,
            case_template.render(
                config=config, project=project, case_html=md.render(case_md)
            ),
        )
        written.append(path)

    path = out_dir / "style.css"
    _write(path, (STATIC_DIR / "style.css").read_text(encoding="utf-8"))
    written.append(path)

    path = out_dir / ".nojekyll"
    _write(path, "")
    written.append(path)

    return sorted(written)
