from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path


NETWORK_NODATA = -9999.0


def _safe_name(value: str) -> str:
    return value.replace("-", "_").replace("/", "_").replace(" ", "_")


def _job_region(work_dir: Path) -> tuple[float, float, float] | None:
    """Read the requested analysis circle from the job beside output/work."""
    job_path = work_dir.parent.parent / "job.json"
    try:
        raw = json.loads(job_path.read_text(encoding="utf-8"))
        region = raw.get("region") or {}
        return (
            float(region["center_lat"]),
            float(region["center_lon"]),
            float(region["radius_km"]),
        )
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
    chunk_rows = 256
    cols = np.arange(src.width, dtype=np.float64) + 0.5

    for r0 in range(0, src.height, chunk_rows):
        r1 = min(src.height, r0 + chunk_rows)
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


def _render_margin_bands(path: Path, out_path: Path, cfg: dict) -> None:
    import numpy as np
    import rasterio
    from PIL import Image

    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        nodata = float(src.nodata if src.nodata is not None else NETWORK_NODATA)

    max_px = int(cfg.get("overlay_max_px", 4096))
    h, w = data.shape
    if max(h, w) > max_px:
        scale = max_px / max(h, w)
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        valid = data > nodata + 1.0
        values = data.copy()
        values[~valid] = 0.0
        values = np.array(Image.fromarray(values, mode="F").resize((nw, nh), Image.BILINEAR), dtype=np.float32)
        valid = np.array(Image.fromarray((valid.astype(np.uint8) * 255), mode="L").resize((nw, nh), Image.NEAREST)) > 0
        data = values
    else:
        valid = data > nodata + 1.0

    valid &= data >= 0.0
    rgba = np.zeros((*data.shape, 4), dtype=np.uint8)
    if not np.any(valid):
        Image.fromarray(rgba, "RGBA").save(out_path, format="PNG", compress_level=6)
        return

    band_db = max(0.5, float(cfg.get("network_heatmap_band_db", 3.0)))
    max_db = max(band_db, float(cfg.get("max_margin_db", 30.0)))
    banded = np.floor(np.clip(data[valid], 0.0, max_db) / band_db) * band_db
    norm = np.clip(banded / max_db, 0.0, 1.0)

    # Blue -> cyan -> green -> yellow -> orange -> red, intentionally stepped.
    r = np.zeros_like(norm)
    g = np.zeros_like(norm)
    b = np.zeros_like(norm)

    s1 = norm < 0.25
    s2 = (norm >= 0.25) & (norm < 0.50)
    s3 = (norm >= 0.50) & (norm < 0.75)
    s4 = norm >= 0.75

    t = norm[s1] / 0.25
    r[s1] = 20
    g[s1] = 80 + 175 * t
    b[s1] = 255

    t = (norm[s2] - 0.25) / 0.25
    r[s2] = 20
    g[s2] = 255
    b[s2] = 255 * (1.0 - t)

    t = (norm[s3] - 0.50) / 0.25
    r[s3] = 255 * t
    g[s3] = 255
    b[s3] = 0

    t = (norm[s4] - 0.75) / 0.25
    r[s4] = 255
    g[s4] = 255 * (1.0 - t)
    b[s4] = 0

    rgba[valid, 0] = np.clip(r, 0, 255).astype(np.uint8)
    rgba[valid, 1] = np.clip(g, 0, 255).astype(np.uint8)
    rgba[valid, 2] = np.clip(b, 0, 255).astype(np.uint8)
    rgba[valid, 3] = int(cfg.get("overlay_alpha", 180))
    Image.fromarray(rgba, "RGBA").save(out_path, format="PNG", compress_level=6)


def _render_inverse(path: Path, out_path: Path, cfg: dict) -> None:
    import numpy as np
    import rasterio
    from PIL import Image

    with rasterio.open(path) as src:
        data = src.read(1)

    max_px = int(cfg.get("overlay_max_px", 4096))
    h, w = data.shape
    if max(h, w) > max_px:
        scale = max_px / max(h, w)
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        data = np.array(Image.fromarray(data.astype(np.uint8), mode="L").resize((nw, nh), Image.NEAREST))

    dead = data > 0
    rgba = np.zeros((*data.shape, 4), dtype=np.uint8)
    rgba[dead, 0] = 220
    rgba[dead, 1] = 35
    rgba[dead, 2] = 35
    rgba[dead, 3] = min(210, int(cfg.get("overlay_alpha", 180)))
    Image.fromarray(rgba, "RGBA").save(out_path, format="PNG", compress_level=6)


def _build_network_products(results: list, dem_path: Path, work_dir: Path, cfg: dict, coverage_count_path: Path) -> None:
    import numpy as np
    import rasterio
    from rasterio.warp import Resampling, reproject, transform_bounds
    from rasterio.windows import Window, from_bounds, transform as window_transform

    best_path = work_dir / "network_best_margin.tif"
    inverse_path = work_dir / "inverse_coverage.tif"
    heat_png = work_dir / "network_margin_bands.png"
    inverse_png = work_dir / "inverse_coverage.png"

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
        for station, vs_path in results:
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
                win_tf = window_transform(win, ref_transform)
                incoming = np.full((r1 - r0, c1 - c0), NETWORK_NODATA, dtype=np.float32)
                src_nodata = src.nodata if src.nodata is not None else -1.0
                reproject(
                    source=rasterio.band(src, 1),
                    destination=incoming,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=win_tf,
                    dst_crs=ref_crs,
                    resampling=Resampling.bilinear,
                    src_nodata=src_nodata,
                    dst_nodata=NETWORK_NODATA,
                )
                current = best_dst.read(1, window=win)
                valid = incoming > NETWORK_NODATA + 1.0
                current[valid] = np.maximum(current[valid], incoming[valid])
                best_dst.write(current, 1, window=win)

    with rasterio.open(best_path, "r+") as dst:
        for _, window in dst.block_windows(1):
            arr = dst.read(1, window=window)
            m = analysis_mask[
                int(window.row_off) : int(window.row_off + window.height),
                int(window.col_off) : int(window.col_off + window.width),
            ]
            arr[~m] = NETWORK_NODATA
            dst.write(arr, 1, window=window)

    with rasterio.open(coverage_count_path) as cov:
        count = cov.read(1)
    dead = (count <= 0) & analysis_mask
    inv_profile = profile.copy()
    inv_profile.update(dtype="uint8", count=1, nodata=0, compress="lzw")
    with rasterio.open(inverse_path, "w", **inv_profile) as dst:
        dst.write(dead.astype(np.uint8), 1)

    _render_margin_bands(best_path, heat_png, cfg)
    _render_inverse(inverse_path, inverse_png, cfg)
    band_db = max(0.5, float(cfg.get("network_heatmap_band_db", 3.0)))
    print(f"   Network products: {band_db:g} dB margin bands + inverse APRS dead-zone raster ready")


def _inject_network_layers(kmz_path: Path, work_dir: Path, cfg: dict | None = None) -> None:
    heat_png = work_dir / "network_margin_bands.png"
    inverse_png = work_dir / "inverse_coverage.png"
    best_path = work_dir / "network_best_margin.tif"
    if not (heat_png.exists() and inverse_png.exists() and best_path.exists()):
        return

    cfg = cfg or {}
    band_db = max(0.5, float(cfg.get("network_heatmap_band_db", 3.0)))
    west, south, east, north = _network_bbox(best_path)
    folder = f"""
  <Folder>
    <name>Network Analysis</name>
    <visibility>1</visibility>
    <open>1</open>
    <GroundOverlay>
      <name>Granular Network Margin ({band_db:g} dB bands)</name>
      <visibility>1</visibility>
      <drawOrder>10</drawOrder>
      <Icon><href>network/network_margin_bands.png</href></Icon>
      <LatLonBox><north>{north}</north><south>{south}</south><east>{east}</east><west>{west}</west></LatLonBox>
    </GroundOverlay>
    <GroundOverlay>
      <name>Inverse Coverage — APRS Not Expected</name>
      <visibility>0</visibility>
      <drawOrder>11</drawOrder>
      <Icon><href>network/inverse_coverage.png</href></Icon>
      <LatLonBox><north>{north}</north><south>{south}</south><east>{east}</east><west>{west}</west></LatLonBox>
    </GroundOverlay>
  </Folder>
"""

    tmp = kmz_path.with_suffix(".network.tmp")
    with zipfile.ZipFile(kmz_path, "r") as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "doc.kml":
                text = data.decode("utf-8")
                text = text.replace("</Document>", folder + "\n</Document>")
                data = text.encode("utf-8")
            dst.writestr(info, data)
        dst.write(heat_png, "network/network_margin_bands.png")
        dst.write(inverse_png, "network/inverse_coverage.png")
    tmp.replace(kmz_path)


def install_coverage_products(engine) -> None:
    """Add toggleable network signal-band and inverse-coverage products."""
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
            print(f"   Warning: network heatmap/inverse products could not be built: {exc}")
        return merged_path, station_tifs

    def build_kmz_with_network(*args, **kwargs):
        kmz_path = Path(original_build(*args, **kwargs))
        try:
            work_dir = Path(kwargs.get("work_dir") or args[4])
            cfg = kwargs.get("cfg") or (args[3] if len(args) > 3 else engine.CONFIG)
            _inject_network_layers(kmz_path, work_dir, cfg)
            print("   KMZ: granular network margin visible by default; inverse layer available as a toggle")
        except Exception as exc:
            print(f"   Warning: network KMZ layers could not be added: {exc}")
        return kmz_path

    engine.merge_viewsheds = merge_viewsheds_with_network
    engine.build_kmz = build_kmz_with_network
    engine._coverage_products_installed = True
