"""Editable antenna starting points and a simplified main-lobe model.

These are not measured pattern files or implementations of an ITU reference
pattern. The quadratic approximation is 3 dB down at half the full beamwidth.
"""
import math


ANTENNA_PRESETS = {
    "Uniform / manual": dict(gain_dbi=0, pattern="uniform", az_bw=360, el_bw=180, frequency_ghz=None,
                             note="Uniform gain in every direction; edit gain for your antenna."),
    "Yagi — generic approximation": dict(gain_dbi=14, pattern="directional", az_bw=30, el_bw=30, frequency_ghz=None,
                                         note="Generic 14 dBi Yagi, 30° beam. Replace values with your antenna's specifications."),
    "Dish — generic approximation": dict(gain_dbi=24, pattern="directional", az_bw=10, el_bw=10, frequency_ghz=None,
                                         note="Generic 24 dBi dish, 10° beam. Replace values with your antenna's specifications."),
    "Dish / MIMO — TP-Link CPE710": dict(gain_dbi=23, pattern="directional", az_bw=9, el_bw=7, frequency_ghz=5.8,
                                        polarization="Dual (H + V)",
                                        note="CPE710: 23 dBi, 9° / 7°, dual H/V, 5.15–5.85 GHz. Hardware maximum 27 dBm varies with region/rate; enter actual power per channel. No MIMO gain bonus."),
    "Sector — generic approximation": dict(gain_dbi=16, pattern="directional", az_bw=90, el_bw=10, frequency_ghz=None,
                                           note="Generic 16 dBi sector, 90° horizontal / 10° vertical beam."),
    "Panel / MIMO — TP-Link CPE510": dict(gain_dbi=13, pattern="directional", az_bw=45, el_bw=30, frequency_ghz=5.5,
                                        note="CPE510: 13 dBi, 45° / 30° beam, dual polarization. Model approximates one selected H/V channel; no MIMO throughput or extra gain."),
    "Dish / MIMO — RocketDish 5G30 LW": dict(gain_dbi=30, pattern="directional", az_bw=5.8, el_bw=5.8, frequency_ghz=5.5,
                                           note="5.1–5.9 GHz, 30 dBi, 5.8° beam specification. Symmetric main-lobe approximation; one selected H/V channel, no MIMO gain."),
}


def pattern_settings(values):
    pattern = values.get("tx_pattern", "uniform")
    if pattern not in ("uniform", "directional"):
        raise ValueError("TX pattern must be uniform or directional.")
    limits = {"tx_azimuth_deg": (0, 360, 0), "tx_tilt_deg": (-90, 90, 0),
              "tx_az_beamwidth_deg": (1, 360, 360),
              "tx_el_beamwidth_deg": (1, 180, 180),
              "tx_pattern_floor_db": (3, 60, 30)}
    result = {"tx_pattern": pattern}
    for key, (low, high, default) in limits.items():
        number = float(values.get(key, default))
        if not math.isfinite(number) or not low <= number <= high:
            raise ValueError(f"{key.replace('_', ' ')} must be between {low} and {high}.")
        result[key] = number
    return result


def pattern_loss_db(cfg, bearing_deg, elevation_deg):
    if cfg.get("tx_pattern", "uniform") == "uniform":
        return 0.0
    delta = (bearing_deg - cfg["tx_azimuth_deg"] + 180.0) % 360.0 - 180.0
    vertical = elevation_deg - cfg["tx_tilt_deg"]
    return min(cfg["tx_pattern_floor_db"],
               12.0 * (delta / cfg["tx_az_beamwidth_deg"]) ** 2
               + 12.0 * (vertical / cfg["tx_el_beamwidth_deg"]) ** 2)

