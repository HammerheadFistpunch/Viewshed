from __future__ import annotations

from pathlib import Path
from tkinter import messagebox, ttk

from advanced_workspace import ViewshedWorkspace as _ViewshedWorkspace
from viewshed_core import APP_VERSION, portable_data_root, resource_path


class ViewshedWorkspace(_ViewshedWorkspace):
    """Workspace with Advanced controls plus bundled offline Help/About access."""

    DOCS = [
        ("README / project overview", "README.md"),
        ("Quick Start", "docs/QUICK_START.md"),
        ("User Guide", "docs/USER_GUIDE.md"),
        ("Propagation Model", "docs/PROPAGATION_MODEL.md"),
        ("Station Data", "docs/STATION_DATA.md"),
        ("Location Corrections", "docs/LOCATION_CORRECTIONS.md"),
        ("Outputs", "docs/OUTPUTS.md"),
        ("Troubleshooting", "docs/TROUBLESHOOTING.md"),
        ("Dependencies / Licenses", "docs/LICENSES_AND_DEPENDENCIES.md"),
        ("Special Considerations", "docs/SPECIAL_CONSIDERATIONS.md"),
        ("Roadmap", "docs/ROADMAP.md"),
    ]

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._clarify_range_labels()
        self._build_help_tab()

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

    def _build_help_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Help / About")

        ttk.Label(tab, text=f"Viewshed {APP_VERSION}", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "Portable map-first APRS/VHF terrain propagation analysis. "
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
                f"ViewshedData: {portable_data_root()}\n"
                "Advanced settings: ViewshedData/advanced_settings.json\n"
                "Station corrections: ViewshedData/station_location_overrides.json\n"
                "Jobs: ViewshedData/jobs/<timestamp>/"
            ),
            wraplength=900,
            justify="left",
        ).pack(anchor="w")
        ttk.Button(data_box, text="Open ViewshedData Folder", command=self._open_data_folder).pack(anchor="w", pady=(8, 0))

        caution = ttk.LabelFrame(tab, text="Key modeling caution", padding=10)
        caution.pack(fill="x", pady=(12, 0))
        ttk.Label(
            caution,
            text=(
                "Area and Station results use explicit reference assumptions because APRS normally does not provide "
                "reliable station ERP, antenna pattern, feedline loss, or installation-height data. The default "
                "operational path-loss cap is 148 dB and can be changed in Advanced. Coverage is a prediction, "
                "not a communications guarantee. A clean circular edge can be the configured maximum calculation "
                "range rather than a physical RF boundary."
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
            messagebox.showerror("Could not open ViewshedData", str(exc), parent=self)
