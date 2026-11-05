"""Fixed-size channel colour editor with native canvas controls."""
import re
import customtkinter as ctk

from studio_widgets import DebouncedCanvas, StudioFader

QUICK_PICKS = (("Spotify Green", "#1ED760"), ("Discord Blurple", "#5865F2"),
               ("Crimson", "#DC143C"), ("Amber", "#FFBF00"),
               ("Cyan", "#00D4FF"), ("Purple", "#A000FF"),
               ("Magenta", "#FF00FF"), ("Pure White", "#FFFFFF"))


def parse_hex(value):
    value = value.strip()
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
        return None
    return "#" + value.lstrip("#").lower()


class ColourSlider(DebouncedCanvas):
    def __init__(self, parent, name, color, command, theme):
        self.scaling = parent._get_widget_scaling
        super().__init__(parent, bg=theme["panel"], width=120,
                         height=round(38 * self.scaling()), highlightthickness=0, takefocus=True)
        self.name, self.color, self.command = name, color, command
        self.value, self.parts = 0, None
        self.bind("<Button-1>", self._mouse)
        self.bind("<B1-Motion>", self._mouse)
        self.bind("<Left>", lambda event: self._change(self.value - 1))
        self.bind("<Right>", lambda event: self._change(self.value + 1))
        self.bind("<Home>", lambda event: self._change(0))
        self.bind("<End>", lambda event: self._change(255))

    def _redraw(self, width, height):
        self.delete("all")
        scale = self.scaling()
        self.left, self.right, self.y = 23 * scale, max(24 * scale, width - 34 * scale), height / 2
        self.create_text(7 * scale, self.y, text=self.name, fill=self.color,
                         font=("Segoe UI", -round(11 * scale), "bold"))
        self.create_polygon(StudioFader.rounded(self.left, self.y - 8 * scale,
                                                self.right, self.y + 8 * scale, 8 * scale),
                            smooth=True, fill="#111114", outline="")
        fill = self.create_polygon(0, 0, 0, 0, 0, 0, smooth=True, fill=self.color, outline="")
        thumb = self.create_polygon(0, 0, 0, 0, 0, 0, smooth=True, fill="#D9D9E2", outline="")
        grip = self.create_line(0, 0, 0, 0, fill="#72727E", width=max(1, scale))
        number = self.create_text(width - 13 * scale, self.y, text="0", fill="#C5C5CF",
                                  font=("Consolas", -round(10 * scale)))
        self.parts = fill, thumb, grip, number
        self._paint()

    def _paint(self):
        if not self.parts:
            return
        scale = self.scaling()
        x = self.left + self.value / 255 * (self.right - self.left)
        fill, thumb, grip, number = self.parts
        self.coords(fill, *StudioFader.rounded(self.left, self.y - 8 * scale,
                                              x, self.y + 8 * scale, 8 * scale))
        self.itemconfigure(fill, state="normal" if self.value else "hidden")
        self.coords(thumb, *StudioFader.rounded(x - 6 * scale, self.y - 10 * scale,
                                               x + 6 * scale, self.y + 10 * scale, 2 * scale))
        self.coords(grip, x, self.y - 4 * scale, x, self.y + 4 * scale)
        self.itemconfigure(number, text=str(self.value))

    def set(self, value):
        self.value = max(0, min(255, round(value)))
        self._paint()

    def get(self):
        return self.value

    def cget(self, name):
        return self.command if name == "command" else super().cget(name)

    def _change(self, value):
        self.set(value)
        self.command(self.value)
        return "break"

    def _mouse(self, event):
        self.focus_set()
        if self.parts:
            self._change((event.x - self.left) / (self.right - self.left) * 255)


class QuickPickGrid(DebouncedCanvas):
    def __init__(self, parent, command, theme):
        self.scaling = parent._get_widget_scaling
        super().__init__(parent, bg=theme["panel"], width=120,
                         height=round(60 * self.scaling()), highlightthickness=0, takefocus=True)
        self.command, self.color, self.rings = command, "", []
        self.bind("<Left>", lambda event: self._key(-1))
        self.bind("<Right>", lambda event: self._key(1))
        self.bind("<Up>", lambda event: self._key(-4))
        self.bind("<Down>", lambda event: self._key(4))

    def _redraw(self, width, height):
        self.delete("all")
        self.rings = []
        scale = self.scaling()
        for index, (name, color) in enumerate(QUICK_PICKS):
            x, y = (index % 4 + 0.5) * width / 4, (index // 4 + 0.5) * height / 2
            radius = min(12 * scale, width / 9)
            ring = self.create_oval(x - radius, y - radius, x + radius, y + radius,
                                    fill="", outline="", width=max(1, 1.3 * scale))
            dot = self.create_oval(x - radius + 3 * scale, y - radius + 3 * scale,
                                   x + radius - 3 * scale, y + radius - 3 * scale,
                                   fill=color, outline="", tags=name)
            self.rings.append(ring)
            for item in (ring, dot):
                self.tag_bind(item, "<Button-1>", lambda event, value=color: self.command(value))
        self.set_color(self.color)

    def set_color(self, color):
        self.color = color.upper()
        for ring, (_, preset) in zip(self.rings, QUICK_PICKS):
            self.itemconfigure(ring, outline="#F5F5F7" if self.color == preset else "")

    def _key(self, offset):
        selected = next((i for i, (_, color) in enumerate(QUICK_PICKS) if color == self.color), 0)
        self.command(QUICK_PICKS[max(0, min(7, selected + offset))][1])
        return "break"


class InlineColourEditor(ctk.CTkFrame):
    def __init__(self, parent, index, initial, theme, label, button, font, *, on_preview, on_save, on_cancel):
        super().__init__(parent, fg_color=theme["panel"], corner_radius=0, width=120, height=120)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        self.on_preview, self.on_save, self.on_cancel = on_preview, on_save, on_cancel
        self.theme, self._syncing, self.valid = theme, False, True
        self.original, self.color = initial, initial.lower()
        label(self, f"Channel {index + 1} · LED Colour", 12, weight="bold", anchor="w").grid(
            row=0, column=0, sticky="ew", padx=12, pady=(12, 12))
        well = ctk.CTkFrame(self, fg_color="#111114", corner_radius=10)
        well.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        well.grid_columnconfigure(1, weight=1)
        self.swatch = ctk.CTkFrame(well, fg_color=initial, width=26, height=20, corner_radius=6)
        self.swatch.grid(row=0, column=0, padx=(9, 4), pady=9)
        self.hex_var = ctk.StringVar(value=initial.upper())
        self.hex_entry = ctk.CTkEntry(well, textvariable=self.hex_var, width=72, height=30,
                                     fg_color="#111114", border_width=0, corner_radius=6,
                                     font=font(11, family="Consolas"), text_color=theme["text"])
        self.hex_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=4)
        self.hex_entry.bind("<Return>", self._commit_hex)
        self.hex_entry.bind("<FocusOut>", self._commit_hex)
        rgb = ctk.CTkFrame(self, fg_color="transparent")
        rgb.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 8))
        rgb.grid_columnconfigure(0, weight=1)
        self.sliders = {}
        for row, (name, color) in enumerate((("R", "#E48490"), ("G", "#84CFA5"), ("B", "#8EAEF0"))):
            slider = ColourSlider(rgb, name, color, self._from_sliders, theme)
            slider.grid(row=row, column=0, sticky="ew", pady=1)
            self.sliders[name] = slider
        picks = ctk.CTkFrame(self, fg_color="transparent")
        picks.grid(row=3, column=0, sticky="ew", padx=12)
        picks.grid_columnconfigure(0, weight=1)
        label(picks, "Quick picks", 10, theme["subtle"], anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.presets = QuickPickGrid(picks, self.set_preset, theme)
        self.presets.grid(row=1, column=0, sticky="ew")
        self.hint = label(self, "Preview on device", 10, theme["subtle"], anchor="w")
        self.hint.grid(row=4, column=0, sticky="ew", padx=12, pady=(8, 0))
        self.actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions.grid(row=6, column=0, sticky="ew", padx=10, pady=(0, 12))
        self.actions.grid_columnconfigure((0, 1), weight=1)
        self.cancel_button = button(self.actions, "Cancel", self.cancel, width=72)
        self.save_button = button(self.actions, "Save", self.save, primary=True, width=52)
        for widget, column, padding in ((self.cancel_button, 0, (0, 3)), (self.save_button, 1, (3, 0))):
            widget.configure(height=30, font=font(10))
            widget.grid(row=0, column=column, sticky="ew", padx=padding)
        self.hex_var.trace_add("write", self._hex_changed)
        self.set_saved_color(initial)

    def set_color(self, color, *, preview=False, update_entry=True):
        color = parse_hex(color)
        if color is None:
            return
        self.color, self.valid = color, True
        self._syncing = True
        try:
            if update_entry:
                self.hex_var.set(color.upper())
            for offset, name in zip((1, 3, 5), ("R", "G", "B")):
                self.sliders[name].set(int(color[offset:offset + 2], 16))
            self.swatch.configure(fg_color=color)
            self.presets.set_color(color)
            self.save_button.configure(state="normal")
            self.hex_entry.configure(text_color=self.theme["text"])
            self.hint.configure(text="Preview on device", text_color=self.theme["subtle"])
        finally:
            self._syncing = False
        if preview:
            self.on_preview(color)

    def set_saved_color(self, color):
        self.original = color
        self.set_color(color)

    def open(self, color):
        self.set_saved_color(color)
        self.on_preview(self.color)

    def _from_sliders(self, value=None):
        self.set_color("#" + "".join(f"{self.sliders[name].get():02x}" for name in ("R", "G", "B")), preview=True)

    def set_preset(self, color):
        self.set_color(color, preview=True)

    def _hex_changed(self, *args):
        if self._syncing:
            return
        color = parse_hex(self.hex_var.get())
        self.valid = color is not None
        if color:
            self.set_color(color, preview=True, update_entry=False)
        else:
            self.save_button.configure(state="disabled")
            self.hint.configure(text="Use #RRGGBB", text_color=self.theme["subtle"])

    def _commit_hex(self, event=None):
        if self.valid:
            self.set_color(self.color)
        else:
            self.hint.configure(text="Use #RRGGBB", text_color=self.theme["red"])

    def save(self):
        if self.valid:
            self.on_save(self.color)

    def cancel(self):
        self.set_color(self.original)
        self.on_cancel()
