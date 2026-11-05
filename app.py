import customtkinter as ctk
import tkinter as tk
import time
import threading
import keyboard
import json
import os
import math
import sys
import copy
import queue
import logging
import argparse
from pathlib import Path
from tkinter import messagebox
from mixer_runtime import MixerEngine, MixerState, AppDiscovery, list_audio_apps as get_active_audio_apps
from tray_icon import MixerTray
from windows_startup import WindowsStartup, AutoConnect
from single_instance import SingleInstance, activate_window
import profiles
from mixer_runtime import list_mixer_ports
from tray_icon import icon_image
from device_view import ProductView
from app_routing import initialize_library, priority_for, resolve_routes, normalize_apps
from priority_editor import PriorityEditor
from dashboard_layout import normalize_layout, swap_channels
from drag_drop import DragDropController
from layout_editor import LayoutEditor
from app_icons import AppIconCache
from studio_widgets import AppSelector, StudioFader, DebouncedCanvas, friendly_name
from colour_editor import InlineColourEditor
from app_paths import config_path, migrate_legacy_config, resource_path
from diagnostics import configure_logging
from power_events import PowerSession, WindowsPowerMonitor
from mixer_version import VERSION

# ==================== PERSISTENCE ====================
CONFIG_FILE = config_path()
DEFAULT_CONFIG = {
    "auto_connect": False,
    "brightness": 45,
    "channels": [
        {"app": "javaw.exe", "color": "#A000FF"}, {"app": "spotify.exe", "color": "#1ED760"},
        {"app": "chrome.exe", "color": "#EB3223"}, {"app": "discord.exe", "color": "#5865F2"}
    ],
    "hotkeys": {"mute": "ctrl+shift+f11", "deafen": "ctrl+shift+f12"}
}

def load_config():
    try:
        migrate_legacy_config(destination=CONFIG_FILE)
    except OSError:
        logging.exception("Could not migrate previous mixer settings")
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                config = json.load(f)
            if not isinstance(config, dict):
                raise ValueError("Settings must be a JSON object")
            config.setdefault("auto_connect", False)
            return config
        except (OSError, ValueError, UnicodeError):
            logging.exception("Could not read mixer settings from %s", CONFIG_FILE)
    return copy.deepcopy(DEFAULT_CONFIG)

def save_config(config_dict):
    profiles.remember(config_dict)
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = CONFIG_FILE.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=4)
        temporary.replace(CONFIG_FILE)
    except OSError:
        logging.exception("Could not save mixer settings")

# ==================== GUI COMPONENTS ====================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")
# The theme is fixed. Reduce the toolkit's periodic appearance checks as well
# as our own painting work; default CustomTkinter checks every 30 milliseconds.
ctk.AppearanceModeTracker.update_loop_interval = 1000

THEME = {
    "bg": "#0D0D0F", "sidebar": "#141417", "panel": "#1C1C21",
    "raised": "#28282F", "border": "#34343D", "text": "#F1F1F3",
    "muted": "#B5B5BF", "subtle": "#93939E", "accent": "#91BFFF",
    "accent_hover": "#B3D3FF", "green": "#82CCA4", "red": "#F49C9C",
    "selection": "#293C55", "hover": "#32323B", "panel_hover": "#222228",
    "dim_panel": "#17171C", "well": "#111114",
}


def ui_font(size=13, weight="normal", family="Segoe UI"):
    return ctk.CTkFont(family=family, size=size, weight=weight)


def ui_label(parent, text, size=13, color=None, weight="normal", **kwargs):
    kwargs.setdefault("height", max(14, int(size * 1.4)))
    return ctk.CTkLabel(parent, text=text, font=ui_font(size, weight),
                        text_color=color or THEME["text"], **kwargs)


def ui_button(parent, text, command=None, primary=False, **kwargs):
    kwargs.setdefault("border_width", 0)
    return ctk.CTkButton(
        parent, text=text, command=command, height=34, corner_radius=8,
        font=ui_font(12, "bold" if primary else "normal"),
        fg_color=THEME["accent"] if primary else THEME["raised"],
        hover_color=THEME["accent_hover"] if primary else THEME["hover"],
        text_color=THEME["bg"] if primary else THEME["text"], **kwargs)


class SegmentedMeter(DebouncedCanvas):
    """Ten inexpensive LED segments, matching the hardware's channel length."""
    def __init__(self, parent, color):
        super().__init__(parent, width=18, height=100, bg=THEME["well"], highlightthickness=0)
        self.color = color
        self.level = 0
        self.segments = []
        self.lit = None

    def _redraw(self, width, total_height):
        self.delete("all")
        height = max(1, (total_height - 27) / 10)
        self.segments = [self.create_rectangle(1, total_height - (i + 1) * (height + 3) + 3,
                                              max(2, width - 1), total_height - i * (height + 3),
                                              fill=THEME["raised"], outline="") for i in range(10)]
        self.lit = None
        self.set_level(self.level)

    def set_level(self, level):
        self.level = max(0, min(100, level))
        lit = min(10, math.ceil(self.level / 10))
        if lit != self.lit:
            for i, segment in enumerate(self.segments):
                self.itemconfigure(segment, fill=self.color if i < lit else THEME["raised"])
            self.lit = lit

    def set_color(self, color):
        self.color = color
        self.lit = None
        self.set_level(self.level)


class MixerApp(ctk.CTk):
    def __init__(self, *, start_services=True, start_hidden=False, instance_guard=None):
        super().__init__()
        if start_hidden:
            self.withdraw()
        self.config = load_config()
        profiles.initialize(self.config)
        initialize_library(self.config)
        self.known_apps = set(self.config["known_apps"])
        self._priority_editor = None
        self._layout_editor = None
        self._undo_swap = None
        self.dashboard_layout = normalize_layout(self.config.get("dashboard_layout"))
        self.config["dashboard_layout"] = self.dashboard_layout
        self.instance_guard = instance_guard
        self.title("Mixer Hub")
        self.geometry("1180x880")
        self.minsize(1000, 760)
        self.configure(fg_color=THEME["bg"])
        # The same four-fader mark appears in the title bar and Windows tray.
        self._window_icon = tk.PhotoImage(data=self._icon_png())
        self.after(350, self.set_window_icon)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.engine = MixerEngine(self.config)
        self.power_session = PowerSession()
        self.power_monitor = None
        self.auto_connect = AutoConnect(self.config.get("auto_connect", False))
        self.windows_startup = WindowsStartup(Path(__file__))
        self._actions = queue.SimpleQueue()
        self._closing = False
        self._hidden = start_hidden
        self._start_hidden_pending = start_hidden and start_services
        self._tray_deadline = time.monotonic() + 4
        self._page = "mixer"
        self._poll_id = None
        self._save_id = None
        self._window_resize_job = None
        self._requested_window_size = None
        self._last_state = None
        self._eq_mode = False
        self.last_eq_levels = [-1] * 4
        self._display_leds = [0.0] * 4
        self._last_meter_time = time.monotonic()
        self._scaling_poll_interval = ctk.ScalingTracker.update_loop_interval
        if start_hidden:
            ctk.ScalingTracker.update_loop_interval = 1000
        self.tray = None
        self.discovery = None
        self.is_connected = False
        self.last_percentages = [-1, -1, -1, -1]
        self.channels = []
        self.icon_cache = AppIconCache()
        self._hovered_card = None
        self.channel_drag = DragDropController(
            self, lambda: {index: channel["card"] for index, channel in enumerate(self.channels)},
            lambda index: f"{self.channels[index]['app_title'].cget('text')} · Channel {index + 1}",
            self.swap_channel_setups, THEME, self.channel_drag_hint)
        self.active_apps = get_active_audio_apps()
        self.remember_audio_apps(self.active_apps)
        self.build_sidebar()
        self.build_dashboard()
        self.apply_dashboard_layout()
        self.build_settings()
        self.bind("<Configure>", self.resize_device_panel, add="+")
        self.bind("<Motion>", self.track_card_hover, add="+")
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        if start_services:
            try:
                self.power_monitor = WindowsPowerMonitor(self.winfo_id(), self.handle_power_event)
            except OSError:
                logging.exception("Windows power notifications unavailable; firmware timeout remains active")
            self.discovery = AppDiscovery(lambda: not self.engine.running,
                                           lambda names: self._actions.put(("apps", names)))
            self.discovery.start()
            try:
                self.tray = MixerTray(self._actions)
                self.tray.start()
            except Exception:
                logging.exception("Could not start tray icon")
                self.tray = None
            self._poll_id = self.after(50, self.poll_runtime)

    @staticmethod
    def _icon_png():
        import base64
        import io
        buffer = io.BytesIO()
        icon_image().save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    def set_window_icon(self):
        if self._closing:
            return
        try:
            icon = str(resource_path("assets/app_icon.ico"))
            self.iconbitmap(icon)
            self.iconbitmap(default=icon)
        except tk.TclError:
            self.iconphoto(True, self._window_icon)

    def report_callback_exception(self, kind, value, traceback):
        logging.error("Interface callback failed", exc_info=(kind, value, traceback))

    def build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(
            self, width=216, corner_radius=0, fg_color=THEME["sidebar"])
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        brand = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand.grid(row=0, column=0, padx=22, pady=(30, 35), sticky="ew")
        mark = tk.Canvas(brand, width=34, height=36, bg=THEME["sidebar"],
                         highlightthickness=0)
        mark.pack(side="left", padx=(0, 12))
        for x, y in [(5, 13), (13, 24), (21, 10), (29, 19)]:
            mark.create_line(x, 5, x, 31, fill=THEME["border"], width=2)
            mark.create_line(x, y, x, 31, fill=THEME["accent"], width=2)
            mark.create_rectangle(x - 3, y - 2, x + 3, y + 2, fill=THEME["text"], outline="")
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left")
        ui_label(brand_text, "Mixer Hub", 18, weight="bold").pack(anchor="w")
        ui_label(brand_text, "4-channel controller", 11, THEME["subtle"]).pack(anchor="w")

        ui_label(self.sidebar_frame, "Workspace", 11, THEME["subtle"]).grid(
            row=1, column=0, padx=24, pady=(0, 10), sticky="w")
        self.btn_dashboard = ui_button(
            self.sidebar_frame, "  Mixer", self.show_dashboard_page,
            width=172, anchor="w")
        self.btn_dashboard.configure(fg_color=THEME["raised"], text_color=THEME["accent"])
        self.btn_dashboard.grid(row=2, column=0, padx=18, pady=(0, 8), sticky="ew")
        self.btn_settings = ui_button(
            self.sidebar_frame, "  Device settings", self.show_settings_page,
            width=172, anchor="w")
        self.btn_settings.configure(fg_color="transparent", text_color=THEME["muted"])
        self.btn_settings.grid(row=3, column=0, padx=18, sticky="ew")

        brightness = ctk.CTkFrame(self.sidebar_frame, corner_radius=12,
                                  fg_color=THEME["panel"])
        brightness.grid(row=5, column=0, padx=18, pady=(15, 12), sticky="ew")
        brightness.grid_columnconfigure(0, weight=1)
        ui_label(brightness, "LED brightness", 12, THEME["muted"]).grid(
            row=0, column=0, padx=(14, 0), pady=(12, 0), sticky="w")
        self.brightness_value = ui_label(
            brightness, f"{round(self.config['brightness'] / 255 * 100)}%", 12,
            THEME["accent"], "bold")
        self.brightness_value.grid(row=0, column=1, padx=(5, 14), pady=(12, 0))
        self.bright_slider = ctk.CTkSlider(
            brightness, from_=0, to=255, width=144, height=16,
            fg_color=THEME["border"], progress_color=THEME["accent"],
            button_color=THEME["accent"], button_hover_color=THEME["accent_hover"],
            command=self.change_brightness)
        self.bright_slider.set(self.config["brightness"])
        self.bright_slider.grid(row=1, column=0, columnspan=2,
                                padx=14, pady=(12, 18), sticky="ew")

        device = ctk.CTkFrame(self.sidebar_frame, corner_radius=12,
                              fg_color=THEME["panel"], border_width=0,
                              border_color=THEME["border"])
        device.grid(row=6, column=0, padx=18, pady=(0, 16), sticky="ew")
        ui_label(device, "YOUR DEVICE", 10, THEME["subtle"], "bold").pack(
            anchor="w", padx=14, pady=(14, 2))
        ui_label(device, "Arduino Nano", 14, weight="bold").pack(anchor="w", padx=14)
        self.status_label = ui_label(device, "● Disconnected", 11, THEME["muted"])
        self.status_label.pack(anchor="w", padx=14, pady=(1, 12))
        self.btn_connect = ui_button(device, "Connect device", self.toggle_connection,
                                     primary=True, width=148)
        self.btn_connect.pack(fill="x", padx=14, pady=(0, 14))
        ui_label(self.sidebar_frame, "Close window to keep mixing", 10, THEME["subtle"]).grid(
            row=7, column=0, padx=20, pady=(0, 20), sticky="w")

    def build_dashboard(self):
        self.dashboard_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dashboard_frame.grid(row=0, column=1, padx=28, pady=26, sticky="nsew")
        self.dashboard_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="channel")
        self.dashboard_frame.grid_rowconfigure(3, weight=1)

        heading = self.dashboard_heading = ctk.CTkFrame(self.dashboard_frame, fg_color="transparent")
        heading.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 20))
        heading.grid_columnconfigure(0, weight=1)
        ui_label(heading, "Mixer", 26, weight="bold").grid(
            row=1, column=0, sticky="w", pady=(2, 0))
        self.btn_refresh = ui_button(heading, "Refresh apps", self.refresh_dropdowns, width=120)
        self.btn_refresh.grid(row=1, column=1, rowspan=2, padx=(15, 0))
        self.btn_customize = ui_button(heading, "Customize", self.open_layout_editor, width=108)
        self.btn_customize.grid(row=1, column=2, rowspan=2, padx=(8, 0))
        profile_bar = ctk.CTkFrame(heading, fg_color="transparent")
        profile_bar.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        ui_label(profile_bar, "Profile", 12, THEME["muted"]).pack(side="left", padx=(0, 10))
        self.profile_menu = ctk.CTkOptionMenu(
            profile_bar, values=list(self.config["profiles"]), command=self.select_profile,
            width=170, height=32, corner_radius=8, dynamic_resizing=False,
            fg_color=THEME["raised"], button_color=THEME["raised"],
            button_hover_color=THEME["border"], dropdown_fg_color=THEME["raised"],
            dropdown_hover_color=THEME["border"], font=ui_font(12))
        self.profile_menu.set(self.config["active_profile"])
        self.profile_menu.pack(side="left")
        ui_button(profile_bar, "+ New", self.new_profile, width=66).pack(side="left", padx=(8, 0))
        self.profile_actions = ctk.CTkOptionMenu(
            profile_bar, values=["Rename profile", "Delete profile"], command=self.manage_profile,
            width=96, height=32, corner_radius=8, dynamic_resizing=False, font=ui_font(12),
            fg_color=THEME["raised"], button_color=THEME["raised"],
            button_hover_color=THEME["border"], dropdown_fg_color=THEME["raised"])
        self.profile_actions.set("Manage")
        self.profile_actions.pack(side="left", padx=(8, 0))
        ui_label(profile_bar, "Saved automatically", 11, THEME["subtle"]).pack(side="right")

        self.hero_frame = ctk.CTkFrame(
            self.dashboard_frame, height=155, corner_radius=0, fg_color="transparent")
        self.hero_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        self.hero_frame.grid_propagate(False)
        self.hero_frame.grid_columnconfigure(0, weight=1)
        self.hero_frame.grid_rowconfigure(1, weight=1)
        device_copy = ctk.CTkFrame(self.hero_frame, fg_color="transparent")
        device_copy.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.device_title = ui_label(device_copy, "Your mixer", 12, weight="bold")
        self.device_title.pack(side="left")
        self.device_hint = ui_label(device_copy, "Channels run left to right on your device.", 11,
                                    THEME["muted"])
        self.device_hint.pack(side="left", padx=(14, 0))
        self.render_toggle = ctk.CTkSegmentedButton(
            device_copy, values=["Top", "Side"], command=self.change_render_view,
            width=110, height=24, font=ui_font(11), corner_radius=4,
            fg_color=THEME["raised"], selected_color=THEME["border"],
            selected_hover_color=THEME["border"], unselected_color=THEME["bg"],
            unselected_hover_color=THEME["raised"], text_color=THEME["text"])
        self.render_toggle.pack(side="right")
        self.render_toggle.set("Top")
        self.device_view = ProductView(self.hero_frame, THEME)
        self.device_view.target_provider = self.preview_channel_centers
        self.device_view.grid(row=1, column=0, sticky="nsew")
        if self.device_view.sources:
            self.render_toggle.configure(values=[name.title() for name in self.device_view.sources])
            self.render_toggle.set(self.device_view.view.title())
        if len(self.device_view.sources) < 2:
            self.render_toggle.configure(state="disabled")
        self.draw_device()

        channel_heading = self.channel_heading = ctk.CTkFrame(self.dashboard_frame, fg_color="transparent")
        channel_heading.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0, 4))
        ui_label(channel_heading, "Channels", 13, weight="bold").pack(side="left")
        self.channel_hint = ui_label(channel_heading, "Drag a channel to swap its setup", 11, THEME["subtle"])
        self.channel_hint.pack(side="left", padx=(12, 0))
        self.undo_swap_btn = ui_button(channel_heading, "Undo swap", self.undo_channel_swap, width=88)
        self.undo_swap_btn.configure(height=26, font=ui_font(10))
        self.mode_label = ui_label(channel_heading, "LEDs follow device output", 11,
                 THEME["subtle"])
        self.mode_label.pack(side="right")
        for i in range(4):
            self.create_channel_card(i)

        self.diag_frame = ctk.CTkFrame(self.dashboard_frame, height=48,
                                      corner_radius=10, fg_color=THEME["panel"])
        self.diag_frame.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(16, 0))
        self.diag_frame.grid_propagate(False)
        self.diag_frame.grid_columnconfigure(1, weight=1)
        self.stat_port = ui_label(self.diag_frame, "USB  /  No device", 11, THEME["muted"])
        self.stat_port.grid(row=0, column=0, padx=16, pady=10, sticky="w")
        self.stat_audio = ui_label(self.diag_frame, "Audio Sync: Idle", 11, THEME["subtle"])
        self.stat_audio.grid(row=0, column=1, padx=12, sticky="w")
        ui_label(self.diag_frame, "MASTER PEAK", 10, THEME["subtle"], "bold").grid(
            row=0, column=2, padx=(10, 12))
        self.vis_bar = ctk.CTkProgressBar(
            self.diag_frame, width=100, height=6, fg_color=THEME["border"],
            progress_color=THEME["green"])
        self.vis_bar.set(0)
        self.vis_bar.grid(row=0, column=3, padx=(0, 16))

    @staticmethod
    def app_identity(app_name):
        return friendly_name(app_name), app_name[:2].upper()

    def available_routes(self, saved_app):
        # An inactive saved route must never silently become master volume.
        return list(dict.fromkeys([*self.active_apps, *sorted(self.known_apps), saved_app]))

    def create_channel_card(self, col_index):
        saved_color = self.config["channels"][col_index]["color"]
        saved_app = self.config["channels"][col_index]["app"]
        if col_index == 0:
            self.console_frame = ctk.CTkFrame(self.dashboard_frame, corner_radius=0,
                                             fg_color="transparent")
            self.console_frame.grid(row=3, column=0, columnspan=4, sticky="nsew")
            self.console_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="strip")
            self.console_frame.grid_rowconfigure(0, weight=1)
        card = ctk.CTkFrame(self.console_frame, corner_radius=12, fg_color=THEME["panel"],
                           border_width=0)
        card.grid(row=0, column=col_index, padx=(0 if col_index == 0 else 5,
                                              0 if col_index == 3 else 5), pady=2, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)
        front_view = ctk.CTkFrame(card, fg_color="transparent")
        front_view.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        front_view.grid_columnconfigure(0, weight=1)
        front_view.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(front_view, fg_color="transparent")
        top.grid(row=0, column=0, padx=12, pady=(12, 10), sticky="ew")
        channel_number = ui_label(top, f"Channel {col_index + 1}", 11, THEME["muted"])
        channel_number.pack(side="left")
        header = ctk.CTkFrame(front_view, fg_color="transparent")
        header.grid(row=1, column=0, padx=8, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        app_icon = ui_label(header, "", width=28, height=28)
        app_icon.grid(row=0, column=0, padx=(0, 4))
        dropdown = AppSelector(
            header, values=self.available_routes(saved_app), width=68, height=32,
            corner_radius=6, fg_color=THEME["panel"], button_color=THEME["panel"],
            button_hover_color=THEME["raised"], text_color=THEME["text"],
            dropdown_fg_color=THEME["raised"], dropdown_hover_color=THEME["border"],
            dropdown_text_color=THEME["text"], font=ui_font(13, "bold"), dropdown_font=ui_font(12),
            dynamic_resizing=False, command=lambda value, idx=col_index: self.save_app_selection(idx, value))
        dropdown.grid(row=0, column=1, sticky="ew")
        dropdown.set(saved_app)
        app_title = dropdown._text_label
        grip = ui_label(header, "⠿", 15, THEME["subtle"], width=14)
        grip.grid(row=0, column=2, padx=(3, 0))

        fader = ctk.CTkFrame(front_view, fg_color=THEME["well"], corner_radius=12, height=90)
        fader.grid(row=2, column=0, padx=10, pady=(16, 12), sticky="nsew")
        fader.grid_rowconfigure(0, weight=1)
        fader.grid_columnconfigure(0, weight=1)
        slider = StudioFader(fader, saved_color, fader._get_widget_scaling)
        slider.set(0)
        slider.grid(row=0, column=0, padx=(12, 6), pady=12, sticky="nsew")
        led_meter = SegmentedMeter(fader, saved_color)
        led_meter.grid(row=0, column=1, padx=(2, 12), pady=18, sticky="ns")

        vol_label = ui_label(front_view, "Idle", 19, THEME["muted"], "bold", width=92, height=34,
                             fg_color=THEME["raised"], corner_radius=17)
        vol_label.grid(row=3, column=0, pady=(0, 12))
        color_preview = ctk.CTkFrame(front_view, height=2, corner_radius=1, fg_color=saved_color)
        color_preview.grid(row=4, column=0, padx=24, pady=(0, 10), sticky="ew")
        actions = ctk.CTkFrame(front_view, fg_color="transparent")
        actions.grid(row=5, column=0, padx=10, pady=(0, 12), sticky="ew")
        actions.grid_columnconfigure((0, 1), weight=1)
        priority_btn = ui_button(actions, "≡ Priority", lambda: self.open_priority_editor(col_index), width=72)
        priority_btn.configure(height=30, font=ui_font(10), border_width=0)
        priority_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        color_btn = ui_button(actions, "Colour", width=52)
        color_btn.configure(height=30, font=ui_font(10), border_width=0)
        color_btn.grid(row=0, column=1, sticky="ew", padx=(3, 0))

        def update_live(hx):
            self.engine.preview_color(col_index, hx)
            self.channels[col_index]["led_meter"].set_color(hx)
            self.draw_device()

        def show_front():
            back_view.grid_forget()
            front_view.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        def save_color(hx):
            self.config["channels"][col_index]["color"] = hx
            save_config(self.config)
            self.sync_settings()
            self.engine.preview_color(col_index)
            self.apply_channel_color(col_index, hx)
            show_front()

        def cancel_color():
            self.engine.preview_color(col_index)
            self.channels[col_index]["led_meter"].set_color(self.config["channels"][col_index]["color"])
            self.draw_device()
            show_front()

        back_view = InlineColourEditor(card, col_index, saved_color, THEME, ui_label, ui_button, ui_font,
                                        on_preview=update_live, on_save=save_color, on_cancel=cancel_color)

        def show_editor():
            back_view.open(self.config["channels"][col_index]["color"])
            front_view.grid_forget()
            back_view.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        color_btn.configure(command=show_editor)
        self.channels.append({
            "slider": slider, "vol_label": vol_label,
            "dropdown": dropdown, "color_preview": color_preview, "back_view": back_view,
            "front_view": front_view, "slider_r": back_view.sliders["R"], "slider_g": back_view.sliders["G"],
            "slider_b": back_view.sliders["B"], "live_color_box": back_view.swatch, "hex_entry": back_view.hex_entry,
            "app_icon": app_icon, "app_title": app_title, "color_btn": color_btn,
            "save_color_btn": back_view.save_button, "cancel_color_btn": back_view.cancel_button,
            "led_meter": led_meter,
            "priority_btn": priority_btn,
            "card": card, "grip": grip, "well": fader,
        })
        self.channel_drag.register(col_index, [card, front_view, top, channel_number, grip,
                                               app_icon, vol_label, fader])
        self.update_app_identity(col_index)

    def draw_device(self):
        if "device" in self.dashboard_layout["hidden"]:
            return
        colors = tuple(self.channels[index]["led_meter"].color if index < len(self.channels)
                       else channel["color"] for index, channel in enumerate(self.config["channels"]))
        self.device_view.set_state(self.last_percentages, self._display_leds, colors, self.is_connected)

    def manage_profile(self, action):
        self.profile_actions.set("Manage")
        if action == "Rename profile":
            self.rename_profile()
        elif action == "Delete profile":
            self.delete_profile()

    def change_render_view(self, view):
        layout = copy.deepcopy(self.dashboard_layout)
        layout["view"] = view.lower()
        self.set_dashboard_layout(layout)

    def open_layout_editor(self):
        self.channel_drag.cancel()
        if self._layout_editor:
            self._layout_editor.lift()
            self._layout_editor.focus_force()
            return
        self._layout_editor = LayoutEditor(self, THEME, ui_label, ui_button, ui_font)

    def set_dashboard_layout(self, layout):
        self.dashboard_layout = normalize_layout(layout)
        self.config["dashboard_layout"] = copy.deepcopy(self.dashboard_layout)
        self.apply_dashboard_layout()
        save_config(self.config)

    def apply_dashboard_layout(self):
        self.channel_drag.cancel()
        for row in range(1, 6):
            self.dashboard_frame.grid_rowconfigure(row, weight=0)
        self.hero_frame.grid_remove()
        self.diag_frame.grid_remove()
        visible_order = [key for key in self.dashboard_layout["order"] if key not in self.dashboard_layout["hidden"]]
        linked_preview = ("device" in visible_order and visible_order.index("device") + 1 < len(visible_order)
                          and visible_order[visible_order.index("device") + 1] == "channels")
        row = 1
        for key in self.dashboard_layout["order"]:
            if key in self.dashboard_layout["hidden"]:
                continue
            if key == "channels":
                if not linked_preview:
                    self.channel_heading.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(0, 4))
                    row += 1
                self.console_frame.grid(row=row, column=0, columnspan=4, sticky="nsew")
                self.dashboard_frame.grid_rowconfigure(row, weight=1)
                row += 1
            else:
                if key == "device" and linked_preview:
                    self.channel_heading.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(0, 10))
                    row += 1
                widget = self.hero_frame if key == "device" else self.diag_frame
                widget.grid(row=row, column=0, columnspan=4, sticky="ew",
                            pady=(0, 0 if key == "device" and linked_preview else 14))
                row += 1
        self.device_view.set_view(self.dashboard_layout["view"])
        self.render_toggle.set(self.device_view.view.title())
        order = self.dashboard_layout["order"]
        self.device_view.set_guides(visible=self.dashboard_layout["guides"],
                                    direction="down" if order.index("device") < order.index("channels") else "up")
        self.draw_device()

    def channel_drag_hint(self, source, target):
        if not hasattr(self, "channel_hint") or not self.channel_hint.winfo_exists():
            return
        text = "Drag a channel to swap its setup"
        if source is not None:
            text = (f"Release to swap channels {source + 1} and {target + 1}"
                    if target is not None and source != target else "Drop on another channel · Esc to cancel")
        self.channel_hint.configure(text=text)

    def swap_channel_setups(self, source, target, *, remember=True):
        if not swap_channels(self.config, source, target):
            return
        self.apply_setup()
        save_config(self.config)
        if remember:
            self._undo_swap = (source, target, self.config["active_profile"])
            self.undo_swap_btn.pack(side="right", padx=(10, 0))

    def undo_channel_swap(self):
        if self._undo_swap and self._undo_swap[2] == self.config["active_profile"]:
            source, target, _ = self._undo_swap
            self.swap_channel_setups(source, target, remember=False)

    def clear_channel_undo(self):
        self._undo_swap = None
        self.undo_swap_btn.pack_forget()

    def resize_device_panel(self, event):
        if event.widget is not self:
            return
        size = (event.width, event.height)
        if size == self._requested_window_size:
            return
        self._requested_window_size = size
        if self._window_resize_job:
            self.after_cancel(self._window_resize_job)
        self._window_resize_job = self.after(60, self.apply_window_resize)

    def apply_window_resize(self):
        self._window_resize_job = None
        # Reserve vertical space for readable fader travel on smaller displays.
        logical_height = self._requested_window_size[1] / self._get_window_scaling()
        height = round(max(150, min(238, logical_height - 650)) * 0.65)
        if self.hero_frame.cget("height") != height:
            self.hero_frame.configure(height=height)

    def preview_channel_centers(self):
        if len(self.channels) != 4 or self.device_view.winfo_width() <= 1:
            return None
        origin = self.device_view.winfo_rootx()
        return tuple(channel["card"].winfo_rootx() + channel["card"].winfo_width() / 2 - origin
                     for channel in self.channels)

    def track_card_hover(self, event):
        if self._hidden or self._page != "mixer":
            return
        hovered = None
        for index, channel in enumerate(self.channels):
            card = channel["card"]
            x, y = card.winfo_rootx(), card.winfo_rooty()
            if card.winfo_ismapped() and x <= event.x_root < x + card.winfo_width() and y <= event.y_root < y + card.winfo_height():
                hovered = index
                break
        if hovered != self._hovered_card:
            previous, self._hovered_card = self._hovered_card, hovered
            for index in (previous, hovered):
                if index is not None:
                    self.paint_channel_surface(index)

    def paint_channel_surface(self, index):
        channel = self.channels[index]
        color = (THEME["panel_hover"] if index == self._hovered_card else
                 THEME["panel"] if self.is_connected else THEME["dim_panel"])
        channel["card"].configure(fg_color=color)
        channel["dropdown"].configure(fg_color=color, button_color=color,
                                       text_color=THEME["text"] if self.is_connected else THEME["subtle"],
                                       text_color_disabled=THEME["muted"] if self.is_connected else THEME["subtle"])
        channel["slider"].set_connected(self.is_connected)

    def update_volume_pill(self, index):
        percent = self.last_percentages[index]
        text = ("MUTED" if percent == 0 else f"{percent}%") if percent >= 0 else (
            "Ready" if self.is_connected else "Idle")
        self.channels[index]["vol_label"].configure(
            text=text, text_color=THEME["text"] if self.is_connected and percent > 0 else THEME["subtle"],
            fg_color=THEME["raised"] if self.is_connected else THEME["panel"])

    def apply_channel_color(self, index, hx):
        ch = self.channels[index]
        ch["color_preview"].configure(fg_color=hx)
        ch["back_view"].set_saved_color(hx)
        ch["slider"].configure(progress_color=hx)
        ch["led_meter"].set_color(hx)
        self.draw_device()

    def build_settings(self):
        self.settings_frame = ctk.CTkScrollableFrame(
            self, fg_color=THEME["bg"], corner_radius=0,
            scrollbar_button_color=THEME["border"], scrollbar_button_hover_color=THEME["subtle"])
        header = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 24))
        ui_label(header, "DEVICE", 10, THEME["accent"], "bold").pack(anchor="w")
        ui_label(header, "Settings", 26, weight="bold").pack(anchor="w", pady=(2, 0))
        ui_label(header, "Hotkeys, hardware controls and background operation", 12, THEME["muted"]).pack(anchor="w")

        device_panel = ctk.CTkFrame(self.settings_frame, corner_radius=5,
                                   fg_color=THEME["panel"], border_width=0, border_color=THEME["border"])
        device_panel.pack(fill="x", pady=(0, 18))
        ui_label(device_panel, "Mixer connection", 18, weight="bold").pack(anchor="w", padx=24, pady=(20, 4))
        ui_label(device_panel, "Choose your USB mixer if more than one serial device is connected.",
                 12, THEME["muted"]).pack(anchor="w", padx=24)
        device_row = ctk.CTkFrame(device_panel, fg_color="transparent")
        device_row.pack(fill="x", padx=24, pady=(14, 8))
        self.device_menu = ctk.CTkOptionMenu(
            device_row, values=["Automatic detection"], command=self.select_device,
            width=350, height=32, dynamic_resizing=False, fg_color=THEME["raised"],
            button_color=THEME["raised"], button_hover_color=THEME["border"],
            dropdown_fg_color=THEME["raised"], dropdown_hover_color=THEME["border"], font=ui_font(12))
        self.device_menu.pack(side="left", fill="x", expand=True)
        ui_button(device_row, "Refresh", self.refresh_devices, width=90).pack(side="right", padx=(12, 0))
        self.device_selection_hint = ui_label(device_panel, "", 11, THEME["subtle"])
        self.device_selection_hint.pack(anchor="w", padx=24, pady=(0, 18))
        self.refresh_devices()

        hotkey_panel = ctk.CTkFrame(self.settings_frame, corner_radius=12,
                                   fg_color=THEME["panel"], border_width=0, border_color=THEME["border"])
        hotkey_panel.pack(fill="x", pady=(0, 18))
        ui_label(hotkey_panel, "Discord shortcuts", 18, weight="bold").pack(
            anchor="w", padx=24, pady=(22, 4))
        ui_label(hotkey_panel, "Match these to your keybinds in Discord's settings.",
                 12, THEME["muted"]).pack(anchor="w", padx=24, pady=(0, 10))
        self.mute_btn, self.mute_box = self.create_recorder_row(hotkey_panel, "Toggle mute", "mute")
        self.deaf_btn, self.deaf_box = self.create_recorder_row(hotkey_panel, "Toggle deafen", "deafen")
        ui_label(hotkey_panel, "Click Record, then press your key combination.", 11,
                 THEME["subtle"]).pack(anchor="w", padx=24, pady=(0, 22))

        controls = ctk.CTkFrame(self.settings_frame, corner_radius=12, fg_color=THEME["panel"],
                               border_width=0, border_color=THEME["border"])
        controls.pack(fill="x", pady=(0, 18))
        ui_label(controls, "Hardware buttons", 18, weight="bold").pack(anchor="w", padx=24, pady=(22, 4))
        self.hardware_button_hint = ui_label(controls, "Your five physical buttons, from left to right.", 12,
                                             THEME["muted"])
        self.hardware_button_hint.pack(anchor="w", padx=24)
        row = ctk.CTkFrame(controls, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(18, 24))
        self.hardware_buttons = []
        self._hardware_button_active = [None] * 5
        for i, name in enumerate(["Previous", "Play / pause", "Next", "Deafen", "Mute"]):
            row.grid_columnconfigure(i, weight=1, uniform="button")
            tile = ctk.CTkFrame(row, fg_color=THEME["raised"], corner_radius=8, border_width=0,
                                border_color="#5865F2")
            tile.grid(row=0, column=i, padx=(0 if i == 0 else 4, 0 if i == 4 else 4), sticky="ew")
            ui_label(tile, f"0{i + 1}", 10, THEME["accent"], "bold").pack(pady=(10, 0))
            ui_label(tile, name, 11, THEME["text"]).pack(pady=(0, 6))
            badge = ui_label(tile, "Media Key" if i < 3 else "Discord Shortcut", 9, THEME["muted"],
                              fg_color=THEME["well"], corner_radius=7, height=18)
            badge.pack(padx=7, pady=(0, 12))
            self.hardware_buttons.append({"card": tile, "badge": badge})

        reset_panel = ctk.CTkFrame(self.settings_frame, corner_radius=12,
                                  fg_color=THEME["panel"], border_width=0, border_color=THEME["border"])
        reset_panel.pack(fill="x")
        ui_label(reset_panel, "Configuration", 18, weight="bold").pack(anchor="w", padx=24, pady=(22, 4))
        ui_label(reset_panel, "Restore default app assignments, LED colours and shortcuts.",
                 12, THEME["muted"]).pack(anchor="w", padx=24, pady=(0, 16))
        reset_btn = ui_button(reset_panel, "Reset to defaults", self.factory_reset, width=150)
        reset_btn.configure(text_color=THEME["red"])
        reset_btn.pack(anchor="w", padx=24, pady=(0, 24))
        background = ctk.CTkFrame(self.settings_frame, corner_radius=12,
                                  fg_color=THEME["panel"], border_width=0, border_color=THEME["border"])
        background.pack(fill="x", pady=(18, 0))
        ui_label(background, "Background operation", 18, weight="bold").pack(anchor="w", padx=24, pady=(22, 4))
        ui_label(background, "Closing the window keeps your mixer running in the system tray.",
                 12, THEME["muted"]).pack(anchor="w", padx=24)
        ui_label(background, "Open it again from the tray icon, or choose Quit to stop it completely.",
                 12, THEME["muted"]).pack(anchor="w", padx=24, pady=(4, 16))
        self.auto_connect_var = ctk.BooleanVar(value=self.config.get("auto_connect", False))
        self.auto_connect_switch = self.create_preference_row(
            background, "Auto-connect device", "Connect on launch and reconnect after unplugging.",
            self.auto_connect_var, self.change_auto_connect)
        try:
            startup_enabled = self.windows_startup.is_enabled()
            startup_error = None
        except OSError as error:
            startup_enabled = False
            startup_error = error
        self.startup_var = ctk.BooleanVar(value=startup_enabled)
        self.startup_switch = self.create_preference_row(
            background, "Start with Windows", "Launch quietly in the tray when you sign in.",
            self.startup_var, self.change_windows_startup)
        if startup_error:
            self.startup_switch.configure(state="disabled")
            ui_label(background, "Windows startup settings are unavailable.", 11,
                     THEME["red"]).pack(anchor="w", padx=24, pady=(0, 12))
        ui_button(background, "Quit Mixer Hub", self.close_app, width=140).pack(
            anchor="w", padx=24, pady=(8, 24))

    def create_preference_row(self, parent, title, description, variable, command):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(4, 16))
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)
        ui_label(text, title, 13, weight="bold").pack(anchor="w")
        ui_label(text, description, 11, THEME["muted"]).pack(anchor="w", pady=(3, 0))
        switch = ctk.CTkSwitch(row, text="", width=40, height=22, variable=variable,
                               command=command, fg_color=THEME["border"],
                               progress_color=THEME["accent"], button_color=THEME["text"],
                               button_hover_color=THEME["muted"])
        switch.pack(side="right", padx=(16, 0))
        return switch

    def change_auto_connect(self):
        enabled = bool(self.auto_connect_var.get())
        self.config["auto_connect"] = enabled
        self.auto_connect.set_enabled(enabled)
        save_config(self.config)

    def refresh_devices(self):
        self._device_choices = {"Automatic detection": {"port": "", "serial": ""}}
        preferred_port = self.config.get("device_port", "")
        preferred_serial = self.config.get("device_serial", "")
        selected = "Automatic detection"
        for device in list_mixer_ports():
            label = f"{device['port']} · {device['description']}"
            self._device_choices[label] = device
            if (preferred_serial and preferred_serial == device["serial"]) or (
                    not preferred_serial and preferred_port == device["port"]):
                selected = label
        if selected == "Automatic detection" and preferred_port:
            selected = f"{preferred_port} · Not connected"
            self._device_choices[selected] = {"port": preferred_port, "serial": preferred_serial}
        self.device_menu.configure(values=list(self._device_choices))
        self.device_menu.set(selected)
        self.device_selection_hint.configure(text="A selected device is remembered. Changes take effect on the next connection.")

    def select_device(self, label):
        device = self._device_choices[label]
        self.config["device_port"] = device["port"]
        self.config["device_serial"] = device["serial"]
        save_config(self.config)
        self.sync_settings()
        self.auto_connect.next_attempt = 0
        self.device_selection_hint.configure(text="Selection saved. Disconnect and reconnect to use it." if self.engine.running
                                             else "Selection saved. Connect when ready.")

    def refresh_profile_menu(self):
        self.profile_menu.configure(values=list(self.config["profiles"]))
        self.profile_menu.set(self.config["active_profile"])

    def select_profile(self, name):
        if self._save_id:
            self.flush_config()
        profiles.select(self.config, name)
        self.apply_setup()
        save_config(self.config)
        self.refresh_profile_menu()

    def profile_name_dialog(self, title):
        dialog = ctk.CTkInputDialog(text="Profile name (up to 32 characters)", title=title,
                                   fg_color=THEME["panel"], button_fg_color=THEME["raised"])
        return dialog.get_input()

    def new_profile(self):
        name = self.profile_name_dialog("New profile · copy current setup")
        if name is None:
            return
        try:
            profiles.create(self.config, name)
        except ValueError as error:
            messagebox.showerror("Profiles", str(error), parent=self)
            return
        self.clear_channel_undo()
        save_config(self.config)
        self.refresh_profile_menu()

    def rename_profile(self):
        name = self.profile_name_dialog("Rename profile")
        if name is None:
            return
        try:
            profiles.rename(self.config, name)
        except ValueError as error:
            messagebox.showerror("Profiles", str(error), parent=self)
            return
        self.clear_channel_undo()
        save_config(self.config)
        self.refresh_profile_menu()

    def delete_profile(self):
        if len(self.config["profiles"]) == 1:
            messagebox.showinfo("Profiles", "Keep at least one profile. Create another before deleting this one.", parent=self)
            return
        name = self.config["active_profile"]
        if not messagebox.askyesno("Delete profile", f'Delete "{name}" and its saved setup?', parent=self):
            return
        profiles.delete(self.config)
        self.apply_setup()
        save_config(self.config)
        self.refresh_profile_menu()

    def apply_setup(self):
        self.channel_drag.cancel()
        self.clear_channel_undo()
        if self._priority_editor:
            self._priority_editor.close()
        self.bright_slider.set(self.config["brightness"])
        self.brightness_value.configure(text=f"{round(self.config['brightness'] / 255 * 100)}%")
        for key, box in [("mute", self.mute_box), ("deafen", self.deaf_box)]:
            box.configure(state="normal")
            box.delete(0, "end")
            box.insert(0, self.config["hotkeys"][key])
            box.configure(state="disabled")
        for index, channel in enumerate(self.channels):
            self.engine.preview_color(index)
            self.apply_channel_color(index, self.config["channels"][index]["color"])
            channel["back_view"].grid_forget()
            channel["front_view"].grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.update_dropdown_values()
        self.sync_settings()
        self._last_state = None

    def change_windows_startup(self):
        enabled = bool(self.startup_var.get())
        try:
            self.windows_startup.set_enabled(enabled)
        except (OSError, ValueError) as error:
            self.startup_var.set(not enabled)
            messagebox.showerror("Windows startup", f"Could not change this setting.\n\n{error}", parent=self)

    def show_settings_page(self):
        self._page = "settings"
        self.dashboard_frame.grid_forget()
        self.settings_frame.grid(row=0, column=1, padx=28, pady=26, sticky="nsew")
        self.btn_settings.configure(fg_color=THEME["raised"], text_color=THEME["accent"])
        self.btn_dashboard.configure(fg_color="transparent", text_color=THEME["muted"])
        self.render_hardware_buttons(self.engine.snapshot())

    def render_hardware_buttons(self, state):
        now = time.monotonic()
        for index, button in enumerate(self.hardware_buttons):
            active = state.connected and (state.button_levels[index] == 0 or
                                           now - state.button_press_times[index] < 0.22)
            if active != self._hardware_button_active[index]:
                button["card"].configure(fg_color="#32323B" if active else THEME["raised"],
                                          border_width=1 if active else 0, border_color="#5865F2")
                button["badge"].configure(fg_color="#5865F2" if active else THEME["well"],
                                           text_color=THEME["text"] if active else THEME["muted"])
                self._hardware_button_active[index] = active

    def show_dashboard_page(self):
        self._page = "mixer"
        self._last_state = None
        self.settings_frame.grid_forget()
        self.dashboard_frame.grid(row=0, column=1, padx=28, pady=26, sticky="nsew")
        self.btn_settings.configure(fg_color="transparent", text_color=THEME["muted"])
        self.btn_dashboard.configure(fg_color=THEME["raised"], text_color=THEME["accent"])

    def create_recorder_row(self, parent, label, key_type):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(8, 16))
        ui_label(frame, label, 13, weight="bold").pack(side="left")
        btn = ui_button(frame, "Record", width=96)
        btn.configure(command=lambda: self.start_recording(btn, key_type))
        btn.pack(side="right", padx=(12, 0))
        box = ctk.CTkEntry(frame, width=190, height=38, corner_radius=8,
                          fg_color=THEME["bg"], border_color=THEME["border"],
                          text_color=THEME["text"], font=ui_font(12), justify="center")
        box.insert(0, self.config["hotkeys"][key_type])
        box.configure(state="disabled")
        box.pack(side="right")
        return btn, box

    def start_recording(self, button, key_type):
        button.configure(text="Listening...", fg_color=THEME["accent"], text_color=THEME["bg"])
        self.update()
        threading.Thread(target=self.wait_for_hotkey,
                         args=(button, key_type, self.config["active_profile"]), daemon=True).start()

    def wait_for_hotkey(self, button, key_type, profile_name):
        new_hotkey = keyboard.read_hotkey(suppress=False)
        self._actions.put(("hotkey", button, key_type, new_hotkey, profile_name))

    def update_hotkey_ui(self, button, key_type, new_hotkey, profile_name=None):
        if profile_name is not None and profile_name != self.config["active_profile"]:
            # A key recorded after switching setups must not overwrite the new one.
            button.configure(text="Record", fg_color=THEME["raised"], text_color=THEME["text"])
            return
        self.config["hotkeys"][key_type] = new_hotkey
        save_config(self.config)
        self.sync_settings()
        button.configure(text="Record", fg_color=THEME["raised"], text_color=THEME["text"])
        target_box = self.mute_box if key_type == "mute" else self.deaf_box
        target_box.configure(state="normal")
        target_box.delete(0, 'end')
        target_box.insert(0, new_hotkey)
        target_box.configure(state="disabled")

    def factory_reset(self):
        self.channel_drag.cancel()
        self.clear_channel_undo()
        if self._priority_editor:
            self._priority_editor.close()
        self.config.update({
            "brightness": 45,
            "channels": [{"app": "javaw.exe", "color": "#A000FF"}, {"app": "spotify.exe", "color": "#1ED760"},
                         {"app": "chrome.exe", "color": "#EB3223"}, {"app": "discord.exe", "color": "#5865F2"}],
            "hotkeys": {"mute": "ctrl+shift+f11", "deafen": "ctrl+shift+f12"}
        })
        save_config(self.config)
        self.bright_slider.set(45)
        self.change_brightness(45)
        self.update_hotkey_ui(self.mute_btn, "mute", self.config["hotkeys"]["mute"])
        self.update_hotkey_ui(self.deaf_btn, "deafen", self.config["hotkeys"]["deafen"])
        for i in range(4):
            hx = self.config["channels"][i]["color"]
            self.apply_channel_color(i, hx)
            # Close editors before the next opening reloads the reset colour.
            self.channels[i]["back_view"].grid_forget()
            self.channels[i]["front_view"].grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
            self.engine.preview_color(i)
        self.sync_settings()
        self.refresh_dropdowns()

    def change_brightness(self, value):
        brightness = int(value)
        self.config["brightness"] = brightness
        self.brightness_value.configure(text=f"{round(brightness / 255 * 100)}%")
        self.sync_settings()
        if self._save_id:
            self.after_cancel(self._save_id)
        self._save_id = self.after(180, self.flush_config)

    def update_app_identity(self, index):
        channel = self.config["channels"][index]
        priority = priority_for(channel)
        app_name = resolve_routes((channel["app"],), (priority,), self.active_apps)[0]
        self.channels[index]["app_icon"].configure(
            text="", image=self.icon_cache.get(app_name, dim=not self.is_connected))
        self.channels[index]["priority_btn"].configure(
            text="≡ Auto" if priority else "≡ Priority",
            fg_color=THEME["selection"] if priority else THEME["raised"],
            text_color=THEME["accent"] if priority else THEME["text"])
        if priority:
            self.channels[index]["dropdown"].configure(state="disabled")
            self.channels[index]["dropdown"].set(app_name or "No app running")
        else:
            self.channels[index]["dropdown"].configure(state="normal")
            self.channels[index]["dropdown"].set(app_name)
        self.paint_channel_surface(index)
        self.update_volume_pill(index)

    def save_app_selection(self, index, app_name):
        self.config["channels"][index]["app"] = app_name
        self.config["channels"][index].pop("priority", None)
        self.remember_audio_apps([app_name])
        save_config(self.config)
        self.sync_settings()
        self.update_app_identity(index)

    def open_priority_editor(self, index):
        if self._priority_editor:
            self._priority_editor.close()
        self._priority_editor = PriorityEditor(self, index, THEME, ui_label, ui_button, ui_font)

    def set_channel_priority(self, index, names):
        self.config["channels"][index]["priority"] = list(normalize_apps(names))
        self.remember_audio_apps(names, persist=False)
        save_config(self.config)
        self.sync_settings()
        self.update_dropdown_values()
        self._last_state = None

    def remember_audio_apps(self, names, *, persist=True):
        new_names = set(normalize_apps(names)) - {"master", ""} - self.known_apps
        if not new_names:
            return
        self.known_apps.update(new_names)
        self.config["known_apps"] = sorted(self.known_apps)
        if persist:
            save_config(self.config)
        if self._priority_editor:
            self._priority_editor.refresh_choices()

    def sync_settings(self):
        self.engine.update_config(self.config)

    def flush_config(self):
        if self._save_id:
            self.after_cancel(self._save_id)
            self._save_id = None
        save_config(self.config)

    def refresh_dropdowns(self):
        if self.engine.running:
            self.engine.refresh_apps()
            return
        self.active_apps = get_active_audio_apps()
        self.remember_audio_apps(self.active_apps)
        self.update_dropdown_values()

    def update_dropdown_values(self):
        self.icon_cache.refresh_for_apps(self.active_apps)
        for i, ch in enumerate(self.channels):
            saved_app = self.config["channels"][i]["app"]
            ch["dropdown"].configure(values=self.available_routes(saved_app))
            ch["dropdown"].set(saved_app)
            self.update_app_identity(i)

    def toggle_connection(self):
        if self.power_session.suspended:
            return
        self.power_session.cancel_reconnect()
        if self.engine.running:
            self.auto_connect.manual_disconnect()
            self.engine.stop()
        else:
            self.auto_connect.manual_connect(time.monotonic())
            self.engine.start()
        self._last_state = None
        self.render_state(self.engine.snapshot())

    def safe_gui_update(self, i, percent, is_muted):
        self.last_percentages[i] = percent
        self.channels[i]["slider"].set(percent)
        self.update_volume_pill(i)

    def render_state(self, state):
        old = self._last_state
        self.is_connected = state.connected
        self._eq_mode = state.eq_mode
        self.last_eq_levels = list(state.eq_levels)
        self.remember_audio_apps(state.known_apps)
        if old is None or (state.connected, state.status, state.port) != (old.connected, old.status, old.port):
            color = THEME["green"] if state.connected else (
                THEME["accent"] if state.status == "Connecting" else THEME["muted"])
            if state.status in ("Port unavailable", "Device not found", "Device disconnected", "Connection error"):
                color = THEME["red"]
            self.status_label.configure(text=f"● {state.status}", text_color=color)
            self.stat_port.configure(text=f"USB  /  {state.port or 'No device'}")
            self.btn_connect.configure(text="Disconnect device" if state.connected else (
                "Cancel connection" if self.engine.running else "Connect device"))
            self.device_title.configure(text="Your mixer" + (f"  ·  {state.port}" if state.connected else ""))
            self.device_hint.configure(text="Channel guides · live LED levels" if state.connected else (
                "Channels run left to right on your device." if state.status != "Connecting" else "Opening serial connection…"))
            if not state.connected:
                self._display_leds = [0.0] * 4
                for channel in self.channels:
                    channel["led_meter"].set_level(0)
                self.draw_device()
        if state.connected and (old is None or state.active_apps != old.active_apps):
            self.active_apps = list(state.active_apps)
            self.update_dropdown_values()
        for i, percent in enumerate(state.percentages):
            if old is None or percent != old.percentages[i]:
                if percent < 0:
                    self.last_percentages[i] = -1
                    self.channels[i]["slider"].set(0)
                    self.update_volume_pill(i)
                else:
                    self.safe_gui_update(i, percent, percent == 0)
            identity_changed = old is None or state.connected != old.connected or state.active_apps != old.active_apps or state.resolved_apps != old.resolved_apps or percent != old.percentages[i]
            if identity_changed:
                self.update_app_identity(i)
        if old is None or state.eq_mode != old.eq_mode or state.connected != old.connected:
            self.stat_audio.configure(text="LED mode: Audio" if state.eq_mode else (
                "LED mode: Volume" if state.connected else "LED mode: —"),
                                      text_color=THEME["accent"] if state.eq_mode else THEME["muted"])
            self.mode_label.configure(text="LEDs · audio reactive" if state.eq_mode else "LEDs · fader level")
        if old is None or state.master_peak != old.master_peak:
            self.vis_bar.set(state.master_peak)
        self._last_state = state

    def render_meters(self):
        now = time.monotonic()
        dt = min(0.12, now - self._last_meter_time)
        self._last_meter_time = now
        for i, channel in enumerate(self.channels):
            volume = max(0, self.last_percentages[i])
            target = self.last_eq_levels[i] if self._eq_mode else -1
            if not self.is_connected:
                level = 0
            elif target < 0:
                level = volume  # -1 means static volume, exactly as on the device.
            else:
                # Temporary visual decay; replace with the firmware's constants
                # once the Arduino sketch is available. Hardware receives raw EQ.
                level = max(target, self._display_leds[i] - 180 * dt)
            self._display_leds[i] = level
            channel["led_meter"].set_level(level)
        self.draw_device()

    def poll_runtime(self):
        self._poll_id = None
        if self._closing:
            return
        # Keep discovering apps while the window is in the tray, without painting.
        self.remember_audio_apps(self.engine.snapshot().known_apps)
        if self.instance_guard and self.instance_guard.restore_requested():
            self.restore_window()
        while not self._actions.empty():
            action = self._actions.get_nowait()
            if action == "quit":
                self.close_app()
                return
            if action == "show":
                self.restore_window()
            elif isinstance(action, tuple) and action[0] == "hotkey":
                self.update_hotkey_ui(*action[1:])
            elif isinstance(action, tuple) and action[0] == "apps":
                self.remember_audio_apps(action[1])
                if not self.engine.running:
                    self.active_apps = list(action[1])
                    self._last_state = None
                    if not self._hidden and self.state() != "iconic":
                        self.update_dropdown_values()
        if self._start_hidden_pending:
            if self.tray and self.tray.ready.is_set():
                self._start_hidden_pending = False
            elif time.monotonic() >= self._tray_deadline:
                self.restore_window()
                messagebox.showerror("Mixer Hub", "The system tray icon could not start. The window has been opened so you can access the app.", parent=self)
        if not self.power_session.suspended:
            now = time.monotonic()
            if (self.power_session.should_reconnect(now, running=self.engine.running,
                                                    connected=self.engine.snapshot().connected and self.engine.connection_requested)
                    or self.auto_connect.should_connect(now, running=self.engine.running,
                                                        connected=self.engine.snapshot().connected)):
                self.engine.start()
        visible = not self._hidden and self.state() != "iconic"
        if visible:
            state = self.engine.snapshot()
            if state != self._last_state:
                self.render_state(state)
            if self._page == "mixer" and state.connected:
                self.render_meters()
            elif self._page == "settings":
                self.render_hardware_buttons(state)
        # Hidden/minimized: process tray actions four times a second, without
        # repainting widgets, reading peaks, or scanning audio in the GUI thread.
        self._poll_id = self.after(50 if visible and self.is_connected else 250,
                                   self.poll_runtime)

    def hide_to_tray(self):
        if not self.tray or not self.tray.ready.is_set():
            messagebox.showerror("Mixer Hub", "The tray icon is not available yet. Try again, or use Quit Mixer Hub in Settings.", parent=self)
            return
        if self._save_id:
            self.flush_config()
        self._hidden = True
        ctk.ScalingTracker.update_loop_interval = 1000
        self.withdraw()

    def handle_power_event(self, event):
        if self._closing:
            return
        logging.info("Windows power event: %s", event)
        if event in ("suspend", "shutdown"):
            self.power_session.suspend(self.engine.connection_requested)
            self.engine.stop()  # Worker owns the blackout write and COM cleanup.
        elif event == "resume":
            self.power_session.resume(time.monotonic())
            self._last_state = None

    def restore_window(self):
        if self._closing:
            return
        self._hidden = False
        self._start_hidden_pending = False
        ctk.ScalingTracker.update_loop_interval = self._scaling_poll_interval
        self._last_state = None
        self.deiconify()
        self.lift()
        self.focus_force()
        activate_window(self.winfo_id())

    def close_app(self):
        if self._closing:
            return
        self._closing = True
        self.power_session.cancel_reconnect()
        if self.power_monitor:
            self.power_monitor.close()
        if self._window_resize_job:
            self.after_cancel(self._window_resize_job)
            self._window_resize_job = None
        self.channel_drag.cancel()
        if self._layout_editor:
            self._layout_editor.close()
        if self._priority_editor:
            self._priority_editor.close()
        ctk.ScalingTracker.update_loop_interval = self._scaling_poll_interval
        if self._poll_id:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        if self._save_id:
            self.flush_config()
        self.engine.stop(wait=True)
        if self.discovery:
            self.discovery.stop()
        if self.tray:
            self.tray.stop()
        self.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mixer Hub")
    parser.add_argument("--background", action="store_true", help="Start quietly in the Windows system tray")
    args = parser.parse_args(argv)
    guard = SingleInstance()
    if guard.acquire(show_existing=not args.background):
        try:
            configure_logging()
            logging.info("Starting Mixer Hub %s (%s)", VERSION, "packaged" if getattr(sys, "frozen", False) else "source")
            app = MixerApp(start_hidden=args.background, instance_guard=guard)
            logging.info("Dashboard ready; product renders: %s", ", ".join(sorted(app.device_view.sources)))
            app.mainloop()
            logging.info("Mixer Hub stopped")
        finally:
            guard.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
