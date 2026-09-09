from __future__ import annotations

import tkinter as tk


class Tooltip:
    """Small dependency-free hover tooltip for Tk/ttk widgets."""

    def __init__(self, widget, text: str, *, delay_ms: int = 500, wraplength: int = 360) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.wraplength = wraplength
        self._after_id = None
        self._window: tk.Toplevel | None = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        if self._window is not None or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 18
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            return

        window = tk.Toplevel(self.widget)
        self._window = window
        window.wm_overrideredirect(True)
        try:
            window.wm_attributes("-topmost", True)
        except Exception:
            pass

        label = tk.Label(
            window,
            text=self.text,
            justify="left",
            anchor="w",
            wraplength=self.wraplength,
            padx=8,
            pady=6,
            relief="solid",
            borderwidth=1,
        )
        label.pack()

        window.update_idletasks()
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        width = window.winfo_reqwidth()
        height = window.winfo_reqheight()
        x = min(x, max(0, screen_w - width - 8))
        y = min(y, max(0, screen_h - height - 8))
        window.wm_geometry(f"+{x}+{y}")

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None


def add_tooltip(widget, text: str, *, delay_ms: int = 500, wraplength: int = 360) -> Tooltip:
    tooltip = Tooltip(widget, text, delay_ms=delay_ms, wraplength=wraplength)
    # Keep a widget-owned reference so the tooltip object's lifetime follows it.
    widget._signal_peak_tooltip = tooltip
    return tooltip
