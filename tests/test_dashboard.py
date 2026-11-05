import copy
import json
import unittest

from dashboard_layout import DEFAULT_LAYOUT, move_widget, normalize_layout, swap_channels
import profiles
from test_runtime import CONFIG


class DashboardTests(unittest.TestCase):
    def test_custom_layout_and_swapped_setup_survive_save_reload(self):
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        import app
        config = copy.deepcopy(CONFIG)
        config["dashboard_layout"] = {"order": ["channels", "device", "activity"],
                                      "hidden": ["activity"], "view": "side", "guides": False}
        swap_channels(config, 2, 1)
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "CONFIG_FILE", Path(folder) / "config.json"):
            app.save_config(config)
            loaded = app.load_config()
            self.assertEqual(normalize_layout(loaded["dashboard_layout"]), config["dashboard_layout"])
            self.assertEqual(loaded["profiles"]["Default"]["channels"][1], CONFIG["channels"][2])

    def test_invalid_saved_layout_keeps_all_widgets_and_channels_visible(self):
        layout = normalize_layout({"order": ["channels", "invalid", "channels"],
                                   "hidden": ["channels", "device", "bad"], "view": "bad"})
        self.assertEqual(layout["order"], ["channels", "device", "activity"])
        self.assertEqual(layout["hidden"], ["device"])
        self.assertEqual(layout["view"], "top")
        self.assertEqual(normalize_layout(None), DEFAULT_LAYOUT)

    def test_section_move_is_saved_without_mutating_source(self):
        layout = copy.deepcopy(DEFAULT_LAYOUT)
        moved = move_widget(layout, "device", "channels")
        self.assertEqual(moved["order"], ["channels", "device", "activity"])
        self.assertEqual(layout, DEFAULT_LAYOUT)
        self.assertEqual(normalize_layout(json.loads(json.dumps(moved))), moved)
        self.assertEqual(move_widget({}, "device", "activity")["order"], ["channels", "activity", "device"])

    def test_swap_moves_entire_setup_and_preserves_other_channels(self):
        config = copy.deepcopy(CONFIG)
        config["channels"][2]["priority"] = ["chrome.exe", "firefox.exe"]
        before = copy.deepcopy(config)
        self.assertTrue(swap_channels(config, 2, 1))
        self.assertEqual(config["channels"][1], before["channels"][2])
        self.assertEqual(config["channels"][2], before["channels"][1])
        self.assertEqual(config["channels"][0], before["channels"][0])
        self.assertEqual(config["channels"][3], before["channels"][3])
        self.assertTrue(swap_channels(config, 2, 1))
        self.assertEqual(config, before)
        self.assertFalse(swap_channels(config, 1, 1))
        with self.assertRaises(ValueError):
            swap_channels(config, -1, 2)

    def test_swapped_channels_are_per_profile_while_layout_is_global(self):
        config = copy.deepcopy(CONFIG)
        profiles.initialize(config)
        profiles.create(config, "Gaming")
        config["dashboard_layout"] = move_widget(DEFAULT_LAYOUT, "device", "activity")
        swap_channels(config, 0, 3)
        profiles.select(config, "Default")
        self.assertEqual(config["channels"], CONFIG["channels"])
        self.assertEqual(config["dashboard_layout"]["order"], ["channels", "activity", "device"])
        profiles.select(config, "Gaming")
        self.assertEqual(config["channels"][3], CONFIG["channels"][0])
