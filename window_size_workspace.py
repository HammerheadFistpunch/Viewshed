from __future__ import annotations


def apply_main_window_size(app) -> None:
    """Size the main application so status and propagation log remain visible."""
    app.geometry("1280x1000")
    app.minsize(1000, 800)
