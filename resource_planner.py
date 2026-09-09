from __future__ import annotations

import math
import os
from dataclasses import dataclass, asdict
from typing import Iterable

GIB = 1024 ** 3
SOURCE_DEM_M = 30.0
DETAIL_TARGETS_M = {
    "auto": 100.0,
    "fast": 200.0,
    "standard": 125.0,
    "high": 75.0,
    "max": 30.0,
}
CPU_FRACTIONS = {
    "auto": 0.75,
    "fast": 1.00,
    "standard": 0.75,
    "high": 0.60,
    "max": 1.00,
}
MAX_ANALYSIS_PX = 16000
MAX_WORKER_PX = 12000
MIN_ANALYSIS_PX = 2000
MIN_WORKER_PX = 1000


@dataclass
class SystemResources:
    total_ram_bytes: int
    available_ram_bytes: int
    logical_cpus: int
    physical_cpus: int | None = None
    cpu_percent: float | None = None
    source: str = "fallback"


@dataclass
class ResourcePlan:
    mode: str
    target_detail_m: float
    actual_detail_m: float
    practical_feature_min_m: float
    practical_feature_good_m: float
    regional_span_km: float
    worker_span_km: float
    analysis_max_px: int
    worker_max_px: int
    cpu_workers: int
    station_count: int
    estimated_peak_ram_bytes: int
    available_ram_bytes: int
    planned_ram_budget_bytes: int
    memory_limit_gb: float
    detail_limited_by: str
    max_warning: bool
    degraded_for_memory: bool

    def to_radio_settings(self) -> dict:
        return {
            "dem_merge_max_dimension": int(self.analysis_max_px),
            "analysis_dem_max_dimension": int(self.analysis_max_px),
            "worker_dem_max_px": int(self.worker_max_px),
            "cpu_workers": int(self.cpu_workers),
            "terrain_detail_mode": self.mode,
            "terrain_detail_actual_m": round(float(self.actual_detail_m), 1),
            "terrain_resource_plan": asdict(self),
        }


def get_system_resources() -> SystemResources:
    logical = max(1, os.cpu_count() or 1)
    try:
        import psutil

        mem = psutil.virtual_memory()
        physical = psutil.cpu_count(logical=False)
        cpu_pct = float(psutil.cpu_percent(interval=0.12))
        return SystemResources(
            total_ram_bytes=int(mem.total),
            available_ram_bytes=int(mem.available),
            logical_cpus=logical,
            physical_cpus=int(physical) if physical else None,
            cpu_percent=cpu_pct,
            source="psutil",
        )
    except Exception:
        pass

    if os.name == "nt":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return SystemResources(
                    total_ram_bytes=int(status.ullTotalPhys),
                    available_ram_bytes=int(status.ullAvailPhys),
                    logical_cpus=logical,
                    source="windows",
                )
        except Exception:
            pass

    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        total = page_size * int(os.sysconf("SC_PHYS_PAGES"))
        avail = page_size * int(os.sysconf("SC_AVPHYS_PAGES"))
        return SystemResources(total, avail, logical, source="sysconf")
    except Exception:
        # Conservative fallback when memory telemetry is unavailable.
        return SystemResources(8 * GIB, 4 * GIB, logical, source="fallback")


def _regional_span_km(stations: Iterable[dict], radius_km: float) -> float:
    points: list[tuple[float, float]] = []
    for station in stations:
        try:
            points.append((float(station["lat"]), float(station["lon"])))
        except (KeyError, TypeError, ValueError):
            continue
    if not points:
        return max(2.0 * radius_km, 1.0)

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    margin_deg = max(1.0, math.ceil(float(radius_km) / 111.0))
    lat_span_deg = (max(lats) - min(lats)) + 2.0 * margin_deg
    lon_span_deg = (max(lons) - min(lons)) + 2.0 * margin_deg
    mean_lat = sum(lats) / len(lats)
    ns_km = lat_span_deg * 111.32
    ew_km = lon_span_deg * 111.32 * max(0.2, math.cos(math.radians(mean_lat)))
    return max(ns_km, ew_km, 1.0)


def _memory_budget(resources: SystemResources, user_limit_gb: float) -> int:
    total = max(resources.total_ram_bytes, 1)
    available = max(resources.available_ram_bytes, 1)
    system_reserve = max(2 * GIB, int(total * 0.20))
    safe_available = max(int(0.5 * GIB), min(int(available * 0.75), available - min(system_reserve, int(available * 0.60))))
    if user_limit_gb > 0:
        safe_available = min(safe_available, int(user_limit_gb * GIB * 0.75))
    return max(int(0.5 * GIB), safe_available)


def _estimate_memory(analysis_px: int, worker_px: int, workers: int) -> int:
    # Conservative empirical planning model: regional raster plus rasterio/numpy
    # working copies, then several float arrays per child process.
    regional = int(analysis_px * analysis_px * 4 * 2.5) + int(0.5 * GIB)
    per_worker = int(worker_px * worker_px * 4 * 4.5) + int(0.125 * GIB)
    return regional + max(1, workers) * per_worker


def _dimensions_for_detail(regional_m: float, worker_m: float, detail_m: float) -> tuple[int, int]:
    analysis = int(math.ceil(regional_m / detail_m))
    worker = int(math.ceil(worker_m / detail_m))
    analysis = max(MIN_ANALYSIS_PX, min(MAX_ANALYSIS_PX, analysis))
    worker = max(MIN_WORKER_PX, min(MAX_WORKER_PX, worker))
    return analysis, worker


def plan_resources(
    stations: Iterable[dict],
    radius_km: float,
    mode: str = "auto",
    memory_limit_gb: float = 0.0,
    resources: SystemResources | None = None,
) -> ResourcePlan:
    mode_key = str(mode or "auto").strip().lower()
    if mode_key not in DETAIL_TARGETS_M:
        mode_key = "auto"
    radius_km = max(1.0, float(radius_km))
    station_list = list(stations)
    station_count = max(1, len(station_list))
    resources = resources or get_system_resources()
    budget = _memory_budget(resources, float(memory_limit_gb or 0.0))

    regional_m = _regional_span_km(station_list, radius_km) * 1000.0
    worker_m = radius_km * 2000.0
    requested = DETAIL_TARGETS_M[mode_key]
    detail = requested
    degraded = False

    logical = max(1, resources.logical_cpus)
    cpu_target = max(1, min(logical, int(math.ceil(logical * CPU_FRACTIONS[mode_key]))))
    cpu_target = min(cpu_target, station_count)

    while True:
        analysis_px, worker_px = _dimensions_for_detail(regional_m, worker_m, detail)
        regional_mem = _estimate_memory(analysis_px, worker_px, 0)
        per_worker_mem = max(1, _estimate_memory(analysis_px, worker_px, 1) - regional_mem)
        worker_budget = max(0, budget - regional_mem)
        memory_workers = int(worker_budget // per_worker_mem)

        # Max preserves requested/native detail until even one worker cannot fit.
        # Other modes may also retain their target if at least one safe worker fits;
        # their coarser target naturally permits greater parallelism.
        if memory_workers >= 1:
            workers = max(1, min(cpu_target, memory_workers, station_count))
            break

        degraded = True
        detail *= 1.15
        if detail > 1000.0:
            workers = 1
            break

    actual = max(
        SOURCE_DEM_M,
        regional_m / max(1, analysis_px),
        worker_m / max(1, worker_px),
    )

    limits = []
    if actual <= SOURCE_DEM_M * 1.05:
        limits.append("native DEM")
    if regional_m / max(1, analysis_px) >= actual * 0.98:
        limits.append("regional DEM")
    if worker_m / max(1, worker_px) >= actual * 0.98:
        limits.append("station worker DEM")
    if degraded:
        limits.append("memory safety")
    limited_by = ", ".join(dict.fromkeys(limits)) or "requested preset"

    peak = _estimate_memory(analysis_px, worker_px, workers)
    return ResourcePlan(
        mode=mode_key,
        target_detail_m=requested,
        actual_detail_m=actual,
        practical_feature_min_m=actual * 2.0,
        practical_feature_good_m=actual * 3.0,
        regional_span_km=regional_m / 1000.0,
        worker_span_km=worker_m / 1000.0,
        analysis_max_px=analysis_px,
        worker_max_px=worker_px,
        cpu_workers=workers,
        station_count=station_count,
        estimated_peak_ram_bytes=peak,
        available_ram_bytes=resources.available_ram_bytes,
        planned_ram_budget_bytes=budget,
        memory_limit_gb=float(memory_limit_gb or 0.0),
        detail_limited_by=limited_by,
        max_warning=(mode_key == "max"),
        degraded_for_memory=degraded,
    )


def format_gb(value: int) -> str:
    return f"{value / GIB:.1f} GB"


def format_plan(plan: ResourcePlan) -> str:
    text = (
        f"{plan.mode.title()} plan: ~{plan.actual_detail_m:.0f} m terrain sampling; "
        f"features ~{plan.practical_feature_min_m:.0f}-{plan.practical_feature_good_m:.0f} m+ are meaningfully represented; "
        f"analysis {plan.analysis_max_px}px; worker {plan.worker_max_px}px; "
        f"{plan.cpu_workers} worker(s); estimated peak {format_gb(plan.estimated_peak_ram_bytes)}. "
        f"Limit: {plan.detail_limited_by}."
    )
    if plan.max_warning:
        text += " Maximum detail prioritizes stability and resolution over speed and may be VERY slow, including single-worker operation."
    elif plan.degraded_for_memory:
        text += " Requested detail was reduced to remain inside the safe memory budget."
    return text
