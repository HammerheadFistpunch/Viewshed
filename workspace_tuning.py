from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import tkintermapview

from advanced_workspace import ViewshedWorkspace as _ViewshedWorkspace
from seed_builder import SeedBuilderDialog as _SeedBuilderDialog
from viewshed_core import Region, prepare_job


REFERENCE_PATH_LOSS_DB = 138.0
REFERENCE_RADIALS = 1080
GAP_FILL_FACTOR = 0.25
CUSTOM_OPERATIONAL_RESERVE_DB = 20.0


def _circle_points(lat: float, lon: float, radius_km: float, count: int = 72) -> list[tuple[float, float]]:
    lat_scale = 111.32
    lon_scale = max(1e-6, 111.32 * math.cos(math.radians(lat)))
    return [
        (
            lat + (radius_km / lat_scale) * math.cos(2.0 * math.pi * i / count),
            lon + (radius_km / lon_scale) * math.sin(2.0 * math.pi * i / count),
        )
        for i in range(count)
    ]


def _set_map_style(map_widget, style: str, attribution_label=None) -> None:
    if style == "topo":
        map_widget.set_tile_server("https://tile.opentopomap.org/{z}/{x}/{y}.png", max_zoom=17)
        text = "Topo: © OpenStreetMap contributors, SRTM | © OpenTopoMap (CC-BY-SA)"
    else:
        map_widget.set_tile_server("https://tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=19)
        text = "Map data: © OpenStreetMap contributors"
    if attribution_label is not None:
        attribution_label.configure(text=text)


class SeedBuilderMapDialog(_SeedBuilderDialog):
    """Seed builder with the same map controls used by the main workspace."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self.title("Viewshed Seed Builder")
        self.geometry("1180x650")
        self.minsize(980, 560)

        children = self.winfo_children()
        if children:
            controls = children[0]
            controls.pack_forget()
            controls.pack(side="left", fill="both", expand=False)

        map_panel = ttk.Frame(self, padding=(0, 14, 14, 14))
        map_panel.pack(side="right", fill="both", expand=True)

        toolbar = ttk.Frame(map_panel)
        toolbar.pack(fill="x", pady=(0, 4))
        ttk.Label(toolbar, text="Collection area", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(toolbar, text="Topo", command=lambda: self._set_seed_style("topo")).pack(side="right")
        ttk.Button(toolbar, text="Standard", command=lambda: self._set_seed_style("standard")).pack(side="right", padx=(0, 4))
        ttk.Button(toolbar, text="Center from fields", command=self._draw_seed_area).pack(side="right", padx=(0, 12))

        self.seed_map = tkintermapview.TkinterMapView(map_panel, corner_radius=0)
        self.seed_map.pack(fill="both", expand=True)
        self.seed_map.add_left_click_map_command(self._seed_click)
        self.seed_attribution = ttk.Label(map_panel)
        self.seed_attribution.pack(anchor="e", pady=(3, 0))
        self._set_seed_style("standard")
        self._draw_seed_area(initial=True)

    def _set_seed_style(self, style: str) -> None:
        _set_map_style(self.seed_map, style, self.seed_attribution)

    def _seed_click(self, coords) -> None:
        self.lat_var.set(f"{coords[0]:.6f}")
        self.lon_var.set(f"{coords[1]:.6f}")
        self._draw_seed_area()

    def _draw_seed_area(self, initial: bool = False) -> None:
        try:
            lat = float(self.lat_var.get())
            lon = float(self.lon_var.get())
            radius = float(self.radius_var.get())
            if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("Invalid center latitude/longitude.")
            if not 1 <= radius <= 2000:
                raise ValueError("Radius must be between 1 and 2000 km.")
        except Exception as exc:
            if not initial:
                messagebox.showerror("Invalid seed area", str(exc), parent=self)
            return

        self.seed_map.delete_all_marker()
        self.seed_map.delete_all_polygon()
        self.seed_map.set_marker(lat, lon, text="Seed center")
        self.seed_map.set_polygon(_circle_points(lat, lon, radius), name="Seed collection radius")
        self.seed_map.set_position(lat, lon)
        if initial:
            self.seed_map.set_zoom(7)


class ViewshedWorkspace(_ViewshedWorkspace):
    """Final UI/model tuning layer for the current map-first workspace."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._migrate_reference_profile()
        self._install_common_map_controls()
        self._use_standard_map()
        self._replace_seed_builder_button()

    def _migrate_reference_profile(self) -> None:
        # Migrate the previous reference defaults without overwriting clearly custom values.
        cap = self._advanced_vars.get("max_path_loss_db")
        radials = self._advanced_vars.get("n_radials")
        changed = False
        if cap is not None:
            try:
                if abs(float(cap.get()) - 148.0) < 1e-6:
                    cap.set(str(REFERENCE_PATH_LOSS_DB))
                    changed = True
            except ValueError:
                pass
        if radials is not None:
            try:
                if int(float(radials.get())) == 720:
                    radials.set(str(REFERENCE_RADIALS))
                    changed = True
            except ValueError:
                pass
        if changed and hasattr(self, "advanced_status"):
            self.advanced_status.set(
                "Reference profile updated: 138 dB operational cap, 1080 radials, reduced lateral gap fill."
            )

    def _advanced_settings(self, *, persist: bool = True) -> dict:
        values = super()._advanced_settings(persist=persist)
        values["gap_fill_factor"] = GAP_FILL_FACTOR
        return values

    def _install_common_map_controls(self) -> None:
        for map_widget in (self.area_map, self.station_map, self.custom_map):
            parent = map_widget.master
            toolbar = ttk.Frame(parent, padding=4)
            toolbar.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
            attribution = ttk.Label(parent)
            attribution.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-6)
            ttk.Button(
                toolbar,
                text="Topo",
                command=lambda m=map_widget, a=attribution: _set_map_style(m, "topo", a),
            ).pack(side="left")
            ttk.Button(
                toolbar,
                text="Standard",
                command=lambda m=map_widget, a=attribution: _set_map_style(m, "standard", a),
            ).pack(side="left", padx=(4, 0))
            _set_map_style(map_widget, "standard", attribution)

    def _replace_seed_builder_button(self) -> None:
        def visit(widget) -> bool:
            try:
                if isinstance(widget, ttk.Button) and widget.cget("text") == "Build Seed…":
                    widget.configure(command=self._open_seed_builder_map)
                    return True
            except Exception:
                pass
            for child in widget.winfo_children():
                if visit(child):
                    return True
            return False

        visit(self.app)

    def _open_seed_builder_map(self) -> None:
        existing = getattr(self.app, "_seed_builder", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
        self.app._seed_builder = SeedBuilderMapDialog(self.app)

    def run_custom(self) -> None:
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
                raise ValueError("TX power must be positive.")
            if not 20 <= freq <= 1000:
                raise ValueError("Frequency must be between 20 and 1000 MHz.")

            tx_dbm = 10.0 * math.log10(power_w * 1000.0)
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
                "margin_display_floor_db": 0.0,
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
