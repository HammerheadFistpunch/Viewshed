from __future__ import annotations

import time
from pathlib import Path


def install_rendering_fix(engine) -> None:
    """Install a nodata-safe Google Earth overlay renderer on the legacy engine.

    The legacy renderer converted per-station floating point rasters to uint8
    before resizing. That clamped the -1 nodata sentinel to zero, after which
    the margin colorizer treated the zeroes as valid RF data. The result was a
    stack of colored rectangular raster footprints instead of terrain-shaped
    coverage.
    """

    def raster_to_png_overlay(
        coverage_path: Path,
        work_dir: Path,
        cfg: dict,
        station_name: str | None = None,
        prebuilt_rgba=None,
        station_type: str | None = None,
    ):
        import numpy as np
        import rasterio
        from PIL import Image
        from pyproj import Transformer

        ge_max_px = int(cfg.get("overlay_max_px", 4096))
        if station_name is not None:
            ge_max_px = min(ge_max_px, 1024)

        t0 = time.perf_counter()
        with rasterio.open(coverage_path) as src:
            data = src.read(1).astype(np.float32)
            bounds = src.bounds
            src_crs = src.crs
            nodata = src.nodata

        h, w = data.shape
        if h > ge_max_px or w > ge_max_px:
            scale = ge_max_px / max(h, w)
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))

            if station_type is not None:
                # Preserve transparency independently from signal values.
                # The current station rasters use -1 as nodata and the legacy
                # colorizer considers only values > -1 visible.
                nodata_value = -1.0 if nodata is None else float(nodata)
                valid = data > nodata_value

                # Resize signal values and the validity mask separately. Values
                # outside the mask are irrelevant and are reset to nodata after
                # resampling, preventing rectangular overlay footprints.
                value_source = data.copy()
                value_source[~valid] = 0.0
                value_img = Image.fromarray(value_source, mode="F").resize(
                    (new_w, new_h), Image.BILINEAR
                )
                mask_img = Image.fromarray((valid.astype(np.uint8) * 255), mode="L").resize(
                    (new_w, new_h), Image.NEAREST
                )
                data = np.array(value_img, dtype=np.float32)
                valid_small = np.array(mask_img, dtype=np.uint8) > 0
                data[~valid_small] = nodata_value
            else:
                # Combined coverage is a non-negative station-count raster.
                max_vp = float(data.max()) if data.max() > 0 else 1.0
                data_u8 = (data / max_vp * 254).clip(0, 254).astype(np.uint8)
                data_img = Image.fromarray(data_u8, mode="L").resize(
                    (new_w, new_h), Image.NEAREST
                )
                data = np.array(data_img, dtype=np.float32) / 254.0 * max_vp

            h, w = new_h, new_w

        if prebuilt_rgba is not None:
            rgba = prebuilt_rgba
        else:
            rgba = engine._colorize(data, cfg, station_type=station_type)

        img = Image.fromarray(rgba.astype(np.uint8), "RGBA")
        if station_name is not None:
            png_path = work_dir / f"station_{station_name}.png"
        else:
            png_path = work_dir / "coverage_overlay.png"
        img.save(str(png_path), format="PNG", compress_level=6)

        transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
        west, south = transformer.transform(bounds.left, bounds.bottom)
        east, north = transformer.transform(bounds.right, bounds.top)
        bbox = (west, south, east, north)

        if station_name is None:
            print(f"   Overlay PNG ready  ({time.perf_counter() - t0:.1f}s total)")
            print(
                f"      WGS84 bbox: N{north:.4f} S{south:.4f} "
                f"E{east:.4f} W{west:.4f}"
            )
        return png_path, bbox

    engine.raster_to_png_overlay = raster_to_png_overlay
