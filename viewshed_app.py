from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from viewshed_core import (
    APP_VERSION,
    Region,
    portable_data_root,
    prepare_job,
    resource_path,
    run_legacy_worker,
    self_test,
)


def _settings_path() -> Path:
    return portable_data_root() / "settings.json"


def _load_settings() -> dict:
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_settings(settings: dict) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


class ViewshedApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Viewshed {APP_VERSION}")
        self.geometry("780x730")
        self.minsize(700, 620)
        self._messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self._last_output: Path | None = None
        self._settings = _load_settings()
        self._build_ui()
        self.after(100, self._drain_messages)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="APRS Viewshed Generator", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Choose an area. Viewshed refreshes/reuses APRS infrastructure data, acquires terrain, computes coverage, and exports KMZ + GeoTIFF.",
            wraplength=720,
        ).pack(anchor="w", pady=(2, 14))

        area = ttk.LabelFrame(outer, text="Search area", padding=12)
        area.pack(fill="x")
        self.lat_var = tk.StringVar(value="40.7608")
        self.lon_var = tk.StringVar(value="-111.8910")
        self.radius_var = tk.StringVar(value="100")
        self.propagation_var = tk.StringVar(value="180")
        self._field(area, 0, "Center latitude", self.lat_var)
        self._field(area, 1, "Center longitude", self.lon_var)
        self._field(area, 2, "Output radius (km)", self.radius_var)
        self._field(area, 3, "Max propagation radius (km)", self.propagation_var)
        ttk.Label(
            area,
            text="Stations are searched out to output radius + propagation radius so coverage crossing the area boundary is not missed.",
            wraplength=670,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        stations = ttk.LabelFrame(outer, text="Station acquisition", padding=12)
        stations.pack(fill="x", pady=(12, 0))
        stations.columnconfigure(1, weight=1)

        self.source_var = tk.StringVar(value=str(resource_path("utah_stations_scraped.json")))
        ttk.Label(stations, text="Seed/fallback JSON").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(stations, textvariable=self.source_var).grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=3)
        ttk.Button(stations, text="Browse…", command=self._browse_source).grid(row=0, column=2, padx=(8, 0), pady=3)

        self.callsign_var = tk.StringVar(
            value=str(self._settings.get("aprs_callsign") or os.environ.get("VIEWSHED_APRS_CALLSIGN", ""))
        )
        self.aprsfi_var = tk.StringVar(
            value=str(self._settings.get("aprs_fi_api_key") or os.environ.get("VIEWSHED_APRSFI_API_KEY", ""))
        )
        self.refresh_var = tk.StringVar(
            value=str(self._settings.get("live_refresh_seconds") or os.environ.get("VIEWSHED_LIVE_REFRESH_SECONDS", "45"))
        )
        self.remember_var = tk.BooleanVar(value=bool(self._settings.get("remember_aprs_settings", True)))

        ttk.Label(stations, text="APRS callsign").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(stations, textvariable=self.callsign_var, width=22).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=3)
        ttk.Label(stations, text="Optional; read-only APRS-IS works with N0CALL if blank.").grid(row=1, column=2, sticky="w", padx=(8, 0))

        ttk.Label(stations, text="aprs.fi API key").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(stations, textvariable=self.aprsfi_var, show="•", width=28).grid(row=2, column=1, sticky="w", padx=(12, 0), pady=3)
        ttk.Label(stations, text="Optional; resolves discovered calls with missing positions.").grid(row=2, column=2, sticky="w", padx=(8, 0))

        ttk.Label(stations, text="Live refresh (sec)").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(stations, textvariable=self.refresh_var, width=10).grid(row=3, column=1, sticky="w", padx=(12, 0), pady=3)
        ttk.Checkbutton(
            stations,
            text="Remember APRS settings on this computer",
            variable=self.remember_var,
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(5, 0))

        types = ttk.Frame(stations)
        types.grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.digi_var = tk.BooleanVar(value=True)
        self.igate_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(types, text="Digipeaters", variable=self.digi_var).pack(side="left")
        ttk.Checkbutton(types, text="iGates", variable=self.igate_var).pack(side="left", padx=(18, 0))
        ttk.Label(
            stations,
            text="The area-aware station cache is reused for up to 6 hours. When stale or for a different area, APRS-IS is sampled live; aprs.fi is used only when a key is supplied.",
            wraplength=690,
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(14, 0))
        self.generate_btn = ttk.Button(actions, text="Generate Viewshed", command=self._generate)
        self.generate_btn.pack(side="left")
        self.open_btn = ttk.Button(actions, text="Open Output Folder", command=self._open_output, state="disabled")
        self.open_btn.pack(side="left", padx=(8, 0))
        ttk.Label(actions, text=f"Data root: {portable_data_root()}").pack(side="right")

        log_frame = ttk.LabelFrame(outer, text="Progress", padding=8)
        log_frame.pack(fill="both", expand=True, pady=(12, 0))
        self.log = tk.Text(log_frame, height=18, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    @staticmethod
    def _field(parent: ttk.Frame, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable, width=24).grid(row=row, column=1, sticky="w", padx=(18, 0), pady=3)

    def _browse_source(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Choose station JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if chosen:
            self.source_var.set(chosen)

    def _apply_station_settings(self) -> None:
        refresh = int(self.refresh_var.get())
        if not 0 <= refresh <= 300:
            raise ValueError("Live refresh must be between 0 and 300 seconds.")
        callsign = self.callsign_var.get().strip().upper()
        api_key = self.aprsfi_var.get().strip()
        if callsign:
            os.environ["VIEWSHED_APRS_CALLSIGN"] = callsign
        else:
            os.environ.pop("VIEWSHED_APRS_CALLSIGN", None)
        if api_key:
            os.environ["VIEWSHED_APRSFI_API_KEY"] = api_key
        else:
            os.environ.pop("VIEWSHED_APRSFI_API_KEY", None)
        os.environ["VIEWSHED_LIVE_REFRESH_SECONDS"] = str(refresh)
        if self.remember_var.get():
            _save_settings({
                "remember_aprs_settings": True,
                "aprs_callsign": callsign,
                "aprs_fi_api_key": api_key,
                "live_refresh_seconds": refresh,
            })
        else:
            _settings_path().unlink(missing_ok=True)

    def _generate(self) -> None:
        try:
            self._apply_station_settings()
            region = Region(float(self.lat_var.get()), float(self.lon_var.get()), float(self.radius_var.get()))
            propagation = float(self.propagation_var.get())
            types = set()
            if self.digi_var.get():
                types.add("digi")
            if self.igate_var.get():
                types.add("igate")
            _, job_file = prepare_job(region, Path(self.source_var.get()), types, propagation)
        except Exception as exc:
            messagebox.showerror("Cannot start viewshed", str(exc))
            return

        self.generate_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self._append_log(f"Starting job: {job_file.parent}\n")
        threading.Thread(target=self._run_job, args=(job_file,), daemon=True).start()

    def _run_job(self, job_file: Path) -> None:
        try:
            if getattr(sys, "frozen", False):
                command = [sys.executable, "--worker", str(job_file)]
            else:
                command = [sys.executable, str(Path(__file__).resolve()), "--worker", str(job_file)]
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(Path(job_file).parent),
            )
            assert process.stdout is not None
            for line in process.stdout:
                self._messages.put(("log", line))
            code = process.wait()
            if code != 0:
                raise RuntimeError(f"Viewshed worker exited with code {code}.")
            self._last_output = job_file.parent / "output"
            self._messages.put(("done", str(self._last_output)))
        except Exception as exc:
            self._messages.put(("error", str(exc)))

    def _drain_messages(self) -> None:
        try:
            while True:
                kind, text = self._messages.get_nowait()
                if kind == "log":
                    self._append_log(text)
                elif kind == "done":
                    self.generate_btn.configure(state="normal")
                    self.open_btn.configure(state="normal")
                    self._append_log(f"\nComplete. Output: {text}\n")
                    messagebox.showinfo("Viewshed complete", f"Outputs are ready in:\n{text}")
                elif kind == "error":
                    self.generate_btn.configure(state="normal")
                    self._append_log(f"\nERROR: {text}\n")
                    messagebox.showerror("Viewshed failed", text)
        except queue.Empty:
            pass
        self.after(100, self._drain_messages)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _open_output(self) -> None:
        if not self._last_output:
            return
        path = str(self._last_output)
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Portable APRS viewshed generator")
    parser.add_argument("--worker", type=Path, help="Run a prepared viewshed job")
    parser.add_argument("--self-test", action="store_true", help="Run a lightweight packaged-app smoke test")
    return parser.parse_args()


def main() -> int:
    multiprocessing.freeze_support()
    args = parse_args()
    if args.self_test:
        print(self_test())
        return 0
    if args.worker:
        run_legacy_worker(args.worker)
        return 0
    ViewshedApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
