from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from map_workspace_patch import ViewshedWorkspace as _ViewshedWorkspace
from viewshed_core import Region, assess_station_locations, portable_data_root, prepare_job


ADVANCED_DEFAULTS = {
    "max_path_loss_db": 148.0,
    "tx_power_dbm": 47.0,
    "tx_antenna_gain_dbd": 0.0,
    "rx_sensitivity_dbm": -119.0,
    "rx_antenna_gain_dbd": 2.0,
    "antenna_height_digi_m": 20.0,
    "antenna_height_igate_m": 3.0,
    "observer_height_m": 2.0,
    "freq_mhz": 144.390,
    "n_radials": 720,
    "margin_display_floor_db": 0.0,
    "max_margin_db": 30.0,
    "worker_dem_max_px": 2500,
    "itm_climate": 4,
    "itm_ens": 301.0,
    "itm_sgm": 0.001,
    "itm_epsr": 15.0,
    "itm_pol": 1,
}


def _advanced_path() -> Path:
    return portable_data_root() / "advanced_settings.json"


def _load_advanced() -> dict:
    values = dict(ADVANCED_DEFAULTS)
    path = _advanced_path()
    if not path.exists():
        return values
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return values
    if isinstance(raw, dict):
        for key in values:
            if key in raw:
                values[key] = raw[key]
    return values


def _save_advanced(values: dict) -> None:
    path = _advanced_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, indent=2), encoding="utf-8")


class ViewshedWorkspace(_ViewshedWorkspace):
    """Current workspace plus persistent advanced propagation controls."""

    def __init__(self, master, app) -> None:
        self._advanced_vars: dict[str, tk.StringVar] = {}
        super().__init__(master, app)
        self._build_advanced_tab()

    def _build_advanced_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Advanced")

        ttk.Label(tab, text="Advanced propagation settings", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "These values materially change predicted coverage. Defaults are the Viewshed reference profile. "
                "Advanced settings apply to Area and Station runs; Custom mode keeps its own site-specific radio controls."
            ),
            wraplength=900,
        ).pack(anchor="w", pady=(3, 10))

        values = _load_advanced()
        for key, value in values.items():
            self._advanced_vars[key] = tk.StringVar(value=str(value))

        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        rf = ttk.LabelFrame(body, text="Radio / link assumptions", padding=10)
        rf.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        model = ttk.LabelFrame(body, text="Propagation / compute", padding=10)
        model.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        rf_fields = [
            ("Operational path-loss cap (dB)", "max_path_loss_db"),
            ("TX power (dBm)", "tx_power_dbm"),
            ("TX antenna gain (dBd)", "tx_antenna_gain_dbd"),
            ("RX sensitivity (dBm)", "rx_sensitivity_dbm"),
            ("RX antenna gain (dBd)", "rx_antenna_gain_dbd"),
            ("Digipeater antenna AGL (m)", "antenna_height_digi_m"),
            ("iGate antenna AGL (m)", "antenna_height_igate_m"),
            ("Receiver / observer height (m)", "observer_height_m"),
            ("Frequency (MHz)", "freq_mhz"),
        ]
        model_fields = [
            ("Radials per station", "n_radials"),
            ("Displayed margin floor (dB)", "margin_display_floor_db"),
            ("Maximum displayed margin (dB)", "max_margin_db"),
            ("Worker DEM max dimension (px)", "worker_dem_max_px"),
            ("ITM climate code (1–7)", "itm_climate"),
            ("Surface refractivity N-units", "itm_ens"),
            ("Ground conductivity (S/m)", "itm_sgm"),
            ("Relative permittivity", "itm_epsr"),
            ("Polarization (0=H, 1=V)", "itm_pol"),
        ]

        for row, (label, key) in enumerate(rf_fields):
            self._advanced_field(rf, row, label, key)
        for row, (label, key) in enumerate(model_fields):
            self._advanced_field(model, row, label, key)

        actions = ttk.Frame(tab)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Save settings", command=self._save_advanced_from_ui).pack(side="left")
        ttk.Button(actions, text="Reset to Viewshed defaults", command=self._reset_advanced).pack(side="left", padx=(6, 0))
        ttk.Label(actions, text=f"Stored in: {_advanced_path()}").pack(side="right")

        self.advanced_status = tk.StringVar(value="Profile loaded. Settings are validated again whenever a job starts.")
        ttk.Label(tab, textvariable=self.advanced_status, wraplength=900).pack(anchor="w", pady=(8, 0))

    def _advanced_field(self, parent, row: int, label: str, key: str) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=self._advanced_vars[key], width=18).grid(
            row=row, column=1, sticky="ew", padx=(8, 0), pady=3
        )
        parent.columnconfigure(1, weight=1)

    def _advanced_settings(self, *, persist: bool = True) -> dict:
        try:
            values = {
                "max_path_loss_db": float(self._advanced_vars["max_path_loss_db"].get()),
                "tx_power_dbm": float(self._advanced_vars["tx_power_dbm"].get()),
                "tx_antenna_gain_dbd": float(self._advanced_vars["tx_antenna_gain_dbd"].get()),
                "rx_sensitivity_dbm": float(self._advanced_vars["rx_sensitivity_dbm"].get()),
                "rx_antenna_gain_dbd": float(self._advanced_vars["rx_antenna_gain_dbd"].get()),
                "antenna_height_digi_m": float(self._advanced_vars["antenna_height_digi_m"].get()),
                "antenna_height_igate_m": float(self._advanced_vars["antenna_height_igate_m"].get()),
                "observer_height_m": float(self._advanced_vars["observer_height_m"].get()),
                "freq_mhz": float(self._advanced_vars["freq_mhz"].get()),
                "n_radials": int(float(self._advanced_vars["n_radials"].get())),
                "margin_display_floor_db": float(self._advanced_vars["margin_display_floor_db"].get()),
                "max_margin_db": float(self._advanced_vars["max_margin_db"].get()),
                "worker_dem_max_px": int(float(self._advanced_vars["worker_dem_max_px"].get())),
                "itm_climate": int(float(self._advanced_vars["itm_climate"].get())),
                "itm_ens": float(self._advanced_vars["itm_ens"].get()),
                "itm_sgm": float(self._advanced_vars["itm_sgm"].get()),
                "itm_epsr": float(self._advanced_vars["itm_epsr"].get()),
                "itm_pol": int(float(self._advanced_vars["itm_pol"].get())),
            }
        except ValueError as exc:
            raise ValueError("All Advanced settings must be numeric.") from exc

        checks = [
            (80 <= values["max_path_loss_db"] <= 200, "Path-loss cap must be 80–200 dB."),
            (0 <= values["tx_power_dbm"] <= 80, "TX power must be 0–80 dBm."),
            (-20 <= values["tx_antenna_gain_dbd"] <= 30, "TX antenna gain must be -20 to 30 dBd."),
            (-160 <= values["rx_sensitivity_dbm"] <= -50, "RX sensitivity must be -160 to -50 dBm."),
            (-20 <= values["rx_antenna_gain_dbd"] <= 30, "RX antenna gain must be -20 to 30 dBd."),
            (0.1 <= values["antenna_height_digi_m"] <= 500, "Digipeater antenna height must be 0.1–500 m."),
            (0.1 <= values["antenna_height_igate_m"] <= 500, "iGate antenna height must be 0.1–500 m."),
            (0.1 <= values["observer_height_m"] <= 100, "Observer height must be 0.1–100 m."),
            (20 <= values["freq_mhz"] <= 1000, "Frequency must be 20–1000 MHz."),
            (90 <= values["n_radials"] <= 2880, "Radials must be 90–2880."),
            (-30 <= values["margin_display_floor_db"] <= 20, "Margin floor must be -30 to 20 dB."),
            (0 < values["max_margin_db"] <= 100, "Maximum margin must be 0–100 dB."),
            (500 <= values["worker_dem_max_px"] <= 6000, "Worker DEM dimension must be 500–6000 px."),
            (1 <= values["itm_climate"] <= 7, "ITM climate code must be 1–7."),
            (200 <= values["itm_ens"] <= 450, "Surface refractivity must be 200–450 N-units."),
            (1e-6 <= values["itm_sgm"] <= 1.0, "Ground conductivity must be 0.000001–1 S/m."),
            (1 <= values["itm_epsr"] <= 100, "Relative permittivity must be 1–100."),
            (values["itm_pol"] in (0, 1), "Polarization must be 0 or 1."),
        ]
        for ok, message in checks:
            if not ok:
                raise ValueError(message)
        if values["margin_display_floor_db"] >= values["max_margin_db"]:
            raise ValueError("Margin floor must be lower than maximum displayed margin.")

        if persist:
            _save_advanced(values)
        return values

    def _save_advanced_from_ui(self) -> None:
        try:
            self._advanced_settings(persist=True)
        except Exception as exc:
            messagebox.showerror("Invalid Advanced settings", str(exc), parent=self)
            return
        self.advanced_status.set("Advanced settings saved and will be used by Area and Station runs.")

    def _reset_advanced(self) -> None:
        for key, value in ADVANCED_DEFAULTS.items():
            self._advanced_vars[key].set(str(value))
        _save_advanced(dict(ADVANCED_DEFAULTS))
        self.advanced_status.set("Reset to Viewshed reference defaults (148 dB path-loss cap).")

    def run_area(self) -> None:
        if not self._area_records:
            messagebox.showwarning(
                "Find stations first",
                "Acquire and review the station list before running propagation.",
                parent=self,
            )
            return
        try:
            region, prop, types = self._area_values()
            records = assess_station_locations(self._area_records)
            radio = self._advanced_settings(persist=True)
            _, job_file = prepare_job(
                region,
                Path(self.app.source_var.get()),
                types,
                prop,
                mode="area",
                selected_records=records,
                radio_settings=radio,
                frozen_stations=True,
            )
            self.app.start_job(job_file, "Area")
        except Exception as exc:
            messagebox.showerror("Cannot start area job", str(exc), parent=self)

    def run_station(self) -> None:
        rec = self._station_records.get(self.station_call.get().upper())
        if not rec:
            messagebox.showwarning("Select station", "Select a station first.", parent=self)
            return
        try:
            radius = float(self.station_radius.get())
            if not 1 <= radius <= 500:
                raise ValueError("Coverage radius must be between 1 and 500 km.")
            rec = assess_station_locations([rec])[0]
            radio = self._advanced_settings(persist=True)
            region = Region(float(rec["lat"]), float(rec["lon"]), radius)
            _, job_file = prepare_job(
                region,
                Path(self.app.source_var.get()),
                {str(rec.get("type") or "digi")},
                radius,
                mode="station",
                selected_records=[rec],
                radio_settings=radio,
                frozen_stations=True,
            )
            self.app.start_job(job_file, f"Station {rec.get('callsign')}")
        except Exception as exc:
            messagebox.showerror("Cannot start station job", str(exc), parent=self)
