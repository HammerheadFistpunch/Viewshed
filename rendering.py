from __future__ import annotations

import os
import re
import sys
import time
import zipfile
from pathlib import Path

from output_styles import color_at, heatmap_colors, heatmap_rgba, hex_to_rgb


def _configure_console_encoding() -> None:
    """Keep diagnostic Unicode from crashing Windows worker processes."""
    os.environ["PYTHONIOENCODING"] = "utf-8:replace"
    os.environ["PYTHONUTF8"] = "1"
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def install_rendering_fix(engine) -> None:
    """Install unified heatmap rendering and CONUS adapters."""
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
                data = np.array(Image.fromarray(value_source, mode="F").resize((new_w, new_h), Image.BILINEAR), dtype=np.float32)
                valid_small = np.array(Image.fromarray((valid.astype(np.uint8) * 255), mode="L").resize((new_w, new_h), Image.NEAREST)) > 0
                data[~valid_small] = nodata_value
            else:
                max_vp = float(data.max()) if data.max() > 0 else 1.0
                data_u8 = (data / max_vp * 254).clip(0, 254).astype(np.uint8)
                data = np.array(Image.fromarray(data_u8, mode="L").resize((new_w, new_h), Image.NEAREST), dtype=np.float32) / 254.0 * max_vp

        if prebuilt_rgba is not None:
            rgba = prebuilt_rgba
        elif station_type is not None:
            rgba = heatmap_rgba(data, cfg, nodata=(-1.0 if nodata is None else float(nodata)))
        else:
            rgba = engine._colorize(data, cfg, station_type=station_type)

        img = Image.fromarray(rgba.astype(np.uint8), "RGBA")
        png_path = work_dir / (f"station_{station_name}.png" if station_name is not None else "coverage_overlay.png")
        img.save(str(png_path), format="PNG", compress_level=6)

        transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
        west, south = transformer.transform(bounds.left, bounds.bottom)
        east, north = transformer.transform(bounds.right, bounds.top)
        if station_name is None:
            print(f"   Temporary merge raster rendered  ({time.perf_counter() - t0:.1f}s total)")
        return png_path, (west, south, east, north)

    def create_clear_legend(work_dir: Path, cfg: dict) -> Path:
        from PIL import Image, ImageDraw

        band_db = max(0.5, float(cfg.get("network_heatmap_band_db", 3.0)))
        max_db = max(band_db, float(cfg.get("max_margin_db", 30.0)))
        colors = heatmap_colors(cfg)
        gap_rgb = hex_to_rgb(cfg.get("gap_color", "#DC2323"))
        pos_rgb = hex_to_rgb(cfg.get("positive_color", "#20C85A"))

        w, h = 350, 170
        img = Image.new("RGBA", (w, h), (20, 20, 20, 220))
        draw = ImageDraw.Draw(img)
        draw.text((10, 8), "Signal Peak Coverage Legend", fill=(255, 255, 255, 255))
        draw.line([(10, 27), (w - 10, 27)], fill=(80, 80, 80, 255), width=1)
        draw.text((10, 35), f"Link margin — {band_db:g} dB bands", fill=(220, 220, 220, 255))
        x0, x1, y0, y1 = 10, w - 10, 55, 75
        n_bands = max(1, int((max_db + band_db - 1e-9) // band_db))
        for i in range(n_bands + 1):
            lo = min(max_db, i * band_db)
            hi = min(max_db, (i + 1) * band_db)
            left = int(round(x0 + (x1 - x0) * (lo / max_db)))
            right = max(left + 1, int(round(x0 + (x1 - x0) * (hi / max_db))))
            rgb = color_at(lo / max_db, colors)
            draw.rectangle((left, y0, min(x1, right), y1), fill=(*rgb, 235))
        draw.rectangle((x0, y0, x1, y1), outline=(230, 230, 230, 255), width=1)
        draw.text((x0, 79), "0 dB", fill=(210, 210, 210, 255))
        draw.text((x1 - 52, 79), f"+{max_db:g} dB", fill=(210, 210, 210, 255))
        draw.text((10, 97), "Composite and per-station heat maps use this same scale", fill=(185, 185, 185, 255))
        draw.rectangle((10, 119, 27, 131), fill=(*pos_rgb, 220))
        draw.text((34, 118), "Positive coverage", fill=(210, 210, 210, 255))
        draw.rectangle((165, 119, 182, 131), fill=(*gap_rgb, 220))
        draw.text((189, 118), "Coverage gap", fill=(210, 210, 210, 255))
        draw.text((10, 145), "Prediction, not guaranteed communication", fill=(160, 160, 160, 255))
        legend_path = work_dir / "legend.png"
        img.save(str(legend_path))
        return legend_path

    original_build_kmz = engine.build_kmz

    def build_kmz_selectable(*args, **kwargs):
        cfg = kwargs.get("cfg") or (args[3] if len(args) > 3 else engine.CONFIG)
        want_station_heatmaps = bool(cfg.get("output_per_station_heatmaps", False))

        call_args = list(args)
        call_kwargs = dict(kwargs)
        if not want_station_heatmaps:
            if len(call_args) > 5:
                call_args[5] = None
            else:
                call_kwargs["station_tifs"] = None
            if len(call_args) > 6:
                call_args[6] = None
            else:
                call_kwargs["prebuilt_pngs"] = None

        kmz_path = Path(original_build_kmz(*call_args, **call_kwargs))
        try:
            tmp = kmz_path.with_suffix(".layers.tmp")
            with zipfile.ZipFile(kmz_path, "r") as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
                for info in src.infolist():
                    if info.filename == "coverage_overlay.png":
                        continue
                    data = src.read(info.filename)
                    if info.filename == "doc.kml":
                        text = data.decode("utf-8")
                        text = re.sub(r"\n  <Folder>\n    <name>📊 Combined Coverage Heatmap</name>.*?\n  </Folder>\n", "\n", text, flags=re.DOTALL)
                        text = text.replace(
                            "    <b>Heatmap colour scale:</b><br/>\n    \u00a0 Yellow = 1 station coverage<br/>\n    \u00a0 Orange = 2–3 stations<br/>\n    \u00a0 Red    = 4+ stations (dense overlap)<br/><br/>\n",
                            "",
                        )
                        start = text.find("  <Folder>\n    <name>📡 Per-Station Viewsheds")
                        end = text.find("  <ScreenOverlay>", start) if start >= 0 else -1
                        if start >= 0 and end > start:
                            section = text[start:end]
                            overlays = re.findall(r"\s*<GroundOverlay>.*?</GroundOverlay>\s*", section, flags=re.DOTALL)
                            section = re.sub(r"\s*<GroundOverlay>.*?</GroundOverlay>\s*", "\n", section, flags=re.DOTALL)
                            section = re.sub(r"<name>📡 Per-Station Viewsheds \([^<]+\)</name>", "<name>📍 Stations</name>", section, count=1)
                            if not bool(cfg.get("output_stations", True)):
                                section = ""
                            extra = ""
                            if want_station_heatmaps and overlays:
                                extra = "  <Folder>\n    <name>🌡 Per-Station Heat Maps</name>\n    <visibility>0</visibility>\n    <open>0</open>\n" + "".join(overlays) + "  </Folder>\n\n"
                            text = text[:start] + section + extra + text[end:]
                        text = text.replace("<b>Per-station overlays:</b>", "<b>Station markers:</b>")
                        data = text.encode("utf-8")
                    dst.writestr(info, data)
            tmp.replace(kmz_path)
            try:
                (Path(call_kwargs.get("work_dir") or call_args[4]) / "coverage_overlay.png").unlink(missing_ok=True)
            except Exception:
                pass
            print("   KMZ station pins and per-station heat maps are independent layers.")
        except Exception as exc:
            print(f"   Warning: could not restructure KMZ station layers: {exc}")
        return kmz_path

    engine.raster_to_png_overlay = raster_to_png_overlay
    engine._create_legend = create_clear_legend
    engine.build_kmz = build_kmz_selectable

    from conus_support import install_conus_support
    install_conus_support(engine)
    from safe_worker import install_safe_worker
    install_safe_worker(engine)
    from conus_station_loader import install_conus_station_loader
    install_conus_station_loader(engine)
    from coverage_products import install_coverage_products
    install_coverage_products(engine)
