from __future__ import annotations

import math
from typing import Iterable

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "Viewshed/0.3 (+https://github.com/HammerheadFistpunch/Viewshed)"
DEFAULT_MATCH_RADIUS_KM = 3.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _usable_station_points(records: Iterable[dict]) -> list[tuple[str, float, float]]:
    points: list[tuple[str, float, float]] = []
    seen: set[str] = set()
    for record in records:
        call = str(record.get("callsign") or "").strip().upper()
        if not call or call in seen:
            continue
        try:
            lat = float(record["lat"])
            lon = float(record["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            continue
        seen.add(call)
        points.append((call, lat, lon))
    return points


def _overpass_query(points: list[tuple[str, float, float]], radius_m: int) -> str:
    clauses: list[str] = []
    for _call, lat, lon in points:
        around = f"(around:{radius_m},{lat:.6f},{lon:.6f})"
        clauses.extend(
            [
                f'nwr{around}["tower:type"="communication"];',
                f'nwr{around}["man_made"="communications_tower"];',
                f'nwr{around}["man_made"="antenna"];',
                f'nwr{around}["communication:radio"];',
                f'nwr{around}["communication:microwave"];',
                f'nwr{around}["communication:mobile_phone"];',
            ]
        )
    return "[out:json][timeout:30];(\n" + "\n".join(clauses) + "\n);out center tags;"


def _feature_point(element: dict) -> tuple[float, float] | None:
    lat = element.get("lat")
    lon = element.get("lon")
    if lat is None or lon is None:
        center = element.get("center") or {}
        lat = center.get("lat")
        lon = center.get("lon")
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
        return None
    return lat_f, lon_f


def _feature_label(tags: dict) -> str:
    for key in ("name", "ref", "operator"):
        value = str(tags.get(key) or "").strip()
        if value:
            return value
    man_made = str(tags.get("man_made") or "").strip()
    tower_type = str(tags.get("tower:type") or "").strip()
    if man_made:
        return man_made.replace("_", " ")
    if tower_type:
        return f"{tower_type} tower"
    return "OSM communications site"


def _strength(distance_km: float) -> str:
    if distance_km <= 0.10:
        return "STRONG"
    if distance_km <= 0.30:
        return "GOOD"
    if distance_km <= 1.0:
        return "NEARBY"
    return "WEAK"


def cross_reference_osm(
    records: Iterable[dict],
    *,
    match_radius_km: float = DEFAULT_MATCH_RADIUS_KM,
) -> dict[str, dict]:
    """Return nearest OSM communications feature for each station.

    OSM is corroborating evidence only. A nearby communications structure does
    not prove that the feature hosts the APRS station, so this function never
    changes station coordinates or reviewed overrides.
    """
    points = _usable_station_points(records)
    if not points:
        return {}

    radius_km = max(0.1, min(float(match_radius_km), 10.0))
    query = _overpass_query(points, int(round(radius_km * 1000.0)))
    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        headers={"User-Agent": USER_AGENT},
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()

    features: list[dict] = []
    seen_features: set[tuple[str, int]] = set()
    for element in payload.get("elements", []):
        try:
            feature_id = (str(element.get("type") or "?"), int(element["id"]))
        except (KeyError, TypeError, ValueError):
            continue
        if feature_id in seen_features:
            continue
        point = _feature_point(element)
        if point is None:
            continue
        seen_features.add(feature_id)
        tags = dict(element.get("tags") or {})
        features.append(
            {
                "osm_type": feature_id[0],
                "osm_id": feature_id[1],
                "lat": point[0],
                "lon": point[1],
                "tags": tags,
                "label": _feature_label(tags),
            }
        )

    matches: dict[str, dict] = {}
    for call, lat, lon in points:
        best: dict | None = None
        best_distance = float("inf")
        for feature in features:
            distance = _haversine_km(lat, lon, float(feature["lat"]), float(feature["lon"]))
            if distance < best_distance:
                best_distance = distance
                best = feature
        if best is None or best_distance > radius_km:
            matches[call] = {
                "matched": False,
                "radius_km": radius_km,
                "source": "OpenStreetMap via Overpass",
            }
            continue
        match = dict(best)
        match.update(
            {
                "matched": True,
                "distance_km": best_distance,
                "distance_m": int(round(best_distance * 1000.0)),
                "strength": _strength(best_distance),
                "radius_km": radius_km,
                "source": "OpenStreetMap via Overpass",
            }
        )
        matches[call] = match
    return matches
