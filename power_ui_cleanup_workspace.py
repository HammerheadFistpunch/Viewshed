from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from station_data_workspace import KM_PER_MI, M_PER_FT, ViewshedWorkspace as _FeatureWorkspace
from tooltips import add_tooltip
from viewshed_core import Region, prepare_job
from workspace_tuning import ViewshedWorkspace as _TunedWorkspace


class ViewshedWorkspace(_FeatureWorkspace):
    """Keep presentation controls in Output and Custom power input in watts."""

    TOOLTIP_TEXT = {
        "Operational path-loss cap (dB)": (
            "The maximum modeled signal loss Signal Peak will consider before the operational reserve is applied."
        ),
        "Operational reserve (dB)": (
            "A safety margin subtracted from the available link budget after the path-loss cap is applied. "
            "This shared value applies to Area, Station, and Custom runs. Higher values make coverage more conservative."
        ),
        "TX power (dBm)": (
            "Transmitter output power expressed in dBm. You can use the watts option below if watts are more familiar."
        ),
        "TX power (W)": "Transmitter output power in watts. Signal Peak converts this to dBm internally.",
        "TX antenna gain (dBd)": (
            "How much the transmitting antenna concentrates signal compared with a half-wave dipole. "
            "Higher gain increases the link budget."
        ),
        "RX sensitivity (dBm)": (
            "The weakest signal the assumed receiver can decode under good conditions. "
            "More-negative numbers mean a more sensitive receiver."
        ),
        "RX antenna gain (dBd)": (
            "Gain of the receiving antenna compared with a half-wave dipole. "
            "This represents the mobile or receiving-side antenna in the link budget."
        ),
        "Digipeater antenna AGL (m)": (
            "Default digipeater antenna height above the local ground when a station-specific height is not known."
        ),
        "iGate antenna AGL (m)": (
            "Default iGate antenna height above the local ground when a station-specific height is not known."
        ),
        "Receiver / observer height (m)": (
            "Height of the receiving/mobile antenna above local ground. This is the other end of each modeled radio path."
        ),
        "Frequency (MHz)": (
            "Radio frequency used by the propagation model. APRS in North America normally uses 144.390 MHz."
        ),
        "Radials per station": (
            "Number of directions calculated outward from each station. More radials improve angular detail but take longer to compute."
        ),
        "Worker DEM max dimension (px)": (
            "Limits the terrain grid size used by a worker. Larger values preserve more terrain detail but use more memory."
        ),
        "ITM climate code (1–7)": (
            "Longley-Rice climate category used by the propagation model. The default represents the reference profile; change it only for a specific modeling reason."
        ),
        "Surface refractivity N-units": (
            "How strongly the atmosphere bends VHF radio waves near the surface. This is an ITM environmental input."
        ),
        "Ground conductivity (S/m)": (
            "How well the ground conducts radio energy. It affects modeled propagation, especially interactions with the terrain surface."
        ),
        "Relative permittivity": (
            "Electrical property of the ground used by ITM. Higher values mean the ground behaves more strongly as a dielectric."
        ),
        "Polarization (0=H, 1=V)": (
            "Antenna polarization used by ITM: 0 is horizontal and 1 is vertical. APRS mobile and infrastructure antennas are normally vertical."
        ),
        "Heatmap band size (dB)": (
            "Width of each color step in the coverage heatmap. Smaller values show finer changes in link margin."
        ),
        "Maximum displayed margin (dB)": (
            "Top of the heatmap color scale. Margin above this value is still good coverage; it is simply shown with the strongest color."
        ),
        "Overlay / inverse opacity (%)": (
            "How solid the coverage and inverse overlays appear. Lower values reveal more of the base map underneath."
        ),
        "Per-station display floor (dB)": (
            "Lowest link margin that will be drawn. Zero shows only coverage at or above the operational edge; a negative value also shows marginal predicted coverage."
        ),
        "Latitude": "North/south position of the custom station.",
        "Longitude": "East/west position of the custom station.",
        "Coverage radius (km)": (
            "Maximum distance from the custom station that Signal Peak will calculate. This limits the search area; it does not guarantee coverage to that distance."
        ),
        "Antenna height AGL (m)": "Height of the custom station antenna above the ground at the site.",
    }

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        if "advanced_power_watts" not in self._ui_prefs:
            self.advanced_power_watts.set(True)
            self._advanced_power_unit_changed()
        self._hide_output_fields_from_advanced()
        self._install_plain_language_tooltips()

    def _install_plain_language_tooltips(self) -> None:
        """Attach plain-language hover help to labels and their input controls."""
        def visit(widget) -> None:
            for child in widget.winfo_children():
                try:
                    text = child.cget("text")
                except Exception:
                    text = None
                help_text = self.TOOLTIP_TEXT.get(str(text)) if text else None
                if help_text:
                    add_tooltip(child, help_text)
                    try:
                        info = child.grid_info()
                        row = int(info.get("row", -1))
                        parent = child.master
                        for sibling in parent.winfo_children():
                            if sibling is child:
                                continue
                            try:
                                sibling_info = sibling.grid_info()
                                if int(sibling_info.get("row", -2)) == row:
                                    add_tooltip(sibling, help_text)
                            except Exception:
                                pass
                    except Exception:
                        pass
                visit(child)

        visit(self)

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
        # Keep the established Custom/future-station UI while using the shared
        # Advanced propagation profile at run time.
        _TunedWorkspace._build_custom(self)
        self.custom_power_value = self.custom_power_w
        self.custom_power_dbm_mode = tk.BooleanVar(value=False)

        # Remove the legacy Custom-only reserve assumption. Operational reserve
        # is now a shared Advanced setting for every propagation mode.
        def remove_legacy_note(widget) -> None:
            for child in widget.winfo_children():
                try:
                    text = str(child.cget("text"))
                except Exception:
                    text = ""
                if isinstance(child, ttk.Label) and "operational reserve" in text.lower():
                    child.destroy()
                    continue
                remove_legacy_note(child)

        remove_legacy_note(self.custom_tab)

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
            if not -20 <= gain <= 30:
                raise ValueError("TX antenna gain must be between -20 and 30 dBd.")
            if not 20 <= freq <= 1000:
                raise ValueError("Frequency must be between 20 and 1000 MHz.")

            tx_dbm = 10.0 * math.log10(power_w * 1000.0)
            if tx_dbm > 80:
                raise ValueError("TX power exceeds the supported 80 dBm maximum.")

            record = {
                "callsign": "CUSTOM",
                "type": "digi",
                "lat": lat,
                "lon": lon,
                "_source": "reviewed_override",
                "lasttime": 0,
            }

            # Start with the same validated propagation profile used by Area and
            # Station. Override only the proposed transmitter/site parameters.
            radio = self._advanced_settings(persist=True)
            radio.update(
                {
                    "freq_mhz": freq,
                    "antenna_height_digi_m": height,
                    "tx_power_dbm": tx_dbm,
                    "tx_antenna_gain_dbd": gain,
                }
            )

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
