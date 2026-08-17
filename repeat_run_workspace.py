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
