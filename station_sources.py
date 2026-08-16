from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Iterable

import requests

CACHE_MAX_AGE_SECONDS = 6 * 60 * 60
DEFAULT_REFRESH_SECONDS = 45
APRS_HOST = "rotate.aprs2.net"
APRS_PORT = 14580
USER_AGENT = "Viewshed/0.2 (+https://github.com/HammerheadFistpunch/Viewshed)"


def _normalize_call(value: str) -> str:
    return value.strip().upper().replace("*", "")


def _load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("stations", raw.get("results", raw.get("data", [])))
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _record_key(record: dict) -> str:
    return _normalize_call(str(record.get("callsign") or record.get("name") or ""))


def _merge_records(*groups: Iterable[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for group in groups:
        for record in group:
            call = _record_key(record)
            if not call:
                continue
            normalized = dict(record)
            normalized["callsign"] = call
            old = merged.get(call, {})
            combined = {**old, **{k: v for k, v in normalized.items() if v not in (None, "")}}

            # Provenance flags describe the coordinate currently in the record,
            # not the callsign forever. If a live/APRS.fi position supersedes a
            # seed coordinate, do not retain a stale _seed_only flag from an
            # earlier merge. This was incorrectly forcing live positions into
            # the LOW-confidence bucket.
            if (
                normalized.get("_source") in {"APRS-IS", "aprs.fi", "reviewed_override"}
                and normalized.get("lat") not in (None, "")
                and normalized.get("lon") not in (None, "")
            ):
                combined.pop("_seed_only", None)

            merged[call] = combined
    return sorted(merged.values(), key=lambda r: r["callsign"])


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _cache_fresh(cache_path: Path, center_lat: float, center_lon: float, acquisition_radius_km: float) -> bool:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        updated = float(payload.get("updated_at", 0))
        if (time.time() - updated) > CACHE_MAX_AGE_SECONDS:
            return False
        cached = payload.get("center") or {}
        cached_lat = float(cached["lat"])
        cached_lon = float(cached["lon"])
        cached_radius = float(cached["radius_km"])
        offset = _haversine_km(center_lat, center_lon, cached_lat, cached_lon)
        return offset + acquisition_radius_km <= cached_radius
    except Exception:
        return False


def _packet_roles(raw_line: str) -> tuple[set[str], set[str]]:
    digis: set[str] = set()
    igates: set[str] = set()
    try:
        header = raw_line.split(":", 1)[0]
        _, route = header.split(">", 1)
        parts = route.split(",")
    except ValueError:
        return digis, igates
    path = parts[1:]
    for i, token in enumerate(path):
        clean = _normalize_call(token)
        if token.endswith("*") and clean and not clean.startswith("QA"):
            digis.add(clean)
        if clean.startswith(("QAR", "QAO", "QAS", "QAC")) and i + 1 < len(path):
            igate = _normalize_call(path[i + 1])
            if igate:
                igates.add(igate)
    return digis, igates


def _parse_position(raw_line: str) -> tuple[str, dict] | None:
    try:
        import aprslib
        parsed = aprslib.parse(raw_line)
    except Exception:
        return None
    call = _normalize_call(str(parsed.get("from") or parsed.get("object_name") or ""))
    lat = parsed.get("latitude")
    lon = parsed.get("longitude")
    if not call or lat is None or lon is None:
        return None
    return call, {
        "callsign": call,
        "lat": float(lat),
        "lon": float(lon),
        "comment": parsed.get("comment", ""),
        "symbol": parsed.get("symbol", ""),
        "lasttime": int(time.time()),
        "_source": "APRS-IS",
    }


def observe_aprs_is(center_lat: float, center_lon: float, radius_km: float, seconds: int, callsign: str = "N0CALL") -> tuple[list[dict], set[str]]:
    seconds = max(0, min(int(seconds), 300))
    if seconds == 0:
        return [], set()
    callsign = _normalize_call(callsign) or "N0CALL"
    filter_text = f"r/{center_lat:.5f}/{center_lon:.5f}/{max(1, int(radius_km))}"
    login = f"user {callsign} pass -1 vers Viewshed 0.2 filter {filter_text}\r\n"
    positions: dict[str, dict] = {}
    digis: set[str] = set()
    igates: set[str] = set()
    deadline = time.monotonic() + seconds
    with socket.create_connection((APRS_HOST, APRS_PORT), timeout=15) as sock:
        sock.settimeout(2)
        sock.sendall(login.encode("ascii", errors="ignore"))
        buffer = ""
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                d, i = _packet_roles(line)
                digis.update(d)
                igates.update(i)
                parsed = _parse_position(line)
                if parsed:
                    call, rec = parsed
                    positions[call] = rec
                    if rec.get("symbol") == "#":
                        digis.add(call)
    records: list[dict] = []
    roles = digis | igates
    for call in sorted(roles):
        rec = positions.get(call)
        if not rec:
            continue
        rec = dict(rec)
        rec["type"] = "digi" if call in digis else "igate"
        records.append(rec)
    return records, roles


def lookup_aprs_fi(callsigns: Iterable[str], api_key: str) -> list[dict]:
    calls = sorted({_normalize_call(c) for c in callsigns if _normalize_call(c)})
    if not calls or not api_key:
        return []
    records: list[dict] = []
    for start in range(0, len(calls), 20):
        batch = calls[start:start + 20]
        response = requests.get(
            "https://api.aprs.fi/api/get",
            params={"name": ",".join(batch), "what": "loc", "apikey": api_key, "format": "json"},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("result") != "ok":
            raise RuntimeError(payload.get("description", "aprs.fi request failed"))
        for entry in payload.get("entries", []):
            try:
                call = _normalize_call(str(entry["name"]))
                lat = float(entry["lat"])
                lon = float(entry["lng"])
            except (KeyError, TypeError, ValueError):
                continue
            records.append({
                "callsign": call,
                "lat": lat,
                "lon": lon,
                "comment": entry.get("comment", ""),
                "symbol": entry.get("symbol", ""),
                "lasttime": int(entry.get("lasttime") or entry.get("time") or 0),
                "_source": "aprs.fi",
            })
    return records


def acquire_station_cache(seed_path: Path, data_root: Path, center_lat: float, center_lon: float, acquisition_radius_km: float, refresh: bool = True, refresh_seconds: int = DEFAULT_REFRESH_SECONDS, callsign: str = "", aprs_fi_api_key: str = "") -> Path:
    cache_dir = data_root / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "stations.json"
    seed_records = _load_records(seed_path)
    cached_records = _load_records(cache_path)
    if not refresh or _cache_fresh(cache_path, center_lat, center_lon, acquisition_radius_km):
        if cache_path.exists():
            print("Station cache is fresh for this area; skipping live refresh.")
            return cache_path
        payload = {"updated_at": time.time(), "stations": _merge_records(seed_records)}
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return cache_path

    print(f"Refreshing station cache from APRS-IS for {refresh_seconds}s within {acquisition_radius_km:.0f} km...")
    live_records: list[dict] = []
    discovered_calls: set[str] = set()
    try:
        live_records, discovered_calls = observe_aprs_is(
            center_lat, center_lon, acquisition_radius_km, refresh_seconds,
            callsign=callsign or os.environ.get("VIEWSHED_APRS_CALLSIGN", "N0CALL"),
        )
        print(f"APRS-IS: {len(discovered_calls)} infrastructure calls observed; {len(live_records)} had positions.")
    except Exception as exc:
        print(f"APRS-IS refresh unavailable: {exc}. Using cached/seed station data.")

    key = aprs_fi_api_key or os.environ.get("VIEWSHED_APRSFI_API_KEY", "")
    fi_records: list[dict] = []
    unresolved = discovered_calls - {_record_key(r) for r in live_records}
    if key and unresolved:
        try:
            fi_records = lookup_aprs_fi(unresolved, key)
            print(f"aprs.fi: resolved {len(fi_records)} additional station position(s).")
        except Exception as exc:
            print(f"aprs.fi lookup unavailable: {exc}. Continuing with APRS-IS/cache data.")

    role_map: dict[str, str] = {}
    for record in seed_records + cached_records + live_records:
        call = _record_key(record)
        if call and record.get("type") in {"digi", "igate"}:
            role_map[call] = record["type"]
    for record in fi_records:
        call = _record_key(record)
        if call in role_map:
            record["type"] = role_map[call]

    merged = _merge_records(seed_records, cached_records, live_records, fi_records)
    usable = [r for r in merged if r.get("type") in {"digi", "igate"} and "lat" in r and "lon" in r]
    payload = {
        "updated_at": time.time(),
        "center": {"lat": center_lat, "lon": center_lon, "radius_km": acquisition_radius_km},
        "stations": usable,
    }
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Station cache: {len(usable)} usable digipeater/iGate records.")
    return cache_path