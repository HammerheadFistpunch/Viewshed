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

from map_workspace_patch import ViewshedWorkspace
from seed_builder import SeedBuilderDialog
from viewshed_core import APP_VERSION, USER_OVERRIDE_ENV, portable_data_root, resource_path, run_legacy_worker, self_test, user_override_path


def _configure_stdio_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except (OSError, ValueError):
                pass


def _settings_path() -> Path:
    return portable_data_root() / "settings.json"


def _load_settings() -> dict:
    path = _settings_path()
    if not path.exists(): return {}
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
        os.environ[USER_OVERRIDE_ENV] = str(user_override_path())
        self.title(f"Viewshed {APP_VERSION}")
        self.geometry("1280x900")
        self.minsize(1000, 720)
        self._settings = _load_settings()
        self._messages: queue.Queue[tuple[str, str]] = queue.Queue()
        self._last_output: Path | None = None
        self._last_kmz: Path | None = None
        self._last_tif: Path | None = None
        self._job_running = False
        self._current_process: subprocess.Popen | None = None
        self._cancel_requested = False
        self._seed_builder: SeedBuilderDialog | None = None
        self._build_ui()
        self.after(100, self._drain_messages)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="Viewshed", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(header, text=f"v{APP_VERSION}  •  map-first VHF propagation workspace").pack(side="left", padx=(10, 0), pady=(7, 0))
        self.open_folder_btn = ttk.Button(header, text="Open Output Folder", command=self._open_output, state="disabled")
        self.open_folder_btn.pack(side="right")
        self.open_kmz_btn = ttk.Button(header, text="Open KMZ", command=lambda: self._open_path(self._last_kmz), state="disabled")
        self.open_kmz_btn.pack(side="right", padx=(0, 6))
        self.open_tif_btn = ttk.Button(header, text="Open GeoTIFF", command=lambda: self._open_path(self._last_tif), state="disabled")
        self.open_tif_btn.pack(side="right", padx=(0, 6))
        ttk.Button(header, text="Build Seed…", command=self._open_seed_builder).pack(side="right", padx=(0, 8))

        settings = ttk.LabelFrame(outer, text="Shared APRS / data settings", padding=8)
        settings.pack(fill="x", pady=(8, 8))
        settings.columnconfigure(7, weight=1)
        self.source_var = tk.StringVar(value=str(resource_path("utah_stations_scraped.json")))
        self.callsign_var = tk.StringVar(value=str(self._settings.get("aprs_callsign") or os.environ.get("VIEWSHED_APRS_CALLSIGN", "")))
        self.aprsfi_var = tk.StringVar(value=str(self._settings.get("aprs_fi_api_key") or os.environ.get("VIEWSHED_APRSFI_API_KEY", "")))
        self.refresh_var = tk.StringVar(value=str(self._settings.get("live_refresh_seconds") or os.environ.get("VIEWSHED_LIVE_REFRESH_SECONDS", "45")))
        self.remember_var = tk.BooleanVar(value=bool(self._settings.get("remember_aprs_settings", True)))

        ttk.Label(settings, text="APRS callsign").grid(row=0, column=0, sticky="w")
        ttk.Entry(settings, textvariable=self.callsign_var, width=13).grid(row=0, column=1, padx=(5, 12))
        ttk.Label(settings, text="aprs.fi key").grid(row=0, column=2, sticky="w")
        ttk.Entry(settings, textvariable=self.aprsfi_var, show="•", width=20).grid(row=0, column=3, padx=(5, 12))
        ttk.Label(settings, text="Live sample (s)").grid(row=0, column=4, sticky="w")
        ttk.Entry(settings, textvariable=self.refresh_var, width=6).grid(row=0, column=5, padx=(5, 12))
        ttk.Checkbutton(settings, text="Remember", variable=self.remember_var).grid(row=0, column=6, sticky="w")

        ttk.Label(settings, text="Optional seed/fallback").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(settings, textvariable=self.source_var).grid(row=1, column=1, columnspan=6, sticky="ew", padx=(5, 6), pady=(6, 0))
        ttk.Button(settings, text="Browse…", command=self._browse_source).grid(row=1, column=7, sticky="e", pady=(6, 0))

        self.workspace = ViewshedWorkspace(outer, self)
        self.workspace.pack(fill="both", expand=True)

        status = ttk.Frame(outer)
        status.pack(fill="x", pady=(8, 0))
        self.status_var = tk.StringVar(value="Ready")
        self.percent_var = tk.StringVar(value="0%")
        ttk.Label(status, textvariable=self.status_var).pack(side="left")
        self.cancel_btn = ttk.Button(status, text="Cancel Run", command=self.cancel_job, state="disabled")
        self.cancel_btn.pack(side="right", padx=(8, 0))
        ttk.Label(status, textvariable=self.percent_var).pack(side="right")
        self.progress = ttk.Progressbar(outer, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(3, 0))

        details = ttk.LabelFrame(outer, text="Propagation job log", padding=5)
        details.pack(fill="x", pady=(5, 0))
        self.log = tk.Text(details, height=6, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(details, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _browse_source(self) -> None:
        chosen = filedialog.askopenfilename(title="Choose station JSON", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if chosen:
            self.source_var.set(chosen)
            self.workspace.reload_station_catalog()

    def _open_seed_builder(self) -> None:
        if self._seed_builder is not None and self._seed_builder.winfo_exists():
            self._seed_builder.lift()
            self._seed_builder.focus_force()
            return
        self._seed_builder = SeedBuilderDialog(self)

    def apply_network_settings(self) -> None:
        refresh = int(self.refresh_var.get())
        if not 0 <= refresh <= 300:
            raise ValueError("Live sample time must be between 0 and 300 seconds.")
        callsign = self.callsign_var.get().strip().upper()
        api_key = self.aprsfi_var.get().strip()
        if callsign: os.environ["VIEWSHED_APRS_CALLSIGN"] = callsign
        else: os.environ.pop("VIEWSHED_APRS_CALLSIGN", None)
        if api_key: os.environ["VIEWSHED_APRSFI_API_KEY"] = api_key
        else: os.environ.pop("VIEWSHED_APRSFI_API_KEY", None)
        os.environ["VIEWSHED_LIVE_REFRESH_SECONDS"] = str(refresh)
        os.environ[USER_OVERRIDE_ENV] = str(user_override_path())
        if self.remember_var.get():
            _save_settings({
                "remember_aprs_settings": True,
                "aprs_callsign": callsign,
                "aprs_fi_api_key": api_key,
                "live_refresh_seconds": refresh,
            })
        else:
            _settings_path().unlink(missing_ok=True)

    def start_job(self, job_file: Path, label: str) -> None:
        if self._job_running:
            messagebox.showwarning("Propagation already running", "Finish or cancel the current propagation job before starting another.", parent=self)
            return
        try:
            self.apply_network_settings()
        except Exception as exc:
            messagebox.showerror("Invalid settings", str(exc), parent=self)
            return
        self._job_running = True
        self._cancel_requested = False
        self._current_process = None
        self.cancel_btn.configure(state="normal")
        self._reset_output_buttons()
        self._set_progress(2, f"Starting {label} propagation…")
        self._append_log(f"\nStarting {label} job: {job_file.parent}\n")
        threading.Thread(target=self._run_job, args=(job_file,), daemon=True).start()

    def _run_job(self, job_file: Path) -> None:
        try:
            if getattr(sys, "frozen", False):
                command = [sys.executable, "--worker", str(job_file)]
            else:
                command = [sys.executable, "-u", str(Path(__file__).resolve()), "--worker", str(job_file)]
            child_env = os.environ.copy()
            child_env["PYTHONIOENCODING"] = "utf-8"
            child_env["PYTHONUTF8"] = "1"
            child_env["PYTHONUNBUFFERED"] = "1"
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=str(Path(job_file).parent),
                env=child_env,
                creationflags=creationflags,
            )
            self._current_process = process
            if self._cancel_requested:
                self._terminate_process_tree(process)
            assert process.stdout is not None
            for line in process.stdout:
                self._messages.put(("log", line))
            code = process.wait()
            self._current_process = None
            if self._cancel_requested:
                self._messages.put(("cancelled", str(job_file.parent)))
                return
            if code != 0:
                raise RuntimeError(f"Viewshed worker exited with code {code}.")
            self._messages.put(("done", str(job_file.parent / "output")))
        except Exception as exc:
            self._current_process = None
            if self._cancel_requested:
                self._messages.put(("cancelled", str(job_file.parent)))
            else:
                self._messages.put(("error", str(exc)))

    @staticmethod
    def _terminate_process_tree(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
            else:
                process.terminate()
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def cancel_job(self) -> None:
        if not self._job_running:
            return
        if not messagebox.askyesno(
            "Cancel propagation",
            "Stop the current propagation run?\n\nDownloaded DEM cache files will be kept for future runs.",
            parent=self,
        ):
            return
        self._cancel_requested = True
        self.cancel_btn.configure(state="disabled")
        self.status_var.set("Cancelling propagation…")
        self._append_log("\nCancellation requested. Stopping worker process tree…\n")
        process = self._current_process
        if process is not None:
            threading.Thread(target=self._terminate_process_tree, args=(process,), daemon=True).start()

    def _set_progress(self, percent: int, status: str) -> None:
        percent = max(0, min(100, percent))
        self.progress["value"] = percent
        self.percent_var.set(f"{percent}%")
        self.status_var.set(status)

    def _update_progress_from_log(self, line: str) -> None:
        text = line.strip()
        stages = (
            (("Station acquisition selected", "Using "), 15, "Station list locked"),
            (("DEM cache:", "Tiles required:", "Source: USGS"), 28, "Preparing elevation data"),
            (("Downloading N", "Merging "), 38, "Downloading / assembling terrain"),
            (("Analysis DEM ready", "Building memory-bounded analysis DEM"), 50, "Preparing analysis terrain"),
            (("Engine:", "Workers:", "DEM in shared memory"), 60, "Computing propagation"),
            (("stations resolved", "Merging viewshed"), 80, "Combining coverage"),
            (("Rendering coverage", "Writing KMZ", "KMZ:"), 92, "Rendering and exporting"),
        )
        for needles, percent, status in stages:
            if any(n in text for n in needles):
                if percent >= int(float(self.progress["value"])): self._set_progress(percent, status)
                break

    def _drain_messages(self) -> None:
        try:
            while True:
                kind, text = self._messages.get_nowait()
                if kind == "log":
                    self._update_progress_from_log(text)
                    self._append_log(text)
                elif kind == "done":
                    self._job_running = False
                    self._cancel_requested = False
                    self.cancel_btn.configure(state="disabled")
                    self._last_output = Path(text)
                    self._refresh_output_buttons()
                    self._set_progress(100, "Complete — outputs are ready")
                    self._append_log(f"\nComplete. Output: {text}\n")
                    if messagebox.askyesno("Viewshed complete", f"Outputs are ready in:\n{text}\n\nOpen the output folder now?", parent=self):
                        self._open_output()
                elif kind == "cancelled":
                    self._job_running = False
                    self._cancel_requested = False
                    self._current_process = None
                    self.cancel_btn.configure(state="disabled")
                    self.status_var.set("Cancelled")
                    self._append_log(f"\nCancelled. Partial job data remains in: {text}\n")
                elif kind == "error":
                    self._job_running = False
                    self._cancel_requested = False
                    self._current_process = None
                    self.cancel_btn.configure(state="disabled")
                    self.status_var.set("Failed — see propagation job log")
                    self._append_log(f"\nERROR: {text}\n")
                    messagebox.showerror("Viewshed failed", text, parent=self)
        except queue.Empty:
            pass
        self.after(100, self._drain_messages)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _reset_output_buttons(self) -> None:
        self._last_output = None
        self._last_kmz = None
        self._last_tif = None
        self.open_folder_btn.configure(state="disabled")
        self.open_kmz_btn.configure(state="disabled")
        self.open_tif_btn.configure(state="disabled")

    def _refresh_output_buttons(self) -> None:
        if not self._last_output or not self._last_output.exists():
            self._reset_output_buttons()
            return
        self.open_folder_btn.configure(state="normal")
        self._last_kmz = next(iter(sorted(self._last_output.glob("*.kmz"))), None)
        tifs = sorted(self._last_output.rglob("*.tif"))
        self._last_tif = next((p for p in tifs if p.name == "coverage_count.tif"), tifs[0] if tifs else None)
        self.open_kmz_btn.configure(state="normal" if self._last_kmz else "disabled")
        self.open_tif_btn.configure(state="normal" if self._last_tif else "disabled")

    def _open_path(self, target: Path | None) -> None:
        if target is None or not target.exists():
            return
        path = str(target)
        if sys.platform == "win32": os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])

    def _open_output(self) -> None:
        self._open_path(self._last_output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Portable APRS viewshed generator")
    parser.add_argument("--worker", type=Path, help="Run a prepared viewshed job")
    parser.add_argument("--self-test", action="store_true", help="Run a lightweight packaged-app smoke test")
    return parser.parse_args()


def main() -> int:
    multiprocessing.freeze_support()
    _configure_stdio_utf8()
    args = parse_args()
    if args.self_test:
        print(self_test(), flush=True)
        return 0
    if args.worker:
        run_legacy_worker(args.worker)
        return 0
    ViewshedApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
