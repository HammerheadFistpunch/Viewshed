from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path

from output_styles import (
    DEFAULT_GAP_COLOR,
    DEFAULT_POSITIVE_COLOR,
    heatmap_rgba,
    redundancy_rgba,
    solid_mask_rgba,
)

NETWORK_NODATA = -9999.0


def _job_region(work_dir: Path) -> tuple[float, float, float] | None:
    job_path = work_dir.parent.parent / "job.json"
    try:
        raw = json.loads(job_path.read_text(encoding="utf-8"))
        region = raw.get("region") or {}
        return float(region["center_lat"]), float(region["center_lon"]), float(region["radius_km"])
    except Exception:
        return None


def _analysis_circle_mask(src, region: tuple[float, float, float] | None):
    import numpy as np

    if region is None:
        return np.ones((src.height, src.width), dtype=bool)
    from pyproj import Transformer
    from conus_support import projected_crs_for_location

    lat, lon, radius_km = region
    local_crs, _, _ = projected_crs_for_location(lat, lon)
    to_local = Transformer.from_crs(src.crs, local_crs, always_xy=True)
    cx, cy = to_local.transform(lon, lat)
    radius_m2 = (radius_km * 1000.0) ** 2
    mask = np.zeros((src.height, src.width), dtype=bool)
    cols = np.arange(src.width, dtype=np.float64) + 0.5
    for r0 in range(0, src.height, 256):
        r1 = min(src.height, r0 + 256)
        rows = np.arange(r0, r1, dtype=np.float64) + 0.5
        cc, rr = np.meshgrid(cols, rows)
        xs = src.transform.c + cc * src.transform.a + rr * src.transform.b
        ys = src.transform.f + cc * src.transform.d + rr * src.transform.e
        lx, ly = to_local.transform(xs, ys)
        mask[r0:r1] = ((lx - cx) ** 2 + (ly - cy) ** 2) <= radius_m2
    return mask


def _network_bbox(path: Path) -> tuple[float, float, float, float]:
    import rasterio
    from pyproj import Transformer

    with rasterio.open(path) as src:
        b = src.bounds
        tr = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True)
        west, south = tr.transform(b.left, b.bottom)
        east, north = tr.transform(b.right, b.top)
    return west, south, east, north


def _save_rgba(rgba, out_path: Path, max_px: int) -> None:
    from PIL import Image

    img = Image.fromarray(rgba, "RGBA")
    if max(img.size) > max_px:
        scale = max_px / max(img.size)
        img = img.resize((max(1, int(round(img.width * scale))), max(1, int(round(img.height * scale)))), Image.NEAREST)
    img.save(out_path, format="PNG", compress_level=6)


def _build_network_products(results: list, dem_path: Path, work_dir: Path, cfg: dict, coverage_count_path: Path) -> None:
    import numpy as np
    import rasterio
    from rasterio.warp import Resampling, reproject, transform_bounds
    from rasterio.windows import Window, from_bounds, transform as window_transform

    best_path = work_dir / "network_best_margin.tif"
    with rasterio.open(dem_path) as ref:
        profile = ref.profile.copy()
        height, width = ref.height, ref.width
        ref_crs = ref.crs
        ref_transform = ref.transform
        dem_nodata = ref.nodata
        dem = ref.read(1)
        circle = _analysis_circle_mask(ref, _job_region(work_dir))

    valid_dem = np.ones((height, width), dtype=bool)
    if dem_nodata is not None:
        valid_dem &= dem != dem_nodata
    if np.issubdtype(dem.dtype, np.floating):
        valid_dem &= np.isfinite(dem)
    analysis_mask = valid_dem & circle
    del dem, circle, valid_dem

    out_profile = profile.copy()
    out_profile.update(dtype="float32", count=1, nodata=NETWORK_NODATA, compress="lzw")
    with rasterio.open(best_path, "w", **out_profile) as dst:
        block = np.full((min(512, height), width), NETWORK_NODATA, dtype=np.float32)
        for r0 in range(0, height, block.shape[0]):
            r1 = min(height, r0 + block.shape[0])
            dst.write(block[: r1 - r0], 1, window=Window(0, r0, width, r1 - r0))

    seen = set()
    with rasterio.open(best_path, "r+") as best_dst:
        for _station, vs_path in results:
            key = str(Path(vs_path).resolve())
            if key in seen:
                continue
            seen.add(key)
            with rasterio.open(vs_path) as src:
                b = transform_bounds(src.crs, ref_crs, *src.bounds)
                win_f = from_bounds(*b, transform=ref_transform)
                c0 = max(0, int(math.floor(win_f.col_off)))
                r0 = max(0, int(math.floor(win_f.row_off)))
                c1 = min(width, int(math.ceil(win_f.col_off + win_f.width)))
                r1 = min(height, int(math.ceil(win_f.row_off + win_f.height)))
                if r1 <= r0 or c1 <= c0:
                    continue
                win = Window(c0, r0, c1 - c0, r1 - r0)
                incoming = np.full((r1 - r0, c1 - c0), NETWORK_NODATA, dtype=np.float32)
                reproject(
                    source=rasterio.band(src, 1), destination=incoming,
                    src_transform=src.transform, src_crs=src.crs,
                    dst_transform=window_transform(win, ref_transform), dst_crs=ref_crs,
                    resampling=Resampling.bilinear,
                    src_nodata=(src.nodata if src.nodata is not None else -1.0), dst_nodata=NETWORK_NODATA,
                )
                current = best_dst.read(1, window=win)
                valid = incoming > NETWORK_NODATA + 1.0
                current[valid] = np.maximum(current[valid], incoming[valid])
                best_dst.write(current, 1, window=win)

    with rasterio.open(best_path, "r+") as dst:
        for _, window in dst.block_windows(1):
            arr = dst.read(1, window=window)
            m = analysis_mask[int(window.row_off):int(window.row_off + window.height), int(window.col_off):int(window.col_off + window.width)]
            arr[~m] = NETWORK_NODATA
            dst.write(arr, 1, window=window)

    with rasterio.open(best_path) as src:
        best = src.read(1).astype(np.float32)
    with rasterio.open(coverage_count_path) as cov:
        count = cov.read(1)

    alpha = int(cfg.get("overlay_alpha", 180))
    max_px = int(cfg.get("overlay_max_px", 4096))
    heat = heatmap_rgba(best, cfg, nodata=NETWORK_NODATA)
    positive = solid_mask_rgba((count > 0) & analysis_mask, cfg.get("positive_color", DEFAULT_POSITIVE_COLOR), alpha)
    gaps = solid_mask_rgba((count <= 0) & analysis_mask, cfg.get("gap_color", DEFAULT_GAP_COLOR), min(210, alpha))
    redundancy = redundancy_rgba(np.where(analysis_mask, count, 0), cfg)

    _save_rgba(heat, work_dir / "network_margin_bands.png", max_px)
    _save_rgba(positive, work_dir / "positive_coverage.png", max_px)
    _save_rgba(gaps, work_dir / "inverse_coverage.png", max_px)
    _save_rgba(redundancy, work_dir / "coverage_redundancy.png", max_px)
    band_db = max(0.5, float(cfg.get("network_heatmap_band_db", 3.0)))
    print(f"   Network products: {band_db:g} dB heat map, positive coverage, gaps, and redundancy ready")


def _overlay(name: str, href: str, visibility: int, order: int, bbox: tuple[float, float, float, float]) -> str:
    west, south, east, north = bbox
    return f"""    <GroundOverlay>
      <name>{name}</name>
      <visibility>{visibility}</visibility>
      <drawOrder>{order}</drawOrder>
      <Icon><href>{href}</href></Icon>
      <LatLonBox><north>{north}</north><south>{south}</south><east>{east}</east><west>{west}</west></LatLonBox>
    </GroundOverlay>
"""


def _inject_network_layers(kmz_path: Path, work_dir: Path, cfg: dict | None = None) -> None:
    cfg = cfg or {}
    best_path = work_dir / "network_best_margin.tif"
    if not best_path.exists():
        return
    bbox = _network_bbox(best_path)
    products = []
    if bool(cfg.get("output_network_heatmap", True)):
        products.append((_overlay(f"Composite Heat Map ({float(cfg.get('network_heatmap_band_db', 3.0)):g} dB bands)", "network/network_margin_bands.png", 1, 10, bbox), work_dir / "network_margin_bands.png", "network/network_margin_bands.png"))
    if bool(cfg.get("output_positive", False)):
        products.append((_overlay("Positive Coverage", "network/positive_coverage.png", 0, 11, bbox), work_dir / "positive_coverage.png", "network/positive_coverage.png"))
    if bool(cfg.get("output_gaps", False)):
        products.append((_overlay("Coverage Gaps — APRS Not Expected", "network/inverse_coverage.png", 0, 12, bbox), work_dir / "inverse_coverage.png", "network/inverse_coverage.png"))
    if bool(cfg.get("output_redundancy", False)):
        products.append((_overlay("Coverage Redundancy (1 / 2 / 3+ stations)", "network/coverage_redundancy.png", 0, 13, bbox), work_dir / "coverage_redundancy.png", "network/coverage_redundancy.png"))
    if not products:
        return

    folder = "  <Folder>\n    <name>Coverage Analysis</name>\n    <visibility>1</visibility>\n    <open>1</open>\n" + "".join(p[0] for p in products) + "  </Folder>\n"
    tmp = kmz_path.with_suffix(".network.tmp")
    with zipfile.ZipFile(kmz_path, "r") as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "doc.kml":
                text = data.decode("utf-8").replace("</Document>", folder + "\n</Document>")
                data = text.encode("utf-8")
            dst.writestr(info, data)
        for _kml, source, arc in products:
            if source.exists():
                dst.write(source, arc)
    tmp.replace(kmz_path)


def install_coverage_products(engine) -> None:
    """Add selectable network-level coverage products without changing ITM."""
    if getattr(engine, "_coverage_products_installed", False):
        return
    original_merge = engine.merge_viewsheds
    original_build = engine.build_kmz

    def merge_viewsheds_with_network(results, dem_path, work_dir, cfg=None):
        cfg = cfg or engine.CONFIG
        merged_path, station_tifs = original_merge(results, dem_path, work_dir, cfg)
        try:
            _build_network_products(results, Path(dem_path), Path(work_dir), cfg, Path(merged_path))
        except Exception as exc:
            print(f"   Warning: coverage analysis products could not be built: {exc}")
        return merged_path, station_tifs

    def build_kmz_with_network(*args, **kwargs):
        kmz_path = Path(original_build(*args, **kwargs))
        try:
            work_dir = Path(kwargs.get("work_dir") or args[4])
            cfg = kwargs.get("cfg") or (args[3] if len(args) > 3 else engine.CONFIG)
            _inject_network_layers(kmz_path, work_dir, cfg)
            print("   KMZ: selected coverage-analysis layers added.")
        except Exception as exc:
            print(f"   Warning: selected KMZ layers could not be added: {exc}")
        return kmz_path

    engine.merge_viewsheds = merge_viewsheds_with_network
    engine.build_kmz = build_kmz_with_network
    engine._coverage_products_installed = True
