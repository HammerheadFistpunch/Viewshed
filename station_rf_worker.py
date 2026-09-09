from __future__ import annotations

import math


def _station_cfg(station: dict, cfg: dict) -> dict:
    merged = dict(cfg)
    stype = str(station.get("type") or "digi").lower()

    height = station.get("antenna_height_m", station.get("antenna_height_agl_m"))
    if height is not None:
        key = "antenna_height_igate_m" if stype == "igate" else "antenna_height_digi_m"
        merged[key] = float(height)

    if station.get("tx_power_dbm") is not None:
        merged["tx_power_dbm"] = float(station["tx_power_dbm"])
    elif station.get("tx_power_w") is not None:
        watts = float(station["tx_power_w"])
        if watts <= 0:
            raise ValueError("Per-station tx_power_w must be positive.")
        merged["tx_power_dbm"] = 10.0 * math.log10(watts * 1000.0)

    if station.get("tx_antenna_gain_dbd") is not None:
        merged["tx_antenna_gain_dbd"] = float(station["tx_antenna_gain_dbd"])
    elif station.get("tx_antenna_gain_dbi") is not None:
        merged["tx_antenna_gain_dbd"] = float(station["tx_antenna_gain_dbi"]) - 2.15

    if station.get("freq_mhz") is not None:
        merged["freq_mhz"] = float(station["freq_mhz"])
    if station.get("max_path_loss_db") is not None:
        merged["max_path_loss_db"] = float(station["max_path_loss_db"])

    # The engine normally precomputes one global link budget. Any station RF
    # override must force the existing worker to recompute the budget locally.
    merged.pop("_resolved_max_loss_db", None)
    return merged


def process_station(args: tuple):
    import aprs_viewshed_utah_parallel as engine

    base = getattr(engine, "_station_rf_base_process_station", None)
    if base is None or base is process_station:
        raise RuntimeError("Per-station RF worker was not installed correctly.")
    mutable = list(args)
    mutable[6] = _station_cfg(dict(mutable[0]), dict(mutable[6]))
    return base(tuple(mutable))


def install(engine) -> None:
    if getattr(engine, "_station_rf_override_installed", False):
        return
    engine._station_rf_base_process_station = engine._process_station
    engine._process_station = process_station
    engine._station_rf_override_installed = True
