"""Render tests over the fixture-based PublishedData."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from roadmap.config import load_config
from roadmap.extract import load_fixture
from roadmap.models import PublishedData
from roadmap.parse import parse_sheets
from roadmap.render import render_site
from roadmap.transform import build_published

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "tests/fixtures/content"
CONFIG = load_config(ROOT / "tests/fixtures/site.yaml")


@pytest.fixture(scope="module")
def data() -> PublishedData:
    parsed, issues = parse_sheets(load_fixture(ROOT / "tests/fixtures/valid.json"), 2026)
    assert issues == []
    return build_published(
        parsed,
        config=CONFIG,
        case_ids={"private-proj"},
        today=datetime.date(2027, 2, 1),
        previous=None,
        min_weeks=4,
    )


@pytest.fixture(scope="module")
def site(data: PublishedData, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[Path]]:
    out = tmp_path_factory.mktemp("dist") / "dist"
    return out, render_site(data, CONFIG, CONTENT, out)


def test_files_written(site: tuple[Path, list[Path]]) -> None:
    out, paths = site
    assert paths == sorted(paths)
    assert (out / "cases/private-proj.html").exists()
    assert (out / "style.css").exists()
    assert (out / ".nojekyll").exists()


def test_index_content(site: tuple[Path, list[Path]]) -> None:
    html = (site[0] / "index.html").read_text(encoding="utf-8")
    assert "<script" not in html
    assert html.count("<h1") == 1
    assert "Data Platforms" in html
    for hidden in ("Secret Competency", "Hidden Project", "Gamma Course"):
        assert hidden not in html
    assert html.count("View credential") == 1
    assert "6.5/9.5 h" in html
    assert "Dec 2026" in html
    assert 'id="chart-title"' in html
    assert "Data last updated: 2027-02-01" in html


def test_no_forbidden_text_anywhere(site: tuple[Path, list[Path]]) -> None:
    for path in site[1]:
        assert "Interno X" not in path.read_text(encoding="utf-8")


def test_case_page_links(site: tuple[Path, list[Path]]) -> None:
    html = (site[0] / "cases/private-proj.html").read_text(encoding="utf-8")
    assert "../index.html" in html
    assert 'href="../style.css"' in html
    assert "<h2>Architecture</h2>" in html


def test_no_chart_when_weekly_empty(data: PublishedData, tmp_path: Path) -> None:
    empty = data.model_copy(update={"weekly": []})
    render_site(empty, CONFIG, CONTENT, tmp_path / "d")
    assert 'id="chart-title"' not in (tmp_path / "d/index.html").read_text(encoding="utf-8")


def test_deterministic(data: PublishedData, tmp_path: Path) -> None:
    render_site(data, CONFIG, CONTENT, tmp_path / "a")
    render_site(data, CONFIG, CONTENT, tmp_path / "b")
    for name in ("index.html", "cases/private-proj.html", "style.css"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_languages_line_in_hero(data: PublishedData, tmp_path: Path) -> None:
    line = "English: B2 · ongoing coaching (speaking & writing)"
    render_site(data, CONFIG.model_copy(update={"languages": [line]}), CONTENT, tmp_path / "a")
    html = (tmp_path / "a/index.html").read_text(encoding="utf-8")
    assert 'class="languages"' in html and "English: B2" in html
    render_site(data, CONFIG, CONTENT, tmp_path / "b")
    assert 'class="languages"' not in (tmp_path / "b/index.html").read_text(encoding="utf-8")


def test_diagrams_copied_only_when_shown(data: PublishedData, tmp_path: Path) -> None:
    diagrams = tmp_path / "diagrams"
    diagrams.mkdir()
    svg = "<svg viewBox='0 0 4 4'><title>diagram</title><rect width='4' height='4'/></svg>"
    for name in ("roadmap-site", "private-proj", "unused"):
        (diagrams / f"{name}.svg").write_text(svg, encoding="utf-8")
    out = tmp_path / "d"
    render_site(data, CONFIG, CONTENT, out, diagrams_dir=diagrams)
    assert sorted(p.name for p in (out / "diagrams").iterdir()) == [
        "private-proj.svg", "roadmap-site.svg",
    ]
    assert 'src="diagrams/roadmap-site.svg"' in (out / "index.html").read_text(encoding="utf-8")
    case = (out / "cases/private-proj.html").read_text(encoding="utf-8")
    assert 'src="../diagrams/private-proj.svg"' in case and 'alt="' in case


def test_no_diagram_section_without_svgs(data: PublishedData, tmp_path: Path) -> None:
    out = tmp_path / "d"
    render_site(data, CONFIG, CONTENT, out, diagrams_dir=tmp_path / "missing")
    assert 'class="panel diagram"' not in (out / "index.html").read_text(encoding="utf-8")
    assert not (out / "diagrams").exists()
