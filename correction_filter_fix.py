from __future__ import annotations


def install_correction_filter_fix() -> None:
    """Prevent an empty Needs Review filter from making Corrections look empty."""
    from map_workspace_patch import ViewshedWorkspace

    if getattr(ViewshedWorkspace, "_empty_review_fallback_installed", False):
        return

    original_refresh = ViewshedWorkspace._refresh_correction_catalog

    def refresh_with_fallback(self, records=None):
        original_refresh(self, records)
        try:
            visible = list(self.correct_combo.cget("values") or ())
            has_catalog = bool(getattr(self, "_correction_records", {}))
            if not visible and has_catalog and not getattr(self, "_correction_show_all", False):
                self._correction_show_all = True
                self._update_filter_button()
                original_refresh(self, getattr(self, "_correction_catalog_source", None) or records)
                if hasattr(self, "correct_status"):
                    self.correct_status.set(
                        "No stations currently need location review — showing the full station catalog instead."
                    )
        except Exception:
            # Corrections should remain usable even if a third-party Tk widget
            # behaves differently during early initialization.
            pass

    ViewshedWorkspace._refresh_correction_catalog = refresh_with_fallback
    ViewshedWorkspace._empty_review_fallback_installed = True
