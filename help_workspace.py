from __future__ import annotations

import json
from pathlib import Path
from tkinter import messagebox, ttk

import station_sources
import viewshed_core
from repeat_run_workspace import ViewshedWorkspace as _ViewshedWorkspace
from viewshed_core import portable_data_root, resource_path


PRODUCT_NAME = "Signal Peak"
PRODUCT_VERSION = "1.0.1"
PRODUCT_HOME = "https://github.com/HammerheadFistpunch/Viewshed"

# Apply release branding before viewshed_app imports APP_VERSION from viewshed_core.
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
        super().__init__(master, app)
        self._brand_application()
        self._install_secure_settings_storage()
        self._clarify_range_labels()
        self._install_area_activity_indicator()
        self._default_seed_field_empty()
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
        """Treat the seed as an opt-in fallback instead of exposing bundled data as a user seed."""
        try:
            self.app.source_var.set("")
        except Exception:
            pass

    def _install_area_activity_indicator(self) -> None:
        """Keep Step 1 visibly active during APRS/cache/OSM station acquisition."""
        parent = self.find_area_btn.master
        self.area_activity = ttk.Progressbar(parent, mode="indeterminate", maximum=100)
        self.area_activity.pack(fill="x", pady=(8, 0))
        self.area_activity.stop()

    def _set_area_activity(self, active: bool) -> None:
        if active:
            self.area_activity.start(12)
            self.area_status.set(
                "Finding stations — live APRS sampling, cache/seed merge, and location checks are running…"
            )
        else:
            self.area_activity.stop()
            self.area_activity["value"] = 0

    def find_area_stations(self) -> None:
        was_busy = self._area_busy
        super().find_area_stations()
        if not was_busy and self._area_busy:
            self._set_area_activity(True)

    def _area_acquired(self, records: list[dict]) -> None:
        self._set_area_activity(False)
        super()._area_acquired(records)

    def _area_acquire_failed(self, exc: Exception) -> None:
        self._set_area_activity(False)
        super()._area_acquire_failed(exc)

    def _polish_progress_shell(self) -> None:
        """Give the run status and log enough space to remain useful at the default window size."""
        try:
            style = ttk.Style(self.app)
            style.configure("SignalPeak.Horizontal.TProgressbar", thickness=12)
            self.app.progress.configure(style="SignalPeak.Horizontal.TProgressbar")
            self.app.log.configure(
                height=9,
                font=("Consolas", 9),
                padx=7,
                pady=5,
                relief="flat",
                borderwidth=0,
            )
            details = self.app.log.master
            details.configure(text="Run progress & log", padding=8)
            details.pack_configure(fill="x", pady=(6, 0))
        except Exception:
            pass

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
        ttk.Button(data_box, text="Open Application Data Folder", command=self._open_data_folder).pack(anchor="w", pady=(8, 0))

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
