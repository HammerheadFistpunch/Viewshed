from __future__ import annotations

from workspace_tuning import ViewshedWorkspace as _ViewshedWorkspace


class ViewshedWorkspace(_ViewshedWorkspace):
    """Workspace layer that makes completed propagation runs immediately reusable."""

    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._install_repeat_run_guard()

    def _install_repeat_run_guard(self) -> None:
        if getattr(self.app, "_repeat_run_guard_installed", False):
            return

        original_start_job = self.app.start_job

        def repeat_safe_start_job(job_file, label):
            # A finished child can leave the UI's coarse running flag stale if
            # completion/cancellation messages race with the next user action.
            # Trust the actual process state before refusing a new job.
            if getattr(self.app, "_job_running", False):
                process = getattr(self.app, "_current_process", None)
                process_finished = process is None
                if process is not None:
                    try:
                        process_finished = process.poll() is not None
                    except Exception:
                        process_finished = False

                if process_finished:
                    self.app._job_running = False
                    self.app._cancel_requested = False
                    self.app._current_process = None
                    try:
                        self.app.cancel_btn.configure(state="disabled")
                    except Exception:
                        pass

            return original_start_job(job_file, label)

        self.app.start_job = repeat_safe_start_job
        self.app._repeat_run_guard_installed = True

    def _mark_new_job_ready(self) -> None:
        """Clear completion presentation when inputs change, preserving old outputs."""
        if getattr(self.app, "_job_running", False):
            return
        try:
            self.app.progress["value"] = 0
            self.app.percent_var.set("0%")
            self.app.status_var.set("Ready for next job")
        except Exception:
            # During workspace construction the status bar does not exist yet.
            pass

    def _area_acquired(self, records: list[dict]) -> None:
        """Unlock Area workflow as soon as station acquisition succeeds.

        Map/correction rendering is useful but non-critical.  A rendering or
        confidence-catalog exception must never strand a valid station list
        behind disabled Review/Run buttons.
        """
        self._area_busy = False
        self.find_area_btn.configure(state="normal")
        self._area_records = list(records or [])

        if not self._area_records:
            self.run_area_btn.configure(state="disabled")
            self.area_review_btn.configure(state="disabled")
            self.area_status.set("No usable stations were found for this area.")
            return

        # Station acquisition is the gate for steps 2 and 3.  Unlock first;
        # everything below is presentation/enrichment and must be best-effort.
        self.run_area_btn.configure(state="normal")
        self.area_review_btn.configure(state="normal")

        low = 0
        review = 0
        try:
            low = sum(
                1
                for record in self._area_records
                if (record.get("_location_confidence") or {}).get("label") == "LOW"
            )
            review = sum(
                1 for record in self._area_records if record.get("_location_review_candidate")
            )
        except Exception:
            pass

        self.area_status.set(
            f"{len(self._area_records)} stations ready. {low} LOW confidence; "
            f"{review} flagged for review. Inspect/correct, then run."
        )

        render_errors: list[str] = []
        try:
            self._draw_area_boundary()
        except Exception as exc:
            render_errors.append(f"map: {exc}")

        try:
            self._refresh_correction_catalog(self._area_records)
        except Exception as exc:
            render_errors.append(f"corrections: {exc}")

        if render_errors:
            self.area_status.set(
                f"{len(self._area_records)} stations ready. Review and Run are available. "
                "Some station display details could not be refreshed."
            )

    def _area_click(self, coords) -> None:
        super()._area_click(coords)
        self._mark_new_job_ready()
        try:
            self.area_status.set("New area selected. Find stations for this location, review if needed, then run propagation.")
        except Exception:
            pass

    def _custom_click(self, coords) -> None:
        super()._custom_click(coords)
        self._mark_new_job_ready()

    def _station_selected(self) -> None:
        super()._station_selected()
        self._mark_new_job_ready()
