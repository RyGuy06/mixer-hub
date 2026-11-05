import copy
import unittest

import profiles
from test_runtime import CONFIG


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = copy.deepcopy(CONFIG)
        self.config.update(auto_connect=True, device_port="COM5", device_serial="nano-1")
        profiles.initialize(self.config)

    def test_existing_settings_become_default_without_changing_them(self):
        self.assertEqual(self.config["profiles"]["Default"], CONFIG)
        self.assertEqual(self.config["active_profile"], "Default")

    def test_copy_and_switch_preserve_edits_and_global_preferences(self):
        profiles.create(self.config, "Gaming")
        self.config["channels"][0]["app"] = "game.exe"
        self.config["channels"][0]["color"] = "#123456"
        self.config["brightness"] = 80
        self.config["hotkeys"]["mute"] = "ctrl+m"
        profiles.select(self.config, "Default")
        self.assertEqual(profiles.snapshot(self.config), CONFIG)
        profiles.select(self.config, "Gaming")
        self.assertEqual(self.config["channels"][0], {"app": "game.exe", "color": "#123456"})
        self.assertEqual(self.config["brightness"], 80)
        self.assertEqual(self.config["hotkeys"]["mute"], "ctrl+m")
        self.assertTrue(self.config["auto_connect"])
        self.assertEqual(self.config["device_serial"], "nano-1")

    def test_names_are_trimmed_and_unique_ignoring_case(self):
        self.assertEqual(profiles.create(self.config, "  Gaming  "), "Gaming")
        for invalid in ("gaming", " ", "a" * 33, "bad\nname"):
            with self.assertRaises(ValueError):
                profiles.create(self.config, invalid)

    def test_rename_and_delete_load_remaining_setup(self):
        profiles.create(self.config, "Gaming")
        self.config["brightness"] = 1
        profiles.rename(self.config, "Games")
        self.assertNotIn("Gaming", self.config["profiles"])
        profiles.delete(self.config)
        self.assertEqual(self.config["active_profile"], "Default")
        self.assertEqual(self.config["brightness"], CONFIG["brightness"])
        with self.assertRaises(ValueError):
            profiles.delete(self.config)

    def test_missing_selection_fails_before_changing_setup(self):
        before = copy.deepcopy(self.config)
        with self.assertRaises(ValueError):
            profiles.select(self.config, "Missing")
        self.assertEqual(self.config, before)
