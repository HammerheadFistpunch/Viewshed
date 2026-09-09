from __future__ import annotations

import help_workspace
import station_sources
import viewshed_core
from station_data_workspace import KM_PER_MI, M_PER_FT, ViewshedWorkspace as _FeatureWorkspace
from workspace_tuning import ViewshedWorkspace as _TunedWorkspace


PRODUCT_VERSION = "1.2.0"

# Keep the product version consistent across the UI, worker logs, APRS user agent,
# Help/About, and the inherited workspace chain without changing propagation math.
help_workspace.PRODUCT_VERSION = PRODUCT_VERSION
help_workspace.APP_VERSION = PRODUCT_VERSION
viewshed_core.APP_VERSION = PRODUCT_VERSION
station_sources.USER_AGENT = f"SignalPeak/{PRODUCT_VERSION} (+{help_workspace.PRODUCT_HOME})"
help_workspace.ViewshedWorkspace.DOCS = [
    ("1.2.0 Release Notes", "docs/RELEASE_NOTES_1.2.0.md")
    if path == "docs/RELEASE_NOTES_1.1.0.md"
    else (label, path)
    for label, path in help_workspace.ViewshedWorkspace.DOCS
]


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

    def _build_custom(self) -> None:
        # Use the established Custom/future-station UI: TX power is entered in W.
        # The unit selector belongs in Advanced propagation settings instead.
        _TunedWorkspace._build_custom(self)

    def run_custom(self) -> None:
        if getattr(self, "_imperial", False):
            with self._metric_values(((self.custom_radius, KM_PER_MI), (self.custom_height, M_PER_FT))):
                return _TunedWorkspace.run_custom(self)
        return _TunedWorkspace.run_custom(self)
