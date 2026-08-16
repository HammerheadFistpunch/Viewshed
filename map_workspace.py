from __future__ import annotations

import json
import math
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import tkintermapview

from viewshed_core import (
    Region,
    USER_OVERRIDE_ENV,
    acquire_area_stations,
    assess_station_locations,
    load_station_records,
    portable_data_root,
    prepare_job,
    resource_path,
    user_override_path,
)


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


def _load_user_registry() -> dict:
    path = user_override_path()
    if not path.exists():
        return {"version": 1, "overrides": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    raw.setdefault("version", 1)
    if not isinstance(raw.get("overrides"), dict):
        raw["overrides"] = {}
    return raw


def save_user_override(callsign: str, entry: dict) -> None:
    path = user_override_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_user_registry()
    payload["overrides"][callsign.strip().upper()] = entry
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def remove_user_override(callsign: str) -> bool:
    payload = _load_user_registry()
    removed = payload["overrides"].pop(callsign.strip().upper(), None) is not None
    if removed:
        path = user_override_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return removed


class ViewshedWorkspace(ttk.Frame):
    """Map-first UI. All modes create jobs for the same propagation engine."""

    def __init__(self, master, app) -> None:
        super().__init__(master, padding=8)
        self.app = app
        os.environ[USER_OVERRIDE_ENV] = str(user_override_path())
        self._area_records: list[dict] = []
        self._station_records: dict[str, dict] = {}
        self._area_busy = False

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.area_tab = ttk.Frame(self.notebook, padding=6)
        self.station_tab = ttk.Frame(self.notebook, padding=6)
        self.custom_tab = ttk.Frame(self.notebook, padding=6)
        self.corrections_tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.area_tab, text="Area")
        self.notebook.add(self.station_tab, text="Station")
        self.notebook.add(self.custom_tab, text="Custom")
        self.notebook.add(self.corrections_tab, text="Corrections")

        self._build_area()
        self._build_station()
        self._build_custom()
        self._build_corrections()
        self.reload_station_catalog()

    @staticmethod
    def _field(parent, row: int, label: str, var: tk.Variable, width: int = 20) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        entry = ttk.Entry(parent, textvariable=var, width=width)
        entry.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)
        parent.columnconfigure(1, weight=1)
        return entry

    def _split(self, parent, width: int = 330):
        pane = ttk.Panedwindow(parent, orient="horizontal")
        pane.pack(fill="both", expand=True)
        controls = ttk.Frame(pane, width=width, padding=(0, 0, 8, 0))
        map_frame = ttk.Frame(pane)
        pane.add(controls, weight=0)
        pane.add(map_frame, weight=1)
        return controls, map_frame

    def _build_area(self) -> None:
        controls, map_frame = self._split(self.area_tab, 350)
        ttk.Label(controls, text="Area analysis", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(
            controls,
            text="1. Pick an area.  2. Find and inspect stations.  3. Correct locations if needed.  4. Run propagation.",
            wraplength=330,
        ).pack(anchor="w", pady=(3, 10))

        area = ttk.LabelFrame(controls, text="Area", padding=10)
        area.pack(fill="x")
        self.area_lat = tk.StringVar(value="40.7608")
        self.area_lon = tk.StringVar(value="-111.8910")
        self.area_radius = tk.StringVar(value="100")
        self.area_prop = tk.StringVar(value="180")
        self._field(area, 0, "Center latitude", self.area_lat)
        self._field(area, 1, "Center longitude", self.area_lon)
        self._field(area, 2, "Area radius (km)", self.area_radius)
        self._field(area, 3, "Station coverage radius (km)", self.area_prop)
        ttk.Button(area, text="Update map", command=self._draw_area_boundary).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(7, 0))

        filters = ttk.LabelFrame(controls, text="Stations", padding=10)
        filters.pack(fill="x", pady=(8, 0))
        self.area_digi = tk.BooleanVar(value=True)
        self.area_igate = tk.BooleanVar(value=True)
        ttk.Checkbutton(filters, text="Digipeaters", variable=self.area_digi).pack(anchor="w")
        ttk.Checkbutton(filters, text="iGates", variable=self.area_igate).pack(anchor="w")
        self.find_area_btn = ttk.Button(filters, text="1 — Find stations", command=self.find_area_stations)
        self.find_area_btn.pack(fill="x", pady=(7, 0))
        self.area_review_btn = ttk.Button(filters, text="2 — Review corrections", command=self.review_area_corrections, state="disabled")
        self.area_review_btn.pack(fill="x", pady=(6, 0))
        self.run_area_btn = ttk.Button(filters, text="3 — Run area propagation", command=self.run_area, state="disabled")
        self.run_area_btn.pack(fill="x", pady=(6, 0))
        self.area_status = tk.StringVar(value="Choose an area, then find stations. No propagation math runs during this step.")
        ttk.Label(controls, textvariable=self.area_status, wraplength=330).pack(anchor="w", pady=(10, 0))

        self.area_map = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
        self.area_map.pack(fill="both", expand=True)
        self.area_map.add_left_click_map_command(self._area_click)
        self._draw_area_boundary(initial=True)

    def _area_click(self, coords) -> None:
        self.area_lat.set(f"{coords[0]:.6f}")
        self.area_lon.set(f"{coords[1]:.6f}")
        self._area_records = []
        self.run_area_btn.configure(state="disabled")
        self.area_review_btn.configure(state="disabled")
        self._draw_area_boundary()

    def _area_values(self):
        region = Region(float(self.area_lat.get()), float(self.area_lon.get()), float(self.area_radius.get()))
        region.validate()
        prop = float(self.area_prop.get())
        if not 1 <= prop <= 500:
            raise ValueError("Station coverage radius must be between 1 and 500 km.")
        types = set()
        if self.area_digi.get(): types.add("digi")
        if self.area_igate.get(): types.add("igate")
        if not types: raise ValueError("Select at least one station type.")
        return region, prop, types

    def _draw_area_boundary(self, initial: bool = False) -> None:
        try:
            region, _, _ = self._area_values()
        except Exception as exc:
            if not initial: messagebox.showerror("Invalid area", str(exc), parent=self)
            return
        self.area_map.delete_all_marker()
        self.area_map.delete_all_polygon()
        self.area_map.set_marker(region.center_lat, region.center_lon, text="Area center")
        self.area_map.set_polygon(_circle_points(region.center_lat, region.center_lon, region.radius_km), name="Area radius")
        for rec in self._area_records:
            try:
                call = str(rec.get("callsign") or "?")
                self.area_map.set_marker(float(rec["lat"]), float(rec["lon"]), text=call, command=lambda _m, c=call: self.open_correction(c))
            except Exception:
                pass
        if initial:
            self.area_map.set_position(region.center_lat, region.center_lon)
            self.area_map.set_zoom(7)

    def find_area_stations(self) -> None:
        if self._area_busy: return
        try:
            region, prop, types = self._area_values()
            self.app.apply_network_settings()
        except Exception as exc:
            messagebox.showerror("Cannot acquire stations", str(exc), parent=self)
            return
        self._area_busy = True
        self.find_area_btn.configure(state="disabled")
        self.run_area_btn.configure(state="disabled")
        self.area_review_btn.configure(state="disabled")
        self.area_status.set("Acquiring APRS/cache station list…")

        def work():
            try:
                records = acquire_area_stations(region, Path(self.app.source_var.get()), types, prop, refresh=True)
                self.after(0, lambda: self._area_acquired(records))
            except Exception as exc:
                self.after(0, lambda e=exc: self._area_acquire_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _area_acquired(self, records: list[dict]) -> None:
        self._area_busy = False
        self.find_area_btn.configure(state="normal")
        self._area_records = records
        self._draw_area_boundary()
        low = sum(1 for r in records if (r.get("_location_confidence") or {}).get("label") == "LOW")
        review = sum(1 for r in records if r.get("_location_review_candidate"))
        self.area_status.set(f"{len(records)} stations ready. {low} LOW confidence; {review} flagged for review. Inspect/correct, then run.")
        if records:
            self.run_area_btn.configure(state="normal")
            self.area_review_btn.configure(state="normal")
            self._refresh_correction_catalog(records)

    def _area_acquire_failed(self, exc: Exception) -> None:
        self._area_busy = False
        self.find_area_btn.configure(state="normal")
        self.area_status.set("Station acquisition failed.")
        messagebox.showerror("Station acquisition failed", str(exc), parent=self)

    def review_area_corrections(self) -> None:
        self._refresh_correction_catalog(self._area_records)
        self.notebook.select(self.corrections_tab)

    def run_area(self) -> None:
        if not self._area_records:
            messagebox.showwarning("Find stations first", "Acquire and review the station list before running propagation.", parent=self)
            return
        try:
            region, prop, types = self._area_values()
            records = assess_station_locations(self._area_records)
            _, job_file = prepare_job(
                region, Path(self.app.source_var.get()), types, prop,
                mode="area", selected_records=records, frozen_stations=True,
            )
            self.app.start_job(job_file, "Area")
        except Exception as exc:
            messagebox.showerror("Cannot start area job", str(exc), parent=self)

    def _build_station(self) -> None:
        controls, map_frame = self._split(self.station_tab, 350)
        ttk.Label(controls, text="Individual station", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(controls, text="Select one known station and model it with the same reference radio assumptions used by Area.", wraplength=330).pack(anchor="w", pady=(3, 10))
        box = ttk.LabelFrame(controls, text="Station", padding=10)
        box.pack(fill="x")
        self.station_call = tk.StringVar()
        self.station_combo = ttk.Combobox(box, textvariable=self.station_call, state="readonly")
        self.station_combo.pack(fill="x")
        self.station_combo.bind("<<ComboboxSelected>>", lambda _e: self._station_selected())
        ttk.Button(box, text="Reload stations", command=self.reload_station_catalog).pack(fill="x", pady=(6, 0))
        self.station_radius = tk.StringVar(value="180")
        row = ttk.Frame(box); row.pack(fill="x", pady=(8, 0))
        ttk.Label(row, text="Coverage radius (km)").pack(side="left")
        ttk.Entry(row, textvariable=self.station_radius, width=10).pack(side="right")
        self.station_info = tk.StringVar(value="No station selected")
        ttk.Label(controls, textvariable=self.station_info, wraplength=330).pack(anchor="w", pady=(10, 0))
        ttk.Button(controls, text="Run station propagation", command=self.run_station).pack(fill="x", pady=(8, 0))

        self.station_map = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
        self.station_map.pack(fill="both", expand=True)
        self.station_map.set_position(40.7608, -111.8910)
        self.station_map.set_zoom(7)

    def _station_source_records(self) -> list[dict]:
        cache = portable_data_root() / "cache" / "stations.json"
        source = cache if cache.exists() else Path(self.app.source_var.get())
        if not source.exists(): source = resource_path("utah_stations_scraped.json")
        return assess_station_locations(load_station_records(source))

    def reload_station_catalog(self) -> None:
        try:
            records = self._station_source_records()
        except Exception:
            records = []
        self._station_records = {
            str(r.get("callsign") or "").upper(): r for r in records
            if r.get("callsign") and r.get("type") in {"digi", "igate"} and "lat" in r and "lon" in r
        }
        calls = sorted(self._station_records)
        self.station_combo["values"] = calls
        if calls and self.station_call.get() not in calls:
            self.station_call.set(calls[0])
        self._station_selected()
        self._refresh_correction_catalog(records)

    def _station_selected(self) -> None:
        rec = self._station_records.get(self.station_call.get().upper())
        self.station_map.delete_all_marker()
        if not rec:
            self.station_info.set("No station selected")
            return
        lat, lon = float(rec["lat"]), float(rec["lon"])
        conf = rec.get("_location_confidence") or {}
        self.station_info.set(f"{rec.get('type','?')}  •  {lat:.6f}, {lon:.6f}  •  confidence {conf.get('label','?')} ({conf.get('score','?')}/100)")
        self.station_map.set_marker(lat, lon, text=self.station_call.get())
        self.station_map.set_position(lat, lon)
        self.station_map.set_zoom(11)

    def run_station(self) -> None:
        rec = self._station_records.get(self.station_call.get().upper())
        if not rec:
            messagebox.showwarning("Select station", "Select a station first.", parent=self); return
        try:
            radius = float(self.station_radius.get())
            if not 1 <= radius <= 500: raise ValueError("Coverage radius must be between 1 and 500 km.")
            rec = assess_station_locations([rec])[0]
            region = Region(float(rec["lat"]), float(rec["lon"]), radius)
            _, job_file = prepare_job(
                region, Path(self.app.source_var.get()), {str(rec.get("type") or "digi")}, radius,
                mode="station", selected_records=[rec], frozen_stations=True,
            )
            self.app.start_job(job_file, f"Station {rec.get('callsign')}")
        except Exception as exc:
            messagebox.showerror("Cannot start station job", str(exc), parent=self)

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
        self.custom_power_w = tk.StringVar(value="50")
        self.custom_gain = tk.StringVar(value="0")
        self.custom_freq = tk.StringVar(value="144.390")
        self._field(box, 0, "Latitude", self.custom_lat)
        self._field(box, 1, "Longitude", self.custom_lon)
        self._field(box, 2, "Coverage radius (km)", self.custom_radius)
        self._field(box, 3, "Antenna height AGL (m)", self.custom_height)
        self._field(box, 4, "TX power (W)", self.custom_power_w)
        self._field(box, 5, "TX antenna gain (dBd)", self.custom_gain)
        self._field(box, 6, "Frequency (MHz)", self.custom_freq)
        ttk.Button(box, text="Update map", command=self._draw_custom).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(7, 0))
        ttk.Button(controls, text="Run custom propagation", command=self.run_custom).pack(fill="x", pady=(10, 0))
        ttk.Label(controls, text="Link budget uses the same receiver assumptions as the reference mobile profile, with a 10 dB operational reserve.", wraplength=340).pack(anchor="w", pady=(8, 0))

        self.custom_map = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
        self.custom_map.pack(fill="both", expand=True)
        self.custom_map.add_left_click_map_command(self._custom_click)
        self._draw_custom(initial=True)

    def _custom_click(self, coords) -> None:
        self.custom_lat.set(f"{coords[0]:.6f}")
        self.custom_lon.set(f"{coords[1]:.6f}")
        self._draw_custom()

    def _draw_custom(self, initial: bool = False) -> None:
        try:
            lat, lon = float(self.custom_lat.get()), float(self.custom_lon.get())
            radius = float(self.custom_radius.get())
            Region(lat, lon, radius).validate()
        except Exception as exc:
            if not initial: messagebox.showerror("Invalid custom site", str(exc), parent=self)
            return
        self.custom_map.delete_all_marker(); self.custom_map.delete_all_polygon()
        self.custom_map.set_marker(lat, lon, text="Proposed station")
        self.custom_map.set_polygon(_circle_points(lat, lon, radius), name="Coverage radius")
        if initial:
            self.custom_map.set_position(lat, lon); self.custom_map.set_zoom(7)

    def run_custom(self) -> None:
        try:
            lat, lon = float(self.custom_lat.get()), float(self.custom_lon.get())
            radius = float(self.custom_radius.get())
            height = float(self.custom_height.get())
            power_w = float(self.custom_power_w.get())
            gain = float(self.custom_gain.get())
            freq = float(self.custom_freq.get())
            Region(lat, lon, radius).validate()
            if height <= 0: raise ValueError("Antenna height must be positive.")
            if power_w <= 0: raise ValueError("TX power must be positive.")
            if not 20 <= freq <= 1000: raise ValueError("Frequency must be between 20 and 1000 MHz.")
            tx_dbm = 10.0 * math.log10(power_w * 1000.0)
            path_budget = tx_dbm + 119.0 + gain + 2.0 - 10.0
            record = {"callsign": "CUSTOM", "type": "digi", "lat": lat, "lon": lon, "_source": "reviewed_override", "lasttime": 0}
            radio = {
                "freq_mhz": freq,
                "antenna_height_digi_m": height,
                "tx_power_dbm": tx_dbm,
                "tx_antenna_gain_dbd": gain,
                "max_path_loss_db": path_budget,
            }
            _, job_file = prepare_job(
                Region(lat, lon, radius), Path(self.app.source_var.get()), {"digi"}, radius,
                mode="custom", selected_records=[record], radio_settings=radio, frozen_stations=True,
            )
            self.app.start_job(job_file, "Custom station")
        except Exception as exc:
            messagebox.showerror("Cannot start custom job", str(exc), parent=self)

    def _build_corrections(self) -> None:
        controls, map_frame = self._split(self.corrections_tab, 370)
        ttk.Label(controls, text="Station location corrections", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(controls, text="Select a station. The reported point stays preserved; only a reviewed correction changes the model coordinate.", wraplength=350).pack(anchor="w", pady=(3, 10))
        box = ttk.LabelFrame(controls, text="Station", padding=10)
        box.pack(fill="x")
        self.correct_call = tk.StringVar()
        self.correct_combo = ttk.Combobox(box, textvariable=self.correct_call, state="readonly")
        self.correct_combo.pack(fill="x")
        self.correct_combo.bind("<<ComboboxSelected>>", lambda _e: self._correction_selected())
        self.correct_info = tk.StringVar(value="No station selected")
        ttk.Label(controls, textvariable=self.correct_info, wraplength=350).pack(anchor="w", pady=(8, 0))

        proposal = ttk.LabelFrame(controls, text="Proposed location", padding=10)
        proposal.pack(fill="x", pady=(10, 0))
        self.correct_lat = tk.StringVar(); self.correct_lon = tk.StringVar()
        self.correct_reason = tk.StringVar(); self.correct_source = tk.StringVar(value="Visual review in Viewshed")
        self._field(proposal, 0, "Latitude", self.correct_lat)
        self._field(proposal, 1, "Longitude", self.correct_lon)
        self._field(proposal, 2, "Reason", self.correct_reason)
        self._field(proposal, 3, "Source", self.correct_source)
        ttk.Button(proposal, text="Show proposed point", command=self._show_correction_proposal).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(7, 0))
        ttk.Button(controls, text="Save as candidate", command=lambda: self._save_correction("candidate")).pack(fill="x", pady=(10, 0))
        ttk.Button(controls, text="Approve correction", command=lambda: self._save_correction("reviewed")).pack(fill="x", pady=(6, 0))
        ttk.Button(controls, text="Remove my override", command=self._remove_correction).pack(fill="x", pady=(6, 0))
        self.correct_status = tk.StringVar(value=f"User corrections: {user_override_path()}")
        ttk.Label(controls, textvariable=self.correct_status, wraplength=350).pack(anchor="w", pady=(8, 0))

        self.correction_map = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
        self.correction_map.pack(fill="both", expand=True)
        self.correction_map.add_left_click_map_command(self._correction_click)
        self.correction_map.set_position(40.7608, -111.8910); self.correction_map.set_zoom(7)
        self._correction_records: dict[str, dict] = {}

    def _refresh_correction_catalog(self, records: list[dict] | None = None) -> None:
        if records is None:
            try: records = self._station_source_records()
            except Exception: records = []
        records = assess_station_locations(records)
        self._correction_records = {
            str(r.get("callsign") or "").upper(): r for r in records
            if r.get("callsign") and "lat" in r and "lon" in r
        }
        calls = sorted(self._correction_records, key=lambda c: (
            0 if (self._correction_records[c].get("_location_confidence") or {}).get("label") == "LOW" else 1, c
        ))
        self.correct_combo["values"] = calls
        if calls and self.correct_call.get() not in calls:
            self.correct_call.set(calls[0])
        self._correction_selected()

    def open_correction(self, callsign: str) -> None:
        self._refresh_correction_catalog(self._area_records or None)
        if callsign in self._correction_records: self.correct_call.set(callsign)
        self._correction_selected()
        self.notebook.select(self.corrections_tab)

    def _correction_selected(self) -> None:
        rec = self._correction_records.get(self.correct_call.get().upper())
        self.correction_map.delete_all_marker()
        if not rec:
            self.correct_info.set("No station selected"); return
        call = self.correct_call.get().upper()
        reported_lat = float(rec.get("_reported_lat", rec["lat"])); reported_lon = float(rec.get("_reported_lon", rec["lon"]))
        model_lat, model_lon = float(rec["lat"]), float(rec["lon"])
        conf = rec.get("_location_confidence") or {}
        self.correct_info.set(f"Reported: {reported_lat:.6f}, {reported_lon:.6f}\nModel: {model_lat:.6f}, {model_lon:.6f}\nConfidence: {conf.get('label','?')} ({conf.get('score','?')}/100)")
        self.correction_map.set_marker(reported_lat, reported_lon, text=f"{call} reported")
        review = rec.get("_location_correction") or rec.get("_location_review_candidate") or {}
        if "candidate_lat" in review:
            self.correct_lat.set(f"{float(review['candidate_lat']):.6f}"); self.correct_lon.set(f"{float(review['candidate_lon']):.6f}")
            self.correct_reason.set(str(review.get("reason") or "")); self.correct_source.set(str(review.get("source") or "Visual review in Viewshed"))
            self.correction_map.set_marker(float(review["candidate_lat"]), float(review["candidate_lon"]), text=f"{call} proposed")
        else:
            self.correct_lat.set(""); self.correct_lon.set(""); self.correct_reason.set(""); self.correct_source.set("Visual review in Viewshed")
        self.correction_map.set_position(model_lat, model_lon); self.correction_map.set_zoom(12)

    def _correction_click(self, coords) -> None:
        if not self.correct_call.get(): return
        self.correct_lat.set(f"{coords[0]:.6f}"); self.correct_lon.set(f"{coords[1]:.6f}")
        self._show_correction_proposal()

    def _show_correction_proposal(self) -> None:
        try:
            lat, lon = float(self.correct_lat.get()), float(self.correct_lon.get())
            if not -90 <= lat <= 90 or not -180 <= lon <= 180: raise ValueError("Invalid latitude/longitude.")
        except Exception as exc:
            messagebox.showerror("Invalid proposed point", str(exc), parent=self); return
        self._correction_selected()
        self.correction_map.set_marker(lat, lon, text=f"{self.correct_call.get()} proposed")

    def _save_correction(self, status: str) -> None:
        call = self.correct_call.get().strip().upper()
        if not call: return
        try:
            lat, lon = float(self.correct_lat.get()), float(self.correct_lon.get())
            if not -90 <= lat <= 90 or not -180 <= lon <= 180: raise ValueError("Invalid latitude/longitude.")
        except Exception as exc:
            messagebox.showerror("Invalid correction", str(exc), parent=self); return
        if status == "reviewed" and not messagebox.askyesno(
            "Approve location correction",
            f"Use {lat:.6f}, {lon:.6f} as the propagation location for {call}?\n\nThe APRS-reported location will still be preserved.",
            parent=self,
        ):
            return
        save_user_override(call, {
            "status": status, "lat": lat, "lon": lon,
            "reason": self.correct_reason.get().strip(),
            "source": self.correct_source.get().strip() or "Visual review in Viewshed",
        })
        self.correct_status.set(f"Saved {status} location for {call}.")
        self._after_correction_change(call)

    def _remove_correction(self) -> None:
        call = self.correct_call.get().strip().upper()
        if call and remove_user_override(call):
            self.correct_status.set(f"Removed user override for {call}.")
            self._after_correction_change(call)

    def _after_correction_change(self, call: str) -> None:
        if self._area_records:
            self._area_records = assess_station_locations(self._area_records)
            self._draw_area_boundary()
            low = sum(1 for r in self._area_records if (r.get("_location_confidence") or {}).get("label") == "LOW")
            self.area_status.set(f"Corrections updated. {len(self._area_records)} stations ready; {low} LOW confidence.")
        self.reload_station_catalog()
        if call in self._correction_records: self.correct_call.set(call)
        self._correction_selected()
