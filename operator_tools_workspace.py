from __future__ import annotations

import tkinter as tk
from contextlib import contextmanager
from tkinter import ttk

import aprs_viewshed_utah_parallel as _engine
from feature_ui_workspace import ViewshedWorkspace as _ViewshedWorkspace
from station_rf_worker import install as _install_station_rf_worker

_install_station_rf_worker(_engine)

KM_PER_MI = 1.609344
M_PER_FT = 0.3048


class ViewshedWorkspace(_ViewshedWorkspace):
    """Operator-facing input units and per-station RF override support."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        saved = str(self._ui_prefs.get("measurement_units", "metric")).lower()
        self.unit_mode = tk.StringVar(value="imperial" if saved == "imperial" else "metric")
        self._display_unit_mode = "metric"
        self._build_tools_tab()
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

    def _sync_haat_station_catalog(self) -> None:
        """Compatibility no-op retained for the station-data workspace chain."""
        return

    def _build_tools_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Tools")

        units = ttk.LabelFrame(tab, text="Input units", padding=10)
        units.pack(fill="x")
        ttk.Label(
            units,
            text="Choose how distance and height fields are entered and displayed. Internal propagation math remains metric.",
        ).pack(anchor="w")
        row = ttk.Frame(units)
        row.pack(anchor="w", pady=(8, 0))
        ttk.Radiobutton(
            row,
            text="Metric (km / m)",
            value="metric",
            variable=self.unit_mode,
            command=self._apply_unit_mode,
        ).pack(side="left")
        ttk.Radiobutton(
            row,
            text="Imperial (mi / ft)",
            value="imperial",
            variable=self.unit_mode,
            command=self._apply_unit_mode,
        ).pack(side="left", padx=(16, 0))
