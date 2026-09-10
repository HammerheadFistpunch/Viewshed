from __future__ import annotations

import json
from pathlib import Path

from dem_sources import prepare_dem as _prepare_dem


_SIGNATURE_FILE = "v2_dem_plan.json"
_DERIVED_FILES = (
    "utah_dem.tif",
    "utah_dem_bounds.json",
    "utah_dem_utm.tif",
    "analysis_dem.tif",
)


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


def prepare_dem(stations: list, cfg: dict, work_dir: Path) -> Path:
    """V2 DEM preparation with resolution-aware derived-raster reuse.

    Persistent USGS source tiles remain in ``dem_cache_dir`` and are never
    removed here. Only job-local mosaics/analysis rasters are invalidated when
    the planned detail or propagation radius changes.
    """
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

    dem_path = _prepare_dem(stations, cfg, work_dir)
    signature_path.write_text(json.dumps(wanted, indent=2), encoding="utf-8")
    return dem_path
