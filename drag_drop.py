"""Event-driven drag and drop for channel setups and dashboard section rows."""
import tkinter as tk


class DragDropController:
    def __init__(self, root, frames, name, on_drop, theme, hint=None):
        self.root, self.frames, self.name, self.on_drop = root, frames, name, on_drop
        self.theme, self.hint = theme, hint
        self.source = self.target = self.widget = self.ghost = None
        self.active = False
        self._styles = {}
        root.bind("<Escape>", lambda event: self.cancel(), add="+")
        root.bind("<Unmap>", lambda event: self.cancel() if event.widget is root else None, add="+")

    def register(self, key, widgets):
        for widget in widgets:
            widget.configure(cursor="fleur")
            widget.bind("<ButtonPress-1>", lambda event, source=key: self.press(source, event), add="+")
            widget.bind("<B1-Motion>", self.motion, add="+")
            widget.bind("<ButtonRelease-1>", self.release, add="+")

    def press(self, source, event):
        self.cancel()
        self.source, self.widget = source, event.widget
        self.start = (event.x_root, event.y_root)
        self._styles = {key: (frame.cget("border_width"), frame.cget("border_color"))
                        for key, frame in self.frames().items()}
        self.root.focus_set()

    def _target_at(self, x, y):
        for key, frame in self.frames().items():
            if frame.winfo_exists() and frame.winfo_ismapped():
                left, top = frame.winfo_rootx(), frame.winfo_rooty()
                if left <= x < left + frame.winfo_width() and top <= y < top + frame.winfo_height():
                    return key
        return None

    def motion(self, event):
        if self.source is None:
            return
        if not self.active:
            if abs(event.x_root - self.start[0]) + abs(event.y_root - self.start[1]) < 8:
                return
            self.active = True
            self.widget.grab_set()
            self.ghost = tk.Toplevel(self.root)
            self.ghost.withdraw()
            self.ghost.overrideredirect(True)
            self.ghost.attributes("-topmost", True)
            self.ghost.attributes("-alpha", 0.96)
            self.ghost.configure(bg=self.theme["border"])
            box = tk.Frame(self.ghost, bg=self.theme["raised"], padx=16, pady=10)
            box.pack(padx=1, pady=1)
            tk.Label(box, text=self.name(self.source), bg=self.theme["raised"], fg=self.theme["text"],
                     font=("Segoe UI", 12, "bold")).pack(anchor="w")
            tk.Label(box, text="Release to place · Esc to cancel", bg=self.theme["raised"],
                     fg=self.theme["muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))
        self.ghost.geometry(f"{event.x_root + 18:+d}{event.y_root + 18:+d}")
        self.ghost.deiconify()
        target = self._target_at(event.x_root, event.y_root)
        if target != self.target:
            self.target = target
            for key, frame in self.frames().items():
                border, color = self._styles[key]
                frame.configure(border_width=2 if key == target and key != self.source else border,
                                border_color=self.theme["accent"] if key == target and key != self.source else color)
            if self.hint:
                self.hint(self.source, target)

    def release(self, event):
        source = self.source
        target = self._target_at(event.x_root, event.y_root) if self.active else None
        self.cancel()
        if source is not None and target is not None and source != target:
            self.on_drop(source, target)

    def cancel(self):
        if self.active:
            for key, frame in self.frames().items():
                if frame.winfo_exists():
                    border, color = self._styles.get(key, (0, self.theme["border"]))
                    frame.configure(border_width=border, border_color=color)
            try:
                self.widget.grab_release()
            except tk.TclError:
                pass
        if self.ghost:
            self.ghost.destroy()
        self.source = self.target = self.widget = self.ghost = None
        self.active = False
        if self.hint:
            self.hint(None, None)
