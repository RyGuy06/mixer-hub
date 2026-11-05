"""Product render with four hardware-to-software channel guides."""
import logging
import math
import tkinter as tk

from PIL import Image, ImageTk
from app_paths import resource_path

ASSET_ROOT = resource_path("assets/product")
# Coordinates within the top render's visible alpha bounds, in channel order.
# Update these anchors when the hardware design/render changes.
SLIDER_X = (0.225, 0.436, 0.654, 0.866)
LED_X = (0.115, 0.325, 0.545, 0.768)
TRACK_TOP, TRACK_BOTTOM = 0.064, 0.50
# Centres of the four blue handles, relative to the side render's alpha bounds.
SIDE_SLIDERS = ((0.398, 0.30), (0.49, 0.38), (0.58, 0.46), (0.673, 0.54))


class ProductView(tk.Canvas):
    def __init__(self, parent, theme):
        super().__init__(parent, bg=theme["bg"], highlightthickness=0, height=212)
        self.theme = theme
        self.view = "top"
        self.direction = "down"
        self.guides = True
        self.target_provider = None
        self.sources = {}
        self._photo = None
        self._layout = None
        self._signature = None
        self._pending_resize = None
        self._state = ((-1,) * 4, (0,) * 4, (theme["accent"],) * 4, False)
        self._lines, self._labels, self._pins, self._leds, self._bridges = [], [], [], [], []
        for name in ("top", "side"):
            path = next(iter(sorted(ASSET_ROOT.glob(f"{name}*.png"))), None)
            if path:
                try:
                    with Image.open(path) as source:
                        rgba = source.convert("RGBA")
                        bounds = rgba.getchannel("A").getbbox()
                        if bounds:
                            cropped = rgba.crop(bounds)
                            cropped.thumbnail((800, 800), Image.Resampling.LANCZOS)
                            self.sources[name] = cropped
                except OSError:
                    logging.exception("Could not load product render %s", path)
        if not self.sources:
            self.create_text(0, 0, text="Product render unavailable", fill=theme["muted"], tags="fallback")
        elif self.view not in self.sources:
            self.view = next(iter(self.sources))
        self._image_id = self.create_image(0, 0, anchor="nw")
        for index in range(4):
            self._lines.append(self.create_line(0, 0, 0, 0, width=1, joinstyle="round"))
            self._bridges.append(self.create_line(0, 0, 0, 0, width=1))
            self._pins.append(self.create_oval(0, 0, 0, 0, outline="", state="hidden"))
            self._labels.append(self.create_text(0, 0, text=f"{index + 1:02d}",
                                                 font=("Segoe UI", 10, "bold")))
            self._leds.append([self.create_rectangle(0, 0, 0, 0, outline="", state="hidden")
                               for _ in range(10)])
        self.bind("<Configure>", self._schedule_resize)
        self.bind("<Destroy>", self._on_destroy)

    def _schedule_resize(self, event):
        if self._pending_resize:
            self.after_cancel(self._pending_resize)
        self._pending_resize = self.after(60, self._resize)

    def _on_destroy(self, event):
        if event.widget is self and self._pending_resize:
            self.after_cancel(self._pending_resize)
            self._pending_resize = None

    def set_view(self, view):
        if view not in self.sources or view == self.view:
            return
        if self._pending_resize:
            self.after_cancel(self._pending_resize)
            self._pending_resize = None
        self.view = view
        self._layout = None
        self._resize()

    def set_guides(self, *, visible=True, direction="down"):
        if (self.guides, self.direction) == (visible, direction):
            return
        self.guides, self.direction = visible, direction
        if self._pending_resize:
            self.after_cancel(self._pending_resize)
            self._pending_resize = None
        self._layout = None
        self._resize()

    def _resize(self):
        self._pending_resize = None
        width, height = self.winfo_width(), self.winfo_height()
        if width < 20 or height < 20:
            return
        centers = self.target_provider() if self.target_provider else None
        layout = (width, height, self.view, self.direction, self.guides, centers)
        if layout == self._layout:
            return
        self._layout = layout
        self._signature = None
        source = self.sources.get(self.view)
        if source is None:
            self.coords("fallback", width / 2, height / 2)
            for item in [*self._lines, *self._labels, *self._bridges]:
                self.itemconfigure(item, state="hidden")
            return
        upward = self.direction == "up"
        scale = min((height - (58 if upward else 22)) / source.height,
                    width * 0.24 / source.width)
        image_w, image_h = max(1, round(source.width * scale)), max(1, round(source.height * scale))
        left, top = (width - image_w) / 2, 46 if upward else 8
        self._photo = ImageTk.PhotoImage(source.resize((image_w, image_h), Image.Resampling.LANCZOS), master=self)
        self.itemconfigure(self._image_id, image=self._photo)
        self.coords(self._image_id, left, top)
        anchors = (tuple((x, TRACK_TOP) for x in SLIDER_X) if self.view == "top" else SIDE_SLIDERS)
        pins = [(left + x * image_w, top + y * image_h) for x, y in anchors]
        branch_start = min(y for _, y in pins) if upward else max(y for _, y in pins)
        for index in range(4):
            target_x = centers[index] if centers else width * (index + 0.5) / 4
            label_y = 10 if upward else height - 10
            self.coords(self._labels[index], target_x, label_y)
            self.coords(self._bridges[index], target_x, 0 if upward else label_y + 9,
                        target_x, label_y - 9 if upward else height)
            pin_x, pin_y = pins[index]
            elbow_y = branch_start + (-1 if upward else 1) * (12 if index in (0, 3) else 26)
            elbow_y = max(25, min(height - 30, elbow_y))
            self.coords(self._lines[index], pin_x, pin_y, pin_x, elbow_y,
                        target_x, elbow_y, target_x, label_y + (13 if upward else -13))
            self.coords(self._pins[index], pin_x - 2, pin_y - 2, pin_x + 2, pin_y + 2)
            for item in (self._lines[index], self._pins[index], self._labels[index], self._bridges[index]):
                self.itemconfigure(item, state="normal" if self.guides else "hidden")
            if self.view == "top":
                strip_x = left + LED_X[index] * image_w
                strip_top = top + TRACK_TOP * image_h
                strip_bottom = top + TRACK_BOTTOM * image_h
                segment_h = (strip_bottom - strip_top) / 10
                for led, item in enumerate(self._leds[index]):
                    bottom = strip_bottom - led * segment_h
                    self.coords(item, strip_x - image_w * 0.018, bottom - segment_h * 0.7,
                                strip_x + image_w * 0.018, bottom)
            else:
                # LED strips retain their rendered perspective in the side view.
                for item in self._leds[index]:
                    self.itemconfigure(item, state="hidden")
        self.set_state(*self._state)

    def set_state(self, percentages, levels, colors, connected):
        self._state = (tuple(percentages), tuple(levels), tuple(colors), connected)
        lit = tuple(min(10, max(0, math.ceil(level / 10))) for level in levels)
        signature = (lit, tuple(colors), connected, self.view)
        if signature == self._signature or not self._layout or not self.sources:
            return
        self._signature = signature
        for index, color in enumerate(colors):
            self.itemconfigure(self._labels[index], fill=color)
            route_color = self._muted_color(color) if connected else self.theme["border"]
            self.itemconfigure(self._lines[index], fill=route_color)
            self.itemconfigure(self._bridges[index], fill=route_color)
            self.itemconfigure(self._pins[index], fill=color)
            if self.view == "top":
                for led, item in enumerate(self._leds[index]):
                    self.itemconfigure(item, state="normal" if connected and led < lit[index] else "hidden", fill=color)

    def _muted_color(self, color):
        foreground = tuple(int(color[start:start + 2], 16) for start in (1, 3, 5))
        background = tuple(int(self.theme["bg"][start:start + 2], 16) for start in (1, 3, 5))
        rgb = tuple(round(fg * 0.55 + bg * 0.45) for fg, bg in zip(foreground, background))
        return "#" + "".join(f"{value:02x}" for value in rgb)
