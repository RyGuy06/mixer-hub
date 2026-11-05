import copy
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import serial
import mixer_runtime as runtime

CONFIG = {
    "brightness": 255,
    "channels": [{"app": name, "color": color} for name, color in
                 [("javaw.exe", "#ff0000"), ("spotify.exe", "#ff00ff"),
                  ("chrome.exe", "#eb3223"), ("discord.exe", "#5865f2")]],
    "hotkeys": {"mute": "ctrl+shift+f11", "deafen": "ctrl+shift+f12"},
}


def wait_for(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Worker did not reach expected state")


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.buffer = bytearray()
        self.writes = []
        self.closed = False
        self.failure = False
        self.lock = threading.Lock()
        self.writer_threads = set()

    @property
    def in_waiting(self):
        if self.failure:
            raise serial.SerialException("USB removed")
        with self.lock:
            return len(self.buffer)

    def feed(self, data):
        with self.lock:
            self.buffer.extend(data)

    def read(self, count):
        with self.lock:
            result = bytes(self.buffer[:count])
            del self.buffer[:count]
            return result

    def write(self, data):
        self.writer_threads.add(threading.get_ident())
        self.writes.append(data)
        return len(data)

    def close(self):
        self.closed = True


class FakeAudio:
    def __init__(self):
        self.refresh_count = 0
        self.peak_count = 0
        self.volumes = []
        self.threads = set()
        self.closed = False
        self.missing = set()
        self.peaks = {"javaw.exe": 0.25, "spotify.exe": 0.0, "chrome.exe": 1.0, "discord.exe": 0.01}

    def refresh(self):
        self.refresh_count += 1
        self.threads.add(threading.get_ident())
        return tuple(["master", *self.peaks])

    def set_volume(self, name, value):
        if name in self.missing:
            return False
        self.volumes.append((name, value))
        self.threads.add(threading.get_ident())
        return True

    def read_peaks(self, apps):
        self.peak_count += 1
        self.threads.add(threading.get_ident())
        return self.peaks, 0.2

    def close(self):
        self.closed = True
        self.threads.add(threading.get_ident())


class ProtocolTests(unittest.TestCase):
    def test_partial_and_invalid_frames_are_ignored(self):
        for line in ("booting", "1|2", "1|2|3|4|1|1|1|1|2", "a|2|3|4|1|1|1|1|1"):
            self.assertIsNone(runtime.parse_frame(line))
        self.assertEqual(runtime.parse_frame("-10|2048|0|1023|1|0|1|0|1\n"),
                         ((0, 1023, 0, 1023), (1, 0, 1, 0, 1)))

    def test_eq_curve_and_static_sentinel(self):
        self.assertEqual([runtime.eq_level(value) for value in (0, 0.001, 0.01, 0.25, 1)],
                         [-1, -1, 10, 52, 100])


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.connection = FakeSerial()
        self.audio = FakeAudio()
        self.buttons = []
        self.config = copy.deepcopy(CONFIG)
        self.com_threads = []
        self.patches = [patch.object(runtime, "CoInitialize", side_effect=lambda: self.com_threads.append(("init", threading.get_ident()))),
                        patch.object(runtime, "CoUninitialize", side_effect=lambda: self.com_threads.append(("uninit", threading.get_ident()))),
                        patch.object(runtime, "EQ_IDLE_SECONDS", 0.06),
                        patch.object(runtime, "TICK_SECONDS", 0.01),
                        patch.object(runtime, "SESSION_REFRESH_SECONDS", 0.4)]
        for patched in self.patches:
            patched.start()
        self.engine = runtime.MixerEngine(self.config, serial_factory=lambda *args, **kwargs: self.connection,
                                          port_finder=lambda: "TEST", audio_factory=lambda: self.audio,
                                          button_sender=lambda index, settings: self.buttons.append((index, settings)), boot_delay=0)

    def tearDown(self):
        self.engine.stop(wait=True)
        for patched in reversed(self.patches):
            patched.stop()

    def start(self):
        self.assertTrue(self.engine.start())
        wait_for(lambda: b"C,3,88,101,242\n" in self.connection.writes)

    def test_startup_settings_cache_and_thread_ownership(self):
        self.start()
        wait_for(lambda: self.audio.peak_count > 8)
        self.assertIn(b"B,255\n", self.connection.writes)
        self.assertIn(b"C,0,255,0,0\n", self.connection.writes)
        self.assertLess(self.audio.refresh_count, self.audio.peak_count)
        self.assertEqual(len(self.audio.threads), 1)
        self.assertNotIn(threading.get_ident(), self.audio.threads)
        self.assertEqual(self.audio.threads, self.connection.writer_threads)
        self.assertFalse(self.engine.start(), "A second worker must not be spawned")
        self.engine.stop(wait=True)
        self.assertEqual(self.com_threads, [("init", next(iter(self.audio.threads))), ("uninit", next(iter(self.audio.threads)))])
        self.assertTrue(self.audio.closed)
        self.assertTrue(self.connection.closed)

    def test_selected_device_is_used_by_the_worker(self):
        from types import SimpleNamespace
        self.config.update(device_port="COM5", device_serial="my-nano")
        opened = []
        self.engine = runtime.MixerEngine(
            self.config, serial_factory=lambda port, *args, **kwargs: (opened.append(port) or self.connection),
            audio_factory=lambda: self.audio, button_sender=lambda *args: None, boot_delay=0)
        ports = [SimpleNamespace(device="COM3", description="USB serial", serial_number="other"),
                 SimpleNamespace(device="COM8", description="Arduino Nano", serial_number="my-nano")]
        with patch.object(runtime.serial.tools.list_ports, "comports", return_value=ports):
            self.start()
            self.assertEqual(opened, ["COM8"])

    def test_partial_frames_volume_and_burst_button_edges(self):
        self.start()
        self.connection.feed(b"512|256|1023|0|1|1")
        time.sleep(0.03)
        self.assertEqual(self.audio.volumes, [])
        self.connection.feed(b"|1|1|1\n512|256|1023|0|0|0|0|0|0\n512|256|1023|0|1|1|1|1|1\n")
        wait_for(lambda: self.engine.snapshot().percentages == (50, 25, 100, 0))
        self.assertEqual([index for index, _ in self.buttons], list(range(5)))
        self.assertEqual(self.buttons[3][1].deafen, "ctrl+shift+f12")
        self.assertEqual(self.buttons[4][1].mute, "ctrl+shift+f11")
        self.assertEqual(len(self.audio.volumes), 4)
        self.connection.feed(b"512|256|1023|0|0|0|0|0|0\n")
        time.sleep(0.03)
        self.assertEqual(len(self.buttons), 5, "Debounce must suppress repeated edges")

    def test_button_snapshot_retains_short_taps_and_reports_held_release(self):
        self.start()
        self.connection.feed(b"512|0|0|0|0|0|0|0|0\n512|0|0|0|1|1|1|1|1\n")
        wait_for(lambda: all(value > 0 for value in self.engine.snapshot().button_press_times))
        self.assertEqual(self.engine.snapshot().button_levels, (1,) * 5)
        self.assertEqual([index for index, _ in self.buttons], list(range(5)))
        self.connection.feed(b"512|0|0|0|0|1|1|1|1\n")
        wait_for(lambda: self.engine.snapshot().button_levels[0] == 0)
        self.assertEqual(len(self.buttons), 5, "Live levels must not bypass action debounce")
        self.connection.feed(b"512|0|0|0|1|1|1|1|1\n")
        wait_for(lambda: self.engine.snapshot().button_levels == (1,) * 5)

    def test_gui_snapshot_uses_the_transmitted_eq_values(self):
        self.start()
        wait_for(lambda: self.engine.snapshot().eq_mode)
        self.assertEqual(self.engine.snapshot().eq_levels, (52, -1, 100, 10))
        self.assertIn(b"E,52,-1,100,10\n", self.connection.writes)
        self.connection.feed(b"1023|512|256|0|1|1|1|1|1\n")
        wait_for(lambda: self.engine.snapshot().percentages == (100, 50, 25, 0))
        self.assertFalse(self.engine.snapshot().eq_mode)
        self.assertIn(b"E,-1,-1,-1,-1\n", self.connection.writes)

    def test_route_changes_apply_existing_fader_to_new_app(self):
        self.start()
        self.connection.feed(b"512|0|0|0|1|1|1|1|1\n")
        wait_for(lambda: self.engine.snapshot().percentages[0] == 50)
        self.config["channels"][0]["app"] = "inactive.exe"
        self.engine.update_config(self.config)
        wait_for(lambda: any(name == "inactive.exe" for name, _ in self.audio.volumes))
        self.assertFalse(any(name == "master" for name, _ in self.audio.volumes))

    def test_color_preview_cancel_and_settings_use_one_writer(self):
        self.start()
        self.engine.preview_color(0, "#010203")
        wait_for(lambda: b"C,0,1,2,3\n" in self.connection.writes)
        self.engine.preview_color(0)
        wait_for(lambda: self.connection.writes.count(b"C,0,255,0,0\n") == 2)
        self.config["brightness"] = 128
        self.engine.update_config(self.config)
        wait_for(lambda: b"B,128\n" in self.connection.writes)
        self.assertEqual(len(self.connection.writer_threads), 1)

    def test_new_audio_session_receives_pending_volume_after_cache_refresh(self):
        self.audio.missing.add("javaw.exe")
        self.start()
        self.connection.feed(b"512|0|0|0|1|1|1|1|1\n")
        wait_for(lambda: self.engine.snapshot().percentages[0] == 50)
        self.assertFalse(any(name == "javaw.exe" for name, _ in self.audio.volumes))
        self.audio.missing.clear()
        self.engine.refresh_apps()
        wait_for(lambda: any(name == "javaw.exe" for name, _ in self.audio.volumes))

    def test_usb_removal_stops_worker_and_cleans_up_com(self):
        self.start()
        with self.assertLogs(runtime.log, level="WARNING"):
            self.connection.failure = True
            wait_for(lambda: not self.engine.running)
        self.assertEqual(self.engine.snapshot().status, "Device disconnected")
        self.assertFalse(self.engine.snapshot().connected)
        self.assertTrue(self.connection.closed)
        self.assertTrue(self.audio.closed)
        self.assertEqual([event for event, _ in self.com_threads], ["init", "uninit"])

    def test_boot_delay_can_be_cancelled_and_worker_restarted(self):
        self.engine.boot_delay = 10
        self.engine.start()
        before = time.monotonic()
        self.engine.stop(wait=True)
        self.assertLess(time.monotonic() - before, 0.5)
        self.assertFalse(self.engine.running)
        self.engine.boot_delay = 0
        self.connection = FakeSerial()
        self.start()
        self.assertTrue(self.engine.snapshot().connected)

    def test_heartbeat_continues_when_settings_and_eq_are_unchanged(self):
        with patch.object(runtime, "HEARTBEAT_SECONDS", 0.03):
            self.start()
            wait_for(lambda: self.connection.writes.count(b"H,1\n") >= 3)
        self.assertEqual(self.connection.writes.count(b"B,255\n"), 1)
        first = self.connection.writes.index(b"H,1\n")
        self.assertIn(b"C,3,88,101,242\n", self.connection.writes[:first])
        self.assertIn(b"E,-1,-1,-1,-1\n", self.connection.writes[:first])
        self.assertEqual(self.connection.writer_threads, self.audio.threads)

    def test_stop_blanks_device_without_changing_saved_brightness(self):
        self.start()
        self.assertTrue(self.engine.connection_requested)
        self.engine.stop(wait=True)
        self.assertEqual(self.connection.writes[-1], b"H,0\nB,0\n")
        self.assertEqual(self.config["brightness"], 255)
        self.assertFalse(self.engine.connection_requested)
        self.connection = FakeSerial()
        self.audio = FakeAudio()
        self.start()
        wait_for(lambda: b"H,1\n" in self.connection.writes)
        self.assertIn(b"B,255\n", self.connection.writes)

    def test_cancelled_boot_also_attempts_blackout_without_com(self):
        self.engine.boot_delay = 10
        self.engine.start()
        wait_for(lambda: self.engine.running)
        self.engine.stop(wait=True)
        self.assertEqual(self.connection.writes[-1], b"H,0\nB,0\n")
        self.assertEqual(self.com_threads, [])


class AudioCacheTests(unittest.TestCase):
    def test_session_interfaces_are_reused_and_duplicate_sessions_are_combined(self):
        volumes = [MagicMock(), MagicMock()]
        meters = [MagicMock(), MagicMock()]
        meters[0].GetPeakValue.return_value = 0.2
        meters[1].GetPeakValue.return_value = 0.7
        sessions = [MagicMock(), MagicMock()]
        for i, session in enumerate(sessions):
            session.Process.name.return_value = "spotify.exe"
            session._ctl.QueryInterface.side_effect = lambda kind, idx=i: volumes[idx] if kind is runtime.ISimpleAudioVolume else meters[idx]
        device = MagicMock()
        device.id = "output-1"
        device._dev.Activate.return_value.QueryInterface.return_value.GetPeakValue.return_value = 0.4
        with patch.object(runtime.AudioUtilities, "GetAllSessions", return_value=sessions) as enumerate_sessions, \
             patch.object(runtime.AudioUtilities, "GetSpeakers", return_value=device), \
             patch.object(runtime.AudioUtilities, "GetAllDevices", return_value=[]):
            audio = runtime.WindowsAudio()
            self.assertIn("spotify.exe", audio.refresh())
            for _ in range(30):
                peaks, master_peak = audio.read_peaks(("spotify.exe", "master"))
            self.assertEqual(enumerate_sessions.call_count, 1)
            self.assertEqual(peaks, {"spotify.exe": 0.7, "master": 0.4})
            self.assertEqual(master_peak, 0.4)
            audio.set_volume("spotify.exe", 0.5)
            for volume in volumes:
                volume.SetMasterVolume.assert_called_once_with(0.5, None)
            audio.refresh()
            self.assertEqual(device._dev.Activate.call_count, 1)
            audio.close()


if __name__ == "__main__":
    unittest.main()
