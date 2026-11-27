"""Extract the allowed ranges from the Google Sheet (ADR-04: minimization at the source)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient import discovery

from roadmap.models import RawSheets

RANGES: dict[str, str] = {
    "publico": "Publico!A1:O",
    "cronograma_totals": "Cronograma!A1:B3",
    "cronograma_left": "Cronograma!A4:C",
    "cronograma_right": "Cronograma!E4:F",
    "modules": "'Spark & Databricks'!A1:D",
}
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def load_sa_from_env(var: str = "GOOGLE_SA_JSON") -> dict[str, Any]:
    """Load the service account info from an environment variable (never logs its content)."""
    raw = os.environ.get(var)
    if not raw:
        raise RuntimeError(f"{var} not set")
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"{var} is not valid JSON") from None
    if not isinstance(info, dict):
        raise RuntimeError(f"{var} is not valid JSON")
    return info


def fetch_raw(sheet_id: str, sa_info: dict[str, Any]) -> RawSheets:
    """Read all allowed ranges with a single ``batchGet`` call."""
    credentials = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    service = discovery.build("sheets", "v4", credentials=credentials, cache_discovery=False)
    response = (
        service.spreadsheets()
        .values()
        .batchGet(
            spreadsheetId=sheet_id,
            ranges=list(RANGES.values()),
            valueRenderOption="FORMATTED_VALUE",
        )
        .execute()
    )
    value_ranges = response.get("valueRanges", [])
    data: dict[str, list[list[str]]] = {}
    for key, value_range in zip(RANGES, value_ranges, strict=True):
        rows = value_range.get("values", [])
        data[key] = [[str(cell) for cell in row] for row in rows]
    return RawSheets.model_validate(data)


def load_fixture(path: Path) -> RawSheets:
    """Load a ``RawSheets`` from a UTF-8 JSON fixture."""
    return RawSheets.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
