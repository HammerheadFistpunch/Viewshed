from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import station_sources
import viewshed_core
from repeat_run_workspace import ViewshedWorkspace as _ViewshedWorkspace
from viewshed_core import portable_data_root, resource_path


PRODUCT_NAME = "Signal Peak"
PRODUCT_VERSION = "1.0.2"
PRODUCT_HOME = "https://github.com/HammerheadFistpunch/Viewshed"

viewshed_core.APP_VERSION = PRODUCT_VERSION
station_sources.USER_AGENT = f"SignalPeak/{PRODUCT_VERSION} (+{PRODUCT_HOME})"
APP_VERSION = PRODUCT_VERSION


class ViewshedWorkspace(_ViewshedWorkspace):
    """Signal Peak workspace with bundled offline Help/About access."""

    DOCS = [
        ("README / project overview", "README.md"),
        ("GNU GPL v2 License", "LICENSE"),
        ("Quick Start", "docs/QUICK_START.md"),
        ("User Guide", "docs/USER_GUIDE.md"),
        ("Propagation Model", "docs/PROPAGATION_MODEL.md"),
        ("CONUS support", "docs/CONUS.md"),
        ("Station Data", "docs/STATION_DATA.md"),
        ("Location Corrections", "docs/LOCATION_CORRECTIONS.md"),
        ("Outputs", "docs/OUTPUTS.md"),
        ("Troubleshooting", "docs/TROUBLESHOOTING.md"),
        ("Dependencies / Licenses", "docs/LICENSES_AND_DEPENDENCIES.md"),
        ("1.0 Release Readiness", "docs/RELEASE_READINESS_1.0.0.md"),
        ("Special Considerations", "docs/SPECIAL_CONSIDERATIONS.md"),
        ("Roadmap", "docs/ROADMAP.md"),
    ]

    def __init__(self, master, app) -> None:
        self._area_cancel_event = threading.Event()
        self._log_window: tk.Toplevel | None = None
        self._log_text: tk.Text | None = None
        self._signal_peak_icon = None
        super().__init__(master, app)
        self._brand_application()
        self._install_secure_settings_storage()
        self._clarify_range_labels()
        self._install_area_activity_indicator()
        self._default_seed_field_empty()
        self._install_window_icon()
        self._build_help_tab()
        self.after_idle(self._polish_progress_shell)

    def _brand_application(self) -> None:
        self.app.title(f"{PRODUCT_NAME} {PRODUCT_VERSION}")

        def visit(widget) -> None:
            try:
                text = widget.cget("text")
            except Exception:
                text = None
            if text == "Viewshed":
                try:
                    widget.configure(text=PRODUCT_NAME)
                except Exception:
                    pass
            try:
                children = widget.winfo_children()
            except Exception:
                children = []
            for child in children:
                visit(child)

        visit(self.app)

    def _install_window_icon(self) -> None:
        try:
            icon_path = resource_path("assets/signal-peak-icon.png")
            if not icon_path.exists():
                return
            self._signal_peak_icon = tk.PhotoImage(file=str(icon_path))
            self.app.iconphoto(True, self._signal_peak_icon)
        except Exception:
            self._signal_peak_icon = None

    def _apply_window_icon(self, window) -> None:
        if self._signal_peak_icon is None:
            return
        try:
            window.iconphoto(False, self._signal_peak_icon)
        except Exception:
            pass

    @staticmethod
    def _remove_saved_api_key() -> None:
        """Keep aprs.fi credentials session-only rather than writing them to disk."""
        path = portable_data_root() / "settings.json"
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or "aprs_fi_api_key" not in raw:
                return
            raw.pop("aprs_fi_api_key", None)
            path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _install_secure_settings_storage(self) -> None:
        if getattr(self.app, "_signal_peak_secure_settings", False):
            return
        self._remove_saved_api_key()
        original_apply = self.app.apply_network_settings

        def secure_apply_network_settings():
            result = original_apply()
            self._remove_saved_api_key()
            return result

        self.app.apply_network_settings = secure_apply_network_settings
        self.app._signal_peak_secure_settings = True

    def _clarify_range_labels(self) -> None:
        replacements = {
            "Station coverage radius (km)": "Max calculation range (km)",
            "Coverage radius (km)": "Max calculation range (km)",
        }

        def visit(widget) -> None:
            try:
                text = widget.cget("text")
            except Exception:
                text = None
            if text in replacements:
                try:
                    widget.configure(text=replacements[text])
                except Exception:
                    pass
            try:
                children = widget.winfo_children()
            except Exception:
                children = []
            for child in children:
                visit(child)

        visit(self)

    def _default_seed_field_empty(self) -> None:
        try:
            self.app.source_var.set("")
        except Exception:
            pass

    def _install_area_activity_indicator(self) -> None:
        parent = self.find_area_btn.master
        self.area_activity = ttk.Progressbar(parent, mode="determinate", maximum=100)
        self.area_activity.pack(fill="x", pady=(8, 0))
        self.area_activity["value"] = 0

    def _set_area_progress(self, elapsed: int, total: int, roles: int, positions: int, packets: int) -> None:
        total = max(0, int(total))
        elapsed = max(0, min(int(elapsed), total)) if total else 0
        remaining = max(0, total - elapsed)
        pct = int(100 * elapsed / total) if total else 100
        status = (
            f"Finding stations — {remaining}s remaining · "
            f"{roles} infrastructure calls · {positions} position packets"
        )
        self.area_activity["value"] = pct
        self.area_status.set(status)
        try:
            self.app.progress["value"] = pct
            self.app.percent_var.set(f"{pct}%")
            self.app.status_var.set(status)
        except Exception:
            pass

    def _restore_main_cancel_button(self) -> None:
        try:
            self.app.cancel_btn.configure(
                text="Cancel Run",
                command=self.app.cancel_job,
                state="normal" if getattr(self.app, "_job_running", False) else "disabled",
            )
        except Exception:
            pass

    def cancel_area_acquisition(self) -> None:
        if not self._area_busy:
            return
        self._area_cancel_event.set()
        try:
            self.app.cancel_btn.configure(state="disabled")
            self.app.status_var.set("Cancelling Step 1…")
        except Exception:
            pass
        self.area_status.set("Cancelling station acquisition…")

    def find_area_stations(self) -> None:
        if self._area_busy:
            return
        try:
            region, prop, types = self._area_values()
            self.app.apply_network_settings()
            refresh_seconds = int(self.app.refresh_var.get())
        except Exception as exc:
            messagebox.showerror("Cannot acquire stations", str(exc), parent=self)
            return

        self._area_cancel_event.clear()
        self._area_busy = True
        self.find_area_btn.configure(state="disabled")
        self.run_area_btn.configure(state="disabled")
        self.area_review_btn.configure(state="disabled")
        self._set_area_progress(0, refresh_seconds, 0, 0, 0)
        try:
            self.app.cancel_btn.configure(
                text="Cancel Step 1",
                command=self.cancel_area_acquisition,
                state="normal",
            )
        except Exception:
            pass

        def report(elapsed, total, roles, positions, packets):
            self.after(
                0,
                lambda: self._set_area_progress(elapsed, total, roles, positions, packets),
            )

        def work():
            try:
                cache_path = station_sources.acquire_station_cache(
                    seed_path=Path(self.app.source_var.get()),
                    data_root=portable_data_root(),
                    center_lat=region.center_lat,
                    center_lon=region.center_lon,
                    acquisition_radius_km=region.radius_km + prop,
                    refresh=True,
                    refresh_seconds=refresh_seconds,
                    callsign=self.app.callsign_var.get().strip().upper(),
                    aprs_fi_api_key=self.app.aprsfi_var.get().strip(),
                    stop_event=self._area_cancel_event,
                    progress=report,
                )
                if self._area_cancel_event.is_set():
                    self.after(0, self._area_acquire_cancelled)
                    return

                self.after(
                    0,
                    lambda: self._set_area_post_sample_status(
                        "Live sample complete — checking station locations…"
                    ),
                )
                records = viewshed_core.assess_station_locations(
                    viewshed_core.load_station_records(cache_path)
                )
                selected = viewshed_core.filter_stations(records, region, types, prop)

                if self._area_cancel_event.is_set():
                    self.after(0, self._area_acquire_cancelled)
                    return

                if selected:
                    self.after(
                        0,
                        lambda: self._set_area_post_sample_status(
                            f"Checking {len(selected)} station locations against OpenStreetMap…"
                        ),
                    )
                    try:
                        matches = viewshed_core.cross_reference_osm(selected, match_radius_km=3.0)
                        attached = []
                        for original in selected:
                            record = dict(original)
                            call = str(record.get("callsign") or "").strip().upper()
                            if call in matches:
                                record["_osm_crossref"] = dict(matches[call])
                            attached.append(record)
                        selected = viewshed_core.assess_station_locations(attached)
                    except Exception:
                        pass

                if self._area_cancel_event.is_set():
                    self.after(0, self._area_acquire_cancelled)
                    return
                self.after(0, lambda: self._area_acquired(selected))
            except Exception as exc:
                self.after(0, lambda e=exc: self._area_acquire_failed(e))

        threading.Thread(target=work, daemon=True).start()

    def _set_area_post_sample_status(self, status: str) -> None:
        self.area_activity["value"] = 100
        self.area_status.set(status)
        try:
            self.app.progress["value"] = 100
            self.app.percent_var.set("100%")
            self.app.status_var.set(status)
        except Exception:
            pass

    def _area_acquire_cancelled(self) -> None:
        self._area_busy = False
        self.find_area_btn.configure(state="normal")
        self.area_activity["value"] = 0
        self.area_status.set("Step 1 cancelled. Existing station results were not changed.")
        try:
            self.app.progress["value"] = 0
            self.app.percent_var.set("0%")
            self.app.status_var.set("Step 1 cancelled")
        except Exception:
            pass
        self._restore_main_cancel_button()

    def _area_acquired(self, records: list[dict]) -> None:
        self.area_activity["value"] = 100
        super()._area_acquired(records)
        try:
            self.app.progress["value"] = 100
            self.app.percent_var.set("100%")
            self.app.status_var.set(f"Step 1 complete — {len(records)} stations ready")
        except Exception:
            pass
        self._restore_main_cancel_button()

    def _area_acquire_failed(self, exc: Exception) -> None:
        self.area_activity["value"] = 0
        super()._area_acquire_failed(exc)
        self._restore_main_cancel_button()

    def _polish_progress_shell(self) -> None:
        """Detach the detailed run log from the main window."""
        try:
            style = ttk.Style(self.app)
            style.configure("SignalPeak.Horizontal.TProgressbar", thickness=12)
            self.app.progress.configure(style="SignalPeak.Horizontal.TProgressbar")

            details = self.app.log.master
            details.pack_forget()

            status = self.app.cancel_btn.master
            self.open_log_btn = ttk.Button(status, text="Open Log", command=self.open_log_window)
            self.open_log_btn.pack(side="right", padx=(8, 0))

            original_append = self.app._append_log

            def append_log(text: str) -> None:
                original_append(text)
                viewer = self._log_text
                if viewer is not None and viewer.winfo_exists():
                    viewer.configure(state="normal")
                    viewer.insert("end", text)
                    viewer.see("end")
                    viewer.configure(state="disabled")

            self.app._append_log = append_log
        except Exception:
            pass

    def open_log_window(self) -> None:
        if self._log_window is not None and self._log_window.winfo_exists():
            self._log_window.deiconify()
            self._log_window.lift()
            self._log_window.focus_force()
            return

        window = tk.Toplevel(self.app)
        self._log_window = window
        window.title(f"{PRODUCT_NAME} — Run Log")
        window.geometry("900x520")
        window.minsize(640, 320)
        self._apply_window_icon(window)

        outer = ttk.Frame(window, padding=10)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Run progress & log", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Detailed diagnostics for station acquisition and propagation runs.",
        ).pack(anchor="w", pady=(2, 8))

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        text = tk.Text(
            body,
            wrap="word",
            state="normal",
            font=("Consolas", 9),
            padx=8,
            pady=6,
            relief="flat",
            borderwidth=0,
        )
        scroll = ttk.Scrollbar(body, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        try:
            existing = self.app.log.get("1.0", "end-1c")
        except Exception:
            existing = ""
        if existing:
            text.insert("end", existing)
            text.see("end")
        text.configure(state="disabled")
        self._log_text = text

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Close", command=window.destroy).pack(side="right")

        def close() -> None:
            self._log_text = None
            self._log_window = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close)

    def _build_help_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Help / About")

        ttk.Label(tab, text=f"{PRODUCT_NAME} {APP_VERSION}", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "Portable map-first APRS/VHF terrain propagation analysis for the continental United States. "
                "Signal Peak is free and open-source software licensed under GNU GPL v2 only. "
                "The documentation below is bundled with the application for offline access."
            ),
            wraplength=900,
        ).pack(anchor="w", pady=(4, 12))

        docs = ttk.LabelFrame(tab, text="Documentation", padding=10)
        docs.pack(fill="x")
        for index, (label, relative_path) in enumerate(self.DOCS):
            row = index // 2
            col = index % 2
            ttk.Button(
                docs,
                text=label,
                command=lambda p=relative_path: self._open_bundled_doc(p),
            ).grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 6, 6 if col == 0 else 0), pady=3)
        docs.columnconfigure(0, weight=1)
        docs.columnconfigure(1, weight=1)

        data_box = ttk.LabelFrame(tab, text="Data and diagnostics", padding=10)
        data_box.pack(fill="x", pady=(12, 0))
        ttk.Label(
            data_box,
            text=(
                f"Application data: {portable_data_root()}\n"
                "Advanced settings: ViewshedData/advanced_settings.json\n"
                "Station corrections: ViewshedData/station_location_overrides.json\n"
                "Jobs: ViewshedData/jobs/<timestamp>/\n"
                "aprs.fi API keys are session-only and are not retained in settings.json."
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w")
        row = ttk.Frame(data_box)
        row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="Open Application Data Folder", command=self._open_data_folder).pack(side="left")
        ttk.Button(row, text="Open Log", command=self.open_log_window).pack(side="left", padx=(8, 0))

        caution = ttk.LabelFrame(tab, text="Key modeling caution", padding=10)
        caution.pack(fill="x", pady=(12, 0))
        ttk.Label(
            caution,
            text=(
                "Area and Station results use explicit reference assumptions because APRS normally does not provide "
                "reliable station ERP, antenna pattern, feedline loss, or installation-height data. The reference "
                "profile uses a 138 dB operational path-loss cap plus reduced lateral radial fill to avoid overstating "
                "marginal canyon coverage. Custom mode uses a 20 dB operational reserve. Coverage is a prediction, "
                "not a communications guarantee."
            ),
            wraplength=900,
        ).pack(anchor="w")

    def _open_bundled_doc(self, relative_path: str) -> None:
        path = resource_path(relative_path)
        if not path.exists():
            messagebox.showerror(
                "Documentation not found",
                f"The bundled document could not be found:\n{path}",
                parent=self,
            )
            return
        try:
            self.app._open_path(Path(path))
        except Exception as exc:
            messagebox.showerror("Could not open document", str(exc), parent=self)

    def _open_data_folder(self) -> None:
        try:
            self.app._open_path(portable_data_root())
        except Exception as exc:
            messagebox.showerror("Could not open application data", str(exc), parent=self)
