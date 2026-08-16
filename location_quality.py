from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable


SOURCE_BASE_SCORES = {
    "APRS-IS": 90,
    "aprs.fi": 85,
    "reviewed_override": 100,
    "seed": 60,
    "cache": 65,
    "unknown": 55,
}


def _normalize_call(value: object) -> str:
    return str(value or "").strip().upper().replace("*", "")


def load_location_registry(path: Path) -> dict[str, dict]:
    """Load reviewed/candidate station-coordinate records keyed by callsign."""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    entries = raw.get("overrides", raw) if isinstance(raw, dict) else {}
    if not isinstance(entries, dict):
        return {}
    return {_normalize_call(k): dict(v) for k, v in entries.items() if isinstance(v, dict)}


def _source_name(record: dict) -> str:
    source = str(record.get("_source") or "").strip()
    if source in SOURCE_BASE_SCORES:
        return source
    if record.get("_seed_only"):
        return "seed"
    return "unknown"


def _score_record(record: dict, registry_entry: dict | None, now: float) -> tuple[int, list[str]]:
    source = _source_name(record)
    score = SOURCE_BASE_SCORES.get(source, SOURCE_BASE_SCORES["unknown"])
    reasons = [f"source={source}"]

    lasttime = record.get("lasttime") or record.get("last seen")
    try:
        age_days = max(0.0, (now - float(lasttime)) / 86400.0)
    except (TypeError, ValueError):
        age_days = None

    if age_days is None or float(lasttime or 0) <= 0:
        score -= 10
        reasons.append("no usable position timestamp")
    elif age_days > 365:
        score -= 15
        reasons.append(f"position older than 1 year ({age_days:.0f} d)")
    elif age_days > 90:
        score -= 7
        reasons.append(f"position older than 90 days ({age_days:.0f} d)")
    elif age_days <= 7:
        score += 3
        reasons.append("position seen within 7 days")

    if record.get("_seed_only"):
        score = min(score, 50)
        reasons.append("seed-only coordinate; not confirmed live")

    if registry_entry:
        status = str(registry_entry.get("status") or "candidate").lower()
        if status == "reviewed":
            score = 100
            reasons.append("reviewed coordinate override")
        else:
            score = min(score, 49)
            reasons.append("coordinate correction candidate requires review")

    return max(0, min(100, int(round(score)))), reasons


def _label(score: int) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 55:
        return "MEDIUM"
    return "LOW"


def assess_and_correct_locations(records: Iterable[dict], registry_path: Path) -> list[dict]:
    """Attach confidence metadata and apply only explicitly reviewed overrides.

    Raw/reporting coordinates are always preserved as _reported_lat/_reported_lon.
    Candidate corrections never change coordinates; they only lower confidence and
    add review metadata.  This keeps data-quality decisions outside propagation math.
    """
    registry = load_location_registry(registry_path)
    now = time.time()
    assessed: list[dict] = []

    for original in records:
        record = dict(original)
        call = _normalize_call(record.get("callsign") or record.get("name"))
        if call:
            record["callsign"] = call

        try:
            reported_lat = float(record["lat"])
            reported_lon = float(record["lon"])
            record.setdefault("_reported_lat", reported_lat)
            record.setdefault("_reported_lon", reported_lon)
        except (KeyError, TypeError, ValueError):
            assessed.append(record)
            continue

        entry = registry.get(call)
        score, reasons = _score_record(record, entry, now)

        if entry:
            status = str(entry.get("status") or "candidate").lower()
            audit = {
                "status": status,
                "reason": entry.get("reason", ""),
                "source": entry.get("source", ""),
                "source_url": entry.get("source_url", ""),
            }
            try:
                audit["candidate_lat"] = float(entry["lat"])
                audit["candidate_lon"] = float(entry["lon"])
            except (KeyError, TypeError, ValueError):
                pass

            if status == "reviewed" and "candidate_lat" in audit:
                record["lat"] = audit["candidate_lat"]
                record["lon"] = audit["candidate_lon"]
                record["_location_correction"] = audit
                record["_location_source"] = "reviewed_override"
            else:
                record["_location_review_candidate"] = audit

        record["_location_confidence"] = {
            "score": score,
            "label": _label(score),
            "reasons": reasons,
            "reported_source": _source_name(record),
        }
        assessed.append(record)

    return assessed


def summarize_location_quality(records: Iterable[dict]) -> dict[str, int]:
    summary = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "CORRECTED": 0, "REVIEW": 0}
    for record in records:
        meta = record.get("_location_confidence") or {}
        label = str(meta.get("label") or "").upper()
        if label in summary:
            summary[label] += 1
        if record.get("_location_correction"):
            summary["CORRECTED"] += 1
        if record.get("_location_review_candidate"):
            summary["REVIEW"] += 1
    return summary
