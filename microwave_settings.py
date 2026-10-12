"""Validated GHz inputs, translated to the engine's MHz/dBd convention."""
import math
from antenna_patterns import pattern_settings


def microwave_radio(values):
    limits = {
        "frequency_ghz": (1, 10), "tx_power_dbm": (0, 80),
        "tx_gain_dbi": (-20, 60), "rx_gain_dbi": (-20, 60),
        "rx_sensitivity_dbm": (-160, -30), "tx_height_m": (0.5, 500),
        "rx_height_m": (0.5, 100), "system_loss_db": (0, 60),
        "reserve_db": (0, 60), "path_loss_cap_db": (80, 250),
        "loss_sample_spacing_m": (25, 1000),
    }
    parsed = {key: float(values[key]) for key in limits}
    for key, (low, high) in limits.items():
        if not math.isfinite(parsed[key]) or not low <= parsed[key] <= high:
            raise ValueError(f"{key.replace('_', ' ')} must be between {low} and {high}.")
    pol = values["polarization"]
    if pol not in ("Horizontal", "Vertical"):
        raise ValueError("Choose Horizontal or Vertical polarization.")
    radio = {
        "freq_mhz": parsed["frequency_ghz"] * 1000,
        "tx_power_dbm": parsed["tx_power_dbm"],
        "tx_antenna_gain_dbd": parsed["tx_gain_dbi"] - 2.15,
        "rx_antenna_gain_dbd": parsed["rx_gain_dbi"] - 2.15,
        "antenna_gain_reference": "isotropic",
        "rx_sensitivity_dbm": parsed["rx_sensitivity_dbm"],
        "antenna_height_digi_m": parsed["tx_height_m"],
        "observer_height_m": parsed["rx_height_m"],
        "system_loss_db": parsed["system_loss_db"],
        "operational_reserve_db": parsed["reserve_db"],
        "max_path_loss_db": parsed["path_loss_cap_db"],
        "itm_pol": int(pol == "Vertical"),
        "sampling_mode": "microwave",
        "loss_sample_spacing_m": parsed["loss_sample_spacing_m"],
    }
    radio.update(pattern_settings(values))
    radio["tx_antenna_preset"] = str(values.get("tx_antenna_preset", "Uniform / manual"))
    radio["rx_antenna_preset"] = str(values.get("rx_antenna_preset", "Uniform / manual"))
    return radio
