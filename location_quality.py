from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Iterable


SOURCE_BASE_SCORES = {
    "APRS-IS": 90,
    "aprs.fi": 85,
    "reviewed_override": 100,
    "seed": 65,
    "cache": 70,
    "unknown": 55,
}

USER_OVERRIDE_ENV = "VIEWSHED_LOCATION_OVERRIDE_PATH"


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


def _effective_registry(registry_path: Path) -> dict[str, dict]:
    """Merge packaged defaults with a user-writable registry when configured.

    The packaged registry is loaded first. A path supplied through
    VIEWSHED_LOCATION_OVERRIDE_PATH is loaded second and wins on callsign
    collisions. This lets reviewed UI corrections survive executable upgrades.
    """
    merged = load_location_registry(registry_path)
    user_path = str(os.environ.get(USER_OVERRIDE_ENV) or "").strip()
    if user_path:
        try:
            candidate = Path(user_path).expanduser()
            if candidate.resolve() != registry_path.resolve():
                merged.update(load_location_registry(candidate))
        except Exception:
            pass
    return merged


def _source_name(record: dict) -> str:
    source = str(record.get("_source") or "").strip()
    if source in SOURCE_BASE_SCORES:
        return source
    if record.get("_seed_only"):
        return "seed"
    return "unknown"


def _position_freshness(record: dict, now: float) -> dict:
    """Describe observation freshness without treating it as coordinate accuracy."""
    lasttime = record.get("lasttime") or record.get("last seen")
    try:
        timestamp = float(lasttime)
        if timestamp <= 0:
            raise ValueError
        age_days = max(0.0, (now - timestamp) / 86400.0)
    except (TypeError, ValueError):
        return {
            "label": "UNKNOWN",
            "age_days": None,
            "reason": "no usable position timestamp",
        }

    if age_days <= 7:
        label = "RECENT"
        reason = f"position seen within {age_days:.1f} days"
    elif age_days <= 90:
        label = "AGING"
        reason = f"position last seen {age_days:.0f} days ago"
    elif age_days <= 365:
        label = "STALE"
        reason = f"position last seen {age_days:.0f} days ago"
    else:
        label = "VERY_STALE"
        reason = f"position last seen {age_days:.0f} days ago"
    return {"label": label, "age_days": age_days, "reason": reason}


def _score_record(record: dict, registry_entry: dict | None) -> tuple[int, list[str]]:
    """Score coordinate provenance, not station observation freshness.

    A missing or old timestamp says whether we know the station was observed
    recently; by itself it does not say the reported latitude/longitude is wrong.
    Freshness is tracked separately in _location_confidence["freshness"].
    """
    source = _source_name(record)
    score = SOURCE_BASE_SCORES.get(source, SOURCE_BASE_SCORES["unknown"])
    reasons = [f"coordinate source={source}"]

    if record.get("_seed_only"):
        score = min(score, 65)
        reasons.append("seed-only coordinate; not confirmed by current live sample")

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
    """Attach coordinate confidence/freshness and apply reviewed overrides only.

    Raw/reporting coordinates are always preserved as _reported_lat/_reported_lon.
    Candidate corrections never change coordinates; they only lower coordinate
    confidence and add review metadata. Observation freshness is recorded
    separately and never moves a station into the correction queue by itself.
    """
    registry = _effective_registry(registry_path)
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
        score, reasons = _score_record(record, entry)
        freshness = _position_freshness(record, now)

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
            "freshness": freshness,
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
