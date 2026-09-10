from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from repeat_run_workspace import ViewshedWorkspace as _ViewshedWorkspace


class ViewshedWorkspace(_ViewshedWorkspace):
    """Stabilize Corrections rendering and expose persistent correction state."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app)

        self.correction_state = tk.StringVar(value="No station selected")
        ttk.Label(
            self.correct_combo.master,
            textvariable=self.correction_state,
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", anchor="w", pady=(6, 0))

        self.notebook.bind("<<NotebookTabChanged>>", self._correction_tab_changed, add="+")
        self.after_idle(self._correction_selected)

    def _refresh_correction_catalog(self, records: list[dict] | None = None) -> None:
        """Never leave a populated catalog hidden behind an empty review filter."""
        super()._refresh_correction_catalog(records)

        visible = list(self.correct_combo.cget("values") or ())
        has_catalog = bool(getattr(self, "_correction_records", {}))
        if visible or not has_catalog or getattr(self, "_correction_show_all", False):
            return

        self._correction_show_all = True
        self._update_filter_button()
        source = getattr(self, "_correction_catalog_source", None) or records
        super()._refresh_correction_catalog(source)
        if hasattr(self, "correct_status"):
            self.correct_status.set(
                f"No stations currently need location review — showing all "
                f"{len(self._correction_records)} stations."
            )

    @staticmethod
    def _correction_state_text(record: dict | None) -> str:
        if not record:
            return "No station selected"
        if record.get("_location_correction"):
            return "Saved correction — approved and used for propagation"
        if record.get("_location_review_candidate"):
            return "Needs review — saved candidate awaiting approval"
        meta = record.get("_location_confidence") or {}
        if str(meta.get("label") or "").upper() == "LOW":
            return "Needs review"
        return "Uncorrected"

    def _correction_selected(self) -> None:
        super()._correction_selected()
        state_var = getattr(self, "correction_state", None)
        if state_var is None:
            return
        rec = getattr(self, "_correction_records", {}).get(self.correct_call.get().strip().upper())
        state_var.set(self._correction_state_text(rec))

    def _correction_tab_changed(self, _event=None) -> None:
        try:
            if self.notebook.select() == str(self.corrections_tab):
                self.after_idle(self._correction_selected)
        except Exception:
            pass

    def review_area_corrections(self) -> None:
        super().review_area_corrections()
        self.after_idle(self._correction_selected)

    def open_correction(self, callsign: str) -> None:
        super().open_correction(callsign)
        self.after_idle(self._correction_selected)
