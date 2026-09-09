from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from station_data_workspace import KM_PER_MI, M_PER_FT, ViewshedWorkspace as _FeatureWorkspace
from viewshed_core import Region, prepare_job
from workspace_tuning import (
    CUSTOM_OPERATIONAL_RESERVE_DB,
    GAP_FILL_FACTOR,
    REFERENCE_RADIALS,
    ViewshedWorkspace as _TunedWorkspace,
)


class ViewshedWorkspace(_FeatureWorkspace):
    """Keep presentation controls in Output and Custom power input in watts."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        # Watts are the more familiar operator-facing unit. If the user has not
        # explicitly saved a preference yet, make Advanced start in watts while
        # preserving dBm internally for the propagation engine.
        if "advanced_power_watts" not in self._ui_prefs:
            self.advanced_power_watts.set(True)
            self._advanced_power_unit_changed()
        self._hide_output_fields_from_advanced()

    def _hide_output_fields_from_advanced(self) -> None:
        """Keep display-only margin controls exclusively on the Output tab."""
        advanced_tab = None
        for tab_id in self.notebook.tabs():
            try:
                if self.notebook.tab(tab_id, "text") == "Advanced":
                    advanced_tab = self.nametowidget(tab_id)
                    break
            except Exception:
                continue
        if advanced_tab is None:
            return

        labels = {"Displayed margin floor (dB)", "Maximum displayed margin (dB)"}

        def visit(widget) -> None:
            for child in widget.winfo_children():
                try:
                    if isinstance(child, ttk.Label) and child.cget("text") in labels:
                        info = child.grid_info()
                        row = int(info.get("row", -1))
                        parent = child.master
                        child.grid_remove()
                        for sibling in parent.winfo_children():
                            if sibling is child:
                                continue
                            try:
                                sibling_info = sibling.grid_info()
                                if int(sibling_info.get("row", -2)) == row:
                                    sibling.grid_remove()
                            except Exception:
                                pass
                        continue
                except Exception:
                    pass
                visit(child)

        visit(advanced_tab)

    def _build_custom(self) -> None:
        # Use the established Custom/future-station UI: TX power is entered in W.
        # Keep compatibility aliases used elsewhere in the workspace chain.
        _TunedWorkspace._build_custom(self)
        self.custom_power_value = self.custom_power_w
        self.custom_power_dbm_mode = tk.BooleanVar(value=False)

    def run_custom(self) -> None:
        if getattr(self, "_imperial", False):
            with self._metric_values(((self.custom_radius, KM_PER_MI), (self.custom_height, M_PER_FT))):
                return self._run_custom_with_output_settings()
        return self._run_custom_with_output_settings()

    def _run_custom_with_output_settings(self) -> None:
        try:
            lat = float(self.custom_lat.get())
            lon = float(self.custom_lon.get())
            radius = float(self.custom_radius.get())
            height = float(self.custom_height.get())
            power_w = float(self.custom_power_w.get())
            gain = float(self.custom_gain.get())
            freq = float(self.custom_freq.get())
            Region(lat, lon, radius).validate()
            if height <= 0:
                raise ValueError("Antenna height must be positive.")
            if power_w <= 0:
                raise ValueError("TX power in watts must be positive.")
            if not 20 <= freq <= 1000:
                raise ValueError("Frequency must be between 20 and 1000 MHz.")

            tx_dbm = 10.0 * math.log10(power_w * 1000.0)
            if tx_dbm > 80:
                raise ValueError("TX power exceeds the supported 80 dBm maximum.")

            path_budget = tx_dbm + 119.0 + gain + 2.0 - CUSTOM_OPERATIONAL_RESERVE_DB
            record = {
                "callsign": "CUSTOM",
                "type": "digi",
                "lat": lat,
                "lon": lon,
                "_source": "reviewed_override",
                "lasttime": 0,
            }
            radio = {
                "freq_mhz": freq,
                "antenna_height_digi_m": height,
                "tx_power_dbm": tx_dbm,
                "tx_antenna_gain_dbd": gain,
                "max_path_loss_db": path_budget,
                "margin_display_floor_db": float(self._advanced_vars["margin_display_floor_db"].get()),
                "max_margin_db": float(self._advanced_vars["max_margin_db"].get()),
                "network_heatmap_band_db": float(self.heatmap_band_db.get()),
                "overlay_alpha": int(round(255.0 * float(self.overlay_opacity_pct.get()) / 100.0)),
                "n_radials": REFERENCE_RADIALS,
                "gap_fill_factor": GAP_FILL_FACTOR,
            }
            _, job_file = prepare_job(
                Region(lat, lon, radius),
                Path(self.app.source_var.get()),
                {"digi"},
                radius,
                mode="custom",
                selected_records=[record],
                radio_settings=radio,
                frozen_stations=True,
            )
            self.app.start_job(job_file, "Custom station")
        except Exception as exc:
            messagebox.showerror("Cannot start custom job", str(exc), parent=self)
