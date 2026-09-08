from __future__ import annotations

import os
import sys


def _configure_worker_streams() -> None:
    """Make spawned Windows worker diagnostics safe for Unicode output."""
    os.environ["PYTHONIOENCODING"] = "utf-8:replace"
    os.environ["PYTHONUTF8"] = "1"
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def process_station(args):
    """ProcessPool-safe wrapper around the legacy station worker."""
    _configure_worker_streams()
    import aprs_viewshed_utah_parallel as legacy_engine

    return legacy_engine._process_station(args)


def install_safe_worker(engine) -> None:
    """Route spawned station jobs through a child-local encoding setup."""
    if getattr(engine, "_safe_worker_installed", False):
        return
    engine._process_station = process_station
    engine._safe_worker_installed = True
