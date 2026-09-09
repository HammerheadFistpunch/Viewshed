from __future__ import annotations

import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from power_ui_cleanup_workspace import ViewshedWorkspace as _ViewshedWorkspace
from resource_planner import format_gb, format_plan, get_system_resources, plan_resources
from tooltips import add_tooltip
from viewshed_core import portable_data_root


_RESOURCE_PREFS = "resource_settings.json"
_DETAIL_VALUES = ("Auto", "Fast", "Standard", "High", "Max")


def _resource_prefs_path() -> Path:
    return portable_data_root() / _RESOURCE_PREFS


def _load_resource_prefs() -> dict:
    path = _resource_prefs_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_resource_prefs(mode: str, memory_limit_gb: float) -> None:
    path = _resource_prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"terrain_detail_mode": mode, "memory_limit_gb": memory_limit_gb}, indent=2),
        encoding="utf-8",
    )


class ViewshedWorkspace(_ViewshedWorkspace):
    """V2 terrain-detail presets and memory-aware propagation planning."""

    def __init__(self, master, app) -> None:
        self._resource_prefs = _load_resource_prefs()
        super().__init__(master, app)
        self._install_resource_controls()
        self._install_resource_planning_guard()

    def _advanced_tab(self):
        for tab_id in self.notebook.tabs():
            try:
                if self.notebook.tab(tab_id, "text") == "Advanced":
                    return self.nametowidget(tab_id)
            except Exception:
                continue
        return None

    def _install_resource_controls(self) -> None:
        tab = self._advanced_tab()
        if tab is None:
            return

        box = ttk.LabelFrame(tab, text="Terrain detail / resource planning", padding=10)
        box.pack(fill="x", pady=(10, 0))
        box.columnconfigure(1, weight=1)

        saved_mode = str(self._resource_prefs.get("terrain_detail_mode", "Auto")).title()
        if saved_mode not in _DETAIL_VALUES:
            saved_mode = "Auto"
        self.terrain_detail_mode = tk.StringVar(value=saved_mode)
        self.memory_limit_gb = tk.StringVar(value=str(self._resource_prefs.get("memory_limit_gb", 0)))

        detail_label = ttk.Label(box, text="Terrain detail")
        detail_label.grid(row=0, column=0, sticky="w", pady=3)
        detail_combo = ttk.Combobox(
            box,
            textvariable=self.terrain_detail_mode,
            values=_DETAIL_VALUES,
            state="readonly",
            width=18,
        )
        detail_combo.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=3)
        detail_combo.bind("<<ComboboxSelected>>", self._resource_pref_changed)

        memory_label = ttk.Label(box, text="Memory limit (GB, 0=Auto)")
        memory_label.grid(row=1, column=0, sticky="w", pady=3)
        memory_entry = ttk.Entry(box, textvariable=self.memory_limit_gb, width=18)
        memory_entry.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=3)
        memory_entry.bind("<FocusOut>", self._resource_pref_changed)
        memory_entry.bind("<Return>", self._resource_pref_changed)

        ttk.Button(box, text="Refresh system resources", command=self._refresh_resource_status).grid(
            row=2, column=0, sticky="w", pady=(8, 0)
        )
        self.resource_system_status = tk.StringVar()
        ttk.Label(box, textvariable=self.resource_system_status, wraplength=760).grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0)
        )

        self.resource_warning = tk.StringVar()
        ttk.Label(box, textvariable=self.resource_warning, wraplength=850, font=("Segoe UI", 9, "bold")).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        self.resource_plan_summary = tk.StringVar(
            value="The exact terrain and worker plan is calculated from the real station set immediately before each run starts."
        )
        ttk.Label(box, textvariable=self.resource_plan_summary, wraplength=850).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        add_tooltip(
            detail_label,
            "Controls the terrain-detail target. Fast favors speed, Standard balances speed and detail, High preserves smaller terrain features, and Max preserves as much terrain detail as the computer can safely handle.",
        )
        add_tooltip(detail_combo, "The selected preset is converted into terrain resolution, memory use, and a safe number of parallel workers for each run.")
        add_tooltip(
            memory_label,
            "Optional ceiling for Signal Peak resource planning. Enter 0 to let Signal Peak use currently available memory automatically. The planner always keeps additional RAM in reserve for Windows and other programs.",
        )
        add_tooltip(memory_entry, "Enter the maximum RAM in GB that Signal Peak may plan around, or 0 for automatic memory management.")

        self._update_resource_warning()
        self._refresh_resource_status()

    def _parse_memory_limit(self) -> float:
        try:
            value = float(self.memory_limit_gb.get().strip() or "0")
        except ValueError as exc:
            raise ValueError("Memory limit must be a number in GB, or 0 for Automatic.") from exc
        if value < 0 or value > 1024:
            raise ValueError("Memory limit must be between 0 and 1024 GB.")
        return value

    def _resource_pref_changed(self, _event=None) -> None:
        try:
            memory_limit = self._parse_memory_limit()
        except ValueError:
            return
        mode = self.terrain_detail_mode.get().strip().title()
        _save_resource_prefs(mode, memory_limit)
        self._update_resource_warning()

    def _update_resource_warning(self) -> None:
        if not hasattr(self, "resource_warning"):
            return
        if self.terrain_detail_mode.get().strip().lower() == "max":
            self.resource_warning.set(
                "WARNING: Maximum detail prioritizes stability first and terrain resolution second. "
                "Signal Peak may reduce parallel processing to one station at a time. Large Max runs can be VERY slow."
            )
        else:
            self.resource_warning.set("")

    def _refresh_resource_status(self) -> None:
        resources = get_system_resources()
        cpu = f"{resources.logical_cpus} logical CPU(s)"
        if resources.physical_cpus:
            cpu += f" / {resources.physical_cpus} physical core(s)"
        if resources.cpu_percent is not None:
            cpu += f" / {resources.cpu_percent:.0f}% current load"
        self.resource_system_status.set(
            f"RAM: {format_gb(resources.available_ram_bytes)} available of {format_gb(resources.total_ram_bytes)}; CPU: {cpu}."
        )

    def _install_resource_planning_guard(self) -> None:
        if getattr(self.app, "_v2_resource_planner_installed", False):
            return
        original_start_job = self.app.start_job

        def resource_planned_start_job(job_file, label):
            try:
                mode = self.terrain_detail_mode.get().strip().lower()
                memory_limit = self._parse_memory_limit()
                _save_resource_prefs(self.terrain_detail_mode.get().strip().title(), memory_limit)

                job_path = Path(job_file)
                raw = json.loads(job_path.read_text(encoding="utf-8"))
                stations_path = Path(raw["filtered_stations"])
                stations = json.loads(stations_path.read_text(encoding="utf-8"))
                if not isinstance(stations, list):
                    raise ValueError("Prepared station list is not valid.")
                radius_km = float(raw.get("propagation_radius_km", 180.0))

                plan = plan_resources(stations, radius_km, mode=mode, memory_limit_gb=memory_limit)
                radio = raw.get("radio_settings")
                if not isinstance(radio, dict):
                    radio = {}
                radio.update(plan.to_radio_settings())
                raw["radio_settings"] = radio
                job_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

                # viewshed_core currently calls prepare_analysis_dem(..., 8000).
                # The V2 analysis layer reads this inherited value and safely
                # substitutes the planner's per-run analysis dimension.
                os.environ["SIGNAL_PEAK_ANALYSIS_MAX_PX"] = str(plan.analysis_max_px)

                summary = format_plan(plan)
                self.resource_plan_summary.set(summary)
                self._refresh_resource_status()
                append_log = getattr(self.app, "_append_log", None)
                if callable(append_log):
                    append_log(f"\nResource plan: {summary}\n")
            except Exception as exc:
                messagebox.showerror("Cannot plan propagation resources", str(exc), parent=self)
                return

            return original_start_job(job_file, label)

        self.app.start_job = resource_planned_start_job
        self.app._v2_resource_planner_installed = True
