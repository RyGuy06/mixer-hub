"""Presentation-only app selector and read-only studio fader."""
import re
import tkinter as tk
import customtkinter as ctk


def friendly_name(app):
    known = {"master": "Master", "javaw.exe": "Minecraft", "java.exe": "Java",
             "spotify.exe": "Spotify", "discord.exe": "Discord", "chrome.exe": "Chrome",
             "msedge.exe": "Edge", "firefox.exe": "Firefox", "rtkuwp.exe": "Realtek Audio",
             "robloxplayerbeta.exe": "Roblox", "No app running": "Waiting for app", "": "Waiting for app"}
    return known.get(app, re.sub(r"[_-]+", " ", app.removesuffix(".exe")).strip().title())


class AppSelector(ctk.CTkOptionMenu):
    """Display friendly names while retaining the original executable values."""
    def __init__(self, parent, *, values, **kwargs):
        self._raw_values = list(values)
        self._route = values[0] if values else ""
        self._routes = {self.menu_label(app): app for app in values}
        super().__init__(parent, values=list(self._routes), **kwargs)
        self._text_label.bind("<Configure>", self._fit_label, add="+")
        self.set(self._route)

    @staticmethod
    def menu_label(app):
        return f"{friendly_name(app)}   ·   {app}"

    def configure(self, **kwargs):
        if "values" in kwargs:
            self._raw_values = list(kwargs["values"])
            self._routes = {self.menu_label(app): app for app in self._raw_values}
            kwargs["values"] = list(self._routes)
        super().configure(**kwargs)

    def cget(self, name):
        return list(self._raw_values) if name == "values" else super().cget(name)

    def set(self, app):
        self._route = app
        if self._current_value != friendly_name(app):
            super().set(friendly_name(app))
        self._fit_label()

    def _fit_label(self, event=None):
        width = self._text_label.winfo_width()
        if width <= 1:
            return
        full = friendly_name(self._route)
        font = self._text_label.cget("font")
        measure = lambda text: int(self.tk.call("font", "measure", font, text))
        display = full
        if measure(full) > width:
            while display and measure(display + "…") > width:
                display = display[:-1]
            display += "…"
        if self._text_label.cget("text") != display:
            self._text_label.configure(text=display)

    def get(self):
        return self._route

    def index(self, value=None):
        return self._raw_values.index(self._route if value is None else value)

    def _dropdown_callback(self, label):
        if label not in self._routes:
            return
        self.set(self._routes[label])
        if self._command:
            self._command(self._route)


class DebouncedCanvas(tk.Canvas):
    """Coalesce geometry changes; painting values does not rebuild the canvas."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._resize_job = None
        self._requested_size = self._drawn_size = None
        self.bind("<Configure>", self._schedule_resize)
        self.bind("<Destroy>", self._cancel_resize)
        self.bind("<Unmap>", self._cancel_resize)
        self.bind("<Map>", lambda event: self._schedule_resize())

    def _schedule_resize(self, event=None):
        size = (event.width, event.height) if event else (self.winfo_width(), self.winfo_height())
        if size == self._requested_size:
            return
        self._requested_size = size
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(60, self._flush_resize)

    def _flush_resize(self):
        self._resize_job = None
        size = (self.winfo_width(), self.winfo_height())
        if size != self._drawn_size and min(size) > 1:
            self._drawn_size = size
            self._redraw(*size)

    def _cancel_resize(self, event):
        if event.widget is self:
            if self._resize_job:
                self.after_cancel(self._resize_job)
                self._resize_job = None
            self._requested_size = None


class StudioFader(DebouncedCanvas):
    """A physical-position display; it never changes Windows or device volume."""
    def __init__(self, parent, color, scaling):
        super().__init__(parent, width=90, height=160, bg="#111114", highlightthickness=0)
        self.color, self.scaling = color, scaling
        self.value, self.connected = 0, False
        self.parts = None

    @staticmethod
    def rounded(x1, y1, x2, y2, radius):
        radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
        return (x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
                x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
                x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1)

    def _redraw(self, width, height):
        self.delete("all")
        scale = self.scaling()
        self.top, self.bottom = 12 * scale, max(12 * scale + 1, height - 12 * scale)
        self.center = width * 0.67
        self.track_width = 14 * scale
        self.thumb_width = min(32 * scale, max(12 * scale, width - 35 * scale))
        for value in (100, 75, 50, 25, 0):
            y = self.top + (100 - value) / 100 * (self.bottom - self.top)
            self.create_text(12 * scale, y, text=str(value), fill="#777782",
                             font=("Segoe UI", -round(9 * scale)))
        self.create_polygon(self.rounded(self.center - self.track_width / 2, self.top,
                                         self.center + self.track_width / 2, self.bottom, 7 * scale),
                            smooth=True, fill="#08080B", outline="")
        self.parts = (self.create_polygon(0, 0, 0, 0, 0, 0, smooth=True, outline=""),
                      self.create_polygon(0, 0, 0, 0, 0, 0, smooth=True, outline=""),
                      self.create_line(0, 0, 0, 0, width=max(1, scale)))
        self._paint()

    def _paint(self):
        if not self.parts:
            return
        scale = self.scaling()
        y = self.bottom - self.value / 100 * (self.bottom - self.top)
        fill, thumb, grip = self.parts
        self.coords(fill, *self.rounded(self.center - self.track_width / 2, y,
                                       self.center + self.track_width / 2, self.bottom, 6 * scale))
        self.itemconfigure(fill, fill=self.color if self.connected else "#34343D",
                           state="normal" if self.value > 0 else "hidden")
        self.coords(thumb, *self.rounded(self.center - self.thumb_width / 2, y - 6 * scale,
                                        self.center + self.thumb_width / 2, y + 6 * scale, 3 * scale))
        self.itemconfigure(thumb, fill="#DBDBE3" if self.connected else "#73737E")
        self.coords(grip, self.center - 7 * scale, y, self.center + 7 * scale, y)
        self.itemconfigure(grip, fill="#74747F" if self.connected else "#4A4A55")

    def set(self, value):
        self.value = max(0, min(100, value))
        self._paint()

    def get(self):
        return self.value

    def set_connected(self, connected):
        if self.connected != connected:
            self.connected = connected
            self._paint()

    def configure(self, cnf=None, **kwargs):
        if "progress_color" in kwargs:
            self.color = kwargs.pop("progress_color")
            self._paint()
        if kwargs or cnf:
            return super().configure(cnf, **kwargs)

    def cget(self, name):
        return self.color if name == "progress_color" else super().cget(name)
