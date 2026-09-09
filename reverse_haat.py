from __future__ import annotations

import math
from pathlib import Path

from dem_sources import _download_tile


FCC_INNER_KM = 3.218688
FCC_OUTER_KM = 16.09344
RADIALS = 8
SAMPLES_PER_RADIAL = 50


def _destination(lat: float, lon: float, bearing_deg: float, distance_km: float) -> tuple[float, float]:
    radius_km = 6371.0088
    angular = distance_km / radius_km
    bearing = math.radians(bearing_deg)
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(angular) + math.cos(p1) * math.sin(angular) * math.cos(bearing))
    l2 = l1 + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(p1),
        math.cos(angular) - math.sin(p1) * math.sin(p2),
    )
    return math.degrees(p2), math.degrees(l2)


def _tile_for(lat: float, lon: float) -> tuple[int, int]:
    if lon >= 0:
        raise ValueError("Reverse HAAT currently uses the CONUS/western-hemisphere 3DEP tile adapter.")
    return math.ceil(lat), math.ceil(abs(lon))


def reverse_haat(lat: float, lon: float, target_haat_m: float, dem_cache: Path) -> dict:
    """Return required antenna AGL for a target FCC-style HAAT.

    Terrain is averaged from 2 to 10 miles along eight radials spaced 45 degrees.
    """
    import rasterio

    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Invalid latitude/longitude.")

    distances = [
        FCC_INNER_KM + (FCC_OUTER_KM - FCC_INNER_KM) * i / (SAMPLES_PER_RADIAL - 1)
        for i in range(SAMPLES_PER_RADIAL)
    ]
    points = [(lat, lon)]
    for radial in range(RADIALS):
        bearing = radial * 45.0
        points.extend(_destination(lat, lon, bearing, d) for d in distances)

    dem_cache.mkdir(parents=True, exist_ok=True)
    tile_paths = {}
    for plat, plon in points:
        key = _tile_for(plat, plon)
        if key not in tile_paths:
            tile_paths[key] = _download_tile(key[0], key[1], dem_cache)

    def sample(point: tuple[float, float]) -> float:
        plat, plon = point
        path = tile_paths[_tile_for(plat, plon)]
        with rasterio.open(path) as src:
            value = float(next(src.sample([(plon, plat)]))[0])
            if src.nodata is not None and abs(value - float(src.nodata)) < 1e-6:
                raise RuntimeError(f"DEM returned nodata near {plat:.5f}, {plon:.5f}.")
            return value

    site_elev = sample((lat, lon))
    radial_means = []
    offset = 1
    for _ in range(RADIALS):
        vals = [sample(p) for p in points[offset:offset + SAMPLES_PER_RADIAL]]
        radial_means.append(sum(vals) / len(vals))
        offset += SAMPLES_PER_RADIAL

    average_terrain = sum(radial_means) / len(radial_means)
    required_amsl = target_haat_m + average_terrain
    required_agl = required_amsl - site_elev
    return {
        "site_elevation_m": site_elev,
        "average_terrain_m": average_terrain,
        "target_haat_m": target_haat_m,
        "required_antenna_amsl_m": required_amsl,
        "required_antenna_agl_m": required_agl,
        "radial_means_m": radial_means,
        "method": "8 radials, 45-degree spacing, terrain sampled 2-10 miles from site",
    }
