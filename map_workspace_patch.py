from __future__ import annotations

import threading
from tkinter import messagebox, ttk

from map_workspace import ViewshedWorkspace as _ViewshedWorkspace, save_user_override
from osm_crossref import cross_reference_osm
from viewshed_core import assess_station_locations


class ViewshedWorkspace(_ViewshedWorkspace):
    """UI fixes layered over the map workspace while the UI is evolving."""

    def __init__(self, master, app) -> None:
        # These flags must exist before the base constructor runs because the
        # base constructor loads the station catalog and dispatches to our
        # overridden _refresh_correction_catalog method.
        self._correction_show_all = False
        self._correction_catalog_source: list[dict] = []
        self._osm_busy = False
        super().__init__(master, app)
        self._install_correction_map_controls()
        self._refresh_correction_catalog(self._correction_catalog_source or None)

    def _install_correction_map_controls(self) -> None:
        controls = ttk.Frame(self.corrections_tab, padding=4)
        controls.place(relx=1.0, rely=0.0, anchor="ne", x=-12, y=12)

        self.review_filter_btn = ttk.Button(
            controls,
            text="Show All",
            command=self._toggle_correction_filter,
        )
        self.review_filter_btn.pack(side="left")
        ttk.Button(controls, text="Next", command=self._next_correction).pack(side="left", padx=(4, 0))
        self.osm_crosscheck_btn = ttk.Button(
            controls,
            text="Cross-check OSM",
            command=self._crosscheck_osm,
        )
        self.osm_crosscheck_btn.pack(side="left", padx=(12, 0))
        self.osm_use_btn = ttk.Button(
            controls,
            text="Use OSM point",
            command=self._use_osm_point,
            state="disabled",
        )
        self.osm_use_btn.pack(side="left", padx=(4, 0))
        ttk.Button(controls, text="Topo", command=self._use_topo_map).pack(side="left", padx=(12, 0))
        ttk.Button(controls, text="Standard", command=self._use_standard_map).pack(side="left", padx=(4, 0))

        self.correction_attribution = ttk.Label(
            self.corrections_tab,
            text="Topo: © OpenStreetMap contributors, SRTM | © OpenTopoMap (CC-BY-SA)",
        )
        self.correction_attribution.place(relx=1.0, rely=1.0, anchor="se", x=-12, y=-8)
        self._use_topo_map()
        self._update_filter_button()

    def _update_filter_button(self) -> None:
        if hasattr(self, "review_filter_btn"):
            self.review_filter_btn.configure(
                text="Needs Review" if self._correction_show_all else "Show All"
            )

    def _toggle_correction_filter(self) -> None:
        self._correction_show_all = not self._correction_show_all
        self._update_filter_button()
        self._refresh_correction_catalog(self._correction_catalog_source or None)

    @staticmethod
    def _confidence_score(record: dict) -> int:
        meta = record.get("_location_confidence") or {}
        try:
            return int(meta.get("score", 999))
        except (TypeError, ValueError):
            return 999

    @staticmethod
    def _needs_location_review(record: dict) -> bool:
        meta = record.get("_location_confidence") or {}
        label = str(meta.get("label") or "").upper()
        return label == "LOW" or bool(record.get("_location_review_candidate"))

    def _refresh_correction_catalog(self, records: list[dict] | None = None) -> None:
        if records is None:
            try:
                records = self._station_source_records()
            except Exception:
                records = []
        self._correction_catalog_source = list(records)
        assessed = assess_station_locations(records)
        self._correction_records = {
            str(r.get("callsign") or "").upper(): r
            for r in assessed
            if r.get("callsign") and "lat" in r and "lon" in r
        }

        all_calls = sorted(
            self._correction_records,
            key=lambda call: (self._confidence_score(self._correction_records[call]), call),
        )
        review_calls = [
            call for call in all_calls
            if self._needs_location_review(self._correction_records[call])
        ]
        visible_calls = all_calls if self._correction_show_all else review_calls
        self.correct_combo["values"] = visible_calls

        current = self.correct_call.get().strip().upper()
        if current not in visible_calls:
            self.correct_call.set(visible_calls[0] if visible_calls else "")

        if hasattr(self, "correct_status"):
            mode = "all stations" if self._correction_show_all else "needs review"
            self.correct_status.set(
                f"Showing {len(visible_calls)} {mode}; {len(review_calls)} of "
                f"{len(all_calls)} stations need review. Lowest confidence is first."
            )
        self._correction_selected()

    def _next_correction(self) -> None:
        calls = list(self.correct_combo.cget("values") or ())
        if not calls:
            self.correct_status.set("No stations in the current correction filter.")
            return
        current = self.correct_call.get().strip().upper()
        try:
            idx = calls.index(current)
        except ValueError:
            idx = -1
        next_idx = idx + 1
        if next_idx >= len(calls):
            self.correct_status.set("End of the current correction list.")
            return
        self.correct_call.set(calls[next_idx])
        self._correction_selected()

    def _advance_after_save(self, saved_call: str, previous_calls: list[str]) -> None:
        current_calls = list(self.correct_combo.cget("values") or ())
        if not current_calls:
            self.correct_call.set("")
            self._correction_selected()
            self.correct_status.set("Review queue complete — no stations remain in this filter.")
            return

        try:
            old_index = previous_calls.index(saved_call)
        except ValueError:
            old_index = -1

        if saved_call in current_calls:
            target_index = old_index + 1
        else:
            target_index = max(0, old_index)

        if target_index >= len(current_calls):
            self.correct_status.set("Saved. End of the current correction list.")
            return

        self.correct_call.set(current_calls[target_index])
        self._correction_selected()

    def open_correction(self, callsign: str) -> None:
        call = str(callsign or "").strip().upper()
        self._refresh_correction_catalog(self._area_records or None)
        if call in self._correction_records:
            visible = list(self.correct_combo.cget("values") or ())
            if call not in visible:
                self._correction_show_all = True
                self._update_filter_button()
                self._refresh_correction_catalog(self._area_records or None)
            self.correct_call.set(call)
            self._correction_selected()
        self.notebook.select(self.corrections_tab)

    def _crosscheck_osm(self) -> None:
        if self._osm_busy:
            return
        visible_calls = list(self.correct_combo.cget("values") or ())
        if not visible_calls:
            messagebox.showinfo(
                "OSM cross-check",
                "There are no stations in the current correction filter. Use Show All to cross-check the full list.",
                parent=self,
            )
            return
        records = [
            self._correction_records[call]
            for call in visible_calls
            if call in self._correction_records
        ]
        if not records:
            return

        self._osm_busy = True
        self.osm_crosscheck_btn.configure(state="disabled")
        self.correct_status.set(
            f"Querying OpenStreetMap communications infrastructure for {len(records)} visible station(s)…"
        )

        def work() -> None:
            try:
                matches = cross_reference_osm(records, match_radius_km=3.0)
                self.after(0, lambda: self._apply_osm_matches(matches))
            except Exception as exc:
                self.after(0, lambda e=exc: self._osm_crosscheck_failed(e))

        threading.Thread(target=work, daemon=True).start()

    def _apply_osm_matches(self, matches: dict[str, dict]) -> None:
        self._osm_busy = False
        self.osm_crosscheck_btn.configure(state="normal")
        matched = sum(1 for m in matches.values() if m.get("matched"))

        def attach(records: list[dict]) -> list[dict]:
            updated: list[dict] = []
            for original in records:
                record = dict(original)
                call = str(record.get("callsign") or "").strip().upper()
                if call in matches:
                    record["_osm_crossref"] = dict(matches[call])
                updated.append(record)
            return updated

        self._correction_catalog_source = attach(self._correction_catalog_source)
        if self._area_records:
            self._area_records = attach(self._area_records)
        for call, match in matches.items():
            if call in self._station_records:
                self._station_records[call] = {**self._station_records[call], "_osm_crossref": dict(match)}

        selected = self.correct_call.get().strip().upper()
        self._refresh_correction_catalog(self._correction_catalog_source)
        if selected in self._correction_records:
            self.correct_call.set(selected)
            self._correction_selected()
        self.correct_status.set(
            f"OSM cross-check complete: {matched} of {len(matches)} station(s) have a communications feature within 3 km."
        )

    def _osm_crosscheck_failed(self, exc: Exception) -> None:
        self._osm_busy = False
        self.osm_crosscheck_btn.configure(state="normal")
        self.correct_status.set("OSM cross-check unavailable.")
        messagebox.showerror(
            "OSM cross-check failed",
            f"Could not query OpenStreetMap/Overpass:\n{exc}",
            parent=self,
        )

    def _use_osm_point(self) -> None:
        call = self.correct_call.get().strip().upper()
        rec = self._correction_records.get(call)
        match = (rec or {}).get("_osm_crossref") or {}
        if not match.get("matched"):
            messagebox.showinfo("No OSM match", "Cross-check OSM first; this station has no matched communications feature.", parent=self)
            return
        try:
            lat = float(match["lat"])
            lon = float(match["lon"])
        except (KeyError, TypeError, ValueError):
            return
        self.correct_lat.set(f"{lat:.6f}")
        self.correct_lon.set(f"{lon:.6f}")
        distance_m = match.get("distance_m", "?")
        label = str(match.get("label") or "communications site")
        self.correct_reason.set(f"OSM communications feature {distance_m} m from reported/model point: {label}")
        self.correct_source.set("OpenStreetMap via Overpass; human reviewed in Viewshed")
        self._show_correction_proposal()

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
        if hasattr(self, "osm_use_btn"):
            self.osm_use_btn.configure(state="disabled")
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
        reasons = conf.get("reasons") or []
        reason_text = "; ".join(str(r) for r in reasons)
        freshness = conf.get("freshness") or {}
        freshness_text = str(freshness.get("reason") or freshness.get("label") or "unknown")

        osm = rec.get("_osm_crossref") or {}
        if osm.get("matched"):
            tags = osm.get("tags") or {}
            service_bits = []
            for key in (
                "communication:radio",
                "communication:microwave",
                "communication:mobile_phone",
                "communication:television",
                "operator",
                "height",
            ):
                if tags.get(key) not in (None, ""):
                    service_bits.append(f"{key}={tags[key]}")
            osm_text = (
                f"{osm.get('strength','?')} — {osm.get('distance_m','?')} m to "
                f"{osm.get('label','OSM communications site')}"
            )
            if service_bits:
                osm_text += " (" + ", ".join(service_bits[:4]) + ")"
            if hasattr(self, "osm_use_btn"):
                self.osm_use_btn.configure(state="normal")
        elif osm:
            osm_text = f"No communications feature within {osm.get('radius_km', 3):g} km"
        else:
            osm_text = "Not checked"

        self.correct_info.set(
            f"Reported: {reported_lat:.6f}, {reported_lon:.6f}\n"
            f"Model: {model_lat:.6f}, {model_lon:.6f}\n"
            f"Location confidence: {conf.get('label','?')} ({conf.get('score','?')}/100)\n"
            f"Why: {reason_text or 'No confidence details'}\n"
            f"Freshness: {freshness_text}\n"
            f"OSM cross-reference: {osm_text}"
        )
        self.correction_map.set_marker(reported_lat, reported_lon, text=f"{call} reported")

        if osm.get("matched"):
            try:
                osm_lat = float(osm["lat"])
                osm_lon = float(osm["lon"])
                self.correction_map.set_marker(
                    osm_lat,
                    osm_lon,
                    text=f"OSM: {osm.get('label','communications site')} ({osm.get('distance_m','?')} m)",
                )
            except (KeyError, TypeError, ValueError):
                pass

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
            osm = rec.get("_osm_crossref") or {}
            if osm.get("matched"):
                try:
                    self.correction_map.set_marker(
                        float(osm["lat"]),
                        float(osm["lon"]),
                        text=f"OSM: {osm.get('label','communications site')} ({osm.get('distance_m','?')} m)",
                    )
                except (KeyError, TypeError, ValueError):
                    pass
        self.correction_map.set_marker(lat, lon, text=f"{call or 'Station'} proposed")
        self.correct_lat.set(f"{lat:.6f}")
        self.correct_lon.set(f"{lon:.6f}")
        self.correct_status.set(
            f"Proposed point: {lat:.6f}, {lon:.6f} — save as candidate or approve when ready."
        )

    def _save_correction(self, status: str) -> None:
        call = self.correct_call.get().strip().upper()
        if not call:
            return
        proposal = self._coordinate_pair(self.correct_lat.get().strip(), self.correct_lon.get().strip())
        if proposal is None:
            messagebox.showerror(
                "Invalid correction",
                "Enter a valid latitude and longitude, or click the map to choose a point.",
                parent=self,
            )
            return
        lat, lon = proposal
        if status == "reviewed" and not messagebox.askyesno(
            "Approve location correction",
            f"Use {lat:.6f}, {lon:.6f} as the propagation location for {call}?\n\n"
            "The APRS-reported location will still be preserved.",
            parent=self,
        ):
            return

        previous_calls = list(self.correct_combo.cget("values") or ())
        save_user_override(
            call,
            {
                "status": status,
                "lat": lat,
                "lon": lon,
                "reason": self.correct_reason.get().strip(),
                "source": self.correct_source.get().strip() or "Visual review in Viewshed",
            },
        )
        self.correct_status.set(f"Saved {status} location for {call}.")
        self._after_correction_change(call)
        self._advance_after_save(call, previous_calls)
