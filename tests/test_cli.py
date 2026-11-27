from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from roadmap.cli import main

FIX = Path("tests/fixtures")
BASE = [
    "build",
    "--source",
    "fixture",
    "--config",
    str(FIX / "site.yaml"),
    "--guardrails",
    str(FIX / "guardrails.yaml"),
    "--content",
    str(FIX / "content"),
    "--today",
    "2027-02-01",
]


def _args(fixture: Path, out: Path, *extra: str) -> list[str]:
    return [*BASE, "--fixture", str(fixture), "--out", str(out), *extra]


def _hashes(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_golden_snapshot(tmp_path: Path) -> None:
    snap = tmp_path / "snap" / "published.json"
    assert main(_args(FIX / "valid.json", tmp_path / "dist", "--snapshot", str(snap))) == 0
    expected = (FIX / "expected_published.json").read_bytes()
    assert snap.read_bytes() == expected
    assert (tmp_path / "dist" / "index.html").exists()


def test_deterministic(tmp_path: Path) -> None:
    for name in ("a", "b"):
        assert main(_args(FIX / "valid.json", tmp_path / name)) == 0
    first = _hashes(tmp_path / "a")
    assert first and first == _hashes(tmp_path / "b")


def test_second_run_with_snapshot_is_stable(tmp_path: Path) -> None:
    snap = tmp_path / "published.json"
    argv = _args(FIX / "valid.json", tmp_path / "dist", "--snapshot", str(snap))
    assert main(argv) == 0
    first = snap.read_bytes()
    assert main(argv) == 0
    assert snap.read_bytes() == first


def test_q3_mutation_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    raw = json.loads((FIX / "valid.json").read_text(encoding="utf-8"))
    raw["cronograma_right"][1][0] = "13,0"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    snap = tmp_path / "snap.json"
    assert main(_args(bad, tmp_path / "dist", "--snapshot", str(snap))) == 1
    assert "[Q3]" in capsys.readouterr().err
    assert not snap.exists()
    assert not (tmp_path / "dist").exists()


def test_forbidden_term_blocks_without_leaking(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    terms = tmp_path / "terms.txt"
    terms.write_text("Alpha\n", encoding="utf-8")
    snap = tmp_path / "snap.json"
    argv = _args(
        FIX / "valid.json",
        tmp_path / "dist",
        "--snapshot",
        str(snap),
        "--forbidden-terms-file",
        str(terms),
    )
    assert main(argv) == 1
    err = capsys.readouterr().err
    assert "[Q8]" in err
    assert "alpha" not in err.lower()
    assert not snap.exists()


def test_sheets_without_terms_or_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("SHEET_ID", raising=False)
    monkeypatch.delenv("FORBIDDEN_TERMS", raising=False)
    argv = ["build", "--source", "sheets", "--out", str(tmp_path / "dist")]
    assert main(argv) == 2
    assert capsys.readouterr().err.strip() == "infrastructure error: KeyError"


def test_sheets_requires_terms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = (FIX / "valid.json").read_text(encoding="utf-8")
    monkeypatch.setenv("SHEET_ID", "secret-id")
    monkeypatch.setenv("GOOGLE_SA_JSON", "{}")
    monkeypatch.delenv("FORBIDDEN_TERMS", raising=False)
    import roadmap.cli as cli
    from roadmap.extract import load_fixture

    monkeypatch.setattr(cli, "fetch_raw", lambda *_: load_fixture(FIX / "valid.json"))
    assert raw
    argv = [
        "build",
        "--source",
        "sheets",
        "--out",
        str(tmp_path / "d"),
        "--today",
        "2027-02-01",
        "--content",
        str(FIX / "content"),
    ]
    assert main(argv) == 2
    assert capsys.readouterr().err.strip() == "FORBIDDEN_TERMS not set"


def test_unparsable_snapshot_is_ignored(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    snap = tmp_path / "snap.json"
    snap.write_text("{not json secret", encoding="utf-8")
    assert main(_args(FIX / "valid.json", tmp_path / "dist", "--snapshot", str(snap))) == 0
    err = capsys.readouterr().err
    assert "warning" in err and "secret" not in err
    assert snap.read_bytes() == (FIX / "expected_published.json").read_bytes()


def test_step_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main(_args(FIX / "valid.json", tmp_path / "dist")) == 0
    text = summary.read_text(encoding="utf-8")
    assert "| Public courses | 3 |" in text
