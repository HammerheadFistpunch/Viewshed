from __future__ import annotations

import io
import json
import math
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


USGS_TNM_API = "https://tnmaccess.nationalmap.gov/api/v1/products"
USGS_3DEP_CURRENT = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1/TIFF/current"


def _tile_id(lat_north: int, lon_west: int) -> str:
    south = lat_north - 1
    return f"n{south:02d}w{lon_west:03d}"


def _current_tile_url(tile_id: str) -> str:
    return f"{USGS_3DEP_CURRENT}/{tile_id}/USGS_1_{tile_id}.tif"


def _validate_tif(path: Path) -> None:
    import rasterio
    with rasterio.open(path) as src:
        if src.width <= 0 or src.height <= 0 or src.count < 1:
            raise RuntimeError(f"Downloaded DEM is not a usable raster: {path.name}")


def _save_response_as_tif(response, target: Path, source_url: str) -> None:
    content_type = response.headers.get("Content-Type", "").lower()
    if source_url.lower().endswith(".zip") or "application/zip" in content_type:
        payload = io.BytesIO(response.content)
        with zipfile.ZipFile(payload) as archive:
            tif_name = next((name for name in archive.namelist() if name.lower().endswith((".tif", ".tiff"))), None)
            if not tif_name:
                raise RuntimeError("USGS archive contained no GeoTIFF")
            target.write_bytes(archive.read(tif_name))
    else:
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def _download_url(requests, url: str, target: Path, timeout: int = 120) -> None:
    part = target.with_suffix(target.suffix + ".part")
    part.unlink(missing_ok=True)
    try:
        with requests.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            _save_response_as_tif(response, part, url)
        _validate_tif(part)
        part.replace(target)
    except Exception:
        part.unlink(missing_ok=True)
        raise


def _iter_product_urls(item: dict) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    direct = item.get("downloadURL")
    if isinstance(direct, str) and direct:
        seen.add(direct)
        urls.append(direct)
    files = item.get("files")
    if isinstance(files, list):
        for entry in files:
            if not isinstance(entry, dict):
                continue
            for key in ("downloadURL", "url", "downloadUrl"):
                candidate = entry.get(key)
                if isinstance(candidate, str) and candidate and candidate not in seen:
                    seen.add(candidate)
                    urls.append(candidate)
    return urls


def _is_current(item: dict, url: str) -> bool:
    lower = url.lower()
    text = " ".join(str(item.get(k) or "") for k in ("title", "name", "description", "dataset")).lower()
    return "/current/" in lower or " current" in text or text.endswith("current")


def _publication_date(item: dict, url: str) -> str:
    value = item.get("publicationDate") or item.get("dateCreated") or ""
    if value:
        return str(value)
    match = re.search(r"_(\d{8})(?:\.|$)", url.rsplit("/", 1)[-1])
    return match.group(1) if match else ""


def _tnm_candidates(requests, lat_north: int, lon_west: int) -> list[str]:
    """Discover actual 1-arc-second products from TNMAccess.

    TNMAccess is authoritative for the product record. Do not require the
    legacy ``USGS_1_<tile>.tif`` filename: current products can have a
    different staged filename, and product records may expose URLs in a
    nested ``files`` collection.
    """
    south = lat_north - 1
    west = -float(lon_west)
    east = west + 1.0
    bbox = f"{west},{south},{east},{lat_north}"
    tile = f"n{south:02d}w{lon_west:03d}".lower()
    candidates: list[tuple[bool, str, str]] = []
    seen: set[str] = set()
    errors: list[str] = []

    queries = (
        {"datasets": "National Elevation Dataset (NED) 1 arc-second Current"},
        {"datasets": "National Elevation Dataset (NED) 1 arc-second"},
        {"q": "1 arc-second DEM"},
        {"q": "National Elevation Dataset (NED) 1 arc-second Current"},
    )

    for extra in queries:
        params = {**extra, "bbox": bbox, "prodExtents": "1 x 1 degree"}
        try:
            response = requests.get(USGS_TNM_API, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data.get("errorMessage"):
                raise RuntimeError(str(data["errorMessage"]))
        except Exception as exc:
            errors.append(f"{extra}: {exc}")
            continue

        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").lower()
            for url in _iter_product_urls(item):
                lower = url.lower()
                clean_url = lower.split("?", 1)[0]
                if not clean_url.endswith((".tif", ".tiff", ".zip")):
                    continue
                if url in seen:
                    continue
                if tile not in lower and tile not in title:
                    continue
                seen.add(url)
                candidates.append((_is_current(item, url), _publication_date(item, url), url))

    if not candidates:
        detail = "; ".join(errors) if errors else "TNMAccess returned no matching product URLs"
        raise RuntimeError(f"no TNMAccess product for {tile.upper()}: {detail}")

    current = [entry for entry in candidates if entry[0]]
    pool = current if current else candidates
    pool.sort(key=lambda entry: entry[1], reverse=True)
    return [entry[2] for entry in pool]


def _download_tile(lat_north: int, lon_west: int, dem_cache: Path) -> Path:
    import requests

    tile_id = _tile_id(lat_north, lon_west)
    target = dem_cache / f"USGS_1_{tile_id}.tif"
    if target.exists():
        try:
            _validate_tif(target)
            return target
        except Exception:
            target.unlink(missing_ok=True)

    errors: list[str] = []
    direct_url = _current_tile_url(tile_id)
    try:
        print(f"   Downloading {tile_id.upper()} from current 3DEP...")
        _download_url(requests, direct_url, target)
        return target
    except Exception as exc:
        errors.append(f"legacy current URL: {exc}")

    candidates = _tnm_candidates(requests, lat_north, lon_west)
    for url in candidates:
        try:
            print(f"      Trying TNM product: {url.rsplit('/', 1)[-1]}")
            _download_url(requests, url, target)
            return target
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    detail = errors[-1] if errors else "no TNM product was returned"
    raise RuntimeError(f"Could not download USGS 3DEP tile {tile_id.upper()}: {detail}")


def _merge_resolution(tile_paths: list[Path], max_dimension: int) -> tuple[tuple[float, float] | None, dict]:
    import rasterio
    with rasterio.open(tile_paths[0]) as first:
        xres = abs(float(first.res[0]))
        yres = abs(float(first.res[1]))
        nodata = float(first.nodata) if first.nodata is not None else -999999.0
        crs = first.crs
    left = float("inf")
    bottom = float("inf")
    right = float("-inf")
    top = float("-inf")
    for path in tile_paths:
        with rasterio.open(path) as src:
            left = min(left, src.bounds.left)
            bottom = min(bottom, src.bounds.bottom)
            right = max(right, src.bounds.right)
            top = max(top, src.bounds.top)
    native_width = max(1, int(math.ceil((right - left) / xres)))
    native_height = max(1, int(math.ceil((top - bottom) / yres)))
    longest = max(native_width, native_height)
    if longest <= max_dimension:
        return None, {"native_width": native_width, "native_height": native_height, "output_width_est": native_width, "output_height_est": native_height, "scale": 1.0, "nodata": nodata, "crs": crs}
    scale = longest / float(max_dimension)
    target_res = (xres * scale, yres * scale)
    output_width = max(1, int(math.ceil((right - left) / target_res[0])))
    output_height = max(1, int(math.ceil((top - bottom) / target_res[1])))
    return target_res, {"native_width": native_width, "native_height": native_height, "output_width_est": output_width, "output_height_est": output_height, "scale": scale, "nodata": nodata, "crs": crs}


def prepare_dem(stations: list, cfg: dict, work_dir: Path) -> Path:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.merge import merge as rio_merge

    dem_cache = Path(cfg.get("dem_cache_dir", "dem_cache"))
    if not dem_cache.is_absolute():
        dem_cache = Path(__file__).resolve().parent / dem_cache
    dem_cache.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    print(f"   DEM cache: {dem_cache}")

    lats = [float(s["lat"]) for s in stations]
    lons = [float(s["lon"]) for s in stations]
    margin_deg = max(1.0, math.ceil(float(cfg.get("max_radius_km", 80.0)) / 111.0))
    lat_min = min(lats) - margin_deg
    lat_max = max(lats) + margin_deg
    lon_min = min(lons) - margin_deg
    lon_max = max(lons) + margin_deg
    if lon_max >= 0:
        raise RuntimeError("The current DEM adapter expects western-hemisphere coordinates; generalized CRS support is still in progress.")

    lon_w_min = math.ceil(abs(lon_max))
    lon_w_max = math.ceil(abs(lon_min))
    lat_n_min = math.ceil(lat_min)
    lat_n_max = math.ceil(lat_max)
    needed_tiles = [(lat_n, lon_w) for lat_n in range(lat_n_min, lat_n_max + 1) for lon_w in range(lon_w_min, lon_w_max + 1)]
    canonical_names = [_tile_id(lat_n, lon_w) for lat_n, lon_w in needed_tiles]

    dem_path = work_dir / "utah_dem.tif"
    bounds_path = work_dir / "utah_dem_bounds.json"
    if dem_path.exists() and bounds_path.exists():
        try:
            cached = json.loads(bounds_path.read_text(encoding="utf-8"))
            if set(cached.get("tiles", [])) == set(canonical_names) and dem_path.stat().st_size > 0:
                print(f"   DEM cached ({dem_path.stat().st_size / 1e6:.0f} MB, {len(canonical_names)} tiles) -- skipping merge")
                return dem_path
        except Exception:
            pass
        dem_path.unlink(missing_ok=True)
        (work_dir / "utah_dem_utm.tif").unlink(missing_ok=True)

    print(f"   Region: lat {lat_min:.1f} to {lat_max:.1f}, lon {lon_min:.1f} to {lon_max:.1f}")
    print(f"   Tiles required: {len(needed_tiles)}")
    print("   Source: USGS 3DEP 1 arc-second products")

    tile_paths: list[Path] = []
    workers = min(4, max(1, len(needed_tiles)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_download_tile, lat_n, lon_w, dem_cache): (lat_n, lon_w) for lat_n, lon_w in needed_tiles}
        for future in as_completed(futures):
            tile_paths.append(future.result())

    tile_paths.sort()
    if not tile_paths:
        raise RuntimeError("No DEM tiles were available for the requested area.")

    max_merge_dimension = int(cfg.get("dem_merge_max_dimension", 8000))
    max_merge_dimension = max(2000, min(max_merge_dimension, 16000))
    merge_res, merge_info = _merge_resolution(tile_paths, max_merge_dimension)
    nodata = float(merge_info["nodata"])
    source_crs = merge_info["crs"] or CRS.from_epsg(4269)
    native_width = int(merge_info["native_width"])
    native_height = int(merge_info["native_height"])
    output_width = int(merge_info["output_width_est"])
    output_height = int(merge_info["output_height_est"])
    estimated_native_gib = native_width * native_height * 4 / (1024 ** 3)

    if merge_res is not None:
        print(f"   Large DEM guard: native mosaic would be {native_width}x{native_height} (~{estimated_native_gib:.1f} GiB float32).")
        print(f"   Merging directly to analysis-safe resolution: ~{output_width}x{output_height} instead of materializing the full mosaic.")

    print(f"   Merging {len(tile_paths)} tile(s) as disk-backed BigTIFF...", end=" ", flush=True)
    started = time.perf_counter()
    dem_path.unlink(missing_ok=True)
    merge_kwargs = {
        "nodata": nodata,
        "dtype": "float32",
        "mem_limit": 256,
        "dst_path": dem_path,
        "dst_kwds": {"driver": "GTiff", "dtype": "float32", "nodata": nodata, "compress": "lzw", "count": 1, "tiled": True, "blockxsize": 512, "blockysize": 512, "BIGTIFF": "YES"},
    }
    if merge_res is not None:
        merge_kwargs["res"] = merge_res
        merge_kwargs["target_aligned_pixels"] = True
    try:
        rio_merge(tile_paths, **merge_kwargs)
        with rasterio.open(dem_path, "r+") as dst:
            if not dst.crs:
                dst.crs = source_crs
            actual_width = dst.width
            actual_height = dst.height
            actual_crs = dst.crs or source_crs
    except Exception:
        dem_path.unlink(missing_ok=True)
        raise

    bounds_path.write_text(json.dumps({
        "tiles": sorted(canonical_names),
        "tiles_found": sorted(p.name for p in tile_paths),
        "lat_min": lat_min,
        "lat_max": lat_max,
        "lon_min": lon_min,
        "lon_max": lon_max,
        "nodata": nodata,
        "crs": str(actual_crs),
        "resolution_arcsec": 1.0 if merge_res is None else None,
        "source": "USGS 3DEP",
        "bigtiff": True,
        "disk_backed_merge": True,
        "merge_mem_limit_mb": 256,
        "native_estimated_width": native_width,
        "native_estimated_height": native_height,
        "output_width": actual_width,
        "output_height": actual_height,
        "adaptive_resolution": merge_res is not None,
        "resolution_scale": float(merge_info["scale"]),
    }, indent=2), encoding="utf-8")
    print(f"done ({actual_width}x{actual_height}, {dem_path.stat().st_size / 1e6:.0f} MB, {time.perf_counter() - started:.1f}s)")
    return dem_path
