from __future__ import annotations

import json
import math
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from analysis_dem import prepare_analysis_dem
from dem_sources import prepare_dem as prepare_usgs_dem
from location_quality import assess_and_correct_locations, summarize_location_quality
from osm_crossref import cross_reference_osm
from rendering import install_rendering_fix
from station_sources import acquire_station_cache

APP_VERSION = "2.1.0"
USER_OVERRIDE_ENV = "VIEWSHED_LOCATION_OVERRIDE_PATH"


@dataclass(frozen=True)
class Region:
    center_lat: float
    center_lon: float
    radius_km: float

    def validate(self) -> None:
        if not -90.0 <= self.center_lat <= 90.0:
            raise ValueError("Latitude must be between -90 and 90 degrees.")
        if not -180.0 <= self.center_lon <= 180.0:
            raise ValueError("Longitude must be between -180 and 180 degrees.")
        if not 1.0 <= self.radius_km <= 1000.0:
            raise ValueError("Radius must be between 1 and 1000 km.")


@dataclass
class JobConfig:
    region: Region
    station_source: str
    include_types: list[str]
    propagation_radius_km: float
    job_dir: str
    filtered_stations: str
    mode: str = "area"
    frozen_stations: bool = False
    radio_settings: dict = field(default_factory=dict)

    def to_json(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: Path) -> "JobConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["region"] = Region(**raw["region"])
        raw.setdefault("mode", "area")
        raw.setdefault("frozen_stations", False)
        raw.setdefault("radio_settings", {})
        return cls(**raw)


def resource_path(relative: str) -> Path:
    """Return a bundled resource path for source and PyInstaller builds."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def portable_data_root() -> Path:
    """Return the writable Signal Peak data directory."""
    if getattr(sys, "frozen", False):
        preferred = Path(sys.executable).resolve().parent / "ViewshedData"
    else:
        preferred = Path(__file__).resolve().parent / "ViewshedData"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return preferred
    except Exception:
        fallback = Path.home() / "ViewshedData"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _location_registry_path() -> Path:
    return resource_path("station_location_overrides.json")


def assess_station_locations(records: Iterable[dict]) -> list[dict]:
    return assess_and_correct_locations(records, _location_registry_path())


def load_station_records(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        for key in ("stations", "records", "data"):
            value = raw.get(key)
            if isinstance(value, list):
                raw = value
                break
    if not isinstance(raw, list):
        raise ValueError("Station source must contain a JSON list of records.")
    return [dict(item) for item in raw if isinstance(item, dict)]


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def filter_stations(records: Iterable[dict], region: Region, include_types: set[str], propagation_radius_km: float) -> list[dict]:
    selected = []
    for record in records:
        try:
            if record.get("type") not in include_types:
                continue
            lat = float(record["lat"])
            lon = float(record["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if _distance_km(region.center_lat, region.center_lon, lat, lon) <= region.radius_km + propagation_radius_km:
            selected.append(record)
    return selected


def prepare_job(
    region: Region,
    station_source: Path,
    include_types: set[str],
    propagation_radius_km: float,
    *,
    mode: str = "area",
    selected_records: Iterable[dict] | None = None,
    radio_settings: dict | None = None,
    frozen_stations: bool = False,
) -> tuple[Path, Path]:
    region.validate()
    if not 1 <= float(propagation_radius_km) <= 1000:
        raise ValueError("Propagation radius must be between 1 and 1000 km.")

    root = portable_data_root()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    job_dir = root / "jobs" / stamp
    suffix = 1
    while job_dir.exists():
        job_dir = root / "jobs" / f"{stamp}-{suffix}"
        suffix += 1
    job_dir.mkdir(parents=True, exist_ok=False)

    if selected_records is None:
        records = assess_station_locations(load_station_records(station_source))
        selected = filter_stations(records, region, include_types, propagation_radius_km)
    else:
        selected = assess_station_locations(selected_records)

    filtered_path = job_dir / "filtered_stations.json"
    filtered_path.write_text(json.dumps(selected, indent=2), encoding="utf-8")

    config = JobConfig(
        region=region,
        station_source=str(station_source),
        include_types=sorted(include_types),
        propagation_radius_km=float(propagation_radius_km),
        job_dir=str(job_dir),
        filtered_stations=str(filtered_path),
        mode=mode,
        frozen_stations=bool(frozen_stations),
        radio_settings=dict(radio_settings or {}),
    )
    job_file = job_dir / "job.json"
    config.to_json(job_file)
    return job_dir, job_file


def copy_outputs_to_job(work_dir: Path, job_dir: Path) -> Path:
    out_dir = job_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.kmz", "*.tif", "*.png", "*.json", "*.csv"):
        for path in work_dir.glob(pattern):
            if path.is_file():
                shutil.copy2(path, out_dir / path.name)
    return out_dir


install_rendering_fix()
