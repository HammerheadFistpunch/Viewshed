from __future__ import annotations

import json
import math
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import tkintermapview

from location_quality import assess_and_correct_locations
from viewshed_core import Region, load_station_records, portable_data_root, resource_path


USER_OVERRIDE_ENV = "VIEWSHED_LOCATION_OVERRIDE_PATH"


def user_override_path() -> Path:
    return portable_data_root() / "station_location_overrides.json"


def _circle_points(lat: float, lon: float, radius_km: float, count: int = 72) -> list[tuple[float, float]]:
    lat_scale = 111.32
    lon_scale = max(1e-6, 111.32 * math.cos(math.radians(lat)))
    points: list[tuple[float, float]] = []
    for i in range(count):
        angle = 2.0 * math.pi * i / count
        points.append((
            lat + (radius_km / lat_scale) * math.cos(angle),
            lon + (radius_km / lon_scale) * math.sin(angle),
        ))
    return points


def _load_user_registry(path: Path) -> dict:
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


def _save_user_override(callsign: str, entry: dict) -> None:
    path = user_override_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_user_registry(path)
    payload["overrides"][callsign.strip().upper()] = entry
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _remove_user_override(callsign: str) -> bool:
    path = user_override_path()
    payload = _load_user_registry(path)
    removed = payload["overrides"].pop(callsign.strip().upper(), None) is not None
    if removed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return removed


class MapWorkspace(tk.Toplevel):
    """Map-driven UI for area selection and reviewed station corrections."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self.app = app
        self.title("Viewshed Map Workspace")
        self.geometry("1120x760")
        self.minsize(900, 620)
        os.environ[USER_OVERRIDE_ENV] = str(user_override_path())

        self._area_marker = None
        self._area_polygon = None
        self._reported_marker = None
        self._proposed_marker = None
        self._records: dict[str, dict] = {}

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        area_tab = ttk.Frame(notebook, padding=8)
        correction_tab = ttk.Frame(notebook, padding=8)
        notebook.add(area_tab, text="Area Selection")
        notebook.add(correction_tab, text="Station Corrections")

        self._build_area_tab(area_tab)
        self._build_correction_tab(correction_tab)

    def _build_area_tab(self, parent: ttk.Frame) -> None:
        pane = ttk.Panedwindow(parent, orient="horizontal")
        pane.pack(fill="both", expand=True)
        controls = ttk.Frame(pane, padding=(0, 0, 8, 0), width=300)
        map_frame = ttk.Frame(pane)
        pane.add(controls, weight=0)
        pane.add(map_frame, weight=1)

        ttk.Label(controls, text="Analysis area", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(
            controls,
            text="Click anywhere on the map to move the current area-search center. The radius ring is a visual guide only.",
            wraplength=285,
        ).pack(anchor="w", pady=(3, 10))

        values = ttk.LabelFrame(controls, text="Current area", padding=10)
        values.pack(fill="x")
        self.area_lat = tk.StringVar(value=self.app.lat_var.get())
        self.area_lon = tk.StringVar(value=self.app.lon_var.get())
        self.area_radius = tk.StringVar(value=self.app.radius_var.get())
        self._field(values, 0, "Latitude", self.area_lat)
        self._field(values, 1, "Longitude", self.area_lon)
        self._field(values, 2, "Radius (km)", self.area_radius)
        ttk.Button(values, text="Update map", command=self._update_area_map).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        ttk.Button(values, text="Use in Area Search", command=self._apply_area_to_app).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0)
        )

        ttk.Label(
            controls,
            text="This changes only the area inputs in the main window. Generate Viewshed still runs the same DEM + ITM pipeline.",
            wraplength=285,
        ).pack(anchor="w", pady=(10, 0))

        self.area_map = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
        self.area_map.pack(fill="both", expand=True)
        self.area_map.add_left_click_map_command(self._area_click)
        self._update_area_map(initial=True)

    def _build_correction_tab(self, parent: ttk.Frame) -> None:
        pane = ttk.Panedwindow(parent, orient="horizontal")
        pane.pack(fill="both", expand=True)
        controls = ttk.Frame(pane, padding=(0, 0, 8, 0), width=340)
        map_frame = ttk.Frame(pane)
        pane.add(controls, weight=0)
        pane.add(map_frame, weight=1)

        ttk.Label(controls, text="Visual station correction", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(
            controls,
            text="Choose a station, then click the map to place a proposed location. A candidate is only flagged; a reviewed correction is used by propagation.",
            wraplength=325,
        ).pack(anchor="w", pady=(3, 10))

        box = ttk.LabelFrame(controls, text="Station", padding=10)
        box.pack(fill="x")
        self.call_var = tk.StringVar()
        self.call_combo = ttk.Combobox(box, textvariable=self.call_var, state="readonly")
        self.call_combo.pack(fill="x")
        self.call_combo.bind("<<ComboboxSelected>>", lambda _event: self._select_station())
        ttk.Button(box, text="Reload station list", command=self._reload_stations).pack(fill="x", pady=(6, 0))

        info = ttk.LabelFrame(controls, text="Current location", padding=10)
        info.pack(fill="x", pady=(10, 0))
        self.reported_var = tk.StringVar(value="—")
        self.model_var = tk.StringVar(value="—")
        self.confidence_var = tk.StringVar(value="—")
        self._info_row(info, 0, "Reported", self.reported_var)
        self._info_row(info, 1, "Model", self.model_var)
        self._info_row(info, 2, "Confidence", self.confidence_var)

        proposal = ttk.LabelFrame(controls, text="Proposed location", padding=10)
        proposal.pack(fill="x", pady=(10, 0))
        self.proposed_lat = tk.StringVar()
        self.proposed_lon = tk.StringVar()
        self.reason_var = tk.StringVar()
        self.source_var = tk.StringVar(value="Visual review in Viewshed")
        self._field(proposal, 0, "Latitude", self.proposed_lat)
        self._field(proposal, 1, "Longitude", self.proposed_lon)
        self._field(proposal, 2, "Reason", self.reason_var)
        self._field(proposal, 3, "Source", self.source_var)
        ttk.Button(proposal, text="Show proposed point", command=self._show_proposal).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

        actions = ttk.Frame(controls)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Save as candidate", command=lambda: self._save("candidate")).pack(fill="x")
        ttk.Button(actions, text="Approve correction", command=lambda: self._save("reviewed")).pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Remove my override", command=self._remove).pack(fill="x", pady=(6, 0))

        self.status_var = tk.StringVar(value=f"User correction file: {user_override_path()}")
        ttk.Label(controls, textvariable=self.status_var, wraplength=325).pack(anchor="w", pady=(8, 0))

        self.correction_map = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
        self.correction_map.pack(fill="both", expand=True)
        self.correction_map.add_left_click_map_command(self._correction_click)
        self.correction_map.set_position(40.7608, -111.8910)
        self.correction_map.set_zoom(7)
        self._reload_stations()

    @staticmethod
    def _field(parent: ttk.Frame, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable, width=24).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)
        parent.columnconfigure(1, weight=1)

    @staticmethod
    def _info_row(parent: ttk.Frame, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", pady=3)
        ttk.Label(parent, textvariable=variable, wraplength=220).grid(row=row, column=1, sticky="w", padx=(8, 0), pady=3)

    def _area_click(self, coords: tuple[float, float]) -> None:
        self.area_lat.set(f"{coords[0]:.6f}")
        self.area_lon.set(f"{coords[1]:.6f}")
        self._update_area_map()

    def _update_area_map(self, initial: bool = False) -> None:
        try:
            lat = float(self.area_lat.get())
            lon = float(self.area_lon.get())
            radius = float(self.area_radius.get())
            Region(lat, lon, radius).validate()
        except Exception as exc:
            if not initial:
                messagebox.showerror("Invalid area", str(exc), parent=self)
            return
        if self._area_marker is not None:
            self._area_marker.delete()
        if self._area_polygon is not None:
            self._area_polygon.delete()
        self._area_marker = self.area_map.set_marker(lat, lon, text="Analysis center")
        self._area_polygon = self.area_map.set_polygon(
            _circle_points(lat, lon, radius),
            fill_color="#3388ff",
            outline_color="#1d5fbf",
            border_width=2,
            name="Analysis radius",
        )
        if initial:
            self.area_map.set_position(lat, lon)
            self.area_map.set_zoom(7)

    def _apply_area_to_app(self) -> None:
        try:
            lat = float(self.area_lat.get())
            lon = float(self.area_lon.get())
            radius = float(self.area_radius.get())
            Region(lat, lon, radius).validate()
        except Exception as exc:
            messagebox.showerror("Invalid area", str(exc), parent=self)
            return
        self.app.lat_var.set(f"{lat:.6f}")
        self.app.lon_var.set(f"{lon:.6f}")
        self.app.radius_var.set(f"{radius:g}")
        self.status_var.set("Area-search inputs updated in the main window.")

    def _station_source(self) -> Path:
        cache = portable_data_root() / "cache" / "stations.json"
        if cache.exists():
            return cache
        try:
            source = Path(self.app.source_var.get())
            if source.exists():
                return source
        except Exception:
            pass
        return resource_path("utah_stations_scraped.json")

    def _reload_stations(self) -> None:
        try:
            records = load_station_records(self._station_source())
            records = assess_and_correct_locations(records, resource_path("station_location_overrides.json"))
        except Exception as exc:
            messagebox.showerror("Cannot load stations", str(exc), parent=self)
            records = []
        self._records = {
            str(record.get("callsign") or "").strip().upper(): record
            for record in records
            if record.get("callsign") and "lat" in record and "lon" in record
        }
        calls = sorted(self._records)
        self.call_combo["values"] = calls
        if "FARNSWT" in calls:
            self.call_var.set("FARNSWT")
        elif calls:
            self.call_var.set(calls[0])
        else:
            self.call_var.set("")
        self._select_station()

    def _select_station(self) -> None:
        call = self.call_var.get().strip().upper()
        record = self._records.get(call)
        self.correction_map.delete_all_marker()
        self._reported_marker = None
        self._proposed_marker = None
        if not record:
            self.reported_var.set("No station selected")
            self.model_var.set("—")
            self.confidence_var.set("—")
            return

        reported_lat = float(record.get("_reported_lat", record["lat"]))
        reported_lon = float(record.get("_reported_lon", record["lon"]))
        model_lat = float(record["lat"])
        model_lon = float(record["lon"])
        confidence = record.get("_location_confidence") or {}
        self.reported_var.set(f"{reported_lat:.6f}, {reported_lon:.6f}")
        self.model_var.set(f"{model_lat:.6f}, {model_lon:.6f}")
        self.confidence_var.set(f"{confidence.get('label', '?')} ({confidence.get('score', '?')}/100)")
        self._reported_marker = self.correction_map.set_marker(reported_lat, reported_lon, text=f"{call} reported")

        review = record.get("_location_correction") or record.get("_location_review_candidate") or {}
        if "candidate_lat" in review and "candidate_lon" in review:
            lat = float(review["candidate_lat"])
            lon = float(review["candidate_lon"])
            self.proposed_lat.set(f"{lat:.6f}")
            self.proposed_lon.set(f"{lon:.6f}")
            self.reason_var.set(str(review.get("reason") or ""))
            self.source_var.set(str(review.get("source") or "Visual review in Viewshed"))
            self._proposed_marker = self.correction_map.set_marker(lat, lon, text=f"{call} proposed")
        else:
            self.proposed_lat.set("")
            self.proposed_lon.set("")
            self.reason_var.set("")
            self.source_var.set("Visual review in Viewshed")
        self.correction_map.set_position(model_lat, model_lon)
        self.correction_map.set_zoom(12)

    def _correction_click(self, coords: tuple[float, float]) -> None:
        if not self.call_var.get():
            return
        self.proposed_lat.set(f"{coords[0]:.6f}")
        self.proposed_lon.set(f"{coords[1]:.6f}")
        self._show_proposal()

    def _show_proposal(self) -> None:
        call = self.call_var.get().strip().upper()
        if not call:
            return
        try:
            lat = float(self.proposed_lat.get())
            lon = float(self.proposed_lon.get())
            if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
                raise ValueError("Coordinate is outside valid latitude/longitude bounds.")
        except Exception as exc:
            messagebox.showerror("Invalid proposed coordinate", str(exc), parent=self)
            return
        if self._proposed_marker is not None:
            self._proposed_marker.delete()
        self._proposed_marker = self.correction_map.set_marker(lat, lon, text=f"{call} proposed")

    def _save(self, status: str) -> None:
        call = self.call_var.get().strip().upper()
        if not call:
            messagebox.showerror("No station", "Select a station first.", parent=self)
            return
        try:
            lat = float(self.proposed_lat.get())
            lon = float(self.proposed_lon.get())
        except ValueError:
            messagebox.showerror("No proposed point", "Click the map or enter a proposed coordinate.", parent=self)
            return
        reason = self.reason_var.get().strip()
        if not reason:
            messagebox.showerror("Reason required", "Add a short reason for this correction.", parent=self)
            return
        _save_user_override(call, {
            "status": status,
            "lat": lat,
            "lon": lon,
            "reason": reason,
            "source": self.source_var.get().strip() or "Visual review in Viewshed",
        })
        os.environ[USER_OVERRIDE_ENV] = str(user_override_path())
        self.status_var.set(
            f"Saved {call} as {'reviewed correction' if status == 'reviewed' else 'review candidate'}."
        )
        self._reload_stations()

    def _remove(self) -> None:
        call = self.call_var.get().strip().upper()
        if not call:
            return
        if _remove_user_override(call):
            self.status_var.set(f"Removed user override for {call}. Bundled defaults still apply if present.")
        else:
            self.status_var.set(f"No user override exists for {call}.")
        self._reload_stations()
