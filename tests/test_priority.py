import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app_routing import initialize_library, priority_for, resolve_routes, validate_app_name
import mixer_runtime as runtime
import profiles
from test_runtime import CONFIG, FakeAudio, FakeSerial, wait_for


class RoutingTests(unittest.TestCase):
    def test_unplugged_discovery_pauses_when_audio_worker_is_running(self):
        import threading
        running = True
        received = threading.Event()
        with patch.object(runtime, "list_audio_apps", return_value=["master", "new-game.exe"]) as scan:
            discovery = runtime.AppDiscovery(lambda: not running,
                                              lambda names: received.set(), scanner=scan, interval=0.01)
            try:
                discovery.start()
                self.assertFalse(received.wait(0.04))
                scan.assert_not_called()
                running = False
                self.assertTrue(received.wait(0.5))
                scan.assert_called()
            finally:
                discovery.stop()
            self.assertFalse(discovery._thread.is_alive())
    def test_first_available_wins_and_missing_list_waits(self):
        self.assertEqual(resolve_routes(("old.exe", "master"),
                                       (("first.exe", "second.exe"), ()), ("master", "second.exe")),
                         ("second.exe", "master"))
        self.assertEqual(resolve_routes(("old.exe",), (("first.exe",),), ("master",)), ("",))
        self.assertEqual(resolve_routes(("old.exe",), (("first.exe", "master"),), ("master",)), ("master",))

    def test_priority_names_are_normalized_without_changing_order(self):
        self.assertEqual(priority_for({"priority": [" BETA.EXE ", "alpha.exe", "beta.exe"]}),
                         ("beta.exe", "alpha.exe"))
        self.assertEqual(priority_for({"priority": "not a list"}), ())

    def test_history_is_global_and_priorities_are_per_profile(self):
        config = copy.deepcopy(CONFIG)
        profiles.initialize(config)
        profiles.create(config, "Games")
        config["channels"][0]["priority"] = ["alpha.exe", "beta.exe"]
        profiles.remember(config)
        initialize_library(config)
        profiles.select(config, "Default")
        self.assertNotIn("priority", config["channels"][0])
        self.assertIn("beta.exe", config["known_apps"])
        profiles.select(config, "Games")
        self.assertEqual(config["channels"][0]["priority"], ["alpha.exe", "beta.exe"])

    def test_history_and_priority_survive_real_config_save_reload(self):
        import app
        config = copy.deepcopy(CONFIG)
        config["known_apps"] = ["closed-game.exe"]
        config["channels"][0]["priority"] = ["alpha.exe", "beta.exe"]
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "CONFIG_FILE", Path(folder) / "mixer_config.json"):
            app.save_config(config)
            loaded = app.load_config()
            self.assertEqual(loaded["known_apps"], ["closed-game.exe"])
            self.assertEqual(loaded["profiles"]["Default"]["channels"][0]["priority"], ["alpha.exe", "beta.exe"])
            self.assertEqual(json.loads(app.CONFIG_FILE.read_text())["known_apps"], ["closed-game.exe"])

    def test_manual_executable_entry_accepts_names_and_rejects_paths(self):
        self.assertEqual(validate_app_name("  Game-Win64-Shipping.EXE "), "game-win64-shipping.exe")
        for name in ("", "game", "C:/game.exe", "../game.exe", "bad\n.exe"):
            with self.assertRaises(ValueError):
                validate_app_name(name)


class PriorityEngineTests(unittest.TestCase):
    def setUp(self):
        self.config = copy.deepcopy(CONFIG)
        self.config["channels"][0]["priority"] = ["alpha.exe", "beta.exe"]
        self.serial, self.audio = FakeSerial(), FakeAudio()
        self.audio.peaks["beta.exe"] = 0.09
        self.patches = [patch.object(runtime, "CoInitialize"), patch.object(runtime, "CoUninitialize"),
                        patch.object(runtime, "SESSION_REFRESH_SECONDS", 0.05),
                        patch.object(runtime, "TICK_SECONDS", 0.01),
                        patch.object(runtime, "EQ_IDLE_SECONDS", 0.02)]
        for item in self.patches:
            item.start()
        self.engine = runtime.MixerEngine(self.config, serial_factory=lambda *args, **kwargs: self.serial,
                                          port_finder=lambda: "TEST", audio_factory=lambda: self.audio,
                                          button_sender=lambda *args: None, boot_delay=0)
        self.engine.start()
        self.serial.feed(b"512|0|0|0|1|1|1|1|1\n")
        wait_for(lambda: self.engine.snapshot().percentages[0] == 50)

    def tearDown(self):
        self.engine.stop(wait=True)
        for item in reversed(self.patches):
            item.stop()

    def test_game_open_close_handoff_uses_current_volume_and_eq(self):
        wait_for(lambda: self.engine.snapshot().eq_levels[0] == 31)
        self.assertEqual(self.engine.snapshot().resolved_apps[0], "beta.exe")
        self.audio.peaks["alpha.exe"] = 0.64
        wait_for(lambda: self.engine.snapshot().resolved_apps[0] == "alpha.exe"
                 and self.engine.snapshot().eq_levels[0] == 84)
        self.assertIn(("alpha.exe", 512 / 1023), self.audio.volumes)
        before = self.audio.volumes.count(("beta.exe", 512 / 1023))
        del self.audio.peaks["alpha.exe"]
        wait_for(lambda: self.engine.snapshot().resolved_apps[0] == "beta.exe")
        self.assertGreater(self.audio.volumes.count(("beta.exe", 512 / 1023)), before)
        self.assertIn("alpha.exe", self.engine.snapshot().known_apps)
        self.assertEqual(self.config["channels"][0]["app"], "javaw.exe")

    def test_no_match_waits_and_next_game_gets_latest_physical_position(self):
        del self.audio.peaks["beta.exe"]
        wait_for(lambda: self.engine.snapshot().resolved_apps[0] == "")
        before = len(self.audio.volumes)
        self.serial.feed(b"770|0|0|0|1|1|1|1|1\n")
        wait_for(lambda: self.engine.snapshot().percentages[0] == 75)
        self.assertEqual(len(self.audio.volumes), before)
        self.audio.peaks["beta.exe"] = 0.2
        wait_for(lambda: self.engine.snapshot().resolved_apps[0] == "beta.exe")
        self.assertIn(("beta.exe", 770 / 1023), self.audio.volumes)

    def test_silent_higher_priority_game_keeps_route(self):
        self.audio.peaks["alpha.exe"] = 0.0
        wait_for(lambda: self.engine.snapshot().resolved_apps[0] == "alpha.exe")
        wait_for(lambda: self.engine.snapshot().eq_levels[0] == -1)
        self.assertIn(("alpha.exe", 512 / 1023), self.audio.volumes)

    def test_reordering_list_live_changes_route_without_slider_movement(self):
        self.audio.peaks["alpha.exe"] = 0.2
        wait_for(lambda: self.engine.snapshot().resolved_apps[0] == "alpha.exe")
        self.config["channels"][0]["priority"] = ["beta.exe", "alpha.exe"]
        self.engine.update_config(self.config)
        wait_for(lambda: self.engine.snapshot().resolved_apps[0] == "beta.exe")
        self.assertIn(("beta.exe", 512 / 1023), self.audio.volumes)
