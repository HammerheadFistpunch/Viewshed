from __future__ import annotations

import math
from contextlib import ExitStack
from pathlib import Path

from dem_sources import _download_tile


FCC_INNER_KM = 3.218688
FCC_OUTER_KM = 16.09344
RADIALS = 8
SAMPLES_PER_RADIAL = 50
MIN_VALID_SAMPLES_PER_RADIAL = 35
NEARBY_VALID_RADIUS_PX = 6


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
    # dem_sources._download_tile() converts its latitude argument N to a file
    # named n(N-1). The current USGS files named nXX span approximately
    # (XX-1)..XX degrees north (for example n38 spans ~37..38 N). Therefore a
    # point at 38.07 N needs n39, which requires passing 40 to _download_tile.
    # The extra +1 below corrects that adapter convention for point sampling.
    return math.ceil(lat) + 1, math.ceil(abs(lon))


def _is_valid_value(src, value: float) -> bool:
    if not math.isfinite(value):
        return False
    if src.nodata is not None and abs(value - float(src.nodata)) < 1e-6:
        return False
    return True


def _dataset_xy(src, lon: float, lat: float) -> tuple[float, float]:
    """Transform WGS84 lon/lat into the raster's native CRS."""
    from rasterio.crs import CRS
    from rasterio.warp import transform

    if not src.crs:
        return lon, lat

    wgs84 = CRS.from_epsg(4326)
    if src.crs == wgs84:
        return lon, lat

    xs, ys = transform(wgs84, src.crs, [lon], [lat])
    return float(xs[0]), float(ys[0])


def _sample_with_nearby_fallback(src, lon: float, lat: float, radius_px: int = NEARBY_VALID_RADIUS_PX) -> float | None:
    """Sample one WGS84 terrain point, falling back to the nearest valid DEM pixel."""
    try:
        x, y = _dataset_xy(src, lon, lat)
        left, bottom, right, top = src.bounds
        if not (left <= x <= right and bottom <= y <= top):
            return None
        row, col = src.index(x, y)
    except Exception:
        return None
    if row < 0 or col < 0 or row >= src.height or col >= src.width:
        return None

    value = float(src.read(1, window=((row, row + 1), (col, col + 1)))[0, 0])
    if _is_valid_value(src, value):
        return value

    for radius in range(1, radius_px + 1):
        r0 = max(0, row - radius)
        r1 = min(src.height, row + radius + 1)
        c0 = max(0, col - radius)
        c1 = min(src.width, col + radius + 1)
        block = src.read(1, window=((r0, r1), (c0, c1)), masked=False)
        candidates: list[tuple[int, float]] = []
        for rr in range(block.shape[0]):
            for cc in range(block.shape[1]):
                v = float(block[rr, cc])
                if not _is_valid_value(src, v):
                    continue
                dr = (r0 + rr) - row
                dc = (c0 + cc) - col
                candidates.append((dr * dr + dc * dc, v))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            return candidates[0][1]
    return None


def reverse_haat(lat: float, lon: float, target_haat_m: float, dem_cache: Path) -> dict:
    """Return required antenna AGL for a target FCC-style HAAT.

    Terrain is averaged from 2 to 10 miles along eight radials spaced 45 degrees.
    Isolated DEM nodata pixels are skipped or replaced by a nearby valid pixel;
    a radial must still retain at least 70 percent of its nominal samples.
    """
    import rasterio

    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Invalid latitude/longitude.")

    distances = [
        FCC_INNER_KM + (FCC_OUTER_KM - FCC_INNER_KM) * i / (SAMPLES_PER_RADIAL - 1)
        for i in range(SAMPLES_PER_RADIAL)
    ]
    radial_points: list[list[tuple[float, float]]] = []
    all_points = [(lat, lon)]
    for radial in range(RADIALS):
        bearing = radial * 45.0
        pts = [_destination(lat, lon, bearing, d) for d in distances]
        radial_points.append(pts)
        all_points.extend(pts)

    dem_cache.mkdir(parents=True, exist_ok=True)
    tile_paths: dict[tuple[int, int], Path] = {}
    for plat, plon in all_points:
        key = _tile_for(plat, plon)
        if key not in tile_paths:
            tile_paths[key] = _download_tile(key[0], key[1], dem_cache)

    with ExitStack() as stack:
        datasets = {
            key: stack.enter_context(rasterio.open(path))
            for key, path in tile_paths.items()
        }

        def sample(point: tuple[float, float]) -> float | None:
            plat, plon = point
            src = datasets[_tile_for(plat, plon)]
            return _sample_with_nearby_fallback(src, plon, plat)

        site_elev = sample((lat, lon))
        if site_elev is None:
            site_key = _tile_for(lat, lon)
            src = datasets[site_key]
            raise RuntimeError(
                f"No valid 3DEP terrain was found at the site ({lat:.5f}, {lon:.5f}). "
                f"Tile={Path(src.name).name}, CRS={src.crs}, bounds={tuple(round(v, 5) for v in src.bounds)}."
            )

        radial_means: list[float] = []
        radial_valid_counts: list[int] = []
        for radial_index, pts in enumerate(radial_points):
            vals = [value for value in (sample(p) for p in pts) if value is not None]
            radial_valid_counts.append(len(vals))
            if len(vals) < MIN_VALID_SAMPLES_PER_RADIAL:
                bearing = radial_index * 45
                raise RuntimeError(
                    f"Insufficient valid 3DEP terrain on the {bearing}° radial: "
                    f"{len(vals)}/{SAMPLES_PER_RADIAL} samples usable."
                )
            radial_means.append(sum(vals) / len(vals))

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
        "radial_valid_samples": radial_valid_counts,
        "method": "8 radials, 45-degree spacing, terrain sampled 2-10 miles from site; corrected 3DEP tile indexing; raster CRS respected; isolated 3DEP nodata tolerated",
    }
