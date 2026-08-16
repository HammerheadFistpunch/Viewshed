from __future__ import annotations

import time
import zipfile
from pathlib import Path


def install_rendering_fix(engine) -> None:
    """Install nodata-safe overlays and clearer categorical KMZ labeling."""

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
                # Combined coverage is station-count data. Nearest-neighbor
                # resizing preserves its categorical meaning.
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

    def create_clear_legend(work_dir: Path, cfg: dict) -> Path:
        from PIL import Image, ImageDraw

        floor_db = float(cfg.get("margin_display_floor_db", -6.0))
        max_db = float(cfg.get("max_margin_db", 30.0))
        w, h = 250, 190
        img = Image.new("RGBA", (w, h), (20, 20, 20, 210))
        draw = ImageDraw.Draw(img)
        draw.text((10, 8), "Viewshed Coverage Legend", fill=(255, 255, 255, 255))
        draw.line([(10, 26), (w - 10, 26)], fill=(80, 80, 80, 255), width=1)

        draw.text((10, 30), "Coverage overlap:", fill=(200, 200, 200, 255))
        if cfg["color_scheme"] == "hot":
            ramp = [
                ((180, 220, 0, 230), "1 station"),
                ((220, 150, 0, 230), "2–3 stations"),
                ((255, 50, 0, 230), "4+ stations"),
            ]
        else:
            ramp = [
                ((0, 200, 120, 230), "1 station"),
                ((0, 140, 180, 230), "2–3 stations"),
                ((0, 60, 255, 230), "4+ stations"),
            ]
        y = 46
        for color, label in ramp:
            draw.rectangle([10, y + 2, 26, y + 14], fill=color, outline=(60, 60, 60, 200))
            draw.text((34, y), label, fill=(240, 240, 240, 255))
            y += 18

        draw.line([(10, y + 2), (w - 10, y + 2)], fill=(60, 60, 60, 255), width=1)
        y += 8
        draw.text((10, y), "Per-station predicted link margin:", fill=(200, 200, 200, 255))
        y += 16
        for i, x in enumerate(range(10, 26)):
            t = i / 15.0
            draw.line([(x, y + 2), (x, y + 14)], fill=(int(40 - 40*t), int(120 + 135*t), int(40 - 40*t), 220))
        draw.text((34, y), f"Digi  {floor_db:+.0f} to +{max_db:.0f} dB", fill=(140, 240, 140, 255))
        y += 18
        for i, x in enumerate(range(10, 26)):
            t = i / 15.0
            draw.line([(x, y + 2), (x, y + 14)], fill=(int(80 - 80*t), int(160 - 130*t), int(200 + 55*t), 220))
        draw.text((34, y), f"iGate {floor_db:+.0f} to +{max_db:.0f} dB", fill=(140, 200, 240, 255))
        y += 22
        draw.line([(10, y), (w - 10, y)], fill=(60, 60, 60, 255), width=1)
        y += 6
        draw.text((10, y), "0 dB = reference operational edge", fill=(180, 180, 180, 255))
        y += 14
        draw.text((10, y), "Prediction, not guaranteed communication", fill=(160, 160, 160, 255))

        legend_path = work_dir / "legend.png"
        img.save(str(legend_path))
        return legend_path

    original_build_kmz = engine.build_kmz

    def build_kmz_with_clear_labels(*args, **kwargs):
        kmz_path = Path(original_build_kmz(*args, **kwargs))
        try:
            replacement_pairs = (
                ("Combined Coverage Heatmap", "Combined Coverage Overlap"),
                ("Coverage Density", "Coverage Overlap"),
                ("Heatmap colour scale:", "Coverage overlap categories:"),
                ("Combined heatmap:", "Coverage overlap:"),
                ("colour shows simultaneous coverage count at each point", "categories show how many modeled stations cover each point"),
            )
            tmp = kmz_path.with_suffix(".relabel.tmp")
            with zipfile.ZipFile(kmz_path, "r") as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
                for info in src.infolist():
                    data = src.read(info.filename)
                    if info.filename == "doc.kml":
                        text = data.decode("utf-8")
                        for old, new in replacement_pairs:
                            text = text.replace(old, new)
                        data = text.encode("utf-8")
                    dst.writestr(info, data)
            tmp.replace(kmz_path)
        except Exception as exc:
            print(f"   Warning: could not relabel KMZ coverage presentation: {exc}")
        return kmz_path

    engine.raster_to_png_overlay = raster_to_png_overlay
    engine._create_legend = create_clear_legend
    engine.build_kmz = build_kmz_with_clear_labels
