"""Tests for roadmap.extract (no network, no real credentials)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from roadmap import extract
from roadmap.models import RawSheets

FIXTURE = Path(__file__).parent / "fixtures" / "valid.json"


def _mock_service(value_ranges: list[dict]) -> MagicMock:
    service = MagicMock()
    batch_get = service.spreadsheets.return_value.values.return_value.batchGet
    batch_get.return_value.execute.return_value = {"valueRanges": value_ranges}
    return service


def test_fetch_raw_requests_exact_ranges_and_maps_values() -> None:
    value_ranges = [
        {"values": [["a", 1]]},
        {},
        {"values": [[2.5]]},
        {"values": []},
        {"values": [["x", "y", "z"]]},
    ]
    service = _mock_service(value_ranges)
    with (
        patch("roadmap.extract.service_account.Credentials.from_service_account_info") as creds,
        patch("roadmap.extract.discovery.build", return_value=service) as build,
    ):
        raw = extract.fetch_raw("sheet-id", {"k": "v"})

    creds.assert_called_once_with({"k": "v"}, scopes=extract.SCOPES)
    assert build.call_args.args == ("sheets", "v4")
    assert build.call_args.kwargs["cache_discovery"] is False
    batch_get = service.spreadsheets.return_value.values.return_value.batchGet
    batch_get.assert_called_once_with(
        spreadsheetId="sheet-id",
        ranges=[
            "Publico!A1:O",
            "Cronograma!A1:B3",
            "Cronograma!A4:C",
            "Cronograma!E4:F",
            "'Spark & Databricks'!A1:D",
        ],
        valueRenderOption="FORMATTED_VALUE",
    )
    assert raw.publico == [["a", "1"]]
    assert raw.cronograma_totals == []
    assert raw.cronograma_left == [["2.5"]]
    assert raw.cronograma_right == []
    assert raw.modules == [["x", "y", "z"]]


def test_forbidden_columns_not_requested() -> None:
    for name, rng in extract.RANGES.items():
        if rng.startswith("Cronograma"):
            assert "!D" not in rng, name
        if "Spark" in rng:
            assert rng.endswith("D"), name
            assert "E" not in rng.split("!")[1], name
    assert extract.SCOPES == ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def test_load_fixture() -> None:
    raw = extract.load_fixture(FIXTURE)
    assert isinstance(raw, RawSheets)
    assert raw.publico


def test_load_sa_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_SA_JSON", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_SA_JSON not set"):
        extract.load_sa_from_env()
    monkeypatch.setenv("GOOGLE_SA_JSON", "{secret-not-json")
    with pytest.raises(RuntimeError, match="not valid JSON") as exc:
        extract.load_sa_from_env()
    assert "secret" not in str(exc.value)
    monkeypatch.setenv("GOOGLE_SA_JSON", '{"a": 1}')
    assert extract.load_sa_from_env() == {"a": 1}
