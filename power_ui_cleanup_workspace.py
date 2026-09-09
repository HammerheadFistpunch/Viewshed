from __future__ import annotations

import tkinter as tk

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

    def _build_custom(self) -> None:
        # Use the established Custom/future-station UI: TX power is entered in W.
        # Keep compatibility aliases expected by the newer custom runner so it
        # can apply the same Output-tab settings as Area/Station without adding
        # the dBm selector back to the Custom UI.
        _TunedWorkspace._build_custom(self)
        self.custom_power_value = self.custom_power_w
        self.custom_power_dbm_mode = tk.BooleanVar(value=False)

    def run_custom(self) -> None:
        # Follow the normal workspace inheritance chain. operator_tools_workspace
        # handles metric/imperial conversion, then feature_ui_workspace applies
        # the shared Output-tab banding, display floor, max margin, and opacity.
        return super().run_custom()
