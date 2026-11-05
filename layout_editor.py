"""A small live editor for the mixer dashboard's optional sections."""
import copy
import customtkinter as ctk

from dashboard_layout import DEFAULT_LAYOUT, move_widget
from drag_drop import DragDropController

NAMES = {"device": "Device view", "channels": "Mixer channels", "activity": "Activity strip"}


class LayoutEditor(ctk.CTkToplevel):
    def __init__(self, owner, theme, label, button, font):
        super().__init__(owner)
        self.owner, self.theme = owner, theme
        self.title("Customize mixer")
        self.geometry("500x450")
        self.resizable(False, False)
        self.configure(fg_color=theme["bg"])
        self.transient(owner)
        self.protocol("WM_DELETE_WINDOW", self.close)
        label(self, "Customize mixer", 22, weight="bold").pack(anchor="w", padx=24, pady=(22, 4))
        label(self, "Drag sections to reorder. Changes save automatically.", 12,
              theme["muted"]).pack(anchor="w", padx=24, pady=(0, 18))
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="x", padx=24)
        self.container.grid_columnconfigure(0, weight=1)
        self.rows, self.switches = {}, {}
        self.drag = DragDropController(self, lambda: self.rows, lambda key: NAMES[key],
                                        self.move, theme)
        for key, name in NAMES.items():
            row = ctk.CTkFrame(self.container, fg_color=theme["panel"], corner_radius=10,
                               border_width=0, border_color=theme["border"])
            self.rows[key] = row
            grip = label(row, "⠿", 18, theme["subtle"], width=26)
            grip.pack(side="left", padx=(12, 6), pady=14)
            title = label(row, name, 13, weight="bold")
            title.pack(side="left")
            self.drag.register(key, [row, grip, title])
            if key != "channels":
                variable = ctk.BooleanVar(value=key not in owner.dashboard_layout["hidden"])
                switch = ctk.CTkSwitch(row, text="", width=42, variable=variable,
                                       progress_color=theme["accent"],
                                       command=lambda name=key, value=variable: self.toggle(name, value.get()))
                switch.pack(side="right", padx=14)
                self.switches[key] = variable
            else:
                label(row, "Always visible", 10, theme["subtle"]).pack(side="right", padx=14)
        self.guides = ctk.BooleanVar(value=owner.dashboard_layout["guides"])
        self.guide_switch = ctk.CTkSwitch(self, text="Channel connection guides", variable=self.guides,
                                         font=font(12), progress_color=theme["accent"],
                                         command=self.toggle_guides)
        self.guide_switch.pack(anchor="w", padx=24, pady=(22, 20))
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(0, 20))
        button(footer, "Restore layout", self.restore, width=130).pack(side="left")
        button(footer, "Done", self.close, primary=True, width=90).pack(side="right")
        self.arrange()

    def arrange(self):
        for index, key in enumerate(self.owner.dashboard_layout["order"]):
            self.rows[key].grid(row=index, column=0, sticky="ew", pady=(0, 8))

    def move(self, source, target):
        self.owner.set_dashboard_layout(move_widget(self.owner.dashboard_layout, source, target))
        self.arrange()

    def toggle(self, key, visible):
        layout = copy.deepcopy(self.owner.dashboard_layout)
        layout["hidden"] = [name for name in layout["hidden"] if name != key]
        if not visible:
            layout["hidden"].append(key)
        self.owner.set_dashboard_layout(layout)

    def toggle_guides(self):
        layout = copy.deepcopy(self.owner.dashboard_layout)
        layout["guides"] = bool(self.guides.get())
        self.owner.set_dashboard_layout(layout)

    def restore(self):
        self.owner.set_dashboard_layout(copy.deepcopy(DEFAULT_LAYOUT))
        for variable in self.switches.values():
            variable.set(True)
        self.guides.set(True)
        self.arrange()

    def close(self):
        self.drag.cancel()
        self.owner._layout_editor = None
        self.destroy()
