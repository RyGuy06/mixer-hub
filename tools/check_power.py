"""Exercise this app's native power callback with simulated hardware; never sleep Windows."""
import copy
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import app as mixer
from mixer_runtime import MixerEngine
from power_events import (WindowsPowerMonitor, WM_POWERBROADCAST, WM_QUERYENDSESSION,
                          WM_ENDSESSION, PBT_APMSUSPEND, PBT_APMRESUMEAUTOMATIC)
from test_runtime import CONFIG, FakeAudio, FakeSerial


def main():
    config = copy.deepcopy(CONFIG)
    config["auto_connect"] = False
    before = (ROOT / "mixer_config.json").read_bytes() if (ROOT / "mixer_config.json").exists() else None
    opened = []
    window = None

    def serial_factory(*args, **kwargs):
        connection = FakeSerial()
        opened.append(connection)
        return connection

    with patch.object(mixer, "load_config", side_effect=lambda: copy.deepcopy(config)), \
         patch.object(mixer, "save_config"), \
         patch.object(mixer, "get_active_audio_apps", return_value=["master", "spotify.exe"]):
        try:
            window = mixer.MixerApp(start_services=False, start_hidden=True)
            window.engine = MixerEngine(config, serial_factory=serial_factory,
                                       port_finder=lambda: "SIMULATED", audio_factory=FakeAudio,
                                       button_sender=lambda *args: None, boot_delay=0)
            errors = []
            window.report_callback_exception = lambda *args: errors.append(args)
            window.power_monitor = WindowsPowerMonitor(window.winfo_id(), window.handle_power_event)
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user.SendMessageW.restype = ctypes.c_ssize_t

            def pump(seconds, condition=None):
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    window.update()
                    if condition and condition():
                        return
                    time.sleep(0.01)
                if condition:
                    raise AssertionError("Power integration check timed out")

            def notify(value):
                user.SendMessageW(window.power_monitor.window, WM_POWERBROADCAST, value, 0)

            window._poll_id = window.after(5, window.poll_runtime)
            window.toggle_connection()
            pump(3, lambda: opened and b"H,1\n" in opened[-1].writes)
            assert window._hidden, "Hidden app must keep heartbeats alive"
            notify(PBT_APMSUSPEND)
            pump(2, lambda: not window.engine.running)
            assert window.power_session.suspended
            assert opened[0].writes[-1] == b"H,0\nB,0\n"
            assert window.config["brightness"] == config["brightness"]
            notify(PBT_APMRESUMEAUTOMATIC)
            pump(3, lambda: len(opened) == 2 and b"H,1\n" in opened[-1].writes)
            assert b"B,255\n" in opened[-1].writes
            assert not window.auto_connect.enabled, "Manual session should resume with auto-connect off"

            # Quick consecutive notifications must not lose reconnect intent.
            notify(PBT_APMSUSPEND)
            notify(PBT_APMRESUMEAUTOMATIC)
            pump(3, lambda: len(opened) == 3 and b"H,1\n" in opened[-1].writes)
            assert user.SendMessageW(window.power_monitor.window, WM_QUERYENDSESSION, 0, 0) == 1
            pump(2, lambda: not window.engine.running)
            user.SendMessageW(window.power_monitor.window, WM_ENDSESSION, 0, 0)  # Cancelled, not a shutdown.
            pump(3, lambda: len(opened) == 4 and b"H,1\n" in opened[-1].writes)

            window.toggle_connection()  # Deliberate Disconnect must remain respected.
            pump(2, lambda: not window.engine.running)
            count = len(opened)
            notify(PBT_APMSUSPEND)
            notify(PBT_APMRESUMEAUTOMATIC)
            pump(0.4)
            assert len(opened) == count
            assert not errors, errors
            window.close_app()
            if before is not None:
                assert (ROOT / "mixer_config.json").read_bytes() == before
            print("PASS: native power hook, hidden heartbeat, blackout, saved brightness, manual-session wake/retry, rapid resume, cancelled shutdown, deliberate disconnect, and clean unhook. No real power event or hardware I/O was used.")
        finally:
            if window is not None and not window._closing:
                window.close_app()


if __name__ == "__main__":
    main()
