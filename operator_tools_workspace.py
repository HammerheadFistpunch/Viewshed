from __future__ import annotations

import threading
import tkinter as tk
from contextlib import contextmanager
from tkinter import messagebox, ttk

import aprs_viewshed_utah_parallel as _engine
from feature_ui_workspace import ViewshedWorkspace as _ViewshedWorkspace
from reverse_haat import reverse_haat
from station_rf_worker import install as _install_station_rf_worker
from viewshed_core import portable_data_root

_install_station_rf_worker(_engine)

KM_PER_MI = 1.609344
M_PER_FT = 0.3048


class ViewshedWorkspace(_ViewshedWorkspace):
    """Operator-facing units, reverse HAAT, and per-station RF override support."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        saved = str(self._ui_prefs.get("measurement_units", "metric")).lower()
        self.unit_mode = tk.StringVar(value="imperial" if saved == "imperial" else "metric")
        self._display_unit_mode = "metric"
        self._build_tools_tab()
        self._sync_haat_station_catalog()
        if self.unit_mode.get() == "imperial":
            self._apply_unit_mode()

    @property
    def _imperial(self) -> bool:
        return hasattr(self, "unit_mode") and self.unit_mode.get() == "imperial"

    @staticmethod
    def _convert_var(var, factor: float) -> None:
        try:
            value = float(var.get())
        except Exception:
            return
        var.set(f"{value * factor:.6g}")

    def _replace_unit_labels(self, imperial: bool) -> None:
        replacements = {
            "Area radius (km)": "Area radius (mi)" if imperial else "Area radius (km)",
            "Station coverage radius (km)": "Station coverage radius (mi)" if imperial else "Station coverage radius (km)",
            "Coverage radius (km)": "Coverage radius (mi)" if imperial else "Coverage radius (km)",
            "Max calculation range (km)": "Max calculation range (mi)" if imperial else "Max calculation range (km)",
            "Antenna height AGL (m)": "Antenna height AGL (ft)" if imperial else "Antenna height AGL (m)",
            "Digipeater antenna AGL (m)": "Digipeater antenna AGL (ft)" if imperial else "Digipeater antenna AGL (m)",
            "iGate antenna AGL (m)": "iGate antenna AGL (ft)" if imperial else "iGate antenna AGL (m)",
            "Receiver / observer height (m)": "Receiver / observer height (ft)" if imperial else "Receiver / observer height (m)",
            "Area radius (mi)": "Area radius (mi)" if imperial else "Area radius (km)",
            "Station coverage radius (mi)": "Station coverage radius (mi)" if imperial else "Station coverage radius (km)",
            "Coverage radius (mi)": "Coverage radius (mi)" if imperial else "Coverage radius (km)",
            "Max calculation range (mi)": "Max calculation range (mi)" if imperial else "Max calculation range (km)",
            "Antenna height AGL (ft)": "Antenna height AGL (ft)" if imperial else "Antenna height AGL (m)",
            "Digipeater antenna AGL (ft)": "Digipeater antenna AGL (ft)" if imperial else "Digipeater antenna AGL (m)",
            "iGate antenna AGL (ft)": "iGate antenna AGL (ft)" if imperial else "iGate antenna AGL (m)",
            "Receiver / observer height (ft)": "Receiver / observer height (ft)" if imperial else "Receiver / observer height (m)",
        }

        def visit(widget):
            try:
                text = widget.cget("text")
                if text in replacements:
                    widget.configure(text=replacements[text])
            except Exception:
                pass
            try:
                children = widget.winfo_children()
            except Exception:
                children = []
            for child in children:
                visit(child)

        visit(self)

    def _apply_unit_mode(self) -> None:
        target = self.unit_mode.get()
        if target == self._display_unit_mode:
            return
        to_imperial = target == "imperial"
        distance_factor = 1.0 / KM_PER_MI if to_imperial else KM_PER_MI
        height_factor = 1.0 / M_PER_FT if to_imperial else M_PER_FT
        for name in ("area_radius", "area_prop", "station_radius", "custom_radius"):
            var = getattr(self, name, None)
            if var is not None:
                self._convert_var(var, distance_factor)
        if hasattr(self, "custom_height"):
            self._convert_var(self.custom_height, height_factor)
        for key in ("antenna_height_digi_m", "antenna_height_igate_m", "observer_height_m"):
            var = self._advanced_vars.get(key)
            if var is not None:
                self._convert_var(var, height_factor)
        self._display_unit_mode = target
        self._replace_unit_labels(to_imperial)
        self._ui_prefs["measurement_units"] = target
        try:
            from feature_ui_workspace import _save_prefs
            _save_prefs(self._ui_prefs)
        except Exception:
            pass

    @contextmanager
    def _metric_values(self, specs):
        if not self._imperial:
            yield
            return
        saved = []
        try:
            for var, factor in specs:
                saved.append((var, var.get()))
                var.set(str(float(var.get()) * factor))
            yield
        finally:
            for var, value in saved:
                var.set(value)

    def _area_values(self):
        if not self._imperial:
            return super()._area_values()
        with self._metric_values(((self.area_radius, KM_PER_MI), (self.area_prop, KM_PER_MI))):
            return super()._area_values()

    def _advanced_settings(self, *, persist: bool = True) -> dict:
        if not self._imperial:
            return super()._advanced_settings(persist=persist)
        specs = tuple((self._advanced_vars[k], M_PER_FT) for k in (
            "antenna_height_digi_m", "antenna_height_igate_m", "observer_height_m"
        ))
        with self._metric_values(specs):
            return super()._advanced_settings(persist=persist)

    def run_station(self) -> None:
        if not self._imperial:
            return super().run_station()
        with self._metric_values(((self.station_radius, KM_PER_MI),)):
            return super().run_station()

    def run_custom(self) -> None:
        if not self._imperial:
            return super().run_custom()
        with self._metric_values(((self.custom_radius, KM_PER_MI), (self.custom_height, M_PER_FT))):
            return super().run_custom()

    def _draw_custom(self, initial: bool = False) -> None:
        if not self._imperial:
            return super()._draw_custom(initial=initial)
        with self._metric_values(((self.custom_radius, KM_PER_MI), (self.custom_height, M_PER_FT))):
            return super()._draw_custom(initial=initial)

    def reload_station_catalog(self) -> None:
        super().reload_station_catalog()
        self._sync_haat_station_catalog()

    def _set_station_catalog(self, records: list[dict], source_label: str) -> None:
        super()._set_station_catalog(records, source_label)
        self._sync_haat_station_catalog()

    def _sync_haat_station_catalog(self) -> None:
        combo = getattr(self, "haat_station_combo", None)
        if combo is None:
            return
        calls = sorted(getattr(self, "_station_records", {}).keys())
        combo["values"] = calls
        current = self.haat_station_call.get().strip().upper()
        if current not in getattr(self, "_station_records", {}):
            self.haat_station_call.set("")
        if calls:
            self.haat_station_status.set(
                f"{len(calls)} station(s) available. Selecting one fills its reviewed coordinates; manual coordinates remain editable."
            )
        else:
            self.haat_station_status.set("No station catalog is loaded. Enter latitude/longitude manually or load stations from the Station tab.")

    def _haat_station_selected(self, _event=None) -> None:
        call = self.haat_station_call.get().strip().upper()
        rec = getattr(self, "_station_records", {}).get(call)
        if not rec:
            return
        try:
            self.haat_lat.set(f"{float(rec['lat']):.6f}")
            self.haat_lon.set(f"{float(rec['lon']):.6f}")
        except (KeyError, TypeError, ValueError):
            self.haat_station_status.set(f"{call} does not have usable coordinates.")
            return
        source = str(rec.get("_location_confidence") or rec.get("_source") or "catalog")
        self.haat_station_status.set(f"{call} selected — coordinates loaded from {source}. You can edit them before calculating.")

    def _build_tools_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Tools")

        units = ttk.LabelFrame(tab, text="Input units", padding=10)
        units.pack(fill="x")
        ttk.Label(units, text="Choose how distance and height fields are entered and displayed. Internal propagation math remains metric.").pack(anchor="w")
        row = ttk.Frame(units)
        row.pack(anchor="w", pady=(8, 0))
        ttk.Radiobutton(row, text="Metric (km / m)", value="metric", variable=self.unit_mode, command=self._apply_unit_mode).pack(side="left")
        ttk.Radiobutton(row, text="Imperial (mi / ft)", value="imperial", variable=self.unit_mode, command=self._apply_unit_mode).pack(side="left", padx=(16, 0))

        box = ttk.LabelFrame(tab, text="Reverse HAAT calculator", padding=10)
        box.pack(fill="x", pady=(12, 0))
        ttk.Label(box, text="Solve the antenna height AGL required to reach a target FCC-style HAAT using 8 radials and terrain from 2–10 miles.", wraplength=850).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.haat_station_call = tk.StringVar(value="")
        self.haat_station_status = tk.StringVar(value="Select a station or enter coordinates manually.")
        self.haat_lat = tk.StringVar(value="40.7608")
        self.haat_lon = tk.StringVar(value="-111.8910")
        self.haat_target = tk.StringVar(value="300")
        self.haat_status = tk.StringVar(value="Enter a site and target HAAT, then calculate.")

        ttk.Label(box, text="Station").grid(row=1, column=0, sticky="w", pady=3)
        self.haat_station_combo = ttk.Combobox(box, textvariable=self.haat_station_call, width=24, state="readonly")
        self.haat_station_combo.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=3)
        self.haat_station_combo.bind("<<ComboboxSelected>>", self._haat_station_selected)
        ttk.Label(box, textvariable=self.haat_station_status, wraplength=520).grid(row=1, column=2, sticky="w", padx=(8, 0), pady=3)

        for row_index, (label, var) in enumerate((("Latitude", self.haat_lat), ("Longitude", self.haat_lon), ("Target HAAT", self.haat_target)), start=2):
            ttk.Label(box, text=label).grid(row=row_index, column=0, sticky="w", pady=3)
            ttk.Entry(box, textvariable=var, width=18).grid(row=row_index, column=1, sticky="w", padx=(8, 0), pady=3)
        self.haat_unit_label = ttk.Label(box, text="m (or ft in Imperial mode)")
        self.haat_unit_label.grid(row=4, column=2, sticky="w", padx=(8, 0))
        self.haat_btn = ttk.Button(box, text="Calculate required antenna AGL", command=self._start_reverse_haat)
        self.haat_btn.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(box, textvariable=self.haat_status, wraplength=850).grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _start_reverse_haat(self) -> None:
        try:
            lat = float(self.haat_lat.get())
            lon = float(self.haat_lon.get())
            target = float(self.haat_target.get())
            if self._imperial:
                target *= M_PER_FT
        except ValueError:
            messagebox.showerror("Reverse HAAT", "Latitude, longitude, and target HAAT must be numeric.", parent=self)
            return
        self.haat_btn.configure(state="disabled")
        self.haat_status.set("Calculating terrain average and required antenna height…")

        def work():
            try:
                result = reverse_haat(lat, lon, target, portable_data_root() / "cache" / "dem")
                self.after(0, lambda r=result: self._finish_reverse_haat(r))
            except Exception as exc:
                self.after(0, lambda e=exc: self._fail_reverse_haat(e))

        threading.Thread(target=work, daemon=True).start()

    def _finish_reverse_haat(self, result: dict) -> None:
        self.haat_btn.configure(state="normal")
        if self._imperial:
            agl = result["required_antenna_agl_m"] / M_PER_FT
            site = result["site_elevation_m"] / M_PER_FT
            terrain = result["average_terrain_m"] / M_PER_FT
            unit = "ft"
        else:
            agl = result["required_antenna_agl_m"]
            site = result["site_elevation_m"]
            terrain = result["average_terrain_m"]
            unit = "m"
        self.haat_status.set(
            f"Required antenna AGL: {agl:.1f} {unit} · site ground: {site:.1f} {unit} AMSL · average 2–10 mi terrain: {terrain:.1f} {unit} AMSL"
        )

    def _fail_reverse_haat(self, exc: Exception) -> None:
        self.haat_btn.configure(state="normal")
        self.haat_status.set(f"Reverse HAAT failed: {exc}")
