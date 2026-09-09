from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, ttk

from operator_tools_workspace import KM_PER_MI, M_PER_FT, ViewshedWorkspace as _ViewshedWorkspace
from station_rf_registry import apply_registry, load_registry, registry_path, save_registry
from viewshed_core import portable_data_root


_EDITABLE_COLUMNS = {"height", "power", "gain", "freq", "pathloss"}
_FIELD_BY_COLUMN = {
    "height": "antenna_height_m",
    "power": "tx_power_w",
    "gain": "tx_antenna_gain_dbd",
    "freq": "freq_mhz",
    "pathloss": "max_path_loss_db",
}


class ViewshedWorkspace(_ViewshedWorkspace):
    """Spreadsheet-style editor for persistent per-station RF overrides."""

    def __init__(self, master, app) -> None:
        self._rf_registry = load_registry(portable_data_root())
        self._rf_pending: dict[tuple[str, str], str] = {}
        self._rf_sort_reverse: dict[str, bool] = {}
        super().__init__(master, app)
        self._apply_registry_to_loaded_catalogs()
        self._build_station_data_tab()
        self._refresh_station_grid()
        self._sync_haat_station_catalog()

    def _apply_registry_to_loaded_catalogs(self) -> None:
        if hasattr(self, "_station_records"):
            current = list(getattr(self, "_station_records", {}).values())
            applied = apply_registry(current, self._rf_registry)
            self._station_records = {
                str(r.get("callsign") or "").strip().upper(): r
                for r in applied
                if r.get("callsign")
            }
        if hasattr(self, "_area_records") and isinstance(self._area_records, list):
            self._area_records = apply_registry(self._area_records, self._rf_registry)

    def reload_station_catalog(self) -> None:
        super().reload_station_catalog()
        self._apply_registry_to_loaded_catalogs()
        self._sync_haat_station_catalog()
        if hasattr(self, "station_data_tree"):
            self._refresh_station_grid()

    def _set_station_catalog(self, records: list[dict], source_label: str) -> None:
        super()._set_station_catalog(apply_registry(records, self._rf_registry), source_label)
        if hasattr(self, "station_data_tree"):
            self._refresh_station_grid()

    def _area_acquired(self, records: list[dict]) -> None:
        super()._area_acquired(apply_registry(records, self._rf_registry))
        self._apply_registry_to_loaded_catalogs()
        self._sync_haat_station_catalog()
        if hasattr(self, "station_data_tree"):
            self._refresh_station_grid()

    def _apply_unit_mode(self) -> None:
        super()._apply_unit_mode()
        if hasattr(self, "station_data_tree"):
            self._refresh_station_grid()

    def _advanced_effective_settings(self) -> dict:
        try:
            return self._advanced_settings(persist=False)
        except Exception:
            return {
                "antenna_height_digi_m": 20.0,
                "antenna_height_igate_m": 3.0,
                "tx_power_dbm": 47.0,
                "tx_antenna_gain_dbd": 0.0,
                "freq_mhz": 144.390,
                "max_path_loss_db": 138.0,
            }

    @staticmethod
    def _power_w(record: dict, defaults: dict) -> float:
        if record.get("tx_power_w") not in (None, ""):
            return float(record["tx_power_w"])
        if record.get("tx_power_dbm") not in (None, ""):
            return 10.0 ** ((float(record["tx_power_dbm"]) - 30.0) / 10.0)
        return 10.0 ** ((float(defaults.get("tx_power_dbm", 47.0)) - 30.0) / 10.0)

    def _height_display(self, record: dict, defaults: dict) -> float:
        stype = str(record.get("type") or "digi").lower()
        value = record.get("antenna_height_m", record.get("antenna_height_agl_m"))
        if value in (None, ""):
            key = "antenna_height_igate_m" if stype == "igate" else "antenna_height_digi_m"
            value = defaults.get(key, 3.0 if stype == "igate" else 20.0)
        meters = float(value)
        return meters / M_PER_FT if self._imperial else meters

    @staticmethod
    def _effective(record: dict, key: str, defaults: dict, fallback: float) -> float:
        value = record.get(key)
        if value in (None, ""):
            value = defaults.get(key, fallback)
        return float(value)

    def _override_summary(self, record: dict) -> str:
        fields = list(record.get("_user_rf_override_fields", []) or [])
        if not fields:
            source_fields = [
                field for field in ("antenna_height_m", "antenna_height_agl_m", "tx_power_w", "tx_power_dbm", "tx_antenna_gain_dbd", "tx_antenna_gain_dbi", "freq_mhz", "max_path_loss_db")
                if record.get(field) not in (None, "")
            ]
            return "Station JSON" if source_fields else "Advanced defaults"
        labels = {
            "antenna_height_m": "height",
            "tx_power_w": "power",
            "tx_antenna_gain_dbd": "gain",
            "freq_mhz": "freq",
            "max_path_loss_db": "path loss",
        }
        return "User: " + ", ".join(labels.get(f, f) for f in fields)

    def _build_station_data_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Station Data")

        ttk.Label(tab, text="Station RF data", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(
            tab,
            text=(
                "This table shows the effective RF values each station will use. Double-click height, power, gain, frequency, or path-loss cells to edit them. "
                "Edits are saved as callsign-based user overrides and survive APRS refreshes. Click any column heading to sort; click it again to reverse the sort."
            ),
            wraplength=980,
        ).pack(anchor="w", pady=(3, 8))

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 6))
        self.station_data_filter = tk.StringVar(value="All")
        ttk.Label(toolbar, text="Show").pack(side="left")
        filter_combo = ttk.Combobox(
            toolbar,
            textvariable=self.station_data_filter,
            values=("All", "Digipeaters", "iGates"),
            state="readonly",
            width=14,
        )
        filter_combo.pack(side="left", padx=(6, 12))
        filter_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_station_grid())
        ttk.Button(toolbar, text="Refresh", command=self._refresh_station_grid).pack(side="left")
        ttk.Button(toolbar, text="Save edits", command=self._save_station_grid_edits).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Clear selected overrides", command=self._clear_selected_station_overrides).pack(side="left", padx=(6, 0))
        ttk.Label(toolbar, text=f"Stored in: {registry_path(portable_data_root())}").pack(side="right")

        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True)
        columns = ("callsign", "type", "lat", "lon", "height", "power", "gain", "freq", "pathloss", "source")
        self.station_data_tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        headings = {
            "callsign": "Callsign",
            "type": "Type",
            "lat": "Latitude",
            "lon": "Longitude",
            "height": "Height AGL (ft)" if self._imperial else "Height AGL (m)",
            "power": "TX Power (W)",
            "gain": "TX Gain (dBd)",
            "freq": "Frequency (MHz)",
            "pathloss": "Path Loss Cap (dB)",
            "source": "RF Source",
        }
        widths = {"callsign": 100, "type": 80, "lat": 105, "lon": 105, "height": 105, "power": 95, "gain": 95, "freq": 110, "pathloss": 120, "source": 190}
        for col in columns:
            self.station_data_tree.heading(col, text=headings[col], command=lambda c=col: self._sort_station_grid(c))
            self.station_data_tree.column(col, width=widths[col], minwidth=65, anchor="center" if col != "source" else "w")

        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.station_data_tree.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=self.station_data_tree.xview)
        self.station_data_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.station_data_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.station_data_tree.bind("<Double-1>", self._begin_station_cell_edit)

        self.station_data_status = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.station_data_status, wraplength=980).pack(anchor="w", pady=(7, 0))

    def _refresh_station_grid(self) -> None:
        tree = getattr(self, "station_data_tree", None)
        if tree is None:
            return
        tree.heading("height", text="Height AGL (ft)" if self._imperial else "Height AGL (m)", command=lambda: self._sort_station_grid("height"))
        for item in tree.get_children():
            tree.delete(item)
        defaults = self._advanced_effective_settings()
        selected_filter = self.station_data_filter.get() if hasattr(self, "station_data_filter") else "All"
        count = 0
        for call, record in sorted(getattr(self, "_station_records", {}).items()):
            stype = str(record.get("type") or "").lower()
            if selected_filter == "Digipeaters" and stype != "digi":
                continue
            if selected_filter == "iGates" and stype != "igate":
                continue
            try:
                lat = f"{float(record.get('lat')):.6f}"
                lon = f"{float(record.get('lon')):.6f}"
            except Exception:
                lat = str(record.get("lat") or "")
                lon = str(record.get("lon") or "")
            height = self._height_display(record, defaults)
            power = self._power_w(record, defaults)
            gain = self._effective(record, "tx_antenna_gain_dbd", defaults, 0.0)
            freq = self._effective(record, "freq_mhz", defaults, 144.390)
            pathloss = self._effective(record, "max_path_loss_db", defaults, 138.0)
            values = (
                call,
                stype,
                lat,
                lon,
                f"{height:.6g}",
                f"{power:.6g}",
                f"{gain:.6g}",
                f"{freq:.6g}",
                f"{pathloss:.6g}",
                self._override_summary(record),
            )
            tree.insert("", "end", iid=call, values=values)
            count += 1
        self.station_data_status.set(
            f"Showing {count} station(s). Double-click editable RF cells. Clearing a cell and saving removes that field's user override and returns it to its source/global fallback."
        )

    def _sort_station_grid(self, column: str) -> None:
        tree = self.station_data_tree
        reverse = not self._rf_sort_reverse.get(column, False)
        self._rf_sort_reverse[column] = reverse
        numeric = column in {"lat", "lon", "height", "power", "gain", "freq", "pathloss"}

        def key(item):
            value = tree.set(item, column)
            if numeric:
                try:
                    return (0, float(value))
                except Exception:
                    return (1, math.inf)
            return str(value).lower()

        items = list(tree.get_children(""))
        items.sort(key=key, reverse=reverse)
        for index, item in enumerate(items):
            tree.move(item, "", index)

    def _begin_station_cell_edit(self, event) -> None:
        tree = self.station_data_tree
        if tree.identify("region", event.x, event.y) != "cell":
            return
        row_id = tree.identify_row(event.y)
        column_id = tree.identify_column(event.x)
        if not row_id or not column_id:
            return
        index = int(column_id[1:]) - 1
        columns = tree["columns"]
        if not (0 <= index < len(columns)):
            return
        column = columns[index]
        if column not in _EDITABLE_COLUMNS:
            return
        bbox = tree.bbox(row_id, column_id)
        if not bbox:
            return
        x, y, width, height = bbox
        old_value = tree.set(row_id, column)
        editor = ttk.Entry(tree)
        editor.insert(0, old_value)
        editor.select_range(0, "end")
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_force()
        committed = {"done": False}

        def finish(_event=None):
            if committed["done"]:
                return
            committed["done"] = True
            value = editor.get().strip()
            tree.set(row_id, column, value)
            self._rf_pending[(row_id, column)] = value
            editor.destroy()
            self.station_data_status.set(f"Unsaved edit: {row_id} {column}. Click Save edits to persist changes.")

        editor.bind("<Return>", finish)
        editor.bind("<FocusOut>", finish)
        editor.bind("<Escape>", lambda _e: editor.destroy())

    def _validated_override_value(self, column: str, text: str) -> tuple[str, float] | None:
        if not text:
            return None
        try:
            value = float(text)
        except ValueError as exc:
            raise ValueError(f"{column} must be numeric or blank.") from exc
        field = _FIELD_BY_COLUMN[column]
        if column == "height":
            if value <= 0:
                raise ValueError("Antenna height must be positive.")
            if self._imperial:
                value *= M_PER_FT
        elif column == "power":
            if value <= 0:
                raise ValueError("TX power must be positive.")
        elif column == "gain":
            if not -20 <= value <= 30:
                raise ValueError("TX gain must be between -20 and 30 dBd.")
        elif column == "freq":
            if not 20 <= value <= 1000:
                raise ValueError("Frequency must be between 20 and 1000 MHz.")
        elif column == "pathloss":
            if not 80 <= value <= 200:
                raise ValueError("Path-loss cap must be between 80 and 200 dB.")
        return field, value

    def _save_station_grid_edits(self) -> None:
        if not self._rf_pending:
            self.station_data_status.set("No station-data edits are waiting to be saved.")
            return
        updated = {call: dict(values) for call, values in self._rf_registry.items()}
        try:
            for (call, column), text in self._rf_pending.items():
                entry = updated.setdefault(call, {})
                parsed = self._validated_override_value(column, text)
                field = _FIELD_BY_COLUMN[column]
                if parsed is None:
                    entry.pop(field, None)
                else:
                    _, value = parsed
                    # Store power as watts and height in meters; the engine remains
                    # metric/dBm internally and converts watts at the worker boundary.
                    entry[field] = value
                if not entry:
                    updated.pop(call, None)
        except Exception as exc:
            messagebox.showerror("Station RF data", str(exc), parent=self)
            return

        self._rf_registry = updated
        path = save_registry(portable_data_root(), self._rf_registry)
        self._rf_pending.clear()
        self._apply_registry_to_loaded_catalogs()
        self._sync_haat_station_catalog()
        self._refresh_station_grid()
        self.station_data_status.set(f"Station RF overrides saved to {path}. New Area and Station runs will use them immediately.")

    def _clear_selected_station_overrides(self) -> None:
        selected = list(self.station_data_tree.selection())
        if not selected:
            messagebox.showinfo("Station RF data", "Select one or more stations first.", parent=self)
            return
        if not messagebox.askyesno(
            "Clear station RF overrides",
            f"Clear all user RF overrides for {len(selected)} selected station(s)?\n\nThose stations will return to station-JSON values where present, otherwise Advanced defaults.",
            parent=self,
        ):
            return
        for call in selected:
            self._rf_registry.pop(call, None)
            for key in list(self._rf_pending):
                if key[0] == call:
                    self._rf_pending.pop(key, None)
        path = save_registry(portable_data_root(), self._rf_registry)
        self._apply_registry_to_loaded_catalogs()
        self._sync_haat_station_catalog()
        self._refresh_station_grid()
        self.station_data_status.set(f"Cleared user RF overrides for {len(selected)} station(s). Registry updated: {path}")
