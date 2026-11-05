import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

import app_paths
from build import build_command, ICON_SIZES


class ProductionPathsTests(unittest.TestCase):
    def test_source_paths_do_not_depend_on_current_directory(self):
        with patch.object(sys, "frozen", False, create=True):
            self.assertEqual(app_paths.config_path(), app_paths.SOURCE_ROOT / "mixer_config.json")
            self.assertEqual(app_paths.resource_path("assets/product"), app_paths.SOURCE_ROOT / "assets/product")

    def test_frozen_config_and_resources_have_separate_roots(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {"APPDATA": directory}), \
             patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", str(Path(directory) / "unpacked"), create=True):
            self.assertEqual(app_paths.config_path(), Path(directory) / "MixerHub/mixer_config.json")
            self.assertEqual(app_paths.resource_path("assets/app_icon.ico"), Path(directory) / "unpacked/assets/app_icon.ico")

    def test_missing_appdata_falls_back_to_home(self):
        with patch.dict(os.environ, {}, clear=True), patch("app_paths.os.path.expanduser", return_value="C:/test-home"):
            self.assertEqual(app_paths.user_data_dir(), Path("C:/test-home/MixerHub"))

    def test_migration_retains_profiles_and_original_without_overwriting_new_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "legacy.json"
            contents = json.dumps({"profiles": {"Gaming": {"channels": [{"app": "game.exe"}]}},
                                   "active_profile": "Gaming", "known_apps": ["game.exe"]}).encode()
            old.write_bytes(contents)
            destination = root / "roaming/MixerHub/mixer_config.json"
            self.assertEqual(app_paths.migrate_legacy_config(destination, [old]), old)
            self.assertEqual(destination.read_bytes(), contents)
            self.assertEqual(old.read_bytes(), contents)
            destination.write_text('{"new": true}', encoding="utf-8")
            self.assertIsNone(app_paths.migrate_legacy_config(destination, [old]))
            self.assertEqual(destination.read_text(), '{"new": true}')

    def test_invalid_legacy_config_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid, valid, destination = (root / name for name in ("bad.json", "good.json", "new.json"))
            invalid.write_text("broken", encoding="utf-8")
            valid.write_text('{"auto_connect": false}', encoding="utf-8-sig")
            with self.assertLogs(level="WARNING"):
                self.assertEqual(app_paths.migrate_legacy_config(destination, [root / "absent.json", invalid, valid]), valid)
            self.assertFalse(json.loads(destination.read_text(encoding="utf-8-sig"))["auto_connect"])

    def test_legacy_search_includes_old_packaged_and_development_config(self):
        with tempfile.TemporaryDirectory() as directory:
            # Compare the canonical paths produced by executable.resolve().
            root = Path(directory).resolve()
            (root / "app.py").touch()
            with patch.dict(os.environ, {"LOCALAPPDATA": str(root / "local")}), \
                 patch.object(sys, "executable", str(root / "dist/MixerHub.exe")):
                self.assertEqual(app_paths.legacy_config_paths(), [root / "local/MixerHub/mixer_config.json",
                                 root / "dist/mixer_config.json", root / "mixer_config.json"])


class BuildTests(unittest.TestCase):
    def test_build_is_windowed_one_file_with_explicit_resources(self):
        command = build_command()
        for required in ("--onefile", "--noconsole", "--icon", "customtkinter", "pystray._win32",
                         "serial.serialwin32", "keyboard._winkeyboard", "comtypes.client"):
            self.assertIn(required, command)
        self.assertFalse(any("mixer_config.json" in argument for argument in command))
        data = [command[i + 1] for i, value in enumerate(command) if value == "--add-data"]
        self.assertTrue(any("assets/product" in argument for argument in data))

    def test_generated_icon_contains_all_native_sizes(self):
        with Image.open(app_paths.resource_path("assets/app_icon.ico")) as icon:
            self.assertEqual(icon.ico.sizes(), {(size, size) for size in ICON_SIZES})
            for size in ICON_SIZES:
                frame = icon.ico.getimage((size, size))
                self.assertEqual(frame.size, (size, size))
                self.assertIsNotNone(frame.getbbox())


if __name__ == "__main__":
    unittest.main()
