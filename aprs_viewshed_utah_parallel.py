#!/usr/bin/env python3
"""
=============================================================================
APRS Digipeater / iGate Viewshed Generator for Utah  —  PARALLEL
=============================================================================
Full ITM Longley-Rice accuracy.  All raster math runs on CPU via numpy
and scipy — no GPU dependencies required.

═══════════════════════════════════════════════════════════════════════════════
DOUBLE-CLICK FIX NOTES  (why the old version needed IDLE)
═══════════════════════════════════════════════════════════════════════════════

Three separate bugs conspired to make double-clicking fail silently:

  BUG 1 — Wrong working directory
    Windows double-click launches Python from the *file-association* CWD,
    which on most systems is C:\\Windows\\System32.  All relative paths
    ("utah_stations_scraped.json", "aprs_viewshed_work/") pointed nowhere.
    Fix: os.chdir(Path(__file__).parent) at the very top of main().

  BUG 2 — pythonw.exe swallows stdout + crashes tqdm
    When .py files are associated with pythonw.exe (the "silent" launcher,
    common after some Python installers), there is NO console window at all.
    tqdm writes escape codes to stdout; with no console those writes raise
    OSError / io.UnsupportedOperation and kill the process before step 1.
    Fix: _bootstrap_console() detects this and re-launches via python.exe
    in a proper cmd.exe window before anything else runs.

  BUG 3 — Window vanishes on completion (or crash)
    Even when launched with python.exe, the cmd window closes the instant the
    process exits — success or exception — leaving no time to read results.
    Fix: input() pause at the end + a run_viewshed.bat launcher that adds
    its own `pause` so the window stays open regardless of how the script ends.

═══════════════════════════════════════════════════════════════════════════════
"""

# ─── CONSOLE BOOTSTRAP ────────────────────────────────────────────────────────
# This block MUST run before any import that touches stdout (tqdm, etc.)
# It detects pythonw.exe / no-console situations and self-relaunches.
import sys, os

def _bootstrap_console():
    """
    On Windows: if we have no real console (pythonw.exe or double-click with
    the silent launcher), re-exec ourselves in a proper cmd.exe window using
    python.exe and then exit this ghost process.

    On Linux/macOS this is a no-op.
    """
    if os.name != 'nt':
        return
    try:
        # Test whether stdout is a real console handle.
        # sys.stdout.fileno() raises io.UnsupportedOperation under pythonw.exe.
        sys.stdout.fileno()
    except Exception:
        # No real console — relaunch in a new cmd window that stays open.
        import subprocess
        script = os.path.abspath(__file__)
        subprocess.Popen(
            f'start "APRS Viewshed" cmd /k python "{script}"',
            shell=True
        )
        raise SystemExit(0)

_bootstrap_console()
# ─── END CONSOLE BOOTSTRAP ────────────────────────────────────────────────────

import subprocess, json, math, zipfile, time, threading
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as _mp

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
CONFIG = {
    "stations_json":          "utah_stations_scraped.json",
    "output_kmz":             "aprs_coverage_utah.kmz",
    "include_types":          ["digi", "igate"],
    "antenna_height_digi_m":  20.0,
    "antenna_height_igate_m": 3.0,
    "observer_height_m":      2.0,
    "max_radius_km":          180.0,
    "curvature_coeff":        0.8,
    "freq_mhz":               144.390,
    # ── Radials ──────────────────────────────────────────────────────────────
    "n_radials":              720,
    # ── Link budget ──────────────────────────────────────────────────────────
    "tx_power_dbm":           37.0,   # 5 W = 37 dBm
    "tx_antenna_gain_dbd":     3.0,   # mobile whip ≈ 0 dBd
    "rx_sensitivity_dbm":   -119.0,   # standard 1200-baud AFSK TNC
    "rx_antenna_gain_dbd":     2.0,   # typical elevated colinear / Yagi
    "max_path_loss_db":       130.0,  # Cap forces terrain shading to show
    "itm_climate":            4,
    "itm_ens":                301.0,
    "itm_sgm":                0.001,
    "itm_epsr":               15.0,
    "itm_pol":                1,
    "dem_resolution":         "30m",
    "work_dir":               "aprs_viewshed_work",
    "dem_cache_dir":          "dem_cache",
    "overlay_alpha":          180,    # Boosted from 80 so it pops on red rock
    "overlay_max_px":         4096,
    "color_scheme":           "hot",
    "deduplicate_coords":     True,

    # ── Margin / heatmap rendering ────────────────────────────────────────────
    "n_margin_samples":       40,
    "margin_display_floor_db": -8.0,   
    "max_margin_db":           20.0,
    "gap_fill_factor":          2.0,

    # ── Per-worker DEM crop / downsample ─────────────────────────────────────
    "worker_dem_max_px":        3000,
    "cpu_workers":            None,
    "clear_viewshed_cache":   True,

    # ── Coordinate overrides ─────────────────────────────────────────────────
    "coordinate_overrides": {
        "SCOTTS":  {"lat": 40.62277001558261, "lon": -111.56863133047902},
    },

    # ── Elevation sanity checks ───────────────────────────────────────────────
    "elev_min_m":             800.0,   
    "elev_max_m":             4200.0,  
    "elev_pit_threshold_m":   40.0,
}
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_max_path_loss(cfg: dict) -> float:
    """Derive the effective max path loss (link budget) from CONFIG."""
    tx_pwr  = cfg.get("tx_power_dbm",        0.0)
    tx_ant  = cfg.get("tx_antenna_gain_dbd",  0.0)
    rx_sens = cfg.get("rx_sensitivity_dbm",   0.0)   
    rx_ant  = cfg.get("rx_antenna_gain_dbd",  0.0)

    cap = float(cfg.get("max_path_loss_db", 110.0))

    if tx_pwr or tx_ant or rx_sens or rx_ant:
        computed = tx_pwr + abs(rx_sens) + tx_ant + rx_ant
        effective = min(computed, cap)
        if effective < computed:
            print(f"   Link budget (computed): {computed:.1f} dB  "
                  f"-> capped by max_path_loss_db to {effective:.1f} dB  "
                  f"(raises {effective:.0f} dB to show terrain shading)")
        else:
            print(f"   Link budget: {tx_pwr:.1f} dBm TX  +  {abs(rx_sens):.1f} dBm sens"
                  f"  +  {tx_ant:.1f} dBd TX-ant  +  {rx_ant:.1f} dBd RX-ant"
                  f"  =  {effective:.1f} dB")
        return effective

    print(f"   Max path loss: {cap:.1f} dB (explicit)")
    return cap


# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _stage(label: str, step: int, total_steps: int = 7):
    bar = "─" * 63
    print(f"\n{bar}")
    print(f"  STEP {step}/{total_steps}  {label}")
    print(f"{bar}")

def _elapsed(t0: float) -> str:
    s = time.perf_counter() - t0
    if s < 60:
        return f"{s:.1f}s"
    return f"{int(s)//60}m {int(s)%60}s"


# ═══════════════════════════════════════════════════════════════════════════════
# WORKER — runs in a child process, one station at a time.
# ═══════════════════════════════════════════════════════════════════════════════

def _process_station(args: tuple):
    """
    Compute the viewshed for one APRS station using the full ITM pipeline.
    All maths here is NumPy + itmlogic on CPU — GPU is not involved.
    """
    (station, _dem_shm_info, utm_tf_tuple, dem_crs_str,
     dem_height, dem_width, cfg, work_dir_str,
     obs_row, obs_col, obs_terrain_elev,
     station_idx, total_stations) = args

    import numpy as np
    import math
    import rasterio
    from rasterio.transform import Affine
    from rasterio.crs import CRS
    from pathlib import Path

    # ── Attach to the shared DEM ──────────────────────────────────────────────
    from multiprocessing.shared_memory import SharedMemory as _SHM
    _worker_shm = _SHM(name=_dem_shm_info["shm_name"], create=False)
    dem_array = np.ndarray(
        _dem_shm_info["shape"],
        dtype=np.dtype(_dem_shm_info["dtype"]),
        buffer=_worker_shm.buf,
    )

    ITM_AVAILABLE = False
    try:
        from itmlogic.preparatory_subroutines.qlrpfl import qlrpfl
        from itmlogic.statistics.avar import avar
        ITM_AVAILABLE = True
    except ImportError:
        pass

    callsign        = station["callsign"]
    stype           = station["type"]
    ant_h           = (cfg["antenna_height_digi_m"] if stype == "digi"
                       else cfg["antenna_height_igate_m"])
    TARGET_H        = cfg["observer_height_m"]
    MAX_LOSS_DB     = _resolve_max_path_loss(cfg) if station_idx == 0 else (
        cfg.get("_resolved_max_loss_db") or _resolve_max_path_loss(cfg))
    RADIUS_M        = cfg["max_radius_km"] * 1000.0
    N_RADIALS       = cfg["n_radials"]
    CURVATURE_COEFF = cfg["curvature_coeff"]
    FREQ_MHZ        = cfg["freq_mhz"]
    ITM_CLIMATE     = cfg["itm_climate"]
    ITM_ENS         = cfg["itm_ens"]
    ITM_SGM         = cfg["itm_sgm"]
    ITM_EPSR        = cfg["itm_epsr"]
    full_nodata     = -9999.0

    N_MARGIN_SAMPLES   = int(cfg.get("n_margin_samples",        20))
    MARGIN_FLOOR_DB    = float(cfg.get("margin_display_floor_db", -6.0))
    MAX_MARGIN_DB      = float(cfg.get("max_margin_db",           30.0))
    GAP_FILL_FACTOR    = float(cfg.get("gap_fill_factor",          1.0))

    work_dir  = Path(work_dir_str)
    safe_call = callsign.replace("-", "_").replace("/", "_").replace(" ", "_")
    vs_path   = work_dir / f"viewshed_{safe_call}.tif"

    if vs_path.exists():
        _cache_ok = False
        try:
            import rasterio as _rc
            from rasterio.transform import Affine as _Af
            with _rc.open(vs_path) as _chk:
                _t = _chk.transform
                _cache_ok = (_t != _Af.identity() and
                             _t.a != 0.0 and _t.e != 0.0)
        except Exception:
            pass 
        if not _cache_ok:
            try:
                vs_path.unlink()
                print(f"   ⚠  {callsign}: cached TIF had no geotransform "
                      f"(corrupt from previous run) — recomputing")
            except Exception:
                pass
        else:
            try:
                _worker_shm.close()
            except Exception:
                pass
            return (station, str(vs_path),
                    "⚡ CACHE HIT — delete viewshed_*.tif to recompute",
                    0, 0, station_idx)

    utm_transform = Affine(*utm_tf_tuple)
    px_size       = abs(utm_transform.a)
    radius_px     = int(RADIUS_M / px_size)

    WORKER_MAX_PX  = int(cfg.get("worker_dem_max_px", 3000))

    cr0 = max(0, obs_row - radius_px)
    cr1 = min(dem_height, obs_row + radius_px + 1)
    cc0 = max(0, obs_col - radius_px)
    cc1 = min(dem_width,  obs_col + radius_px + 1)

    work_dem  = dem_array[cr0:cr1, cc0:cc1].copy()
    work_h, work_w = work_dem.shape

    work_obs_row = obs_row - cr0
    work_obs_col = obs_col - cc0

    crop_scale = min(1.0, WORKER_MAX_PX / max(work_h, work_w))
    if crop_scale < 0.999:
        from PIL import Image as _PILw
        ds_h = max(1, int(round(work_h * crop_scale)))
        ds_w = max(1, int(round(work_w * crop_scale)))
        _tmp = work_dem.copy()
        _tmp[_tmp <= (full_nodata + 1)] = float('nan')
        work_dem = np.array(
            _PILw.fromarray(_tmp).resize((ds_w, ds_h), _PILw.BILINEAR),
            dtype=np.float32,
        )
        del _tmp
        work_obs_row = max(0, min(ds_h - 1, int(round(work_obs_row * crop_scale))))
        work_obs_col = max(0, min(ds_w - 1, int(round(work_obs_col * crop_scale))))
        work_h, work_w = ds_h, ds_w

    work_px_size  = px_size / crop_scale
    work_radius_px = int(RADIUS_M / work_px_size)
    work_origin_e = (utm_transform.c + cc0 * utm_transform.a
                     + (0.5 * utm_transform.a * (1 - crop_scale)) / crop_scale)
    work_origin_n = (utm_transform.f + cr0 * utm_transform.e
                     + (0.5 * utm_transform.e * (1 - crop_scale)) / crop_scale)
    work_transform = Affine(work_px_size, 0.0, utm_transform.c + cc0 * px_size,
                            0.0, -work_px_size, utm_transform.f + cr0 * utm_transform.e)

    px_size    = work_px_size
    radius_px  = work_radius_px
    obs_row    = work_obs_row
    obs_col    = work_obs_col
    dem_height = work_h
    dem_width  = work_w

    radial_angles = np.linspace(0, 2 * np.pi, N_RADIALS, endpoint=False)

    if station_idx == 0:
        mem_mb = work_h * work_w * 4 / 1e6
        print(f"   Worker resolution: {work_w}×{work_h} px "
              f"@ {px_size:.0f} m/px  ({mem_mb:.0f} MB/worker)")

    coverage = np.zeros((dem_height, dem_width), dtype=np.float32)
    coverage[obs_row, obs_col] = MAX_MARGIN_DB

    dem_safe = work_dem.copy()
    dem_safe[dem_safe <= (full_nodata + 1)] = np.nan

    n_covered = 0
    n_rays    = 0

    def _extract_profile_vectorized(prof_rows, prof_cols):
        r0 = np.clip(prof_rows.astype(np.int32),     0, dem_height - 2)
        c0 = np.clip(prof_cols.astype(np.int32),     0, dem_width  - 2)
        dr = prof_rows - r0
        dc = prof_cols - c0
        vals = (dem_safe[r0,     c0]   * (1 - dr) * (1 - dc) +
                dem_safe[r0 + 1, c0]   * dr        * (1 - dc) +
                dem_safe[r0,     c0+1] * (1 - dr)  * dc       +
                dem_safe[r0 + 1, c0+1] * dr         * dc)
        nan_mask = np.isnan(vals)
        if nan_mask.any():
            for i in range(1, len(vals)):
                if nan_mask[i]:
                    vals[i] = vals[i - 1] if not np.isnan(vals[i - 1]) else obs_terrain_elev
        if np.isnan(vals[0]):
            vals[0] = obs_terrain_elev
        return vals.tolist()

    def _itm_loss_for_slice(profile_slice: list, dist_m: float) -> float:
        n_pts  = len(profile_slice)
        step_m = dist_m / max(n_pts - 1, 1)
        pfl    = [n_pts - 1, float(step_m)] + [float(v) for v in profile_slice]
        prop   = {
            'pfl':   pfl,
            'wn':    2.0 * math.pi * FREQ_MHZ * 1e6 / 299792458.0,
            'hg':    [float(ant_h), float(TARGET_H)],
            'ens':   ITM_ENS,
            'gme':   (1.0 / 6370e3) * (1.0 - 0.04665 * math.exp(0.005577 * ITM_ENS)),
            'zgnd':  complex(ITM_EPSR, -18000.0 * ITM_SGM / FREQ_MHZ),
            'he':    [0.0, 0.0], 'dl':  [0.0, 0.0], 'the': [0.0, 0.0],
            'dh':    0.0,        'dist': 0.0,
            'kwx':   0,          'mdp': -1,
            'dlsa':  0.0, 'dx':  0.0, 'tha': 0.0, 'dbxa': 0.0, 'xae': 0.0,
            'sgc':   0.0,
            'lvar': 5,  'mdvar': 1,  'klim': ITM_CLIMATE,
            'kdv': -1,  'mdvarx': -1,  'klimx': -1,
        }
        qlrpfl(prop)
        result = avar(0.0, 0.0, 0.0, prop)
        aref = result[0] if isinstance(result, tuple) else result
        
        # ── FSPL MATH FIX INCLUDED HERE ──────────────────────────────────────
        fspl = 32.45 + 20.0 * math.log10(max(dist_m, 1.0) / 1000.0) + 20.0 * math.log10(FREQ_MHZ)
        
        return fspl + aref

    for angle in radial_angles:
        end_col = obs_col + radius_px * np.sin(angle)
        end_row = obs_row - radius_px * np.cos(angle)

        n_steps   = max(int(radius_px), 2)
        step_cols = np.linspace(obs_col, end_col, n_steps + 1)[1:]
        step_rows = np.linspace(obs_row, end_row, n_steps + 1)[1:]

        n_profile_pts = min(1200, n_steps + 1)
        prof_cols     = np.linspace(obs_col, end_col, n_profile_pts)
        prof_rows     = np.linspace(obs_row, end_row, n_profile_pts)

        terrain_profile = _extract_profile_vectorized(prof_rows, prof_cols)

        ray_dist_m  = math.sqrt((end_col - obs_col)**2 +
                                 (end_row - obs_row)**2) * px_size
        distance_km = ray_dist_m / 1000.0

        if distance_km < 0.1:
            continue

        n_prof = len(terrain_profile)

        min_dist_m    = max(500.0, ray_dist_m * 0.01)
        n_near        = max(3, N_MARGIN_SAMPLES // 3)
        n_far         = N_MARGIN_SAMPLES - n_near
        near_dists    = np.linspace(min_dist_m,
                                    ray_dist_m * 0.20, n_near + 1)[1:]
        far_dists     = np.linspace(ray_dist_m * 0.20,
                                    ray_dist_m, n_far + 1)[1:]
        sample_dists  = np.concatenate([near_dists, far_dists])

        sample_margins   = np.empty(len(sample_dists), dtype=np.float32)
        _first_itm_error = None   
        for si, sdist_m in enumerate(sample_dists):
            frac           = sdist_m / ray_dist_m
            n_pts_slice    = max(2, int(frac * n_prof))
            profile_slice  = terrain_profile[:n_pts_slice]
            try:
                if ITM_AVAILABLE and sdist_m >= 500.0:
                    loss = _itm_loss_for_slice(profile_slice, sdist_m)
                else:
                    geo_ok = _geometric_los_check(
                        profile_slice, ant_h, TARGET_H,
                        CURVATURE_COEFF, sdist_m)
                    loss = (MAX_LOSS_DB - 20.0) if geo_ok else (MAX_LOSS_DB + 30.0)
                sample_margins[si] = MAX_LOSS_DB - loss
            except Exception as _e:
                sample_margins[si] = MARGIN_FLOOR_DB - 1.0
                if _first_itm_error is None:
                    _first_itm_error = _e   

        if sample_margins.max() < MARGIN_FLOOR_DB:
            if n_rays == 0 and angle == radial_angles[0]:
                if _first_itm_error is not None:
                    print(f"   ⚠  {callsign} ITM exception on radial 0: "
                          f"{type(_first_itm_error).__name__}: {_first_itm_error}")
                else:
                    print(f"   ℹ  {callsign} radial 0: no exception — "
                          f"ITM computed margins {sample_margins.tolist()[:5]}... "
                          f"max={sample_margins.max():.1f} dB < floor={MARGIN_FLOOR_DB} dB")
            continue
        n_rays += 1

        step_dists     = np.linspace(0.0, ray_dist_m, n_steps + 2)[1:-1]
        margins_interp = np.interp(step_dists, sample_dists,
                                   sample_margins).astype(np.float32)

        paint_mask = margins_interp > MARGIN_FLOOR_DB
        if not paint_mask.any():
            continue

        rows_int  = np.clip(np.round(step_rows).astype(np.int32),
                            0, dem_height - 1)
        cols_int  = np.clip(np.round(step_cols).astype(np.int32),
                            0, dem_width  - 1)
        flat_idx  = rows_int * dem_width + cols_int
        np.maximum.at(coverage.ravel(),
                      flat_idx[paint_mask],
                      margins_interp[paint_mask])

        if (sample_margins > 0).any():
            n_covered += 1

    try:
        from scipy.ndimage import maximum_filter, gaussian_filter

        half_radius_px = radius_px / 2.0
        gap_px         = (2.0 * math.pi * half_radius_px / N_RADIALS)
        fill_r         = max(2, int(round(gap_px * GAP_FILL_FACTOR * 0.5)))
        diam           = fill_r * 2 + 1

        filled   = maximum_filter(coverage, size=diam)
        gap_mask = coverage == 0
        coverage = np.where(gap_mask, filled, coverage).astype(np.float32)
        del filled

        coverage[coverage == 0.0] = -1.0

        pre_gaussian_nodata = (coverage <= -0.9)
        sigma    = max(1.0, fill_r * 0.6)
        coverage = gaussian_filter(coverage, sigma=sigma).astype(np.float32)
        coverage[pre_gaussian_nodata] = -1.0

    except ImportError:
        coverage[coverage == 0.0] = -1.0
        pass  

    NODATA_SENTINEL = -1.0
    coverage[coverage < MARGIN_FLOOR_DB] = NODATA_SENTINEL
    coverage = np.clip(coverage, NODATA_SENTINEL, MAX_MARGIN_DB)

    vs_meta = {
        "driver":    "GTiff", "dtype": "float32",
        "width":     dem_width, "height": dem_height, "count": 1,
        "crs":       CRS.from_string(dem_crs_str),
        "transform": work_transform,
        "nodata":    -1.0, "compress": "lzw",
    }
    with rasterio.open(vs_path, "w", **vs_meta) as dst:
        dst.write(coverage, 1)

    try:
        with rasterio.open(vs_path) as _v:
            _wt = _v.transform
            from rasterio.transform import Affine as _Afv
            if _wt == _Afv.identity() or _wt.a == 0.0:
                print(f"\n   ⚠⚠  {callsign}: TIF written but geotransform is "
                      f"IDENTITY — rasterio/GDAL write did not flush metadata.\n"
                      f"      Expected transform: {work_transform}\n"
                      f"      Try: pip install --upgrade rasterio  or downgrade "
                      f"to Python 3.12 if you are running 3.14-pre-release.")
    except Exception:
        pass  

    engine = "ITM" if ITM_AVAILABLE else "geo"
    pct    = 100 * n_covered / max(n_rays, 1)

    if n_covered == 0 and n_rays > 0:
        r0 = max(0, obs_row - 2); r1 = min(dem_height, obs_row + 3)
        c0 = max(0, obs_col - 2); c1 = min(dem_width,  obs_col + 3)
        hood = work_dem[r0:r1, c0:c1].astype(np.float32).copy()
        hood[hood <= (full_nodata + 1)] = np.nan
        hood[np.isnan(work_dem[r0:r1, c0:c1])] = np.nan
        hood[obs_row - r0, obs_col - c0] = np.nan   
        valid_hood = hood[~np.isnan(hood)]
        nbr_median = float(np.median(valid_hood)) if valid_hood.size >= 4 else float('nan')
        pit_drop   = nbr_median - obs_terrain_elev

        first_angle  = 0.0
        fe_col = obs_col + radius_px * math.sin(first_angle)
        fe_row = obs_row - radius_px * math.cos(first_angle)
        fp_cols = np.linspace(obs_col, fe_col, min(600, max(int(radius_px), 2) + 1))
        fp_rows = np.linspace(obs_row, fe_row, min(600, max(int(radius_px), 2) + 1))
        first_profile = []
        for pr, pc in zip(fp_rows, fp_cols):
            rr = int(max(0, min(pr, dem_height - 2)))
            cc = int(max(0, min(pc, dem_width  - 2)))
            dr = pr - rr; dc = pc - cc
            v  = (dem_safe[rr,     cc]   * (1 - dr) * (1 - dc) +
                  dem_safe[rr + 1, cc]   * dr        * (1 - dc) +
                  dem_safe[rr,     cc+1] * (1 - dr)  * dc       +
                  dem_safe[rr + 1, cc+1] * dr         * dc)
            if v == full_nodata or np.isnan(v):
                v = first_profile[-1] if first_profile else obs_terrain_elev
            first_profile.append(float(v))
        fe_dist_m = math.sqrt((fe_col - obs_col)**2 + (fe_row - obs_row)**2) * px_size
        itm_diag = "n/a (ITM not available)"
        if ITM_AVAILABLE and fe_dist_m >= 500:
            try:
                from itmlogic.preparatory_subroutines.qlrpfl import qlrpfl
                from itmlogic.statistics.avar import avar
                n_pts  = len(first_profile)
                step_m = fe_dist_m / max(n_pts - 1, 1)
                pfl_d  = [n_pts - 1, float(step_m)] + [float(v) for v in first_profile]
                prop_d = {
                    'pfl':   pfl_d,
                    'wn':    2.0 * math.pi * FREQ_MHZ * 1e6 / 299792458.0,
                    'hg':    [float(ant_h), float(TARGET_H)],
                    'ens':   ITM_ENS,
                    'gme':   (1.0 / 6370e3) * (1.0 - 0.04665 * math.exp(0.005577 * ITM_ENS)),
                    'zgnd':  complex(ITM_EPSR, -18000.0 * ITM_SGM / FREQ_MHZ),
                    'he':    [0.0, 0.0], 'dl':  [0.0, 0.0], 'the': [0.0, 0.0],
                    'dh':    0.0,        'dist': 0.0,
                    'kwx':   0,          'mdp': -1,
                    'dlsa':  0.0, 'dx':  0.0, 'tha': 0.0, 'dbxa': 0.0, 'xae': 0.0,
                    'sgc':   0.0, 'lvar': 5,  'mdvar': 1,  'klim': ITM_CLIMATE,
                    'kdv': -1,  'mdvarx': -1,  'klimx': -1,
                }
                qlrpfl(prop_d)
                _loss_raw = avar(0.0, 0.0, 0.0, prop_d)
                aref      = _loss_raw[0] if isinstance(_loss_raw, tuple) else _loss_raw
                
                # ── FSPL DIAGNOSTIC FIX INCLUDED HERE ────────────────────────
                fspl_d    = 32.45 + 20.0 * math.log10(max(fe_dist_m, 1.0) / 1000.0) + 20.0 * math.log10(FREQ_MHZ)
                loss_val  = fspl_d + aref
                
                itm_diag  = f"{loss_val:.1f} dB  (threshold {MAX_LOSS_DB} dB)"
            except Exception as exc:
                itm_diag = f"error: {exc}"

        print(
            f"\n   ⚠⚠  ZERO COVERAGE — {callsign}\n"
            f"      Coordinates    : lat={station['lat']:.5f}  lon={station['lon']:.5f}\n"
            f"      Station type   : {station.get('type','?')}\n"
            f"      DEM elevation  : {obs_terrain_elev:.1f} m\n"
            f"      Neighbour med  : {nbr_median:.1f} m\n"
            f"      Pit drop       : {pit_drop:.1f} m  "
            f"({'⚠ likely DEM pit' if pit_drop > 40 else 'OK'})\n"
            f"      Antenna height : {ant_h:.1f} m (TX)  /  {TARGET_H:.1f} m (RX)\n"
            f"      ITM loss (N)   : {itm_diag}\n"
            f"      Hint: if DEM pit, delete the cached TIF and verify coordinates.\n"
        )

    try:
        _worker_shm.close()
    except Exception:
        pass

    return (station, str(vs_path),
            f"{engine} ✅  {n_covered}/{max(n_rays,1)} radials ({pct:.0f}%)",
            n_covered, n_rays, station_idx)

def _geometric_los_check(profile, ant_h, target_h, curvature_coeff,
                         ray_dist_m=None):
    """Curvature-corrected geometric LOS (CPU fallback when ITM unavailable)."""
    R_EARTH = 6_371_000.0
    n = len(profile)
    if n < 2:
        return True
    total_m      = ray_dist_m if ray_dist_m is not None else float(n - 1)
    obs_elev     = profile[0] + ant_h
    tgt_elev     = profile[-1] + target_h
    max_blockage = -1e9
    for k in range(1, n - 1):
        d         = k / (n - 1)
        d_m       = d * total_m
        curv      = (d_m * (total_m - d_m)) * curvature_coeff / (2.0 * R_EARTH)
        terrain_h = profile[k] + curv
        los_h     = obs_elev + d * (tgt_elev - obs_elev)
        if terrain_h - los_h > max_blockage:
            max_blockage = terrain_h - los_h
    return max_blockage <= 0


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE STAGES
# ═══════════════════════════════════════════════════════════════════════════════

def install_deps():
    """Auto-install required packages."""
    packages = [
        "itmlogic", "rasterio", "numpy", "Pillow",
        "pyproj", "tqdm", "scipy", "requests"
    ]
    try:
        import tqdm as _t  # noqa: F401
    except ImportError:
        print("   Installing tqdm...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "tqdm", "-q"])

    from tqdm import tqdm
    with tqdm(packages, unit="pkg", ncols=70, colour="cyan",
              bar_format="   {l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]"
              ) as pbar:
        for pkg in pbar:
            pbar.set_postfix_str(pkg, refresh=True)
            try:
                __import__(pkg.lower().replace("-", "_").split("[")[0])
            except ImportError:
                pbar.write(f"   Installing {pkg}...")
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg, "-q"])
    print("   ✅ All dependencies ready.")


def load_stations(path: str, cfg: dict) -> tuple:
    """Load and validate stations from JSON."""
    with open(path) as f:
        raw = json.load(f)

    raw = [s for s in raw if s.get("type") in cfg["include_types"]]

    seed_only = [s for s in raw if s.get('_seed_only')]
    if seed_only:
        print(f"   ⚠  {len(seed_only)} station(s) have UNCONFIRMED seed coordinates "
              f"(never heard on-air — position may be wrong):")
        for s in seed_only:
            print(f"      {s['callsign']:<12} lat={s['lat']:.5f} lon={s['lon']:.5f}  "
                  f"← seed-list only, not verified by live beacon")
        print(f"      Tip: set APRSDOTFI_API_KEY in the scraper, or add overrides "
              f"to coordinate_overrides in CONFIG.")

    overrides = cfg.get("coordinate_overrides", {})
    if overrides:
        for s in raw:
            if s.get("callsign") in overrides:
                fix = overrides[s["callsign"]]
                old_lat, old_lon = s.get("lat"), s.get("lon")
                s["lat"] = fix["lat"]
                s["lon"] = fix["lon"]
                print(f"   📍 Coordinate override: {s['callsign']} "
                      f"({old_lat:.5f}, {old_lon:.5f}) → "
                      f"({fix['lat']:.5f}, {fix['lon']:.5f})")

    valid = []
    for s in raw:
        lat, lon = s.get("lat"), s.get("lon")
        if lat is None or lon is None:
            continue
        if not (36.5 <= lat <= 42.5 and -115.0 <= lon <= -108.5):
            print(f"   ⚠  Skipping {s['callsign']} -- outside Utah region "
                  f"({lat:.4f}, {lon:.4f})")
            continue
        valid.append(s)

    from collections import defaultdict
    loc_groups = defaultdict(list)
    for s in valid:
        loc_key = (round(s["lat"], 4), round(s["lon"], 4))
        loc_groups[loc_key].append(s["callsign"])

    colocation_map = {}   
    for members in loc_groups.values():
        canonical = sorted(members)[0]
        for m in members:
            colocation_map[m] = canonical

    shared_sites = {k: v for k, v in loc_groups.items() if len(v) > 1}
    if shared_sites:
        print(f"   Co-located station groups ({len(shared_sites)} sites):")
        for (lat, lon), members in sorted(shared_sites.items()):
            canonical = colocation_map[members[0]]
            aliases   = [m for m in sorted(members) if m != canonical]
            print(f"      {canonical} (canonical) + {', '.join(aliases)}"
                  f"  @ ({lat:.4f}, {lon:.4f})")
        print(f"   Viewshed will be computed once per site and shared.")

    n_unique_sites = len(set(colocation_map.values()))
    print(f"   Loaded {len(valid)} stations "
          f"({len(shared_sites)} co-located sites, "
          f"{n_unique_sites} unique viewshed computations needed).")
    return valid, colocation_map


def prepare_dem(stations: list, cfg: dict, work_dir: Path) -> Path:
    """Build a merged, cached DEM from local 1-arcsecond tiles.
    Automatically downloads missing tiles from the USGS API."""
    import rasterio
    from rasterio.merge import merge as rio_merge
    from rasterio.crs import CRS
    import numpy as np
    import requests
    import zipfile
    import io
    import time
    import json

    cache_dir_name = cfg.get("dem_cache_dir", "dem_cache")
    script_root    = Path(__file__).parent
    dem_cache      = script_root / cache_dir_name
    dem_cache.mkdir(exist_ok=True)

    print(f"   DEM cache: {dem_cache}")

    lats = [s["lat"] for s in stations]
    lons = [s["lon"] for s in stations]
    margin_deg = max(1.0, math.ceil(cfg.get("max_radius_km", 80) / 111.0))

    lat_min = min(lats) - margin_deg;  lat_max = max(lats) + margin_deg
    lon_min = min(lons) - margin_deg;  lon_max = max(lons) + margin_deg

    lon_w_min = math.ceil(abs(lon_max))   
    lon_w_max = math.ceil(abs(lon_min))   
    lat_n_min = math.ceil(lat_min)
    lat_n_max = math.ceil(lat_max)

    needed_tiles = [
        (lat_n, lon_w)
        for lat_n in range(lat_n_min, lat_n_max + 1)
        for lon_w in range(lon_w_min, lon_w_max + 1)
    ]
    tile_names = [f"n{lt:02d}w{lw:03d}" for lt, lw in needed_tiles]

    dem_path    = work_dir / "utah_dem.tif"
    bounds_path = work_dir / "utah_dem_bounds.json"

    if dem_path.exists() and bounds_path.exists():
        try:
            with open(bounds_path) as bf:
                cached = json.load(bf)
            if (set(cached.get("tiles", [])) == set(tile_names)
                    and dem_path.stat().st_size > 0):
                sz = dem_path.stat().st_size / 1e6
                print(f"   ✅ DEM cached  ({sz:.0f} MB, {len(tile_names)} tiles) -- skipping merge")
                return dem_path
            else:
                print("   ⚠  Cached DEM covers a different tile set -- rebuilding.")
                dem_path.unlink(missing_ok=True)
                bounds_path.unlink(missing_ok=True)
                (work_dir / "utah_dem_utm.tif").unlink(missing_ok=True)
        except Exception:
            dem_path.unlink(missing_ok=True)
            bounds_path.unlink(missing_ok=True)
            (work_dir / "utah_dem_utm.tif").unlink(missing_ok=True)
    elif dem_path.exists():
        print("   ⚠  DEM exists but no bounds record -- rebuilding.")
        dem_path.unlink(missing_ok=True)
        (work_dir / "utah_dem_utm.tif").unlink(missing_ok=True)

    print(f"   Region: lat {lat_min:.1f} to {lat_max:.1f}, lon {lon_min:.1f} to {lon_max:.1f}")
    print(f"   Tiles required: {len(tile_names)}")

    USGS_API_URL = "https://tnmaccess.nationalmap.gov/api/v1/products"
    
    def download_tile(lat, lon):
        local_tif_path = dem_cache / f"n{lat}w{lon}.tif"
        if local_tif_path.exists():
            return local_tif_path
            
        bbox_str = f"{-(lon+1)},{lat-1},-{lon},{lat}"
        params = {
            'datasets': 'National Elevation Dataset (NED) 1 arc-second',
            'bbox': bbox_str,
            'prodFormats': 'GeoTIFF,TIFF'
        }
        
        for attempt in range(3):
            try:
                print(f"   Downloading N{lat} W{lon} (Attempt {attempt+1})...")
                r = requests.get(USGS_API_URL, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()

                if not data.get('items'):
                    params['datasets'] = '3DEP 1 arc-second'
                    r = requests.get(USGS_API_URL, params=params, timeout=30)
                    data = r.json()

                if data.get('items'):
                    download_url = data['items'][0]['downloadURL']
                    
                    with requests.get(download_url, stream=True, timeout=60) as r_dl:
                        r_dl.raise_for_status()
                        if download_url.lower().endswith('.zip') or 'application/zip' in r_dl.headers.get('Content-Type', ''):
                            z = zipfile.ZipFile(io.BytesIO(r_dl.content))
                            tif_name = next((name for name in z.namelist() if name.lower().endswith('.tif')), None)
                            if tif_name:
                                with open(local_tif_path, 'wb') as f:
                                    f.write(z.read(tif_name))
                                return local_tif_path
                        else:
                            with open(local_tif_path, 'wb') as f:
                                for chunk in r_dl.iter_content(chunk_size=16384):
                                    f.write(chunk)
                            return local_tif_path
            except Exception as e:
                print(f"      API issue: {e}")
                time.sleep(2)
        
        raise RuntimeError(f"Could not download tile N{lat} W{lon} from USGS API.")

    tile_paths = []
    for lat_n, lon_w in needed_tiles:
        tp = download_tile(lat_n, lon_w)
        tile_paths.append(tp)
        time.sleep(0.5)

    print(f"   Merging {len(tile_paths)} tile(s)...", end=" ", flush=True)
    t_m = time.perf_counter()

    TILE_NODATA = -999999.0
    datasets = []
    for p in sorted(tile_paths):
        ds = rasterio.open(p)
        nd = ds.nodata
        if nd is not None and abs(float(nd) - TILE_NODATA) > 1:
            TILE_NODATA = float(nd)
        datasets.append(ds)

    mosaic, mosaic_tf = rio_merge(datasets, nodata=TILE_NODATA)
    for ds in datasets:
        ds.close()

    ref_ds      = rasterio.open(tile_paths[0])
    ref_profile = ref_ds.profile.copy()
    ref_ds.close()
    ref_profile.update(
        driver     = "GTiff",
        height     = mosaic.shape[1],
        width      = mosaic.shape[2],
        transform  = mosaic_tf,
        dtype      = "float32",
        nodata     = TILE_NODATA,
        compress   = "lzw",
        count      = 1,
        tiled      = True,
        blockxsize = 512,
        blockysize = 512,
    )
    if not ref_profile.get("crs"):
        ref_profile["crs"] = CRS.from_epsg(4269)

    with rasterio.open(dem_path, "w", **ref_profile) as dst:
        dst.write(mosaic[0].astype(np.float32), 1)

    size_mb = dem_path.stat().st_size / 1e6
    print(f"done ✅  ({size_mb:.0f} MB, {_elapsed(t_m)})")

    with open(bounds_path, "w") as bf:
        json.dump({
            "tiles"            : sorted(tile_names),
            "tiles_found"      : sorted(p.name for p in tile_paths),
            "lat_min"          : lat_min,
            "lat_max"          : lat_max,
            "lon_min"          : lon_min,
            "lon_max"          : lon_max,
            "nodata"           : TILE_NODATA,
            "crs"              : "EPSG:4269",
            "resolution_arcsec": 1.0,
        }, bf, indent=2)

    return dem_path


def compute_viewsheds(stations: list, dem_path: Path, cfg: dict,
                      work_dir: Path,
                      colocation_map: dict = None) -> list:
    """Distribute viewshed computation across all CPU cores."""
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    import numpy as np
    from pyproj import Transformer
    from tqdm import tqdm

    dem_utm_path = work_dir / "utah_dem_utm.tif"
    if not dem_utm_path.exists():
        print("   Reprojecting DEM to UTM 12N...", end=" ", flush=True)
        t_proj = time.perf_counter()
        dst_crs = "EPSG:32612"
        with rasterio.open(dem_path) as src:
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds)
            profile = src.profile.copy()
            profile.update(crs=dst_crs, transform=transform, width=width,
                           height=height, nodata=-9999, dtype="float32",
                           compress="lzw")
            with rasterio.open(dem_utm_path, "w", **profile) as dst:
                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_transform=src.transform, src_crs=src.crs,
                    dst_transform=transform, dst_crs=dst_crs,
                    resampling=Resampling.bilinear,
                    src_nodata=src.nodata, dst_nodata=-9999,
                )
        print(f"done ✅  ({_elapsed(t_proj)})")
    else:
        print("   UTM DEM cached ✅")

    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32612", always_xy=True)

    with rasterio.open(dem_utm_path) as ref:
        utm_transform = ref.transform
        px_size       = abs(utm_transform.a)
        full_nodata   = ref.nodata if ref.nodata is not None else -9999
        dem_full      = ref.read(1).astype(np.float32)
        dem_crs       = ref.crs
        dem_height    = ref.height
        dem_width     = ref.width

    utm_tf_tuple = (utm_transform.a, utm_transform.b, utm_transform.c,
                    utm_transform.d, utm_transform.e, utm_transform.f)
    dem_crs_str  = dem_crs.to_wkt()

    n_workers = cfg.get("cpu_workers") or os.cpu_count() or 4
    total     = len(stations)
    N_RADIALS = cfg["n_radials"]

    max_loss = _resolve_max_path_loss(cfg)
    cfg["_resolved_max_loss_db"] = max_loss

    print(f"\n   Engine:  itmlogic Longley-Rice ITM (CPU — full accuracy)")
    print(f"   Workers: {n_workers} CPU processes")
    print(f"   DEM:     {dem_width}×{dem_height} px @ {px_size:.1f} m/px")
    print(f"   Radials: {N_RADIALS}/station × {total} stations "
          f"= {N_RADIALS*total:,} ITM calls")
    print(f"   Max path loss: {max_loss:.1f} dB\n")

    colo_map = colocation_map or {}

    _elev_min   = cfg.get("elev_min_m", 800.0)
    _elev_max   = cfg.get("elev_max_m", 4200.0)
    _pit_thresh = cfg.get("elev_pit_threshold_m", 40.0)

    def _check_elevation(callsign, row, col, elev):
        warns = []
        if elev < _elev_min:
            warns.append(
                f"   ⚠  {callsign:<12} elevation {elev:.0f} m is BELOW "
                f"minimum expected ({_elev_min:.0f} m) — possible DEM "
                f"void or bad coordinate"
            )
        elif elev > _elev_max:
            warns.append(
                f"   ⚠  {callsign:<12} elevation {elev:.0f} m is ABOVE "
                f"maximum expected ({_elev_max:.0f} m) — possible DEM error"
            )

        if _pit_thresh is not None:
            r0 = max(0, row - 2);  r1 = min(dem_height, row + 3)
            c0 = max(0, col - 2);  c1 = min(dem_width,  col + 3)
            hood = dem_full[r0:r1, c0:c1].copy().astype(np.float32)
            hood[hood <= (full_nodata + 1)] = np.nan
            hood[row - r0, col - c0] = np.nan   
            valid = hood[~np.isnan(hood)]
            if valid.size >= 4:
                median_elev = float(np.median(valid))
                drop = median_elev - elev
                if drop > _pit_thresh:
                    warns.append(
                        f"   ⚠  {callsign:<12} DEM pit — station "
                        f"cell is {drop:.0f} m below neighbourhood median "
                        f"({elev:.0f} m vs {median_elev:.0f} m).  "
                        f"Antenna may appear underground; expect 0 radials.  "
                        f"Verify coordinates or clear the viewshed cache."
                    )
        return warns

    from multiprocessing.shared_memory import SharedMemory
    _shm = SharedMemory(create=True, size=int(dem_full.nbytes))
    _shm_array = np.ndarray(dem_full.shape, dtype=dem_full.dtype, buffer=_shm.buf)
    np.copyto(_shm_array, dem_full)
    _dem_shm_info = {
        "shm_name": _shm.name,
        "shape":    dem_full.shape,
        "dtype":    str(dem_full.dtype),
    }
    print(f"   DEM in shared memory: {dem_full.nbytes / 1e9:.2f} GB "
          f"(block: {_shm.name})")

    try:
        job_args = []
        skipped  = []
        for i, station in enumerate(stations):
            obs_east, obs_north = to_utm.transform(station["lon"], station["lat"])
            obs_col = int((obs_east  - utm_transform.c) / utm_transform.a)
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

            for warn in _check_elevation(station["callsign"], obs_row, obs_col, obs_terrain):
                print(warn)

            job_args.append((
                station, _dem_shm_info, utm_tf_tuple, dem_crs_str,
                dem_height, dem_width, cfg, str(work_dir),
                obs_row, obs_col, obs_terrain, i, total,
            ))

        canonical_calls = {a[0]["callsign"] for a in job_args
                           if colo_map.get(a[0]["callsign"], a[0]["callsign"])
                           == a[0]["callsign"]}

        primary_args  = [a for a in job_args
                         if a[0]["callsign"] in canonical_calls]
        deferred      = [a for a in job_args
                         if a[0]["callsign"] not in canonical_calls]

        n_deferred = len(deferred)
        if n_deferred:
            print(f"   Co-location: {n_deferred} station(s) will share "
                  f"a canonical viewshed TIF (no duplicate ITM work).")

        results    = []
        print_lock = threading.Lock()
        ctx        = _mp.get_context("spawn")
        t_dispatch = time.perf_counter()

        bar_fmt = ("   {l_bar}{bar}| {n_fmt}/{total_fmt} stations "
                   "[{elapsed}<{remaining}, {rate_fmt}]")

        with tqdm(total=len(primary_args), unit="stn", ncols=72, colour="green",
                  bar_format=bar_fmt) as pbar:
            with ProcessPoolExecutor(max_workers=n_workers, mp_context=ctx) as pool:
                futures = {pool.submit(_process_station, a): a[0]["callsign"]
                           for a in primary_args}

                for fut in as_completed(futures):
                    callsign_orig = futures[fut]
                    try:
                        (station_ret, vs_path_str, status,
                         n_cov, n_ray, idx) = fut.result()
                        ant_h = (cfg["antenna_height_digi_m"]
                                 if station_ret["type"] == "digi"
                                 else cfg["antenna_height_igate_m"])
                        line = (f"   [{idx+1:3d}/{total}] "
                                f"{station_ret['callsign']:<12} "
                                f"({station_ret['type']:<5}) "
                                f"ant={ant_h:.0f}m  {status}")
                        with print_lock:
                            pbar.write(line)
                            pbar.update(1)
                        if vs_path_str:
                            results.append((station_ret, Path(vs_path_str), idx))
                    except Exception as exc:
                        with print_lock:
                            pbar.write(f"   ❌ Worker failed for "
                                       f"{callsign_orig}: {exc}")
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
                safe_call = callsign.replace("-","_").replace("/","_").replace(" ","_")
                fallback_tif = work_dir / f"viewshed_{safe_call}.tif"
                if fallback_tif.exists():
                    results.append((station, fallback_tif, args[12]))
                    print(f"   [COLO] {callsign:<12} canonical missing, using cached TIF")
                else:
                    print(f"   ⚠  {callsign:<12} co-location fallback: "
                          f"canonical '{canon}' had no TIF, running solo ITM")
                    try:
                        ret = _process_station(args)
                        _, vs_str, status, _, _, idx = ret
                        if vs_str:
                            results.append((station, Path(vs_str), idx))
                    except Exception as exc:
                        print(f"   ❌ Solo ITM failed for {callsign}: {exc}")

        results.sort(key=lambda r: r[2])
        results = [(s, p) for s, p, _ in results]

        n_computed = len(primary_args)
        n_shared   = len(deferred)
        rate = n_computed / max((time.perf_counter() - t_dispatch) / 60, 0.01)
        print(f"\n   ✅ {len(results)}/{total} stations resolved  "
              f"({n_computed} ITM computed, {n_shared} shared, "
              f"{len(skipped)} skipped)  --  {rate:.1f} ITM/min")

    finally:
        try:
            _shm.close()
            _shm.unlink()
        except Exception:
            pass

    return results


# ───────────────────────────────────────────────────────────────────────────
# RASTER HELPERS  (CPU / numpy only)
# ───────────────────────────────────────────────────────────────────────────

def _colorize(data: "np.ndarray", cfg: dict, station_type: str = None):
    """Convert a coverage array to an RGBA uint8 image."""
    import numpy as np

    alpha       = int(cfg["overlay_alpha"])
    floor_db    = float(cfg.get("margin_display_floor_db", -6.0))
    max_db      = float(cfg.get("max_margin_db", 30.0))
    d           = np.asarray(data, dtype=np.float32)
    h, w        = d.shape
    rgba        = np.zeros((h, w, 4), dtype=np.uint8)

    margin_mode = (station_type is not None) and (d.max() > 1.5)

    if margin_mode:
        NODATA = -1.0
        visible = d > NODATA
        if not np.any(visible):
            return rgba

        m = d[visible]   
        norm = np.clip((m - floor_db) / (max_db - floor_db), 0.0, 1.0)

        if station_type == "digi":
            # Digi: dim green → bright neon lime (excellent contrast for red rock)
            r = np.clip( 40 -  40 * norm,      0, 255).astype(np.uint8)
            g = np.clip(120 + 135 * norm,      0, 255).astype(np.uint8)
            b = np.clip( 40 -  40 * norm,      0, 255).astype(np.uint8)
        else:
            r = np.clip( 80 -  80 * norm,      0, 255).astype(np.uint8)
            g = np.clip(160 - 130 * norm,      0, 255).astype(np.uint8)
            b = np.clip(200 +  55 * norm,      0, 255).astype(np.uint8)

        alpha_scale = np.clip(0.3 + 0.7 * (norm / 0.6), 0.0, 1.0)
        a = np.clip(alpha * alpha_scale, 0, 255).astype(np.uint8)

        rgba[visible, 0] = r
        rgba[visible, 1] = g
        rgba[visible, 2] = b
        rgba[visible, 3] = a

    else:
        visible = d > 0.5
        if not np.any(visible):
            return rgba

        max_val = float(d.max()) if d.max() > 0 else 1.0
        norm    = d[visible] / max_val

        if cfg["color_scheme"] == "hot":
            rgba[visible, 0] = np.clip(128 + 127 * norm, 0, 255).astype(np.uint8)
            rgba[visible, 1] = np.clip(220 - 220 * norm, 0, 255).astype(np.uint8)
            rgba[visible, 2] = 0
        else:
            rgba[visible, 0] = 0
            rgba[visible, 1] = np.clip(200 - 150 * norm, 0, 255).astype(np.uint8)
            rgba[visible, 2] = np.clip(100 + 155 * norm, 0, 255).astype(np.uint8)
        rgba[visible, 3] = alpha

    return rgba


def _colorize_batch(data_list: list, station_types: list, cfg: dict):
    if not data_list:
        return []
    return [_colorize(d, cfg, st) for d, st in zip(data_list, station_types)]


def _binary_closing(mask: "np.ndarray", k: int):
    import numpy as np
    try:
        from scipy.ndimage import binary_closing
        struct = np.ones((2*k+1, 2*k+1), dtype=bool)
        return binary_closing(mask > 0.5, structure=struct)
    except ImportError:
        return mask > 0.5   


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — merge_viewsheds
# ─────────────────────────────────────────────────────────────────────────────

def merge_viewsheds(results: list, dem_path: Path, work_dir: Path, cfg: dict = None):
    import rasterio
    from rasterio.warp import reproject, Resampling, transform_bounds
    from rasterio.windows import (from_bounds as _win_from_bounds,
                                   transform  as _win_tf, Window)
    from rasterio.transform import Affine
    import numpy as np
    import math
    from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed
    from tqdm import tqdm

    cfg        = cfg or CONFIG
    STN_MAX_PX = int(cfg.get("stn_tif_max_px", 2048))
    n_workers  = min(len(results), os.cpu_count() or 4)

    print(f"   Merging {len(results)} viewshed rasters "
          f"(windowed reproject, {n_workers} threads, "
          f"TIF cap {STN_MAX_PX} px)...")

    with rasterio.open(dem_path) as ref:
        ref_profile   = ref.profile.copy()
        ref_transform = ref.transform
        ref_crs       = ref.crs
        ref_shape     = (ref.height, ref.width)

    t_acc    = time.perf_counter()
    coverage = np.zeros(ref_shape, dtype=np.int16)

    def _process_one(station_vs):
        station, vs_path = station_vs
        callsign = station["callsign"]
        safe     = callsign.replace("-","_").replace("/","_").replace(" ","_")
        tif_key  = str(vs_path.resolve())

        with rasterio.open(vs_path) as src:
            dst_bnds = transform_bounds(src.crs, ref_crs, *src.bounds)
            win_f    = _win_from_bounds(*dst_bnds, transform=ref_transform)
            col_off  = max(0, int(math.floor(win_f.col_off)))
            row_off  = max(0, int(math.floor(win_f.row_off)))
            col_end  = min(ref_shape[1],
                           int(math.ceil(win_f.col_off + win_f.width)))
            row_end  = min(ref_shape[0],
                           int(math.ceil(win_f.row_off + win_f.height)))
            win_h    = row_end - row_off
            win_w    = col_end - col_off

            if win_h <= 0 or win_w <= 0:
                return callsign, tif_key, None, 0, 0, 0, 0, None

            win    = Window(col_off=col_off, row_off=row_off,
                            width=win_w, height=win_h)
            win_tf = _win_tf(win, ref_transform)

            vs_reproj = np.full((win_h, win_w), -1.0, dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=vs_reproj,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=win_tf,
                dst_crs=ref_crs,
                resampling=Resampling.bilinear,
                src_nodata=-1.0, dst_nodata=-1.0,
            )

        mask = (vs_reproj > 0).astype(np.uint8)

        scale = (min(1.0, STN_MAX_PX / max(win_h, win_w))
                 if STN_MAX_PX > 0 else 1.0)
        if scale < 0.999:
            from PIL import Image as _PIL
            out_h = max(1, int(round(win_h * scale)))
            out_w = max(1, int(round(win_w * scale)))
            _tmp = vs_reproj.copy()
            _tmp[_tmp < -0.5] = float("nan")
            vs_small = np.array(
                _PIL.fromarray(_tmp).resize((out_w, out_h), _PIL.BILINEAR),
                dtype=np.float32,
            )
            vs_small[np.isnan(vs_small)] = -1.0
            out_tf = Affine(win_tf.a / scale, 0.0, win_tf.c,
                            0.0, win_tf.e / scale, win_tf.f)
        else:
            vs_small = vs_reproj
            out_h, out_w, out_tf = win_h, win_w, win_tf

        stn_path = work_dir / f"station_{safe}_wgs84.tif"
        with rasterio.open(stn_path, "w",
                           driver="GTiff", dtype="float32", count=1,
                           crs=ref_crs, transform=out_tf,
                           width=out_w, height=out_h,
                           nodata=-1.0) as dst:
            dst.write(vs_small, 1)

        return callsign, tif_key, mask, row_off, col_off, row_end, col_end, stn_path

    worker_results = [None] * len(results)
    with _TPE(max_workers=n_workers) as pool:
        futs = {pool.submit(_process_one, sv): i
                for i, sv in enumerate(results)}
        with tqdm(total=len(results), unit="stn", ncols=72, colour="yellow",
                  bar_format=("   {l_bar}{bar}| {n_fmt}/{total_fmt} "
                              "[{elapsed}<{remaining}]")) as pbar:
            for fut in as_completed(futs):
                i = futs[fut]
                try:
                    worker_results[i] = fut.result()
                except Exception as e:
                    callsign = results[i][0]["callsign"]
                    pbar.write(f"   ⚠  Could not merge {callsign}: {e}")
                pbar.update(1)

    seen_tif_paths = set()
    station_tifs   = {}
    for res in worker_results:
        if res is None:
            continue
        callsign, tif_key, mask, row_off, col_off, row_end, col_end, stn_path = res
        if mask is not None and tif_key not in seen_tif_paths:
            coverage[row_off:row_end, col_off:col_end] += mask
            seen_tif_paths.add(tif_key)
        if stn_path is not None:
            station_tifs[callsign] = stn_path

    n_unique = len(seen_tif_paths)
    n_shared = len(results) - n_unique
    if n_shared:
        print(f"   Coverage count: {n_unique} unique viewsheds "
              f"({n_shared} co-located callsigns share a footprint)")

    print(f"   Accumulating coverage masks... done  ({_elapsed(t_acc)})")

    merged_path = work_dir / "coverage_count.tif"
    out_profile = ref_profile.copy()
    out_profile.update(dtype="int16", count=1, nodata=0)
    with rasterio.open(merged_path, "w", **out_profile) as dst:
        dst.write(coverage, 1)

    max_cov = int(coverage.max())
    cov_pct = 100.0 * (coverage > 0).sum() / coverage.size
    print(f"   ✅ Coverage raster written")
    print(f"      Max stations visible at any point: {max_cov}")
    print(f"      Grid cells with >=1 station:       {cov_pct:.1f}%")
    return merged_path, station_tifs


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — raster_to_png_overlay
# ─────────────────────────────────────────────────────────────────────────────

def raster_to_png_overlay(coverage_path: Path, work_dir: Path, cfg: dict,
                          station_name: str = None, prebuilt_rgba=None,
                          station_type: str = None):
    import rasterio
    import numpy as np
    from PIL import Image

    GE_MAX_PX = int(cfg.get("overlay_max_px", 4096))
    if station_name is not None:
        GE_MAX_PX = min(GE_MAX_PX, 1024)

    t0 = time.perf_counter()
    with rasterio.open(coverage_path) as src:
        data    = src.read(1).astype(np.float32)
        bounds  = src.bounds
        src_crs = src.crs
    h, w = data.shape

    if h > GE_MAX_PX or w > GE_MAX_PX:
        scale    = GE_MAX_PX / max(h, w)
        new_w    = max(1, int(round(w * scale)))
        new_h    = max(1, int(round(h * scale)))
        max_vp   = float(data.max()) if data.max() > 0 else 1.0
        data_u8  = (data / max_vp * 254).clip(0, 254).astype(np.uint8)
        data_img = Image.fromarray(data_u8, mode="L").resize(
                       (new_w, new_h), Image.NEAREST)
        data     = np.array(data_img, dtype=np.float32) / 254.0 * max_vp
        h, w     = new_h, new_w

    if prebuilt_rgba is not None:
        rgba = prebuilt_rgba
    else:
        rgba = _colorize(data, cfg, station_type=station_type)

    img = Image.fromarray(rgba.astype(np.uint8), "RGBA")
    if station_name is not None:
        png_path = work_dir / f"station_{station_name}.png"
    else:
        png_path = work_dir / "coverage_overlay.png"
    img.save(str(png_path), format="PNG", compress_level=6)

    from pyproj import Transformer
    transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
    west,  south = transformer.transform(bounds.left,  bounds.bottom)
    east,  north = transformer.transform(bounds.right, bounds.top)
    bbox = (west, south, east, north)

    if station_name is None:
        print(f"   ✅ Overlay PNG ready  ({_elapsed(t0)} total)")
        print(f"      WGS84 bbox: N{north:.4f} S{south:.4f} E{east:.4f} W{west:.4f}")
    return png_path, bbox


def build_kmz(stations: list, png_path: Path, bbox: tuple, cfg: dict,
              work_dir: Path, station_tifs: dict = None,
              prebuilt_pngs: dict = None):
    import math
    west, south, east, north = bbox

    t0 = time.perf_counter()
    print(f"   Building per-station PNGs + KML ({len(stations)} stations)...",
          flush=True)

    max_loss = cfg.get("_resolved_max_loss_db") or _resolve_max_path_loss(cfg)

    shared_styles = """
  <Style id="digi_style">
    <IconStyle>
      <scale>1.0</scale>
      <Icon><href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href></Icon>
      <hotSpot x="0.5" y="0" xunits="fraction" yunits="fraction"/>
    </IconStyle>
    <LabelStyle><scale>0.85</scale></LabelStyle>
    <BalloonStyle>
      <bgColor>ff1a1a2e</bgColor>
      <textColor>ffffffff</textColor>
      <text><![CDATA[$[description]]]></text>
    </BalloonStyle>
  </Style>
  <Style id="igate_style">
    <IconStyle>
      <scale>1.0</scale>
      <Icon><href>http://maps.google.com/mapfiles/kml/paddle/blu-circle.png</href></Icon>
      <hotSpot x="0.5" y="0" xunits="fraction" yunits="fraction"/>
    </IconStyle>
    <LabelStyle><scale>0.85</scale></LabelStyle>
    <BalloonStyle>
      <bgColor>ff1a1a2e</bgColor>
      <textColor>ffffffff</textColor>
      <text><![CDATA[$[description]]]></text>
    </BalloonStyle>
  </Style>"""

    digi_folders, igate_folders = [], []
    kmz_overlays = []

    def _render_station(idx_s):
        idx, s    = idx_s
        callsign  = s["callsign"]
        lat, lon  = s["lat"], s["lon"]
        stype     = s["type"]
        
        comment   = s.get("comment", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lasttime  = s.get("last seen", s.get("lasttime", ""))
        
        style_id  = "digi_style" if stype == "digi" else "igate_style"
        safe      = callsign.replace("-","_").replace("/","_").replace(" ","_")
        ant_h     = (cfg["antenna_height_digi_m"] if stype == "digi"
                     else cfg["antenna_height_igate_m"])
        type_label    = "📡 Digipeater" if stype == "digi" else "🌐 iGate"
        sidebar_label = (f"[{stype.upper()}] {callsign}"
                         + (f" — {comment[:40]}" if comment else ""))

        desc = (
            f"<table style='font-family:monospace;font-size:13px;'>"
            f"<tr><td><b>Callsign</b></td><td>{callsign}</td></tr>"
            f"<tr><td><b>Type</b></td><td>{type_label}</td></tr>"
            f"<tr><td><b>Frequency</b></td><td>144.390 MHz (APRS)</td></tr>"
            f"<tr><td><b>Coordinates</b></td><td>{lat:.5f}°N, {lon:.5f}°E</td></tr>"
            f"<tr><td><b>Antenna height</b></td><td>{ant_h:.0f} m AGL</td></tr>"
            f"<tr><td><b>Max path loss</b></td><td>{max_loss:.1f} dB (link budget)</td></tr>"
            f"<tr><td><b>Comment</b></td><td>{comment if comment else '—'}</td></tr>"
            f"<tr><td><b>Last seen</b></td><td>{lasttime if lasttime else '—'}</td></tr>"
            f"</table>"
        )

        arc_name    = None
        png_path    = None
        overlay_kml = ""
        if station_tifs and callsign in station_tifs:
            pre_rgba = (prebuilt_pngs or {}).get(callsign)
            stn_png, stn_bbox = raster_to_png_overlay(
                station_tifs[callsign], work_dir, cfg,
                station_name=safe, prebuilt_rgba=pre_rgba,
                station_type=stype)           
            sw, ss, se, sn = stn_bbox
            arc_name  = f"viewsheds/{safe}.png"
            png_path  = stn_png
            
            overlay_kml = (
                f"      <GroundOverlay>\n"
                f"        <name>{callsign} RF Coverage ({stype.upper()})</name>\n"
                f"        <visibility>1</visibility>\n"
                f"        <color>ffffffff</color>\n"
                f"        <drawOrder>1</drawOrder>\n"
                f"        <Icon><href>{arc_name}</href></Icon>\n"
                f"        <LatLonBox>\n"
                f"          <north>{sn}</north>\n"
                f"          <south>{ss}</south>\n"
                f"          <east>{se}</east>\n"
                f"          <west>{sw}</west>\n"
                f"        </LatLonBox>\n"
                f"      </GroundOverlay>\n"
            )

        folder = (
            f"    <Folder>\n"
            f"      <name>{sidebar_label}</name>\n"
            f"      <visibility>1</visibility>\n"
            f"      <open>0</open>\n"
            f"{overlay_kml}"
            f"      <Placemark>\n"
            f"        <name>{callsign}</name>\n"
            f"        <description><![CDATA[{desc}]]></description>\n"
            f"        <styleUrl>#{style_id}</styleUrl>\n"
            f"        <Point>\n"
            f"          <coordinates>{lon},{lat},0</coordinates>\n"
            f"        </Point>\n"
            f"      </Placemark>\n"
            f"    </Folder>\n"
        )
        return (idx, stype, folder, arc_name, png_path)

    from concurrent.futures import ThreadPoolExecutor as _TPE
    n_png_workers = min(len(stations), os.cpu_count() or 4)
    print(f"   Rendering {len(stations)} station PNGs "
          f"({n_png_workers} threads)...", flush=True)

    ordered_results = [None] * len(stations)
    with _TPE(max_workers=n_png_workers) as pool:
        futs = {pool.submit(_render_station, (i, s)): i
                for i, s in enumerate(stations)}
        done = 0
        for fut in as_completed(futs):
            idx, stype, folder, arc_name, png_path = fut.result()
            ordered_results[idx] = (stype, folder, arc_name, png_path)
            done += 1
            if done % 16 == 0 or done == len(stations):
                print(f"   ... {done}/{len(stations)} done  ({_elapsed(t0)})",
                      flush=True)

    for stype, folder, arc_name, png_path in ordered_results:
        if arc_name is not None:
            kmz_overlays.append((arc_name, png_path))
        (digi_folders if stype == "digi" else igate_folders).append(folder)

    dc    = len(digi_folders)
    ic    = len(igate_folders)
    total = len(stations)
    print(f"   done  ({dc} digis, {ic} iGates, {len(kmz_overlays)} overlays, {_elapsed(t0)})")

    t1 = time.perf_counter()
    print("   Rendering KML document...", end=" ", flush=True)
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"
     xmlns:gx="http://www.google.com/kml/ext/2.2">
<Document>
  <name>APRS Coverage — Utah ({total} stations)</name>
  <description><![CDATA[
    <b>Utah APRS Digipeater / iGate RF Coverage</b><br/>
    Generated by aprs_viewshed_utah_parallel.py<br/><br/>
    <b>Heatmap colour scale:</b><br/>
      Yellow = 1 station coverage<br/>
      Orange = 2–3 stations<br/>
      Red    = 4+ stations (dense overlap)<br/><br/>
    <b>Per-station overlays:</b><br/>
      🔴 Red  = Digipeater ({dc} stations)<br/>
      🔵 Blue = iGate ({ic} stations)<br/><br/>
    Toggle individual stations/folders in the sidebar.<br/>
    Click any placemark pin for station details.
  ]]></description>
  <open>1</open>
{shared_styles}

  <Folder>
    <name>📊 Combined Coverage Heatmap</name>
    <visibility>1</visibility>
    <description>All {total} stations merged — colour shows simultaneous coverage count at each point</description>
    <GroundOverlay>
      <name>Coverage Density (all {total} stations)</name>
      <color>ffffffff</color>
      <drawOrder>2</drawOrder>
      <Icon><href>coverage_overlay.png</href></Icon>
      <LatLonBox>
        <north>{north}</north>
        <south>{south}</south>
        <east>{east}</east>
        <west>{west}</west>
      </LatLonBox>
      <altitudeMode>clampToGround</altitudeMode>
    </GroundOverlay>
  </Folder>

  <Folder>
    <name>📡 Per-Station Viewsheds ({total} total)</name>
    <visibility>1</visibility>
    <open>0</open>
    <Folder>
      <name>📡 Digipeaters ({dc})</name>
      <visibility>1</visibility>
      <open>0</open>
{"".join(digi_folders)}    </Folder>
    <Folder>
      <name>🌐 iGates ({ic})</name>
      <visibility>1</visibility>
      <open>0</open>
{"".join(igate_folders)}    </Folder>
  </Folder>

  <ScreenOverlay>
    <name>Coverage Legend</name>
    <Icon><href>legend.png</href></Icon>
    <overlayXY x="0" y="0" xunits="fraction" yunits="fraction"/>
    <screenXY x="0.01" y="0.05" xunits="fraction" yunits="fraction"/>
    <size x="0" y="0" xunits="pixels" yunits="pixels"/>
  </ScreenOverlay>

</Document>
</kml>"""
    print(f"done  ({len(kml):,} chars, {_elapsed(t1)})")

    t2 = time.perf_counter()
    print("   Creating legend PNG...", end=" ", flush=True)
    legend_path = _create_legend(work_dir, cfg)
    print(f"done  ({_elapsed(t2)})")

    t3 = time.perf_counter()
    print("   Writing KMZ archive...", end=" ", flush=True)
    kmz_path = work_dir.parent / cfg["output_kmz"]
    with zipfile.ZipFile(kmz_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml)
        zf.write(png_path,    "coverage_overlay.png")
        zf.write(legend_path, "legend.png")
        for arc_name, file_path in kmz_overlays:
            zf.write(file_path, arc_name)
    print(f"done  ({kmz_path.stat().st_size/1e6:.1f} MB, {_elapsed(t3)})")
    print(f"   ✅ KMZ written: {kmz_path}  ({_elapsed(t0)} total)")
    return kmz_path


def _create_legend(work_dir: Path, cfg: dict) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    floor_db = float(cfg.get("margin_display_floor_db", -6.0))
    max_db   = float(cfg.get("max_margin_db", 30.0))
    w, h = 230, 185
    img  = Image.new("RGBA", (w, h), (20, 20, 20, 210))
    draw = ImageDraw.Draw(img)
    draw.text((10, 8),  "APRS Coverage Legend", fill=(255, 255, 255, 255))
    draw.line([(10, 26), (w-10, 26)], fill=(80, 80, 80, 255), width=1)

    draw.text((10, 30), "Combined heatmap:", fill=(200, 200, 200, 255))
    hm_ramp = ([((180,220,0,230),"1 station"),
                ((220,150,0,230),"2–3 stations"),
                ((255,50, 0,230),"4+ stations")]
               if cfg["color_scheme"] == "hot"
               else [((0,200,120,230),"1 station"),
                     ((0,140,180,230),"2–3 stations"),
                     ((0, 60,255,230),"4+ stations")])
    y = 46
    for color, label in hm_ramp:
        draw.rectangle([10,y+2,26,y+14], fill=color, outline=(60,60,60,200))
        draw.text((34, y), label, fill=(240, 240, 240, 255))
        y += 18

    draw.line([(10,y+2),(w-10,y+2)], fill=(60,60,60,255), width=1)
    y += 8

    draw.text((10, y), "Per-station (link margin):", fill=(200,200,200,255))
    y += 16
    for i, x in enumerate(range(10, 26)):
        t = i / 15.0
        r2 = int(40 - 40*t); g2 = int(120 + 135*t); b2 = int(40 - 40*t)
        draw.line([(x, y+2),(x, y+14)], fill=(r2,g2,b2,220))
    draw.text((34, y), f"📡 Digi  {floor_db:+.0f}→+{max_db:.0f} dB", fill=(140,240,140,255))
    y += 18
    for i, x in enumerate(range(10, 26)):
        t = i / 15.0
        r2 = int(80-80*t); g2 = int(160-130*t); b2 = int(200+55*t)
        draw.line([(x, y+2),(x, y+14)], fill=(r2,g2,b2,220))
    draw.text((34, y), f"🌐 iGate {floor_db:+.0f}→+{max_db:.0f} dB", fill=(140,200,240,255))
    y += 22

    draw.line([(10,y),(w-10,y)], fill=(60,60,60,255), width=1)
    y += 6
    draw.text((10, y), "Faint halo = diffraction tail", fill=(160,160,160,255))
    y += 14
    draw.text((10, y), "Bright core = strong signal", fill=(160,160,160,255))

    legend_path = work_dir / "legend.png"
    img.save(str(legend_path))
    return legend_path


def clear_viewshed_cache(work_dir: Path):
    removed = 0
    for f in work_dir.glob("viewshed_*.tif"):       
        f.unlink(missing_ok=True)
        removed += 1
    for f in work_dir.glob("station_*_wgs84.tif"):  
        f.unlink(missing_ok=True)
        removed += 1
    cov = work_dir / "coverage_count.tif"
    if cov.exists():
        cov.unlink(missing_ok=True)
        removed += 1
    if removed:
        print(f"   🗑  Cleared {removed} cached TIF(s) (Steps 4+5) — will recompute")
    return removed


def cleanup(work_dir: Path):
    keep    = {"coverage_count.tif", "utah_dem.tif", "utah_dem_utm.tif",
               "utah_dem_bounds.json"}
    removed = 0
    for f in work_dir.iterdir():
        if f.name not in keep and f.suffix in {".tif",".shp",".shx",".dbf",".prj"}:
            f.unlink(missing_ok=True)
            removed += 1
    print(f"   Removed {removed} intermediate file(s)  "
          f"(DEM + coverage raster kept for re-runs)")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    _mp.freeze_support()

    os.chdir(Path(__file__).parent)

    TOTAL_STEPS = 7
    t_global    = time.perf_counter()

    print("=" * 65)
    print("  APRS Viewshed Generator for Utah  —  PARALLEL")
    print("  ITM Longley-Rice + raster math on CPU (numpy/scipy)")
    print("=" * 65)

    cfg = CONFIG

    _stage("Installing / verifying dependencies", 1, TOTAL_STEPS)
    install_deps()

    _stage("Loading station list", 2, TOTAL_STEPS)
    work_dir = Path(cfg["work_dir"])
    work_dir.mkdir(exist_ok=True)

    stations_path = Path(cfg["stations_json"])
    if not stations_path.exists():
        stations_path = Path(__file__).parent / cfg["stations_json"]
    if not stations_path.exists():
        print(f"❌ Cannot find {cfg['stations_json']}")
        print(f"   Expected at: {Path(__file__).parent / cfg['stations_json']}")
        _pause_and_exit(1)

    stations, colocation_map = load_stations(str(stations_path), cfg)
    if not stations:
        print("❌ No valid stations found.")
        _pause_and_exit(1)

    n_workers = cfg.get("cpu_workers") or os.cpu_count() or 4
    print(f"   CPU workers: {n_workers}")

    _stage("Loading elevation data from dem_cache (1-arcsec NED tiles)", 3, TOTAL_STEPS)
    t3       = time.perf_counter()
    dem_path = prepare_dem(stations, cfg, work_dir)
    print(f"   Step 3 complete  ({_elapsed(t3)})")

    _stage("Computing VHF viewsheds (ITM Longley-Rice — CPU only)", 4, TOTAL_STEPS)
    if cfg.get("clear_viewshed_cache"):
        clear_viewshed_cache(work_dir)
    t4 = time.perf_counter()

    def _vs_path(s):
        canon = colocation_map.get(s["callsign"], s["callsign"])
        safe  = canon.replace("-","_").replace("/","_").replace(" ","_")
        return work_dir / f"viewshed_{safe}.tif"

    all_cached = all(_vs_path(s).exists() for s in stations)
    if all_cached:
        print(f"   ✅ All {len(stations)} viewshed TIFs cached — skipping compute")
        results = [(s, _vs_path(s)) for s in stations]
    else:
        results = compute_viewsheds(stations, dem_path, cfg, work_dir,
                                        colocation_map=colocation_map)
        if not results:
            print("❌ No viewsheds computed.")
            _pause_and_exit(1)
    print(f"   Step 4 complete  ({_elapsed(t4)})")

    _stage("Merging viewsheds into coverage count raster", 5, TOTAL_STEPS)
    t5 = time.perf_counter()

    merged_path = work_dir / "coverage_count.tif"

    def _stn_tif(s):
        safe = s["callsign"].replace("-","_").replace("/","_").replace(" ","_")
        return work_dir / f"station_{safe}_wgs84.tif"

    def _tif_oversized(s):
        p = _stn_tif(s)
        if not p.exists():
            return False
        try:
            import rasterio
            with rasterio.open(p) as _src:
                cap = int(cfg.get("stn_tif_max_px", 2048))
                return cap > 0 and max(_src.height, _src.width) > cap * 1.1
        except Exception:
            return False   

    _files_exist  = merged_path.exists() and all(_stn_tif(s).exists() for s in stations)
    _oversized    = _files_exist and any(_tif_oversized(s) for s in stations)
    merge_cached  = _files_exist and not _oversized
    if _oversized:
        print(f"   ⚠  Cached station TIFs are oversized (pre-optimisation) — rebuilding")
    if merge_cached:
        print(f"   ✅ Merged raster + station TIFs cached — skipping merge")
        coverage_path = merged_path
        station_tifs  = {s["callsign"]: _stn_tif(s) for s in stations}
    else:
        coverage_path, station_tifs = merge_viewsheds(results, dem_path,
                                                       work_dir, cfg)
    print(f"   Step 5 complete  ({_elapsed(t5)})")

    _stage("Rendering coverage PNG overlay", 6, TOTAL_STEPS)
    t6             = time.perf_counter()
    png_path, bbox = raster_to_png_overlay(coverage_path, work_dir, cfg)
    print(f"   Step 6 complete  ({_elapsed(t6)})")

    prebuilt_pngs = {}
    if station_tifs:
        import rasterio, numpy as _np
        from PIL import Image as _Img
        GE_STN_PX = min(int(cfg.get("overlay_max_px", 4096)), 1024)
        stn_items = [(s["callsign"], s["type"],
                      station_tifs[s["callsign"]])
                     for s in stations
                     if s["callsign"] in station_tifs]
        data_list, stypes, calls = [], [], []
        t_batch = time.perf_counter()
        for callsign, stype, tif_path in stn_items:
            try:
                with rasterio.open(tif_path) as src:
                    h_full, w_full = src.height, src.width
                    scale = GE_STN_PX / max(h_full, w_full)
                    if scale < 1.0:
                        nh = max(1, int(round(h_full * scale)))
                        nw = max(1, int(round(w_full * scale)))
                        d = src.read(
                            1,
                            out_shape=(nh, nw),
                            resampling=rasterio.enums.Resampling.nearest,
                        ).astype(_np.float32)
                    else:
                        d = src.read(1).astype(_np.float32)
                data_list.append(d)
                stypes.append(stype)
                calls.append(callsign)
            except Exception as e:
                print(f"   ⚠  Batch pre-read failed for {callsign}: {e}")
        if data_list:
            max_h = max(d.shape[0] for d in data_list)
            max_w = max(d.shape[1] for d in data_list)
            padded = []
            for d in data_list:
                if d.shape == (max_h, max_w):
                    padded.append(d)
                else:
                    p = _np.zeros((max_h, max_w), dtype=_np.float32)
                    p[:d.shape[0], :d.shape[1]] = d
                    padded.append(p)
            rgba_list = _colorize_batch(padded, stypes, cfg)
            for callsign, d_orig, rgba in zip(calls, data_list, rgba_list):
                prebuilt_pngs[callsign] = rgba[:d_orig.shape[0],
                                               :d_orig.shape[1]]
            print(f"   Batch colorised {len(prebuilt_pngs)} station PNGs"
                  f" ({_elapsed(t_batch)})")

    _stage("Building KMZ output file", 7, TOTAL_STEPS)
    t7       = time.perf_counter()
    kmz_path = build_kmz(stations, png_path, bbox, cfg, work_dir,
                         station_tifs=station_tifs,
                         prebuilt_pngs=prebuilt_pngs)
    print(f"   Step 7 complete  ({_elapsed(t7)})")

    print()
    cleanup(work_dir)

    total_s = time.perf_counter() - t_global
    m, s    = divmod(int(total_s), 60)

    print()
    print("=" * 65)
    print(f"  ✅  ALL DONE  —  total time: {m}m {s}s")
    print("=" * 65)
    print(f"")
    print(f"  Output:  {kmz_path.resolve()}")
    print(f"")
    print(f"  To use in Google Earth Pro:")
    print(f"    1. File → Open → aprs_coverage_utah.kmz")
    print(f"    2. File → Open → your historical track KMZ")
    print(f"    3. Toggle layers in the sidebar")
    print(f"")
    print(f"  Cached files in: {work_dir.resolve()}")
    print(f"  (DEM + coverage raster kept — re-runs skip download & viewsheds)")
    print("=" * 65)

    input("\n  Press Enter to close...\n")


def _pause_and_exit(code: int = 1):
    input("\n  Press Enter to close...\n")
    sys.exit(code)

if __name__ == "__main__":
    import traceback
    log_path = Path(__file__).parent / "run_log.txt"
    try:
        main()
    except SystemExit:
        raise   
    except Exception:
        tb = traceback.format_exc()
        print("\n" + "="*65)
        print("  ❌  UNHANDLED EXCEPTION")
        print("="*65)
        print(tb)
        try:
            with open(log_path, "w") as lf:
                lf.write(f"Run failed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                lf.write(tb)
            print(f"  Full traceback saved to: {log_path}")
        except Exception:
            pass
        input("\n  Press Enter to close...\n")
        sys.exit(1)
