from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

RF_FIELDS = (
    "antenna_height_m",
    "tx_power_w",
    "tx_antenna_gain_dbd",
    "freq_mhz",
    "max_path_loss_db",
)


def registry_path(data_root: Path) -> Path:
    return Path(data_root) / "station_rf_overrides.json"


def load_registry(data_root: Path) -> dict[str, dict]:
    path = registry_path(data_root)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(raw, dict) and isinstance(raw.get("overrides"), dict):
        raw = raw["overrides"]
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, dict] = {}
    for call, values in raw.items():
        if not isinstance(values, dict):
            continue
        key = str(call).strip().upper()
        if not key:
            continue
        entry = {field: values[field] for field in RF_FIELDS if field in values and values[field] not in (None, "")}
        if entry:
            cleaned[key] = entry
    return cleaned


def save_registry(data_root: Path, overrides: dict[str, dict]) -> Path:
    path = registry_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned: dict[str, dict] = {}
    for call, values in overrides.items():
        key = str(call).strip().upper()
        if not key or not isinstance(values, dict):
            continue
        entry = {field: values[field] for field in RF_FIELDS if field in values and values[field] not in (None, "")}
        if entry:
            cleaned[key] = entry
    path.write_text(json.dumps({"version": 1, "overrides": cleaned}, indent=2, sort_keys=True), encoding="utf-8")
    return path


def apply_registry(records: Iterable[dict], overrides: dict[str, dict]) -> list[dict]:
    applied: list[dict] = []
    for source in records:
        record = dict(source)

        # Undo a previous in-memory registry overlay before applying the current
        # registry. This lets a user clear an override and return to a value that
        # came from the source station JSON, rather than losing that source value.
        prior_fields = list(record.pop("_user_rf_override_fields", []) or [])
        prior_base = dict(record.pop("_user_rf_base", {}) or {})
        for field in prior_fields:
            if field in prior_base:
                record[field] = prior_base[field]
            else:
                record.pop(field, None)

        call = str(record.get("callsign") or record.get("name") or "").strip().upper()
        values = overrides.get(call, {}) if call else {}
        if values:
            base: dict[str, object] = {}
            fields: list[str] = []
            for field in RF_FIELDS:
                if field not in values:
                    continue
                if field in record:
                    base[field] = record[field]
                record[field] = values[field]
                fields.append(field)
            record["_user_rf_override_fields"] = fields
            record["_user_rf_base"] = base
        applied.append(record)
    return applied
