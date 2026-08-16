from __future__ import annotations

import json
import math
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

APP_VERSION = "0.1.0"


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

    def to_json(self, path: Path) -> None:
        payload = asdict(self)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: Path) -> "JobConfig":
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["region"] = Region(**raw["region"])
        return cls(**raw)


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def portable_data_root() -> Path:
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
    except OSError:
        fallback = Path.home() / "ViewshedData"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def load_station_records(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        for key in ("stations", "results", "data"):
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break
    if not isinstance(raw, list):
        raise ValueError("Station source must contain a JSON list of station records.")
    return [item for item in raw if isinstance(item, dict)]


def filter_stations(
    stations: Iterable[dict],
    region: Region,
    include_types: set[str],
    propagation_radius_km: float,
) -> list[dict]:
    # Stations outside the requested output circle can still illuminate it.
    acquisition_radius = region.radius_km + propagation_radius_km
    selected: list[dict] = []
    for station in stations:
        if station.get("type") not in include_types:
            continue
        try:
            lat = float(station["lat"])
            lon = float(station["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if haversine_km(region.center_lat, region.center_lon, lat, lon) <= acquisition_radius:
            selected.append(station)
    return selected


def prepare_job(
    region: Region,
    station_source: Path,
    include_types: set[str],
    propagation_radius_km: float,
) -> tuple[JobConfig, Path]:
    region.validate()
    if not station_source.exists():
        raise FileNotFoundError(f"Station source not found: {station_source}")
    if not include_types:
        raise ValueError("Select at least one station type.")
    if not 1.0 <= propagation_radius_km <= 500.0:
        raise ValueError("Propagation radius must be between 1 and 500 km.")

    stations = load_station_records(station_source)
    selected = filter_stations(stations, region, include_types, propagation_radius_km)
    if not selected:
        raise ValueError(
            "No stations were found for this area. The bundled v0.1 station source is Utah-focused; "
            "choose an area covered by that dataset or browse to another compatible station JSON file."
        )

    stamp = time.strftime("%Y%m%d-%H%M%S")
    job_dir = portable_data_root() / "jobs" / stamp
    output_dir = job_dir / "output"
    work_dir = output_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    filtered = job_dir / "stations.json"
    filtered.write_text(json.dumps(selected, indent=2), encoding="utf-8")

    cfg = JobConfig(
        region=region,
        station_source=str(station_source),
        include_types=sorted(include_types),
        propagation_radius_km=propagation_radius_km,
        job_dir=str(job_dir),
        filtered_stations=str(filtered),
    )
    job_file = job_dir / "job.json"
    cfg.to_json(job_file)
    return cfg, job_file


def run_legacy_worker(job_file: Path) -> Path:
    """Run the proven legacy computation pipeline without its interactive console wrapper."""
    job = JobConfig.from_json(job_file)
    job_dir = Path(job.job_dir)
    output_dir = job_dir / "output"
    work_dir = output_dir / "work"
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    import aprs_viewshed_utah_parallel as engine

    cfg = dict(engine.CONFIG)
    cfg.update(
        {
            "stations_json": job.filtered_stations,
            "output_kmz": "viewshed.kmz",
            "include_types": job.include_types,
            "max_radius_km": float(job.propagation_radius_km),
            "work_dir": str(work_dir),
            "dem_cache_dir": str(portable_data_root() / "cache" / "dem"),
            "clear_viewshed_cache": False,
        }
    )

    print(f"Viewshed {APP_VERSION}")
    print(f"Job: {job_dir}")
    print(
        f"Area: {job.region.center_lat:.5f}, {job.region.center_lon:.5f} "
        f"radius {job.region.radius_km:.1f} km"
    )

    stations, colocation_map = engine.load_stations(job.filtered_stations, cfg)
    if not stations:
        raise RuntimeError("No valid stations remained after validation.")
    print(f"Using {len(stations)} station(s).")

    dem_path = engine.prepare_dem(stations, cfg, work_dir)
    results = engine.compute_viewsheds(stations, dem_path, cfg, work_dir, colocation_map=colocation_map)
    if not results:
        raise RuntimeError("The propagation engine produced no station viewsheds.")

    coverage_path, station_tifs = engine.merge_viewsheds(results, dem_path, work_dir, cfg)
    png_path, bbox = engine.raster_to_png_overlay(coverage_path, work_dir, cfg)
    kmz_path = engine.build_kmz(
        stations,
        png_path,
        bbox,
        cfg,
        work_dir,
        station_tifs=station_tifs,
        prebuilt_pngs=None,
    )

    final_tif = output_dir / "coverage_count.tif"
    shutil.copy2(coverage_path, final_tif)
    print(f"KMZ: {kmz_path}")
    print(f"GeoTIFF: {final_tif}")
    return output_dir


def self_test() -> str:
    source = resource_path("utah_stations_scraped.json")
    stations = load_station_records(source)
    region = Region(40.7608, -111.8910, 100.0)
    selected = filter_stations(stations, region, {"digi", "igate"}, 180.0)
    if not selected:
        raise RuntimeError("Bundled station data could not be loaded or filtered.")
    return f"Viewshed {APP_VERSION}: core OK, {len(stations)} bundled stations, {len(selected)} selected in smoke region"
