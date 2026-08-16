from __future__ import annotations

import argparse
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


class ViewshedApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Viewshed {APP_VERSION}")
        self.geometry("760x650")
        self.minsize(680, 560)
        self._messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self._last_output: Path | None = None
        self._build_ui()
        self.after(100, self._drain_messages)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="APRS Viewshed Generator", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Choose an area. Viewshed will select relevant stations, acquire/cache terrain, compute coverage, and export KMZ + GeoTIFF.",
            wraplength=700,
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
            wraplength=650,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        stations = ttk.LabelFrame(outer, text="Station data", padding=12)
        stations.pack(fill="x", pady=(12, 0))
        self.source_var = tk.StringVar(value=str(resource_path("utah_stations_scraped.json")))
        ttk.Entry(stations, textvariable=self.source_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(stations, text="Browse…", command=self._browse_source).grid(row=0, column=1, padx=(8, 0))
        stations.columnconfigure(0, weight=1)

        types = ttk.Frame(stations)
        types.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.digi_var = tk.BooleanVar(value=True)
        self.igate_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(types, text="Digipeaters", variable=self.digi_var).pack(side="left")
        ttk.Checkbutton(types, text="iGates", variable=self.igate_var).pack(side="left", padx=(18, 0))
        ttk.Label(
            stations,
            text="v0.1 ships with the current Utah station dataset. Another compatible station JSON can be selected for other datasets.",
            wraplength=650,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

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
        chosen = filedialog.askopenfilename(title="Choose station JSON", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if chosen:
            self.source_var.set(chosen)

    def _generate(self) -> None:
        try:
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
