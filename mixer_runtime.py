"""Serial/audio worker. No Tk widgets or GUI callbacks belong in this module."""
from dataclasses import dataclass, replace
import ctypes
import logging
import math
import threading
import time

import keyboard
import serial
import serial.tools.list_ports
from comtypes import CoInitialize, CoUninitialize, CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioMeterInformation
from app_routing import priority_for, resolve_routes, normalize_apps

log = logging.getLogger(__name__)
TICK_SECONDS = 0.04
SESSION_REFRESH_SECONDS = 2.0
EQ_IDLE_SECONDS = 1.5
HEARTBEAT_SECONDS = 1.0


def list_audio_apps():
    CoInitialize()
    try:
        names = {"master"}
        for session in AudioUtilities.GetAllSessions():
            try:
                if session.Process:
                    names.add(session.Process.name().lower())
            except Exception:
                continue
        return ["master", *sorted(names - {"master"})]
    except Exception:
        return ["master"]
    finally:
        CoUninitialize()


class AppDiscovery:
    """Learn audio apps while unplugged; connected discovery uses the audio cache."""
    def __init__(self, can_scan, on_result, *, scanner=list_audio_apps, interval=10.0):
        self.can_scan, self.on_result = can_scan, on_result
        self.scanner, self.interval = scanner, interval
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        def run():
            while not self._stop.wait(self.interval):
                if self.can_scan():
                    try:
                        names = self.scanner()
                        if not self._stop.is_set():
                            self.on_result(tuple(names))
                    except Exception:
                        log.exception("Audio app discovery failed")
        self._thread = threading.Thread(target=run, name="Mixer app discovery", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)


@dataclass(frozen=True)
class MixerSettings:
    apps: tuple
    colors: tuple
    brightness: int
    mute: str
    deafen: str
    device_port: str = ""
    device_serial: str = ""
    priorities: tuple = ((), (), (), ())

    @classmethod
    def from_config(cls, config):
        return cls(tuple(ch["app"].lower() for ch in config["channels"]),
                   tuple(ch["color"] for ch in config["channels"]),
                   int(config["brightness"]), config["hotkeys"]["mute"],
                   config["hotkeys"]["deafen"], config.get("device_port", ""),
                   config.get("device_serial", ""),
                   tuple(priority_for(channel) for channel in config["channels"]))


@dataclass(frozen=True)
class MixerState:
    connected: bool = False
    status: str = "Disconnected"
    port: str = ""
    percentages: tuple = (-1, -1, -1, -1)
    eq_levels: tuple = (-1, -1, -1, -1)
    eq_mode: bool = False
    master_peak: float = 0.0
    active_apps: tuple = ("master",)
    resolved_apps: tuple = ("", "", "", "")
    known_apps: tuple = ()
    button_levels: tuple = (1, 1, 1, 1, 1)
    button_press_times: tuple = (-float("inf"),) * 5


def list_mixer_ports():
    return [{"port": port.device, "description": port.description,
             "serial": port.serial_number or ""}
            for port in serial.tools.list_ports.comports()]


def find_mixer_port(preferred_port="", preferred_serial=""):
    if preferred_serial:
        return next((port.device for port in serial.tools.list_ports.comports()
                     if port.serial_number == preferred_serial), None)
    if preferred_port:
        return next((port.device for port in serial.tools.list_ports.comports()
                     if port.device == preferred_port), None)
    for port in serial.tools.list_ports.comports():
        if any(name in port.description.lower() for name in ("ch340", "usb serial", "arduino", "cp210")):
            return port.device
    return None


def parse_frame(line):
    """Ignore partial/noisy frames without disconnecting the device."""
    try:
        values = tuple(int(part) for part in line.strip().split("|"))
        if len(values) != 9 or any(button not in (0, 1) for button in values[4:]):
            return None
        return tuple(max(0, min(1023, value)) for value in values[:4]), values[4:]
    except (ValueError, TypeError):
        return None


def eq_level(peak):
    return min(100, int(math.sqrt(max(0, peak)) * 105)) if peak > 0.001 else -1


def send_button(index, settings):
    if index < 3:
        vk = (0xB1, 0xB3, 0xB0)[index]
        scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
        ctypes.windll.user32.keybd_event(vk, scan, 0x0001, 0)
        time.sleep(0.02)
        ctypes.windll.user32.keybd_event(vk, scan, 0x0001 | 0x0002, 0)
    else:
        keyboard.send(settings.deafen if index == 3 else settings.mute)


class WindowsAudio:
    """Cache interfaces on the same COM-initialized thread that uses them."""
    def __init__(self):
        self.sessions = {}
        self.master_volume = None
        self.master_meter = None
        self.device_id = None
        self.device = None

    def refresh(self):
        sessions = {}
        try:
            for session in AudioUtilities.GetAllSessions():
                try:
                    if session.Process:
                        name = session.Process.name().lower()
                        volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                        try:
                            meter = session._ctl.QueryInterface(IAudioMeterInformation)
                        except Exception:
                            meter = None
                        sessions.setdefault(name, []).append((volume, meter))
                except Exception:
                    continue  # A process can disappear during enumeration.
            self.sessions = sessions
        except Exception:
            self.sessions = {}
        try:
            device = AudioUtilities.GetSpeakers()
            device_id = getattr(device, "id", None)
            if device_id != self.device_id or self.master_volume is None or self.master_meter is None:
                self.device_id = device_id
                # Retain the existing preference for AirPods/headphones for master volume.
                preferred = device
                for candidate in AudioUtilities.GetAllDevices(data_flow=0):
                    state = getattr(candidate.state, "value", candidate.state)
                    name = (candidate.FriendlyName or "").lower()
                    if state == 1 and ("airpod" in name or "headphones" in name):
                        preferred = candidate
                        break
                self.device = preferred
                self.master_volume = preferred.EndpointVolume
                # New pycaw exposes the raw IMMDevice through _dev.
                raw_device = getattr(preferred, "_dev", preferred)
                interface = raw_device.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
                self.master_meter = interface.QueryInterface(IAudioMeterInformation)
        except Exception:
            self.master_meter = None
        return tuple(["master", *sorted(self.sessions)])

    def set_volume(self, app_name, value):
        try:
            if app_name == "master":
                if self.master_volume:
                    self.master_volume.SetMasterVolumeLevelScalar(value, None)
                    return True
                return False
            sessions = self.sessions.get(app_name, ())
            for volume, _ in sessions:
                volume.SetMasterVolume(value, None)
            return bool(sessions)
        except Exception:
            return False  # Refresh replaces stale interfaces on the next sweep.

    def read_peaks(self, apps):
        peaks = {}
        master_peak = 0.0
        if self.master_meter:
            try:
                master_peak = self.master_meter.GetPeakValue()
            except Exception:
                self.master_meter = None
        for name in set(apps):
            peak = master_peak if name == "master" else 0.0
            for _, meter in self.sessions.get(name, ()):
                if meter:
                    try:
                        peak = max(peak, meter.GetPeakValue())
                    except Exception:
                        continue
            peaks[name] = peak
        return peaks, master_peak

    def close(self):
        self.sessions.clear()
        self.master_volume = self.master_meter = self.device = None


class MixerEngine:
    def __init__(self, config, *, serial_factory=serial.Serial, port_finder=find_mixer_port,
                 audio_factory=WindowsAudio, button_sender=send_button, boot_delay=1.5):
        self._settings = MixerSettings.from_config(config)
        self._known_apps = set(normalize_apps(config.get("known_apps", ()))) - {"master"}
        self._state = MixerState()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._refresh = threading.Event()
        self._thread = None
        self._preview_colors = {}
        self.serial_factory = serial_factory
        self.port_finder = port_finder
        self.audio_factory = audio_factory
        self.button_sender = button_sender
        self.boot_delay = boot_delay

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def connection_requested(self):
        return self.running and not self._stop.is_set()

    def snapshot(self):
        with self._lock:
            return self._state

    def _publish(self, **changes):
        with self._lock:
            self._state = replace(self._state, **changes)

    def update_config(self, config):
        settings = MixerSettings.from_config(config)
        with self._lock:
            routes_changed = (settings.apps, settings.priorities) != (self._settings.apps, self._settings.priorities)
            self._settings = settings
            self._known_apps.update(normalize_apps(config.get("known_apps", ())))
        if routes_changed:
            self._refresh.set()

    def preview_color(self, index, hx=None):
        with self._lock:
            if hx is None:
                self._preview_colors.pop(index, None)
            else:
                self._preview_colors[index] = hx

    def refresh_apps(self):
        self._refresh.set()

    def start(self):
        if self.running:
            return False
        self._stop.clear()
        self._refresh.set()
        with self._lock:
            self._state = MixerState(status="Connecting", known_apps=tuple(sorted(self._known_apps)))
        self._thread = threading.Thread(target=self._run, name="Mixer audio", daemon=True)
        self._thread.start()
        return True

    def stop(self, wait=False):
        self._stop.set()
        if wait and self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=3)

    def _run(self):
        connection = audio = None
        initialized = False
        terminal_status = "Disconnected"
        try:
            with self._lock:
                settings = self._settings
            port = (find_mixer_port(settings.device_port, settings.device_serial)
                    if self.port_finder is find_mixer_port else self.port_finder())
            if not port:
                terminal_status = "Device not found"
                return
            connection = self.serial_factory(port, 9600, timeout=0.01, write_timeout=0.25)
            if self._stop.wait(self.boot_delay):
                return
            CoInitialize()
            initialized = True
            audio = self.audio_factory()
            self._publish(connected=True, status="Connected", port=port)
            sent_brightness, sent_colors = None, [None] * 4
            previous_eq = None
            next_heartbeat = 0.0
            last_values = [-1.0] * 4
            percentages = [-1] * 4
            button_states = (1,) * 5
            press_times = [-float("inf")] * 5
            last_move = time.monotonic()
            next_refresh = 0.0
            previous_routes = None
            active_apps = ("master",)
            receive_buffer = bytearray()
            pending_volume_indices = set()

            def write(message):
                connection.write((message + "\n").encode("utf-8"))

            def apply_volume(index):
                if not routes[index]:
                    pending_volume_indices.discard(index)
                    return
                if audio.set_volume(routes[index], last_values[index]) is False:
                    pending_volume_indices.add(index)
                else:
                    pending_volume_indices.discard(index)

            while not self._stop.is_set():
                tick_start = time.monotonic()
                with self._lock:
                    settings = self._settings
                    colors = tuple(self._preview_colors.get(i, hx) for i, hx in enumerate(settings.colors))
                refreshed = tick_start >= next_refresh or self._refresh.is_set()
                if refreshed:
                    self._refresh.clear()
                    active_apps = audio.refresh()
                    with self._lock:
                        self._known_apps.update(set(active_apps) - {"master", ""})
                        known_apps = tuple(sorted(self._known_apps))
                    self._publish(active_apps=active_apps, known_apps=known_apps)
                    next_refresh = tick_start + SESSION_REFRESH_SECONDS
                routes = resolve_routes(settings.apps, settings.priorities, active_apps)
                changed_indices = {i for i, name in enumerate(routes)
                                   if previous_routes is not None and name != previous_routes[i] and last_values[i] >= 0}
                for index in changed_indices | (pending_volume_indices if refreshed else set()):
                    apply_volume(index)
                previous_routes = routes
                if settings.brightness != sent_brightness:
                    write(f"B,{settings.brightness}")
                    sent_brightness = settings.brightness
                for i, hx in enumerate(colors):
                    if hx != sent_colors[i]:
                        r, g, b = (int(hx[j:j + 2], 16) for j in (1, 3, 5))
                        write(f"C,{i},{r},{g},{b}")
                        sent_colors[i] = hx

                # Read available bytes, retaining partial lines across ticks. Coalesce
                # slider readings, but process every button transition in the burst.
                pending = connection.in_waiting
                if pending:
                    receive_buffer.extend(connection.read(pending))
                newest_sliders = None
                while b"\n" in receive_buffer:
                    line, _, remainder = receive_buffer.partition(b"\n")
                    receive_buffer = bytearray(remainder)
                    frame = parse_frame(line.decode("utf-8", errors="ignore"))
                    if frame is None:
                        continue
                    newest_sliders, buttons = frame
                    for index, pressed in enumerate(buttons):
                        if pressed == 0 and button_states[index] == 1 and tick_start - press_times[index] > 0.35:
                            press_times[index] = tick_start
                            try:
                                self.button_sender(index, settings)
                            except Exception:
                                log.exception("Could not send hardware button %s", index)
                    button_states = buttons
                if len(receive_buffer) > 4096:
                    receive_buffer.clear()
                if newest_sliders is not None:
                    for i, raw in enumerate(newest_sliders):
                        value = raw / 1023.0
                        if abs(value - last_values[i]) > 0.015:
                            last_values[i] = value
                            apply_volume(i)
                            percentages[i] = int(value * 100)
                            last_move = tick_start

                is_idle = tick_start - last_move > EQ_IDLE_SECONDS
                levels = (-1,) * 4
                master_peak = 0.0
                if is_idle:
                    peaks, master_peak = audio.read_peaks(tuple(name for name in routes if name))
                    levels = tuple(eq_level(peaks.get(name, 0.0)) if name else -1 for name in routes)
                if levels != previous_eq:
                    write("E," + ",".join(str(level) for level in levels))
                    previous_eq = levels
                # Renew only after the current settings/EQ have been applied.
                # Uses the existing worker and serial owner, including in tray.
                if tick_start >= next_heartbeat:
                    write("H,1")
                    next_heartbeat = tick_start + HEARTBEAT_SECONDS
                self._publish(percentages=tuple(percentages), eq_levels=levels,
                              eq_mode=is_idle, master_peak=master_peak, resolved_apps=routes,
                              button_levels=button_states, button_press_times=tuple(press_times))
                # Sleep for the unused portion of the tick; hidden GUI has no effect
                # on hardware cadence, and stopping interrupts the wait immediately.
                self._stop.wait(max(0, TICK_SECONDS - (time.monotonic() - tick_start)))
        except (serial.SerialException, OSError):
            terminal_status = "Device disconnected" if self.snapshot().connected else "Port unavailable"
            log.warning("Mixer serial connection unavailable", exc_info=True)
        except Exception:
            terminal_status = "Connection error"
            log.exception("Mixer worker stopped unexpectedly")
        finally:
            if connection:
                try:
                    # Keep persisted brightness intact. B,0 also blanks older
                    # firmware; new firmware additionally understands H,0.
                    connection.write(b"H,0\nB,0\n")
                except (serial.SerialException, OSError):
                    pass  # Firmware's lease expiry handles a dead USB link.
                try:
                    connection.close()
                except Exception:
                    pass
            try:
                if audio:
                    audio.close()
            finally:
                audio = None
                if initialized:
                    CoUninitialize()
                self._publish(connected=False, status=terminal_status, port="",
                              eq_levels=(-1,) * 4, eq_mode=False, master_peak=0.0, resolved_apps=("",) * 4,
                              button_levels=(1,) * 5)
