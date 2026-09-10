from __future__ import annotations

from resource_ui_workspace import ViewshedWorkspace as _ViewshedWorkspace
from viewshed_core import haversine_km


class ViewshedWorkspace(_ViewshedWorkspace):
    """Keep Area propagation scoped to station centers inside the chosen Area radius."""

    def _area_acquired(self, records: list[dict]) -> None:
        try:
            region, _, types = self._area_values()
            scoped: list[dict] = []
            for record in records:
                if record.get("type") not in types:
                    continue
                try:
                    lat = float(record["lat"])
                    lon = float(record["lon"])
                except (KeyError, TypeError, ValueError):
                    continue
                if haversine_km(region.center_lat, region.center_lon, lat, lon) <= region.radius_km:
                    scoped.append(record)
        except Exception:
            # Preserve the previous acquisition behavior if the Area controls
            # become invalid between the background search and UI callback.
            scoped = records

        super()._area_acquired(scoped)

        try:
            excluded = max(0, len(records) - len(scoped))
            if excluded:
                self.area_status.set(
                    f"{len(scoped)} stations inside the selected Area radius are ready; "
                    f"{excluded} nearby acquisition candidates were excluded from propagation. "
                    "Inspect/correct, then run."
                )
        except Exception:
            pass
