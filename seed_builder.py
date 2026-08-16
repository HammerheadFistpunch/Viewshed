from __future__ import annotations

import json
import os
import socket
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from station_sources import (
    APRS_HOST,
    APRS_PORT,
    _normalize_call,
    _packet_roles,
    _parse_position,
    lookup_aprs_fi,
)
from viewshed_core import portable_data_root


def collect_seed(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    duration_seconds: int,
    callsign: str = "",
    aprs_fi_api_key: str = "",
    stop_event: threading.Event | None = None,
    progress=None,
) -> tuple[list[dict], dict]:
    """Collect APRS infrastructure over a long session.

    Unlike the short Area sample, role sightings and position packets are accumulated
    across the entire run. A station can therefore be identified as a digi/iGate at
    one time and have its own position packet arrive much later.
    """
    stop_event = stop_event or threading.Event()
    duration_seconds = max(1, int(duration_seconds))
    callsign = _normalize_call(callsign) or "N0CALL"
    filter_text = f"r/{center_lat:.5f}/{center_lon:.5f}/{max(1, int(radius_km))}"
    login = f"user {callsign} pass -1 vers Viewshed 0.3 filter {filter_text}\r\n"

    positions: dict[str, dict] = {}
    digis: set[str] = set()
    igates: set[str] = set()
    packets = 0
    reconnects = 0
    started = time.monotonic()
    deadline = started + duration_seconds
    last_report = 0.0

    while time.monotonic() < deadline and not stop_event.is_set():
        try:
            with socket.create_connection((APRS_HOST, APRS_PORT), timeout=15) as sock:
                sock.settimeout(2)
                sock.sendall(login.encode("ascii", errors="ignore"))
                buffer = ""
                while time.monotonic() < deadline and not stop_event.is_set():
                    try:
                        chunk = sock.recv(65536)
                    except socket.timeout:
                        chunk = b""
                    if chunk:
                        buffer += chunk.decode("utf-8", errors="replace")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            packets += 1
                            d, i = _packet_roles(line)
                            digis.update(d)
                            igates.update(i)
                            parsed = _parse_position(line)
                            if parsed:
                                call, record = parsed
                                positions[call] = record
                                if record.get("symbol") == "#":
                                    digis.add(call)
                    now = time.monotonic()
                    if progress and now - last_report >= 2.0:
                        elapsed = min(duration_seconds, int(now - started))
                        progress(elapsed, duration_seconds, len(digis | igates), len(positions), packets)
                        last_report = now
                    if not chunk and time.monotonic() >= deadline:
                        break
        except Exception:
            reconnects += 1
            if time.monotonic() >= deadline or stop_event.is_set():
                break
            time.sleep(2)

    roles = digis | igates
    records: dict[str, dict] = {}
    for call in roles:
        rec = positions.get(call)
        if not rec:
            continue
        item = dict(rec)
        item["type"] = "digi" if call in digis else "igate"
        item["_source"] = "APRS-IS long-run"
        records[call] = item

    unresolved = sorted(roles - set(records))
    if aprs_fi_api_key and unresolved and not stop_event.is_set():
        try:
            for rec in lookup_aprs_fi(unresolved, aprs_fi_api_key):
                call = _normalize_call(str(rec.get("callsign") or ""))
                if not call:
                    continue
                item = dict(rec)
                item["type"] = "digi" if call in digis else "igate"
                records[call] = item
        except Exception:
            pass

    output = sorted(records.values(), key=lambda r: str(r.get("callsign") or ""))
    meta = {
        "center": {"lat": center_lat, "lon": center_lon, "radius_km": radius_km},
        "duration_seconds": int(time.monotonic() - started),
        "packets_observed": packets,
        "infrastructure_calls_observed": len(roles),
        "positions_resolved": len(output),
        "unresolved_calls": sorted(roles - {str(r.get("callsign") or "") for r in output}),
        "reconnects": reconnects,
        "stopped_early": stop_event.is_set(),
        "created_at": time.time(),
    }
    return output, meta


class SeedBuilderDialog(tk.Toplevel):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.app = app
        self.title("Viewshed Seed Builder")
        self.geometry("620x520")
        self.minsize(560, 470)
        self._stop = threading.Event()
        self._running = False

        area_lat = getattr(getattr(app, "workspace", None), "area_lat", None)
        area_lon = getattr(getattr(app, "workspace", None), "area_lon", None)
        area_radius = getattr(getattr(app, "workspace", None), "area_radius", None)
        lat = area_lat.get() if area_lat is not None else "40.7608"
        lon = area_lon.get() if area_lon is not None else "-111.8910"
        radius = area_radius.get() if area_radius is not None else "100"

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Long-run APRS seed builder", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Listen to APRS-IS for an extended period and save the accumulated digi/iGate locations as a reusable JSON seed. Callsign and aprs.fi key remain optional.",
            wraplength=570,
        ).pack(anchor="w", pady=(4, 12))

        form = ttk.LabelFrame(outer, text="Collection", padding=10)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        self.lat_var = tk.StringVar(value=lat)
        self.lon_var = tk.StringVar(value=lon)
        self.radius_var = tk.StringVar(value=radius)
        self.duration_var = tk.StringVar(value="30")
        default_dir = portable_data_root() / "seeds"
        default_dir.mkdir(parents=True, exist_ok=True)
        self.output_var = tk.StringVar(value=str(default_dir / time.strftime("stations_%Y%m%d-%H%M%S.json")))
        self.use_var = tk.BooleanVar(value=True)

        self._row(form, 0, "Center latitude", self.lat_var)
        self._row(form, 1, "Center longitude", self.lon_var)
        self._row(form, 2, "Radius (km)", self.radius_var)
        self._row(form, 3, "Duration (minutes)", self.duration_var)
        ttk.Label(form, text="Output JSON").grid(row=4, column=0, sticky="w", pady=3)
        ttk.Entry(form, textvariable=self.output_var).grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=3)
        ttk.Button(form, text="Browse…", command=self._browse).grid(row=4, column=2, padx=(6, 0), pady=3)
        ttk.Checkbutton(form, text="Use completed file as the active seed/fallback", variable=self.use_var).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )

        self.status_var = tk.StringVar(value="Ready")
        self.progress = ttk.Progressbar(outer, maximum=100)
        self.progress.pack(fill="x", pady=(14, 4))
        ttk.Label(outer, textvariable=self.status_var, wraplength=570).pack(anchor="w")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(14, 0))
        self.start_btn = ttk.Button(actions, text="Start long-run collection", command=self._start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(actions, text="Stop and save", command=self._request_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(8, 0))

        ttk.Label(
            outer,
            text="Tip: 30–60 minutes is much more likely than a 45-second sample to see periodic infrastructure beacons. Longer runs can be used when building a regional reference seed.",
            wraplength=570,
        ).pack(anchor="w", pady=(16, 0))

    @staticmethod
    def _row(parent, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)

    def _browse(self) -> None:
        chosen = filedialog.asksaveasfilename(
            parent=self,
            title="Save station seed",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if chosen:
            self.output_var.set(chosen)

    def _start(self) -> None:
        if self._running:
            return
        try:
            lat = float(self.lat_var.get())
            lon = float(self.lon_var.get())
            radius = float(self.radius_var.get())
            minutes = float(self.duration_var.get())
            if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("Invalid center latitude/longitude.")
            if not 1 <= radius <= 2000:
                raise ValueError("Radius must be between 1 and 2000 km.")
            if not 1 <= minutes <= 1440:
                raise ValueError("Duration must be between 1 minute and 24 hours.")
            output = Path(self.output_var.get()).expanduser()
            if not output.name:
                raise ValueError("Choose an output JSON file.")
            self.app.apply_network_settings()
        except Exception as exc:
            messagebox.showerror("Cannot start seed builder", str(exc), parent=self)
            return

        self._running = True
        self._stop.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_var.set("Connecting to APRS-IS…")
        duration_seconds = int(minutes * 60)

        def report(elapsed, total, roles, positions, packets):
            self.after(0, lambda: self._report(elapsed, total, roles, positions, packets))

        def work():
            try:
                records, meta = collect_seed(
                    lat,
                    lon,
                    radius,
                    duration_seconds,
                    callsign=os.environ.get("VIEWSHED_APRS_CALLSIGN", ""),
                    aprs_fi_api_key=os.environ.get("VIEWSHED_APRSFI_API_KEY", ""),
                    stop_event=self._stop,
                    progress=report,
                )
                output.parent.mkdir(parents=True, exist_ok=True)
                payload = {"metadata": meta, "stations": records}
                output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                self.after(0, lambda: self._done(output, records, meta))
            except Exception as exc:
                self.after(0, lambda e=exc: self._failed(e))

        threading.Thread(target=work, daemon=True).start()

    def _report(self, elapsed: int, total: int, roles: int, positions: int, packets: int) -> None:
        pct = min(100, int(100 * elapsed / max(total, 1)))
        self.progress["value"] = pct
        self.status_var.set(
            f"Listening… {elapsed // 60}m {elapsed % 60:02d}s / {total // 60}m • "
            f"{roles} infrastructure calls • {positions} position packets • {packets} packets"
        )

    def _request_stop(self) -> None:
        if self._running:
            self._stop.set()
            self.status_var.set("Stopping collection and writing the seed file…")
            self.stop_btn.configure(state="disabled")

    def _done(self, output: Path, records: list[dict], meta: dict) -> None:
        self._running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.progress["value"] = 100
        unresolved = len(meta.get("unresolved_calls") or [])
        self.status_var.set(
            f"Saved {len(records)} usable stations to {output}. "
            f"Observed {meta.get('infrastructure_calls_observed', 0)} infrastructure calls; {unresolved} remain unresolved."
        )
        if self.use_var.get():
            self.app.source_var.set(str(output))
            self.app.workspace.reload_station_catalog()
        messagebox.showinfo(
            "Seed collection complete",
            f"Saved {len(records)} usable station records.\n\n{output}",
            parent=self,
        )

    def _failed(self, exc: Exception) -> None:
        self._running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_var.set("Seed collection failed.")
        messagebox.showerror("Seed collection failed", str(exc), parent=self)
