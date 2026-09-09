from __future__ import annotations

from station_data_workspace import KM_PER_MI, M_PER_FT, ViewshedWorkspace as _FeatureWorkspace
from workspace_tuning import ViewshedWorkspace as _TunedWorkspace


class ViewshedWorkspace(_FeatureWorkspace):
    """Keep the W/dBm selector in Advanced; Custom remains watts-only."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        # Watts are the more familiar operator-facing unit. If the user has not
        # explicitly saved a preference yet, make Advanced start in watts while
        # preserving dBm internally for the propagation engine.
        if "advanced_power_watts" not in self._ui_prefs:
            self.advanced_power_watts.set(True)
            self._advanced_power_unit_changed()
        self._clarify_reverse_haat_ui()

    def _build_custom(self) -> None:
        # Use the established Custom/future-station UI: TX power is entered in W.
        # The unit selector belongs in Advanced propagation settings instead.
        _TunedWorkspace._build_custom(self)

    def _clarify_reverse_haat_ui(self) -> None:
        """Present reverse HAAT as an estimator of antenna height above the site."""
        replacements = {
            "Solve the antenna height AGL required to reach a target FCC-style HAAT using 8 radials and terrain from 2–10 miles.": (
                "Enter a known/published HAAT to estimate the antenna height above the station site (AGL) "
                "using 8 radials and terrain from 2–10 miles."
            ),
            "Target HAAT": "Known / published HAAT",
        }

        def visit(widget) -> None:
            try:
                text = widget.cget("text")
                if text in replacements:
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
        try:
            self.haat_btn.configure(text="Estimate antenna height above site")
            self.haat_unit_label.configure(text="input follows Metric / Imperial selection")
            self.haat_status.set(
                "Enter the station's known/published HAAT. The result will be antenna height above site (AGL)."
            )
        except Exception:
            pass

    def _haat_station_selected(self, _event=None) -> None:
        call = self.haat_station_call.get().strip().upper()
        rec = getattr(self, "_station_records", {}).get(call)
        if not rec:
            return
        try:
            self.haat_lat.set(f"{float(rec['lat']):.6f}")
            self.haat_lon.set(f"{float(rec['lon']):.6f}")
        except (KeyError, TypeError, ValueError):
            self.haat_station_status.set(f"{call} does not have usable coordinates.")
            return

        confidence = rec.get("_location_confidence")
        if isinstance(confidence, dict):
            source = str(confidence.get("label") or confidence.get("status") or "catalog")
        elif confidence:
            source = str(confidence)
        else:
            source = str(rec.get("_source") or "catalog")
        self.haat_station_status.set(
            f"{call} selected — coordinates loaded ({source}). You can edit them before calculating."
        )

    def _finish_reverse_haat(self, result: dict) -> None:
        """Make antenna AGL the primary reverse-HAAT result and show both units."""
        self.haat_btn.configure(state="normal")
        agl_m = float(result["required_antenna_agl_m"])
        agl_ft = agl_m / M_PER_FT
        site_m = float(result["site_elevation_m"])
        terrain_m = float(result["average_terrain_m"])
        published_m = float(result["target_haat_m"])

        detail = (
            f"Published HAAT: {published_m:.1f} m / {published_m / M_PER_FT:.1f} ft · "
            f"site ground: {site_m:.1f} m AMSL · "
            f"average 2–10 mi terrain: {terrain_m:.1f} m AMSL"
        )
        if agl_m < 0:
            detail += " · WARNING: negative AGL suggests the HAAT value, units, or site coordinates are inconsistent."

        self.haat_status.set(
            f"Estimated antenna height above site (AGL): {agl_ft:.1f} ft / {agl_m:.1f} m\n{detail}"
        )

    def run_custom(self) -> None:
        if getattr(self, "_imperial", False):
            with self._metric_values(((self.custom_radius, KM_PER_MI), (self.custom_height, M_PER_FT))):
                return _TunedWorkspace.run_custom(self)
        return _TunedWorkspace.run_custom(self)
