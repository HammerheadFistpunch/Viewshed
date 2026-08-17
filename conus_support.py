from __future__ import annotations

import math
import multiprocessing as _mp
import os
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def projected_crs_for_location(lat: float, lon: float) -> tuple[str, int, str]:
    """Return the local UTM CRS for a geographic location.

    CONUS is entirely in the northern hemisphere, but the southern branch is
    supported so the projection helper remains generally correct.
    """
    zone = int(math.floor((float(lon) + 180.0) / 6.0)) + 1
    zone = max(1, min(60, zone))
    north = float(lat) >= 0.0
    epsg = (32600 if north else 32700) + zone
    return f"EPSG:{epsg}", zone, "N" if north else "S"


def install_conus_support(engine) -> None:
    """Replace only the projection/dispatch layer of the legacy RF engine.

    The underlying per-station ITM worker is intentionally reused unchanged.
    This removes the old hard-coded UTM Zone 12N assumption while preserving
    the propagation math that has already been exercised in Utah.
    """
    if getattr(engine, "_conus_projection_installed", False):
        return

    def compute_viewsheds(stations: list, dem_path: Path, cfg: dict,
                          work_dir: Path, colocation_map: dict | None = None) -> list:
        import numpy as np
        import rasterio
        from multiprocessing.shared_memory import SharedMemory
        from pyproj import Transformer
        from rasterio.warp import Resampling, calculate_default_transform, reproject
        from tqdm import tqdm

        if not stations:
            return []

        center_lat = sum(float(s["lat"]) for s in stations) / len(stations)
        center_lon = sum(float(s["lon"]) for s in stations) / len(stations)
        dst_crs, zone, hemisphere = projected_crs_for_location(center_lat, center_lon)
        dem_utm_path = work_dir / f"region_dem_utm_z{zone:02d}{hemisphere}.tif"

        if not dem_utm_path.exists():
            print(
                f"   Reprojecting DEM to UTM Zone {zone}{hemisphere} "
                f"({dst_crs})...",
                end=" ",
                flush=True,
            )
            t_proj = time.perf_counter()
            with rasterio.open(dem_path) as src:
                transform, width, height = calculate_default_transform(
                    src.crs, dst_crs, src.width, src.height, *src.bounds
                )
                profile = src.profile.copy()
                profile.update(
                    crs=dst_crs,
                    transform=transform,
                    width=width,
                    height=height,
                    nodata=-9999,
                    dtype="float32",
                    compress="lzw",
                )
                with rasterio.open(dem_utm_path, "w", **profile) as dst:
                    reproject(
                        source=rasterio.band(src, 1),
                        destination=rasterio.band(dst, 1),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.bilinear,
                        src_nodata=src.nodata,
                        dst_nodata=-9999,
                    )
            print(f"done ({engine._elapsed(t_proj)})")
        else:
            print(f"   Projected DEM cached: UTM Zone {zone}{hemisphere} ({dst_crs})")

        to_utm = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)

        with rasterio.open(dem_utm_path) as ref:
            utm_transform = ref.transform
            px_size = abs(utm_transform.a)
            full_nodata = ref.nodata if ref.nodata is not None else -9999
            dem_full = ref.read(1).astype(np.float32)
            dem_crs = ref.crs
            dem_height = ref.height
            dem_width = ref.width

        utm_tf_tuple = (
            utm_transform.a,
            utm_transform.b,
            utm_transform.c,
            utm_transform.d,
            utm_transform.e,
            utm_transform.f,
        )
        dem_crs_str = dem_crs.to_wkt()

        n_workers = cfg.get("cpu_workers") or os.cpu_count() or 4
        total = len(stations)
        n_radials = cfg["n_radials"]
        max_loss = engine._resolve_max_path_loss(cfg)
        cfg["_resolved_max_loss_db"] = max_loss
        cfg["projected_crs"] = dst_crs
        cfg["utm_zone"] = zone
        cfg["utm_hemisphere"] = hemisphere

        print("\n   Engine:  itmlogic Longley-Rice ITM (CPU — full accuracy)")
        print(f"   Projection: UTM Zone {zone}{hemisphere} ({dst_crs})")
        print(f"   Workers: {n_workers} CPU processes")
        print(f"   DEM:     {dem_width}×{dem_height} px @ {px_size:.1f} m/px")
        print(
            f"   Radials: {n_radials}/station × {total} stations "
            f"= {n_radials * total:,} ITM calls"
        )
        print(f"   Max path loss: {max_loss:.1f} dB\n")

        colo_map = colocation_map or {}

        # Broad physical sanity limits appropriate to the contiguous U.S.
        # They catch obvious DEM/coordinate failures without assuming Utah's
        # 800–4200 m terrain range.
        elev_min = float(cfg.get("conus_elev_min_m", -200.0))
        elev_max = float(cfg.get("conus_elev_max_m", 5000.0))
        pit_thresh = cfg.get("elev_pit_threshold_m", 40.0)

        def check_elevation(callsign, row, col, elev):
            warns = []
            if elev < elev_min:
                warns.append(
                    f"   ⚠  {callsign:<12} elevation {elev:.0f} m is below "
                    f"the broad CONUS sanity floor ({elev_min:.0f} m) — "
                    "possible DEM void or bad coordinate"
                )
            elif elev > elev_max:
                warns.append(
                    f"   ⚠  {callsign:<12} elevation {elev:.0f} m is above "
                    f"the broad CONUS sanity ceiling ({elev_max:.0f} m) — "
                    "possible DEM or coordinate error"
                )

            if pit_thresh is not None:
                r0 = max(0, row - 2)
                r1 = min(dem_height, row + 3)
                c0 = max(0, col - 2)
                c1 = min(dem_width, col + 3)
                hood = dem_full[r0:r1, c0:c1].copy().astype(np.float32)
                hood[hood <= (full_nodata + 1)] = np.nan
                hood[row - r0, col - c0] = np.nan
                valid = hood[~np.isnan(hood)]
                if valid.size >= 4:
                    median_elev = float(np.median(valid))
                    drop = median_elev - elev
                    if drop > float(pit_thresh):
                        warns.append(
                            f"   ⚠  {callsign:<12} DEM pit — station cell is "
                            f"{drop:.0f} m below neighbourhood median "
                            f"({elev:.0f} m vs {median_elev:.0f} m). Verify coordinates."
                        )
            return warns

        shm = SharedMemory(create=True, size=int(dem_full.nbytes))
        shm_array = np.ndarray(dem_full.shape, dtype=dem_full.dtype, buffer=shm.buf)
        np.copyto(shm_array, dem_full)
        dem_shm_info = {
            "shm_name": shm.name,
            "shape": dem_full.shape,
            "dtype": str(dem_full.dtype),
        }
        print(
            f"   DEM in shared memory: {dem_full.nbytes / 1e9:.2f} GB "
            f"(block: {shm.name})"
        )

        try:
            job_args = []
            skipped = []
            for i, station in enumerate(stations):
                obs_east, obs_north = to_utm.transform(station["lon"], station["lat"])
                obs_col = int((obs_east - utm_transform.c) / utm_transform.a)
                obs_row = int((obs_north - utm_transform.f) / utm_transform.e)
                if not (0 <= obs_row < dem_height and 0 <= obs_col < dem_width):
                    print(f"   ⚠  {station['callsign']:<12} outside DEM — skipped")
                    skipped.append(i)
                    continue
                obs_terrain = float(dem_full[obs_row, obs_col])
                if np.isnan(obs_terrain) or obs_terrain <= (full_nodata + 1):
                    print(f"   ⚠  {station['callsign']:<12} no elevation — skipped")
                    skipped.append(i)
                    continue

                for warn in check_elevation(
                    station["callsign"], obs_row, obs_col, obs_terrain
                ):
                    print(warn)

                job_args.append(
                    (
                        station,
                        dem_shm_info,
                        utm_tf_tuple,
                        dem_crs_str,
                        dem_height,
                        dem_width,
                        cfg,
                        str(work_dir),
                        obs_row,
                        obs_col,
                        obs_terrain,
                        i,
                        total,
                    )
                )

            canonical_calls = {
                a[0]["callsign"]
                for a in job_args
                if colo_map.get(a[0]["callsign"], a[0]["callsign"])
                == a[0]["callsign"]
            }
            primary_args = [a for a in job_args if a[0]["callsign"] in canonical_calls]
            deferred = [a for a in job_args if a[0]["callsign"] not in canonical_calls]

            if deferred:
                print(
                    f"   Co-location: {len(deferred)} station(s) will share "
                    "a canonical viewshed TIF (no duplicate ITM work)."
                )

            results = []
            print_lock = threading.Lock()
            ctx = _mp.get_context("spawn")
            t_dispatch = time.perf_counter()
            bar_fmt = (
                "   {l_bar}{bar}| {n_fmt}/{total_fmt} stations "
                "[{elapsed}<{remaining}, {rate_fmt}]"
            )

            with tqdm(
                total=len(primary_args),
                unit="stn",
                ncols=72,
                colour="green",
                bar_format=bar_fmt,
            ) as pbar:
                with ProcessPoolExecutor(max_workers=n_workers, mp_context=ctx) as pool:
                    futures = {
                        pool.submit(engine._process_station, a): a[0]["callsign"]
                        for a in primary_args
                    }
                    for fut in as_completed(futures):
                        callsign_orig = futures[fut]
                        try:
                            station_ret, vs_path_str, status, _, _, idx = fut.result()
                            ant_h = (
                                cfg["antenna_height_digi_m"]
                                if station_ret["type"] == "digi"
                                else cfg["antenna_height_igate_m"]
                            )
                            line = (
                                f"   [{idx + 1:3d}/{total}] "
                                f"{station_ret['callsign']:<12} "
                                f"({station_ret['type']:<5}) "
                                f"ant={ant_h:.0f}m  {status}"
                            )
                            with print_lock:
                                pbar.write(line)
                                pbar.update(1)
                            if vs_path_str:
                                results.append((station_ret, Path(vs_path_str), idx))
                        except Exception as exc:
                            with print_lock:
                                pbar.write(
                                    f"   ❌ Worker failed for {callsign_orig}: {exc}"
                                )
                                pbar.update(1)

            canonical_tif = {s["callsign"]: p for s, p, *_ in results}
            for args in deferred:
                station = args[0]
                callsign = station["callsign"]
                canon = colo_map.get(callsign, callsign)
                if canon in canonical_tif:
                    shared_tif = canonical_tif[canon]
                    results.append((station, shared_tif, args[12]))
                    print(f"   [COLO] {callsign:<12} shares TIF with {canon}")
                else:
                    safe_call = callsign.replace("-", "_").replace("/", "_").replace(" ", "_")
                    fallback_tif = work_dir / f"viewshed_{safe_call}.tif"
                    if fallback_tif.exists():
                        results.append((station, fallback_tif, args[12]))
                        print(
                            f"   [COLO] {callsign:<12} canonical missing, using cached TIF"
                        )
                    else:
                        print(
                            f"   ⚠  {callsign:<12} co-location fallback: canonical "
                            f"'{canon}' had no TIF, running solo ITM"
                        )
                        try:
                            ret = engine._process_station(args)
                            _, vs_str, _, _, _, idx = ret
                            if vs_str:
                                results.append((station, Path(vs_str), idx))
                        except Exception as exc:
                            print(f"   ❌ Solo ITM failed for {callsign}: {exc}")

            results.sort(key=lambda r: r[2])
            resolved = [(s, p) for s, p, _ in results]
            n_computed = len(primary_args)
            n_shared = len(deferred)
            rate = n_computed / max((time.perf_counter() - t_dispatch) / 60, 0.01)
            print(
                f"\n   ✅ {len(resolved)}/{total} stations resolved  "
                f"({n_computed} ITM computed, {n_shared} shared, "
                f"{len(skipped)} skipped)  --  {rate:.1f} ITM/min"
            )
            return resolved
        finally:
            try:
                shm.close()
                shm.unlink()
            except Exception:
                pass

    engine.compute_viewsheds = compute_viewsheds
    engine._conus_projection_installed = True
