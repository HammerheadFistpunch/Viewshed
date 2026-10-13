"""Ideal aligned free-space checks, separate from terrain propagation."""
import math
from microwave_settings import microwave_radio

CPE710_PRESET = "Dish / MIMO — TP-Link CPE710"
CPE710_PLANNING = dict(frequency_ghz=5.8, tx_power_dbm=20, tx_gain_dbi=23,
                      rx_gain_dbi=23, rx_sensitivity_dbm=-85, system_loss_db=2,
                      reserve_db=15, path_loss_cap_db=200, radius_km=30,
                      polarization="Dual (H + V)")


def free_space_budget(values):
    radio = microwave_radio(values)
    distance = float(values["radius_km"])
    if not math.isfinite(distance) or distance <= 0:
        raise ValueError("Radius must be a positive finite distance.")
    frequency = radio["freq_mhz"]
    power = radio["tx_power_dbm"]
    tx_gain = radio["tx_antenna_gain_dbd"] + 2.15
    rx_gain = radio["rx_antenna_gain_dbd"] + 2.15
    losses = radio["system_loss_db"]
    raw_budget = power + tx_gain + rx_gain - losses - radio["rx_sensitivity_dbm"]
    effective = min(raw_budget, radio["max_path_loss_db"]) - radio["operational_reserve_db"]
    fspl = 32.45 + 20 * math.log10(frequency) + 20 * math.log10(distance)
    return dict(raw_budget_db=raw_budget, effective_budget_db=effective,
                received_dbm=power + tx_gain + rx_gain - losses - fspl,
                margin_db=effective - fspl,
                ideal_distance_km=10 ** ((effective - 32.45 - 20 * math.log10(frequency)) / 20),
                # Midpoint first Fresnel zone and 4/3-earth curvature only;
                # not a terrain/obstacle clearance test.
                fresnel_60pct_m=0.6 * math.sqrt((299792458 / (frequency * 1e6)) * distance * 1000 / 4),
                midpoint_bulge_m=(distance * 1000) ** 2 / (8 * (4 / 3) * 6371000))


def budget_text(values):
    result = free_space_budget(values)
    return (f"Aligned free-space check at {float(values['radius_km']):g} km: "
            f"RX {result['received_dbm']:.1f} dBm; margin after reserve/cap {result['margin_db']:+.1f} dB. "
            f"Ideal distance at 0 dB margin: {result['ideal_distance_km']:.1f} km. "
            f"Midpoint 60% Fresnel radius {result['fresnel_60pct_m']:.1f} m + "
            f"4/3-earth bulge {result['midpoint_bulge_m']:.1f} m. "
            "Terrain, interference and aiming can reduce range; this does not predict throughput or reliability.")
