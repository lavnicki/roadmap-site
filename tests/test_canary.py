"""End-to-end canaries: text planted in every non-public place must never reach the output.

Canaries go into hidden Publico rows (every text column), unmapped Cronograma courses and the
module tab's Tema column (read, but never published). The whole build runs through ``main``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from roadmap.cli import main

FIX = Path("tests/fixtures")
CANARY = "ZQXCANARY"
TEXT_COLUMNS = (4, 5, 6, 7, 8, 9, 10, 11)  # nome_en .. stack in the Publico header


def _planted_fixture(tmp_path: Path) -> Path:
    data = json.loads((FIX / "valid.json").read_text(encoding="utf-8"))
    for n, row in enumerate(data["publico"][1:], start=1):
        if row[2] != "sim" or row[1] in ("hidden-proj", "gamma"):
            for col in TEXT_COLUMNS:
                if col in (9, 10) and not row[col]:
                    continue  # leave empty URLs empty so the row stays valid
                if col in (9, 10):
                    row[col] = f"https://example.com/{CANARY}{n}"
                elif col == 6:
                    continue  # competencias must keep referencing real ids
                else:
                    row[col] = f"{row[col]} {CANARY}{n}".strip()
    # Unmapped course names in the Cronograma (like DevSpeak or interview prep).
    for row in data["cronograma_left"][1:]:
        if row[2] == "Interno X":
            row[2] = f"Interno {CANARY}"
    # The Tema column is extracted but must never be published.
    for row in data["modules"][1:]:
        row[1] = f"{row[1]} {CANARY}"
    path = tmp_path / "planted.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _build(tmp_path: Path, fixture: Path, *extra: str) -> tuple[int, Path, Path]:
    out, snap = tmp_path / "dist", tmp_path / "published.json"
    code = main(
        [
            "build", "--source", "fixture", "--fixture", str(fixture),
            "--config", str(FIX / "site.yaml"), "--guardrails", str(FIX / "guardrails.yaml"),
            "--content", str(FIX / "content"), "--today", "2027-02-01",
            "--out", str(out), "--snapshot", str(snap), *extra,
        ]
    )
    return code, out, snap


def test_canaries_never_reach_site_or_snapshot(tmp_path: Path) -> None:
    code, out, snap = _build(tmp_path, _planted_fixture(tmp_path))
    assert code == 0
    published = [p for p in out.rglob("*") if p.is_file()] + [snap]
    assert len(published) >= 4
    for path in published:
        assert CANARY.lower() not in path.read_text(encoding="utf-8").lower(), path


@pytest.mark.parametrize(
    ("needle", "why"),
    [
        ("Observação: pular", "private vocabulary"),
        ("CPF " + "123.456" + ".789-09", "secret-like pattern 'cpf'"),  # built from parts
    ],
)
def test_sensitive_text_in_a_public_field_blocks_the_build(
    tmp_path: Path, needle: str, why: str, capsys: pytest.CaptureFixture[str]
) -> None:
    data = json.loads((FIX / "valid.json").read_text(encoding="utf-8"))
    data["publico"][1][5] = f"{data['publico'][1][5]} {needle}"  # public competency
    fixture = tmp_path / "bad.json"
    fixture.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    code, out, snap = _build(tmp_path, fixture)
    err = capsys.readouterr().err
    assert code == 1
    assert why in err
    assert needle.split()[-1] not in err  # the match itself is never logged
    assert not out.exists() and not snap.exists()


def test_runtime_literal_blocks_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret_id = "1SheetIdThatMustNeverLeak0123456789"
    monkeypatch.setenv("SHEET_ID", secret_id)
    data = json.loads((FIX / "valid.json").read_text(encoding="utf-8"))
    data["publico"][1][5] = f"see {secret_id}"
    fixture = tmp_path / "bad.json"
    fixture.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    code, out, _ = _build(tmp_path, fixture)
    err = capsys.readouterr().err
    assert code == 1 and "sensitive literal" in err and secret_id not in err
    assert not out.exists()


def test_non_allowed_link_blocks_the_build(tmp_path: Path) -> None:
    data = json.loads((FIX / "valid.json").read_text(encoding="utf-8"))
    for row in data["publico"]:
        if row[1] == "public-proj":
            row[9] = "https://tracker.example.net/public-proj"
    fixture = tmp_path / "bad.json"
    fixture.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    code, out, _ = _build(tmp_path, fixture)
    assert code == 1 and not out.exists()
