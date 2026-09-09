from __future__ import annotations

from operator_tools_workspace import ViewshedWorkspace as _FeatureWorkspace
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
        # The unit selector belongs in Advanced propagation settings instead.
        _TunedWorkspace._build_custom(self)

    def run_custom(self) -> None:
        _TunedWorkspace.run_custom(self)
