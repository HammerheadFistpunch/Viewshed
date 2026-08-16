from __future__ import annotations

from tkinter import messagebox, ttk

from map_workspace import ViewshedWorkspace as _ViewshedWorkspace


class ViewshedWorkspace(_ViewshedWorkspace):
    """UI fixes layered over the map workspace while the UI is evolving."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._install_correction_map_controls()

    def _install_correction_map_controls(self) -> None:
        controls = ttk.Frame(self.corrections_tab, padding=4)
        controls.place(relx=1.0, rely=0.0, anchor="ne", x=-12, y=12)
        ttk.Button(controls, text="Topo", command=self._use_topo_map).pack(side="left")
        ttk.Button(controls, text="Standard", command=self._use_standard_map).pack(side="left", padx=(4, 0))
        self.correction_attribution = ttk.Label(
            self.corrections_tab,
            text="Topo: © OpenStreetMap contributors, SRTM | © OpenTopoMap (CC-BY-SA)",
        )
        self.correction_attribution.place(relx=1.0, rely=1.0, anchor="se", x=-12, y=-8)
        self._use_topo_map()

    def _use_topo_map(self) -> None:
        self.correction_map.set_tile_server(
            "https://tile.opentopomap.org/{z}/{x}/{y}.png",
            max_zoom=17,
        )
        if hasattr(self, "correction_attribution"):
            self.correction_attribution.configure(
                text="Topo: © OpenStreetMap contributors, SRTM | © OpenTopoMap (CC-BY-SA)"
            )

    def _use_standard_map(self) -> None:
        self.correction_map.set_tile_server(
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            max_zoom=19,
        )
        if hasattr(self, "correction_attribution"):
            self.correction_attribution.configure(text="Map data: © OpenStreetMap contributors")

    @staticmethod
    def _coordinate_pair(lat_value, lon_value):
        """Return a validated numeric coordinate pair, or None for incomplete data."""
        try:
            if lat_value in (None, "") or lon_value in (None, ""):
                return None
            lat = float(lat_value)
            lon = float(lon_value)
        except (TypeError, ValueError):
            return None
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return None
        return lat, lon

    def _correction_selected(self) -> None:
        rec = self._correction_records.get(self.correct_call.get().upper())
        self.correction_map.delete_all_marker()
        if not rec:
            self.correct_info.set("No station selected")
            self.correct_lat.set("")
            self.correct_lon.set("")
            return

        call = self.correct_call.get().upper()
        model = self._coordinate_pair(rec.get("lat"), rec.get("lon"))
        if model is None:
            self.correct_info.set("Selected station has no usable model coordinate")
            self.correct_lat.set("")
            self.correct_lon.set("")
            return
        model_lat, model_lon = model

        reported = self._coordinate_pair(
            rec.get("_reported_lat", rec.get("lat")),
            rec.get("_reported_lon", rec.get("lon")),
        ) or model
        reported_lat, reported_lon = reported

        conf = rec.get("_location_confidence") or {}
        self.correct_info.set(
            f"Reported: {reported_lat:.6f}, {reported_lon:.6f}\n"
            f"Model: {model_lat:.6f}, {model_lon:.6f}\n"
            f"Confidence: {conf.get('label','?')} ({conf.get('score','?')}/100)"
        )
        self.correction_map.set_marker(reported_lat, reported_lon, text=f"{call} reported")

        review = rec.get("_location_correction") or rec.get("_location_review_candidate") or {}
        candidate = self._coordinate_pair(review.get("candidate_lat"), review.get("candidate_lon"))
        if candidate is None:
            candidate = model
        proposal_lat, proposal_lon = candidate
        self.correct_lat.set(f"{proposal_lat:.6f}")
        self.correct_lon.set(f"{proposal_lon:.6f}")
        self.correct_reason.set(str(review.get("reason") or ""))
        self.correct_source.set(str(review.get("source") or "Visual review in Viewshed"))

        if candidate != reported:
            self.correction_map.set_marker(proposal_lat, proposal_lon, text=f"{call} proposed")
        self.correction_map.set_position(model_lat, model_lon)
        self.correction_map.set_zoom(12)

    def _show_correction_proposal(self) -> None:
        """Draw the working proposal without reloading and erasing its fields."""
        proposal = self._coordinate_pair(self.correct_lat.get().strip(), self.correct_lon.get().strip())
        if proposal is None:
            messagebox.showerror(
                "Invalid proposed point",
                "Enter a valid latitude and longitude, or click the map to choose a point.",
                parent=self,
            )
            return

        lat, lon = proposal
        call = self.correct_call.get().strip().upper()
        rec = self._correction_records.get(call)

        self.correction_map.delete_all_marker()
        if rec:
            reported = self._coordinate_pair(
                rec.get("_reported_lat", rec.get("lat")),
                rec.get("_reported_lon", rec.get("lon")),
            )
            if reported:
                self.correction_map.set_marker(reported[0], reported[1], text=f"{call} reported")
        self.correction_map.set_marker(lat, lon, text=f"{call or 'Station'} proposed")
        self.correct_lat.set(f"{lat:.6f}")
        self.correct_lon.set(f"{lon:.6f}")
        self.correct_status.set(f"Proposed point: {lat:.6f}, {lon:.6f} — save as candidate or approve when ready.")
