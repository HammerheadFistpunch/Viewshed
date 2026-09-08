from __future__ import annotations

import os
import re
import sys
import time
import zipfile
from pathlib import Path


def _configure_console_encoding() -> None:
    """Keep diagnostic Unicode from crashing Windows worker processes."""
    # Configure the parent process too. Spawned workers get an explicit child-
    # local setup through safe_worker.py below.
    os.environ["PYTHONIOENCODING"] = "utf-8:replace"
    os.environ["PYTHONUTF8"] = "1"
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def install_rendering_fix(engine) -> None:
    """Install nodata-safe per-station overlays and the CONUS projection adapter."""
    _configure_console_encoding()

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
                nodata_value = -1.0 if nodata is None else float(nodata)
                valid = data > nodata_value
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
                max_vp = float(data.max()) if data.max() > 0 else 1.0
                data_u8 = (data / max_vp * 254).clip(0, 254).astype(np.uint8)
                data_img = Image.fromarray(data_u8, mode="L").resize(
                    (new_w, new_h), Image.NEAREST
                )
                data = np.array(data_img, dtype=np.float32) / 254.0 * max_vp

        if prebuilt_rgba is not None:
            rgba = prebuilt_rgba
        else:
            rgba = engine._colorize(data, cfg, station_type=station_type)

        img = Image.fromarray(rgba.astype(np.uint8), "RGBA")
        if station_name is not None:
            png_path = work_dir / f"station_{station_name}.png"
        else:
            # The engine still produces this temporary composite as an internal
            # compatibility artifact. It is removed from the final KMZ below.
            png_path = work_dir / "coverage_overlay.png"
        img.save(str(png_path), format="PNG", compress_level=6)

        transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
        west, south = transformer.transform(bounds.left, bounds.bottom)
        east, north = transformer.transform(bounds.right, bounds.top)
        bbox = (west, south, east, north)

        if station_name is None:
            print(f"   Temporary merge raster rendered  ({time.perf_counter() - t0:.1f}s total)")
        return png_path, bbox

    def create_clear_legend(work_dir: Path, cfg: dict) -> Path:
        from PIL import Image, ImageDraw

        band_db = max(0.5, float(cfg.get("network_heatmap_band_db", 3.0)))
        max_db = max(band_db, float(cfg.get("max_margin_db", 30.0)))
        floor_db = float(cfg.get("margin_display_floor_db", 0.0))

        def network_rgb(value_db: float) -> tuple[int, int, int]:
            banded = int(value_db // band_db) * band_db
            norm = max(0.0, min(1.0, banded / max_db))
            if norm < 0.25:
                t = norm / 0.25
                return 20, int(80 + 175 * t), 255
            if norm < 0.50:
                t = (norm - 0.25) / 0.25
                return 20, 255, int(255 * (1.0 - t))
            if norm < 0.75:
                t = (norm - 0.50) / 0.25
                return int(255 * t), 255, 0
            t = (norm - 0.75) / 0.25
            return 255, int(255 * (1.0 - t)), 0

        w, h = 330, 190
        img = Image.new("RGBA", (w, h), (20, 20, 20, 220))
        draw = ImageDraw.Draw(img)
        draw.text((10, 8), "Signal Peak Link-Margin Legend", fill=(255, 255, 255, 255))
        draw.line([(10, 27), (w - 10, 27)], fill=(80, 80, 80, 255), width=1)

        draw.text(
            (10, 35),
            f"Network best margin — {band_db:g} dB bands",
            fill=(220, 220, 220, 255),
        )

        x0, x1 = 10, w - 10
        y0, y1 = 55, 75
        n_bands = max(1, int((max_db + band_db - 1e-9) // band_db))
        for i in range(n_bands + 1):
            lo = min(max_db, i * band_db)
            left = int(round(x0 + (x1 - x0) * (lo / max_db)))
            hi = min(max_db, (i + 1) * band_db)
            right = int(round(x0 + (x1 - x0) * (hi / max_db)))
            if right <= left:
                right = left + 1
            rgb = network_rgb(lo)
            draw.rectangle((left, y0, min(x1, right), y1), fill=(*rgb, 235))

        draw.rectangle((x0, y0, x1, y1), outline=(230, 230, 230, 255), width=1)
        draw.text((x0, 79), "0 dB", fill=(210, 210, 210, 255))
        max_label = f"+{max_db:g} dB"
        draw.text((x1 - 48, 79), max_label, fill=(210, 210, 210, 255))
        draw.text((10, 96), "0 dB = modeled operational edge", fill=(185, 185, 185, 255))

        y = 116
        draw.rectangle((10, y, 27, y + 12), fill=(220, 35, 35, 210))
        draw.text((34, y - 1), "Inverse: APRS not expected", fill=(220, 205, 205, 255))

        y += 21
        draw.rectangle((10, y, 27, y + 12), fill=(20, 210, 40, 220))
        draw.text(
            (34, y - 1),
            f"Per-station Digi  {floor_db:+.0f} to +{max_db:g} dB",
            fill=(150, 235, 155, 255),
        )

        y += 21
        draw.rectangle((10, y, 27, y + 12), fill=(45, 95, 230, 220))
        draw.text(
            (34, y - 1),
            f"Per-station iGate {floor_db:+.0f} to +{max_db:g} dB",
            fill=(155, 195, 245, 255),
        )

        draw.text((10, 174), "Prediction, not guaranteed communication", fill=(160, 160, 160, 255))

        legend_path = work_dir / "legend.png"
        img.save(str(legend_path))
        return legend_path

    original_build_kmz = engine.build_kmz

    def build_kmz_without_composite(*args, **kwargs):
        kmz_path = Path(original_build_kmz(*args, **kwargs))
        try:
            tmp = kmz_path.with_suffix(".perstation.tmp")
            with zipfile.ZipFile(kmz_path, "r") as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
                for info in src.infolist():
                    if info.filename == "coverage_overlay.png":
                        continue
                    data = src.read(info.filename)
                    if info.filename == "doc.kml":
                        text = data.decode("utf-8")
                        text = re.sub(
                            r"\n  <Folder>\n    <name>📊 Combined Coverage Heatmap</name>.*?\n  </Folder>\n",
                            "\n",
                            text,
                            flags=re.DOTALL,
                        )
                        text = text.replace(
                            "    <b>Heatmap colour scale:</b><br/>\n"
                            "    \u00a0 Yellow = 1 station coverage<br/>\n"
                            "    \u00a0 Orange = 2–3 stations<br/>\n"
                            "    \u00a0 Red    = 4+ stations (dense overlap)<br/><br/>\n",
                            "",
                        )
                        text = text.replace(
                            "    <b>Per-station overlays:</b><br/>",
                            "    <b>Per-station predicted link margin:</b><br/>",
                        )
                        data = text.encode("utf-8")
                    dst.writestr(info, data)
            tmp.replace(kmz_path)
            try:
                (Path(kwargs.get("work_dir") or args[4]) / "coverage_overlay.png").unlink(missing_ok=True)
            except Exception:
                pass
            print("   Legacy composite count view removed; per-station viewsheds retained for network products.")
        except Exception as exc:
            print(f"   Warning: could not remove composite KMZ view: {exc}")
        return kmz_path

    engine.raster_to_png_overlay = raster_to_png_overlay
    engine._create_legend = create_clear_legend
    engine.build_kmz = build_kmz_without_composite

    # Keep the legacy RF worker intact, but replace its Utah-only projection
    # wrapper with a location-derived UTM projection for CONUS jobs.
    from conus_support import install_conus_support

    install_conus_support(engine)

    # Windows ProcessPool uses spawn. Configure encoding inside each spawned
    # child before the legacy station worker can emit diagnostic Unicode.
    from safe_worker import install_safe_worker

    install_safe_worker(engine)

    # The legacy loader also had a Utah bounding-box gate. Replace that before
    # viewshed_core asks the engine to validate the selected stations.
    from conus_station_loader import install_conus_station_loader

    install_conus_station_loader(engine)

    # Add network-level products without changing the established ITM worker:
    # a stepped best-margin heatmap and an inverse/dead-zone overlay.
    from coverage_products import install_coverage_products

    install_coverage_products(engine)
