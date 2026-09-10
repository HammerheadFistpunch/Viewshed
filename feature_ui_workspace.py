from __future__ import annotations

import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, messagebox, ttk

import tkintermapview

from output_styles import (
    DEFAULT_GAP_COLOR,
    DEFAULT_HEATMAP_COLORS,
    DEFAULT_POSITIVE_COLOR,
    DEFAULT_REDUNDANCY_COLORS,
    apply_output_preset,
    normalize_hex,
)
from workspace_tuning import (
    CUSTOM_OPERATIONAL_RESERVE_DB,
    GAP_FILL_FACTOR,
    REFERENCE_RADIALS,
    ViewshedWorkspace as _ViewshedWorkspace,
)
from viewshed_core import Region, assess_station_locations, portable_data_root, prepare_job


_UI_PREFS_FILE = "output_ui_settings.json"


def _prefs_path() -> Path:
    return portable_data_root() / _UI_PREFS_FILE


def _load_prefs() -> dict:
    path = _prefs_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_prefs(values: dict) -> None:
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, indent=2), encoding="utf-8")


def _find_widget_by_text(root, widget_type, text: str):
    for child in root.winfo_children():
        try:
            if isinstance(child, widget_type) and child.cget("text") == text:
                return child
        except Exception:
            pass
        found = _find_widget_by_text(child, widget_type, text)
        if found is not None:
            return found
    return None


class ViewshedWorkspace(_ViewshedWorkspace):
    """Run-scoped station lists, unified output styling, and operator power units."""

    def __init__(self, master, app) -> None:
        self._ui_prefs = _load_prefs()
        self._advanced_power_is_watts_current = False
        super().__init__(master, app)
        self._install_advanced_power_unit_control()
        self._build_output_tab()

    def _build_station(self) -> None:
        super()._build_station()
        self.station_catalog_status = tk.StringVar(
            value="Showing the full cached station catalog until an Area station search is completed."
        )
        reload_btn = _find_widget_by_text(self.station_tab, ttk.Button, "Reload stations")
        if reload_btn is not None:
            reload_btn.configure(text="Load full cached catalog")
            controls = reload_btn.master.master
            ttk.Label(controls, textvariable=self.station_catalog_status, wraplength=330).pack(anchor="w", pady=(8, 0))

    def reload_station_catalog(self) -> None:
        super().reload_station_catalog()
        if hasattr(self, "station_catalog_status"):
            self.station_catalog_status.set(
                f"Full cached catalog loaded: {len(self._station_records)} station(s). "
                "The next Area station search will replace this list with that run's stations."
            )

    def _set_station_catalog(self, records: list[dict], source_label: str) -> None:
        assessed = assess_station_locations(records)
        self._station_records = {
            str(r.get("callsign") or "").upper(): r
            for r in assessed
            if r.get("callsign") and r.get("type") in {"digi", "igate"} and "lat" in r and "lon" in r
        }
        calls = sorted(self._station_records)
        self.station_combo["values"] = calls
        current = self.station_call.get().strip().upper()
        if current not in self._station_records:
            self.station_call.set(calls[0] if calls else "")
        self._station_selected()
        if hasattr(self, "station_catalog_status"):
            self.station_catalog_status.set(
                f"Showing {len(calls)} station(s) from {source_label}. "
                "Use 'Load full cached catalog' only when you intentionally want the cumulative cache."
            )

    def _area_acquired(self, records: list[dict]) -> None:
        super()._area_acquired(records)
        self._set_station_catalog(records, "the most recent Area search")

    def _install_advanced_power_unit_control(self) -> None:
        power_var = self._advanced_vars.get("tx_power_dbm")
        if power_var is None:
            return
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
        self._advanced_power_label = _find_widget_by_text(advanced_tab, ttk.Label, "TX power (dBm)")
        saved_watts = bool(self._ui_prefs.get("advanced_power_watts", False))
        self.advanced_power_watts = tk.BooleanVar(value=saved_watts)
        row = ttk.Frame(advanced_tab)
        row.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(row, text="Enter TX power in watts", variable=self.advanced_power_watts, command=self._advanced_power_unit_changed).pack(side="left")
        ttk.Label(row, text="Internally converted to dBm for link-budget math.").pack(side="left", padx=(10, 0))
        if saved_watts:
            self._convert_advanced_power_display(True)
        else:
            self._update_advanced_power_label()

    def _update_advanced_power_label(self) -> None:
        if getattr(self, "_advanced_power_label", None) is not None:
            self._advanced_power_label.configure(text="TX power (W)" if self._advanced_power_is_watts_current else "TX power (dBm)")

    def _convert_advanced_power_display(self, target_watts: bool) -> None:
        if target_watts == self._advanced_power_is_watts_current:
            self._update_advanced_power_label()
            return
        var = self._advanced_vars.get("tx_power_dbm")
        if var is None:
            return
        try:
            value = float(var.get())
            if target_watts:
                var.set(f"{10.0 ** ((value - 30.0) / 10.0):.4g}")
            else:
                if value <= 0:
                    raise ValueError("TX power in watts must be positive.")
                var.set(f"{10.0 * math.log10(value * 1000.0):.3f}")
        except ValueError as exc:
            messagebox.showerror("Invalid TX power", str(exc), parent=self)
            if hasattr(self, "advanced_power_watts"):
                self.advanced_power_watts.set(self._advanced_power_is_watts_current)
            return
        self._advanced_power_is_watts_current = target_watts
        self._update_advanced_power_label()

    def _advanced_power_unit_changed(self) -> None:
        self._convert_advanced_power_display(bool(self.advanced_power_watts.get()))

    def _collect_output_settings(self) -> dict:
        try:
            band_db = float(self.heatmap_band_db.get())
            opacity_pct = float(self.overlay_opacity_pct.get())
        except (AttributeError, ValueError) as exc:
            raise ValueError("Heatmap band size and opacity must be numeric.") from exc
        if not 0.5 <= band_db <= 20.0:
            raise ValueError("Heatmap band size must be between 0.5 and 20 dB.")
        if not 5.0 <= opacity_pct <= 100.0:
            raise ValueError("Overlay opacity must be between 5 and 100 percent.")
        return {
            "network_heatmap_band_db": band_db,
            "overlay_alpha": int(round(255.0 * opacity_pct / 100.0)),
            "output_stations": bool(self.output_stations.get()),
            "output_network_heatmap": bool(self.output_network_heatmap.get()),
            "output_positive": bool(self.output_positive.get()),
            "output_gaps": bool(self.output_gaps.get()),
            "output_redundancy": bool(self.output_redundancy.get()),
            "output_per_station_heatmaps": bool(self.output_per_station_heatmaps.get()),
            "heatmap_colors": [normalize_hex(v.get(), DEFAULT_HEATMAP_COLORS[i]) for i, v in enumerate(self.heatmap_color_vars)],
            "positive_color": normalize_hex(self.positive_color.get(), DEFAULT_POSITIVE_COLOR),
            "gap_color": normalize_hex(self.gap_color.get(), DEFAULT_GAP_COLOR),
            "redundancy_colors": [normalize_hex(v.get(), DEFAULT_REDUNDANCY_COLORS[i]) for i, v in enumerate(self.redundancy_color_vars)],
        }

    def _advanced_settings(self, *, persist: bool = True) -> dict:
        power_var = self._advanced_vars.get("tx_power_dbm")
        displayed_power = power_var.get() if power_var is not None else None
        restore_watts = self._advanced_power_is_watts_current
        if power_var is not None and restore_watts:
            watts = float(displayed_power)
            if watts <= 0:
                raise ValueError("TX power in watts must be positive.")
            power_var.set(str(10.0 * math.log10(watts * 1000.0)))
        try:
            values = super()._advanced_settings(persist=persist)
        finally:
            if power_var is not None and displayed_power is not None:
                power_var.set(displayed_power)
        output = self._collect_output_settings()
        values.update(output)
        values["gap_fill_factor"] = GAP_FILL_FACTOR
        if persist:
            self._ui_prefs.update(output)
            self._ui_prefs.update({
                "advanced_power_watts": bool(self.advanced_power_watts.get()),
                "overlay_opacity_pct": float(self.overlay_opacity_pct.get()),
                "output_preset": self.output_preset.get(),
            })
            _save_prefs(self._ui_prefs)
        return values

    def _reset_advanced(self) -> None:
        was_watts = self._advanced_power_is_watts_current
        if was_watts:
            self._convert_advanced_power_display(False)
        super()._reset_advanced()
        if was_watts:
            self.advanced_power_watts.set(True)
            self._convert_advanced_power_display(True)

    def _build_output_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Output")
        ttk.Label(tab, text="Output builder", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(tab, text="Choose which products are exported and how they are styled. These settings do not change propagation math.", wraplength=900).pack(anchor="w", pady=(3, 8))

        preset_row = ttk.Frame(tab)
        preset_row.pack(fill="x", pady=(0, 8))
        ttk.Label(preset_row, text="Preset").pack(side="left")
        self.output_preset = tk.StringVar(value=str(self._ui_prefs.get("output_preset", "Standard")))
        preset = ttk.Combobox(preset_row, textvariable=self.output_preset, state="readonly", width=22, values=("Standard", "Coverage Analysis", "Station Analysis", "Everything", "Custom"))
        preset.pack(side="left", padx=(8, 0))
        preset.bind("<<ComboboxSelected>>", lambda _e: self._apply_output_preset())

        layers = ttk.LabelFrame(tab, text="Layers", padding=10)
        layers.pack(fill="x", pady=(0, 8))
        defaults = apply_output_preset("Standard")
        self.output_stations = tk.BooleanVar(value=bool(self._ui_prefs.get("output_stations", defaults["output_stations"])))
        self.output_network_heatmap = tk.BooleanVar(value=bool(self._ui_prefs.get("output_network_heatmap", defaults["output_network_heatmap"])))
        self.output_positive = tk.BooleanVar(value=bool(self._ui_prefs.get("output_positive", defaults["output_positive"])))
        self.output_gaps = tk.BooleanVar(value=bool(self._ui_prefs.get("output_gaps", defaults["output_gaps"])))
        self.output_redundancy = tk.BooleanVar(value=bool(self._ui_prefs.get("output_redundancy", defaults["output_redundancy"])))
        self.output_per_station_heatmaps = tk.BooleanVar(value=bool(self._ui_prefs.get("output_per_station_heatmaps", defaults["output_per_station_heatmaps"])))
        layer_items = (
            ("Station pins / metadata", self.output_stations),
            ("Composite heat map", self.output_network_heatmap),
            ("Positive coverage", self.output_positive),
            ("Coverage gaps", self.output_gaps),
            ("Coverage redundancy", self.output_redundancy),
            ("Per-station heat maps", self.output_per_station_heatmaps),
        )
        for i, (label, var) in enumerate(layer_items):
            ttk.Checkbutton(layers, text=label, variable=var, command=self._layers_changed).grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 24), pady=3)

        heat = ttk.LabelFrame(tab, text="Heat map style", padding=10)
        heat.pack(fill="x", pady=(0, 8))
        self.heatmap_band_db = tk.StringVar(value=str(self._ui_prefs.get("network_heatmap_band_db", 3.0)))
        self.overlay_opacity_pct = tk.StringVar(value=str(self._ui_prefs.get("overlay_opacity_pct", 70.0)))
        self._field(heat, 0, "Heatmap band size (dB)", self.heatmap_band_db)
        self._field(heat, 1, "Maximum displayed margin (dB)", self._advanced_vars["max_margin_db"])
        self._field(heat, 2, "Overlay opacity (%)", self.overlay_opacity_pct)
        saved_heat = self._ui_prefs.get("heatmap_colors") or DEFAULT_HEATMAP_COLORS
        self.heatmap_color_vars = [tk.StringVar(value=normalize_hex(saved_heat[i] if i < len(saved_heat) else DEFAULT_HEATMAP_COLORS[i], DEFAULT_HEATMAP_COLORS[i])) for i in range(6)]
        color_row = ttk.Frame(heat)
        color_row.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(color_row, text="Weak → strong").pack(side="left", padx=(0, 8))
        for var in self.heatmap_color_vars:
            ttk.Button(color_row, textvariable=var, width=9, command=lambda v=var: self._choose_color(v)).pack(side="left", padx=2)

        simple = ttk.LabelFrame(tab, text="Coverage layer colors", padding=10)
        simple.pack(fill="x")
        self.positive_color = tk.StringVar(value=normalize_hex(self._ui_prefs.get("positive_color", DEFAULT_POSITIVE_COLOR), DEFAULT_POSITIVE_COLOR))
        self.gap_color = tk.StringVar(value=normalize_hex(self._ui_prefs.get("gap_color", DEFAULT_GAP_COLOR), DEFAULT_GAP_COLOR))
        saved_red = self._ui_prefs.get("redundancy_colors") or DEFAULT_REDUNDANCY_COLORS
        self.redundancy_color_vars = [tk.StringVar(value=normalize_hex(saved_red[i] if i < len(saved_red) else DEFAULT_REDUNDANCY_COLORS[i], DEFAULT_REDUNDANCY_COLORS[i])) for i in range(3)]
        ttk.Label(simple, text="Positive").grid(row=0, column=0, sticky="w")
        ttk.Button(simple, textvariable=self.positive_color, width=10, command=lambda: self._choose_color(self.positive_color)).grid(row=0, column=1, padx=(8, 20))
        ttk.Label(simple, text="Coverage gap").grid(row=0, column=2, sticky="w")
        ttk.Button(simple, textvariable=self.gap_color, width=10, command=lambda: self._choose_color(self.gap_color)).grid(row=0, column=3, padx=(8, 20))
        ttk.Label(simple, text="Redundancy 1 / 2 / 3+").grid(row=1, column=0, sticky="w", pady=(6, 0))
        for i, var in enumerate(self.redundancy_color_vars):
            ttk.Button(simple, textvariable=var, width=10, command=lambda v=var: self._choose_color(v)).grid(row=1, column=i + 1, padx=(8 if i == 0 else 2, 2), pady=(6, 0))

        ttk.Label(tab, text="Per-station heat maps now use the same stepped link-margin palette as the composite heat map. Station pins are independent of coverage layers.", wraplength=900).pack(anchor="w", pady=(8, 0))
        ttk.Button(tab, text="Save output settings", command=self._save_output_settings).pack(anchor="w", pady=(10, 0))
        self.output_status = tk.StringVar(value=f"Output preferences: {_prefs_path()}")
        ttk.Label(tab, textvariable=self.output_status, wraplength=900).pack(anchor="w", pady=(8, 0))

    def _choose_color(self, var: tk.StringVar) -> None:
        chosen = colorchooser.askcolor(color=var.get(), parent=self)[1]
        if chosen:
            var.set(chosen.upper())

    def _apply_output_preset(self) -> None:
        settings = apply_output_preset(self.output_preset.get())
        if not settings:
            return
        for key, value in settings.items():
            getattr(self, key).set(value)

    def _layers_changed(self) -> None:
        self.output_preset.set("Custom")

    def _save_output_settings(self) -> None:
        try:
            self._advanced_settings(persist=True)
        except Exception as exc:
            messagebox.showerror("Invalid output settings", str(exc), parent=self)
            return
        self.output_status.set("Output settings saved. They will be applied to the next Area, Station, or Custom run.")

    def _build_custom(self) -> None:
        controls, map_frame = self._split(self.custom_tab, 360)
        ttk.Label(controls, text="Custom / future station", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(controls, text="Click the map to place a proposed station, then define the installation assumptions.", wraplength=340).pack(anchor="w", pady=(3, 10))
        box = ttk.LabelFrame(controls, text="Proposed site", padding=10)
        box.pack(fill="x")
        self.custom_lat = tk.StringVar(value="40.7608")
        self.custom_lon = tk.StringVar(value="-111.8910")
        self.custom_radius = tk.StringVar(value="180")
        self.custom_height = tk.StringVar(value="20")
        self.custom_power_value = tk.StringVar(value="50")
        self.custom_power_w = self.custom_power_value
        self.custom_power_dbm_mode = tk.BooleanVar(value=False)
        self.custom_gain = tk.StringVar(value="0")
        self.custom_freq = tk.StringVar(value="144.390")
        self._field(box, 0, "Latitude", self.custom_lat)
        self._field(box, 1, "Longitude", self.custom_lon)
        self._field(box, 2, "Coverage radius (km)", self.custom_radius)
        self._field(box, 3, "Antenna height AGL (m)", self.custom_height)
        self._custom_power_label = ttk.Label(box, text="TX power (W)")
        self._custom_power_label.grid(row=4, column=0, sticky="w", pady=3)
        ttk.Entry(box, textvariable=self.custom_power_value, width=20).grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=3)
        box.columnconfigure(1, weight=1)
        ttk.Checkbutton(box, text="Enter TX power in dBm", variable=self.custom_power_dbm_mode, command=self._custom_power_unit_changed).grid(row=5, column=0, columnspan=2, sticky="w", pady=(2, 4))
        self._field(box, 6, "TX antenna gain (dBd)", self.custom_gain)
        self._field(box, 7, "Frequency (MHz)", self.custom_freq)
        ttk.Button(box, text="Update map", command=self._draw_custom).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(7, 0))
        ttk.Button(controls, text="Run custom propagation", command=self.run_custom).pack(fill="x", pady=(10, 0))
        ttk.Label(controls, text="Watts and dBm are equivalent input choices; Signal Peak converts to dBm internally. Custom mode keeps its own site-specific radio controls and operational reserve.", wraplength=340).pack(anchor="w", pady=(8, 0))
        self.custom_map = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
        self.custom_map.pack(fill="both", expand=True)
        self.custom_map.add_left_click_map_command(self._custom_click)
        self._draw_custom(initial=True)

    def _custom_power_unit_changed(self) -> None:
        target_dbm = bool(self.custom_power_dbm_mode.get())
        try:
            value = float(self.custom_power_value.get())
            if target_dbm:
                if value <= 0:
                    raise ValueError("TX power in watts must be positive.")
                self.custom_power_value.set(f"{10.0 * math.log10(value * 1000.0):.3f}")
                self._custom_power_label.configure(text="TX power (dBm)")
            else:
                self.custom_power_value.set(f"{10.0 ** ((value - 30.0) / 10.0):.4g}")
                self._custom_power_label.configure(text="TX power (W)")
        except ValueError as exc:
            messagebox.showerror("Invalid TX power", str(exc), parent=self)
            self.custom_power_dbm_mode.set(not target_dbm)

    def run_custom(self) -> None:
        try:
            lat = float(self.custom_lat.get())
            lon = float(self.custom_lon.get())
            radius = float(self.custom_radius.get())
            height = float(self.custom_height.get())
            power_value = float(self.custom_power_value.get())
            gain = float(self.custom_gain.get())
            freq = float(self.custom_freq.get())
            Region(lat, lon, radius).validate()
            if height <= 0:
                raise ValueError("Antenna height must be positive.")
            if not 20 <= freq <= 1000:
                raise ValueError("Frequency must be between 20 and 1000 MHz.")
            if self.custom_power_dbm_mode.get():
                tx_dbm = power_value
                if not 0 <= tx_dbm <= 80:
                    raise ValueError("TX power must be between 0 and 80 dBm.")
            else:
                if power_value <= 0:
                    raise ValueError("TX power in watts must be positive.")
                tx_dbm = 10.0 * math.log10(power_value * 1000.0)
                if tx_dbm > 80:
                    raise ValueError("TX power exceeds the supported 80 dBm maximum.")
            path_budget = tx_dbm + 119.0 + gain + 2.0 - CUSTOM_OPERATIONAL_RESERVE_DB
            record = {"callsign": "CUSTOM", "type": "digi", "lat": lat, "lon": lon, "_source": "reviewed_override", "lasttime": 0}
            radio = {
                "freq_mhz": freq,
                "antenna_height_digi_m": height,
                "tx_power_dbm": tx_dbm,
                "tx_antenna_gain_dbd": gain,
                "max_path_loss_db": path_budget,
                "margin_display_floor_db": 0.0,
                "max_margin_db": float(self._advanced_vars["max_margin_db"].get()),
                "n_radials": REFERENCE_RADIALS,
                "gap_fill_factor": GAP_FILL_FACTOR,
            }
            radio.update(self._collect_output_settings())
            _, job_file = prepare_job(
                Region(lat, lon, radius), Path(self.app.source_var.get()), {"digi"}, radius,
                mode="custom", selected_records=[record], radio_settings=radio, frozen_stations=True,
            )
            self.app.start_job(job_file, "Custom station")
        except Exception as exc:
            messagebox.showerror("Cannot start custom job", str(exc), parent=self)
