"""An ordered app list for one hardware channel, edited on the GUI thread."""
import customtkinter as ctk
import tkinter as tk

from app_routing import priority_for, validate_app_name


class PriorityEditor(ctk.CTkToplevel):
    def __init__(self, owner, index, theme, label, button, font):
        super().__init__(owner)
        self.owner, self.index = owner, index
        self.profile_name = owner.config["active_profile"]
        channel = owner.config["channels"][index]
        self.draft = list(priority_for(channel) or [channel["app"]])
        self.title(f"Channel {index + 1} · App priority")
        self.geometry("570x540")
        self.minsize(530, 500)
        self.configure(fg_color=theme["bg"])
        self.transient(owner)
        self.protocol("WM_DELETE_WINDOW", self.close)
        label(self, f"Channel {index + 1} · App priority", 21, weight="bold").pack(
            anchor="w", padx=24, pady=(22, 4))
        label(self, "First running audio app wins. Move your favourite games to the top.",
              12, theme["muted"]).pack(anchor="w", padx=24)
        label(self, "No matching app: wait. Add master last if you want a Master fallback.",
              11, theme["subtle"]).pack(anchor="w", padx=24, pady=(4, 14))
        middle = ctk.CTkFrame(self, fg_color=theme["panel"], corner_radius=5)
        middle.pack(fill="both", expand=True, padx=24)
        middle.grid_columnconfigure(0, weight=1)
        middle.grid_rowconfigure(0, weight=1)
        self.listbox = tk.Listbox(middle, bg=theme["panel"], fg=theme["text"],
                                  selectbackground=theme["raised"], selectforeground=theme["text"],
                                  font=("Segoe UI", 12), borderwidth=0, highlightthickness=0,
                                  activestyle="none", exportselection=False)
        self.listbox.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        scroll = ctk.CTkScrollbar(middle, command=self.listbox.yview)
        scroll.grid(row=0, column=1, sticky="ns", pady=12)
        self.listbox.configure(yscrollcommand=scroll.set)
        controls = ctk.CTkFrame(middle, fg_color="transparent")
        controls.grid(row=0, column=2, padx=(8, 12), pady=12, sticky="n")
        button(controls, "Move up", lambda: self.move(-1), width=90).pack(pady=(0, 8))
        button(controls, "Move down", lambda: self.move(1), width=90).pack(pady=(0, 8))
        button(controls, "Remove", self.remove, width=90).pack()
        label(self, "Remembered audio apps · or type an executable name", 11, theme["muted"]).pack(
            anchor="w", padx=24, pady=(16, 6))
        add_row = ctk.CTkFrame(self, fg_color="transparent")
        add_row.pack(fill="x", padx=24)
        self.candidate = ctk.CTkComboBox(
            add_row, values=owner.available_routes(channel["app"]), font=font(12),
            height=34, fg_color=theme["raised"], border_width=0,
            button_color=theme["raised"], button_hover_color=theme["border"],
            dropdown_fg_color=theme["panel"], dropdown_hover_color=theme["raised"])
        self.candidate.pack(side="left", fill="x", expand=True)
        self.candidate.set(next((app for app in owner.available_routes(channel["app"])
                                 if app != "master" and app not in self.draft), ""))
        self.candidate.bind("<Return>", lambda event: self.add())
        button(add_row, "Add", self.add, width=72).pack(side="right", padx=(10, 0))
        self.error = label(self, "", 11, theme["red"])
        self.error.pack(anchor="w", padx=24, pady=(6, 8))
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(0, 22))
        button(footer, "Save priority list", lambda: self.apply(self.draft), primary=True,
               width=145).pack(side="left")
        button(footer, "Use single app", lambda: self.apply([]), width=130).pack(side="left", padx=8)
        button(footer, "Cancel", self.close, width=84).pack(side="right")
        self.redraw()
        self._focus_id = self.after(150, self._focus)

    def _focus(self):
        self._focus_id = None
        self.grab_set()
        self.lift()
        self.focus_force()

    def redraw(self, selected=0):
        self.listbox.delete(0, "end")
        for index, app in enumerate(self.draft):
            self.listbox.insert("end", f"{index + 1:02d}   {app}")
        if self.draft:
            self.listbox.selection_set(min(selected, len(self.draft) - 1))
        self.error.configure(text="")

    def add(self):
        try:
            name = validate_app_name(self.candidate.get())
            if name in self.draft:
                raise ValueError("This app is already in the list.")
        except ValueError as error:
            self.error.configure(text=str(error))
            return
        self.draft.append(name)
        self.redraw(len(self.draft) - 1)
        self.listbox.see("end")

    def move(self, direction):
        selection = self.listbox.curselection()
        if not selection:
            return
        index, target = selection[0], selection[0] + direction
        if 0 <= target < len(self.draft):
            self.draft[index], self.draft[target] = self.draft[target], self.draft[index]
            self.redraw(target)
            self.listbox.see(target)

    def remove(self):
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            del self.draft[index]
            self.redraw(index)

    def apply(self, names):
        if names is self.draft and not names:
            self.error.configure(text="Add at least one app, or choose Use single app.")
            return
        if self.profile_name != self.owner.config["active_profile"]:
            self.close()
            return
        self.owner.set_channel_priority(self.index, names)
        self.close()

    def refresh_choices(self):
        channel = self.owner.config["channels"][self.index]
        self.candidate.configure(values=self.owner.available_routes(channel["app"]))

    def close(self):
        if self._focus_id:
            self.after_cancel(self._focus_id)
            self._focus_id = None
        self.grab_release()
        self.owner._priority_editor = None
        self.destroy()
