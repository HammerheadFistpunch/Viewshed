from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from dem_sources import prepare_dem as _prepare_dem


_SIGNATURE_FILE = "v2_dem_plan.json"
_DERIVED_FILES = (
    "utah_dem.tif",
    "utah_dem_bounds.json",
    "utah_dem_utm.tif",
    "analysis_dem.tif",
)
_USGS_TNM_API = "https://tnmaccess.nationalmap.gov/api/v1/products"


def _plan_signature(cfg: dict) -> dict:
    """Return the parts of the resource plan that determine derived DEM fidelity."""
    return {
        "version": 1,
        "dem_merge_max_dimension": int(cfg.get("dem_merge_max_dimension", 8000)),
        "analysis_dem_max_dimension": int(cfg.get("analysis_dem_max_dimension", 8000)),
        "terrain_detail_mode": str(cfg.get("terrain_detail_mode", "legacy")),
        "terrain_detail_actual_m": float(cfg.get("terrain_detail_actual_m", 0.0) or 0.0),
        "max_radius_km": float(cfg.get("max_radius_km", 80.0)),
    }


def _read_signature(path: Path) -> dict | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def _invalidate_derived_dem(work_dir: Path) -> None:
    for name in _DERIVED_FILES:
        try:
            (work_dir / name).unlink(missing_ok=True)
        except Exception:
            pass


def _tile_id(lat_north: int, lon_west: int) -> str:
    return f"n{lat_north - 1:02d}w{lon_west:03d}"


def _tile_download_url(item: dict, tile: str) -> str | None:
    """Extract a GeoTIFF/ZIP download URL from a TNM product result."""
    urls: list[str] = []
    direct = item.get("downloadURL")
    if isinstance(direct, str):
        urls.append(direct)
    for file_info in item.get("files", []) or []:
        if isinstance(file_info, dict):
            url = file_info.get("url") or file_info.get("downloadURL")
            if isinstance(url, str):
                urls.append(url)

    tile_lower = tile.lower()
    for url in urls:
        lower = url.lower()
        name = lower.rsplit("/", 1)[-1]
        if tile_lower in name and name.endswith((".tif", ".tiff", ".zip")):
            return url
    return None


def _save_download(response, target: Path, url: str) -> None:
    if url.lower().endswith(".zip") or "application/zip" in response.headers.get("Content-Type", "").lower():
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            tif_name = next(
                (name for name in archive.namelist() if name.lower().endswith((".tif", ".tiff"))),
                None,
            )
            if not tif_name:
                raise RuntimeError("TNM archive contained no GeoTIFF")
            target.write_bytes(archive.read(tif_name))
        return

    with target.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)


def _download_missing_usgs_tiles(stations: list, cfg: dict) -> int:
    """Populate missing 1-arc-second source tiles directly from TNMAccess.

    This is a recovery path for the legacy staged-S3 URL used by dem_sources.
    USGS documents TNMAccess as the programmatic interface to downloadable
    National Map products, while 1-arc-second 3DEP tiles remain available as
    current and historical GeoTIFF products.
    """
    import requests
    import rasterio

    dem_cache = Path(cfg.get("dem_cache_dir", "dem_cache"))
    if not dem_cache.is_absolute():
        dem_cache = Path(__file__).resolve().parent / dem_cache
    dem_cache.mkdir(parents=True, exist_ok=True)

    lats = [float(s["lat"]) for s in stations]
    lons = [float(s["lon"]) for s in stations]
    margin_deg = max(1.0, __import__("math").ceil(float(cfg.get("max_radius_km", 80.0)) / 111.0))
    lat_min = min(lats) - margin_deg
    lat_max = max(lats) + margin_deg
    lon_min = min(lons) - margin_deg
    lon_max = max(lons) + margin_deg

    if lon_max >= 0:
        return 0

    lon_w_min = __import__("math").ceil(abs(lon_max))
    lon_w_max = __import__("math").ceil(abs(lon_min))
    lat_n_min = __import__("math").ceil(lat_min)
    lat_n_max = __import__("math").ceil(lat_max)
    needed_tiles = [
        (lat_n, lon_w)
        for lat_n in range(lat_n_min, lat_n_max + 1)
        for lon_w in range(lon_w_min, lon_w_max + 1)
    ]

    downloaded = 0
    session = requests.Session()
    dataset_queries = (
        {"q": "1 arc-second DEM"},
        {"q": "Digital Elevation Model (DEM) 1 arc-second"},
        {"datasets": "National Elevation Dataset (NED) 1 arc-second Current"},
        {"datasets": "National Elevation Dataset (NED) 1 arc-second"},
    )

    for lat_n, lon_w in needed_tiles:
        tile = _tile_id(lat_n, lon_w)
        target = dem_cache / f"USGS_1_{tile}.tif"
        if target.exists():
            try:
                with rasterio.open(target) as src:
                    if src.width > 0 and src.height > 0 and src.count >= 1:
                        continue
            except Exception:
                target.unlink(missing_ok=True)

        south = lat_n - 1
        west = -float(lon_w)
        east = west + 1.0
        bbox = f"{west},{south},{east},{lat_n}"
        candidates: list[str] = []

        for query in dataset_queries:
            params = dict(query)
            params.update({"bbox": bbox, "prodFormats": "GeoTIFF", "max": 100})
            try:
                response = session.get(_USGS_TNM_API, params=params, timeout=45)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                print(f"      TNM recovery lookup failed for {tile.upper()}: {exc}")
                continue

            for item in data.get("items", []) or []:
                if not isinstance(item, dict):
                    continue
                url = _tile_download_url(item, tile)
                if url and url not in candidates:
                    candidates.append(url)

            if candidates:
                break

        for url in candidates:
            part = target.with_suffix(target.suffix + ".part")
            part.unlink(missing_ok=True)
            try:
                print(f"      TNM recovery: downloading {tile.upper()} from {url.rsplit('/', 1)[-1]}")
                with session.get(url, stream=True, timeout=120) as response:
                    response.raise_for_status()
                    _save_download(response, part, url)
                with rasterio.open(part) as src:
                    if src.width <= 0 or src.height <= 0 or src.count < 1:
                        raise RuntimeError("downloaded raster is not usable")
                part.replace(target)
                downloaded += 1
                break
            except Exception as exc:
                part.unlink(missing_ok=True)
                print(f"      TNM recovery download failed for {tile.upper()}: {exc}")

    return downloaded


def prepare_dem(stations: list, cfg: dict, work_dir: Path) -> Path:
    """V2 DEM preparation with resolution-aware derived-raster reuse."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    signature_path = work_dir / _SIGNATURE_FILE
    wanted = _plan_signature(cfg)
    cached = _read_signature(signature_path)

    derived_exists = (work_dir / "utah_dem.tif").exists()
    if derived_exists and cached != wanted:
        print("   V2 DEM cache: terrain-detail plan changed; rebuilding derived DEM from cached USGS source tiles.")
        _invalidate_derived_dem(work_dir)
    elif derived_exists and cached == wanted:
        print("   V2 DEM cache: detail plan matches cached derived DEM.")

    try:
        dem_path = _prepare_dem(stations, cfg, work_dir)
    except RuntimeError as exc:
        message = str(exc)
        if "Could not download USGS 3DEP tile" not in message:
            raise

        print("   USGS 3DEP staged download failed; attempting TNMAccess recovery for missing source tiles...")
        recovered = _download_missing_usgs_tiles(stations, cfg)
        if recovered <= 0:
            raise
        print(f"   TNMAccess recovery populated {recovered} missing USGS source tile(s); retrying DEM preparation.")
        dem_path = _prepare_dem(stations, cfg, work_dir)

    signature_path.write_text(json.dumps(wanted, indent=2), encoding="utf-8")
    return dem_path
