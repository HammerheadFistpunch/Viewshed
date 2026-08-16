from __future__ import annotations

from pathlib import Path


def prepare_analysis_dem(source_dem: Path, work_dir: Path, max_dimension: int = 8000) -> Path:
    """Build a memory-bounded analysis DEM from the cached full-resolution source.

    The source 3DEP mosaic remains untouched. The returned raster preserves the
    same CRS and geographic bounds while reducing the longest raster dimension
    to ``max_dimension`` so the legacy propagation engine does not require a
    multi-gigabyte Windows shared-memory allocation.
    """
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import Affine

    source_dem = Path(source_dem)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path = work_dir / "analysis_dem.tif"

    with rasterio.open(source_dem) as src:
        longest = max(src.width, src.height)
        if longest <= max_dimension:
            print(
                f"   Analysis DEM: source already memory-safe "
                f"({src.width}x{src.height}); using full resolution."
            )
            return source_dem

        scale = max_dimension / float(longest)
        out_width = max(1, int(round(src.width * scale)))
        out_height = max(1, int(round(src.height * scale)))
        expected_bytes = out_width * out_height * 4

        print(
            f"   Building memory-bounded analysis DEM: "
            f"{src.width}x{src.height} -> {out_width}x{out_height} "
            f"(~{expected_bytes / 1e6:.0f} MB float32)"
        )

        data = src.read(
            1,
            out_shape=(out_height, out_width),
            resampling=Resampling.bilinear,
        ).astype(np.float32, copy=False)

        transform = src.transform * Affine.scale(
            src.width / float(out_width),
            src.height / float(out_height),
        )
        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            width=out_width,
            height=out_height,
            transform=transform,
            dtype="float32",
            count=1,
            compress="lzw",
            tiled=True,
            blockxsize=512,
            blockysize=512,
            BIGTIFF="IF_SAFER",
        )

        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(data, 1)

    size_mb = out_path.stat().st_size / 1e6
    print(f"   Analysis DEM ready: {size_mb:.0f} MB on disk")
    return out_path
