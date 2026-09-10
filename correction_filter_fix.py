from __future__ import annotations


def install_correction_filter_fix() -> None:
    """Keep Corrections populated and redraw the selected station once visible."""
    from map_workspace_patch import ViewshedWorkspace

    if getattr(ViewshedWorkspace, "_empty_review_fallback_installed", False):
        return

    original_init = ViewshedWorkspace.__init__
    original_refresh = ViewshedWorkspace._refresh_correction_catalog

    def refresh_with_fallback(self, records=None):
        original_refresh(self, records)
        try:
            visible = tuple(self.correct_combo.cget("values") or ())
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
            # Never make the Corrections UI unusable because a Tk widget is in
            # an intermediate state during startup or a tab transition.
            pass

    def render_visible_selection(self):
        """Redraw after Tk has laid out the Corrections map canvas."""
        try:
            self.update_idletasks()
            # Refresh the catalog first so the StringVar, combobox values, and
            # record dictionary are guaranteed to agree before drawing markers.
            source = getattr(self, "_correction_catalog_source", None)
            self._refresh_correction_catalog(source or None)
            self.update_idletasks()
            self._correction_selected()
        except Exception:
            pass

    def on_tab_changed(self, _event=None):
        try:
            selected = self.notebook.select()
            corrections_id = str(self.corrections_tab)
            if selected == corrections_id:
                self.after_idle(lambda: render_visible_selection(self))
        except Exception:
            pass

    def init_with_visible_redraw(self, master, app):
        original_init(self, master, app)
        try:
            self.notebook.bind("<<NotebookTabChanged>>", on_tab_changed.__get__(self, type(self)), add="+")
        except Exception:
            pass

    ViewshedWorkspace._refresh_correction_catalog = refresh_with_fallback
    ViewshedWorkspace.__init__ = init_with_visible_redraw
    ViewshedWorkspace._empty_review_fallback_installed = True
