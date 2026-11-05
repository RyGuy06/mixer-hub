import ctypes
from ctypes import wintypes
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
import psutil
from app_icons import AppIconCache, extract_icon


class IconTests(unittest.TestCase):
    def test_icons_are_cached_and_missing_app_can_be_discovered_later(self):
        process = SimpleNamespace(info={"name": "Game.exe", "exe": "C:/Games/Game.exe"})
        with patch("app_icons.psutil.process_iter", side_effect=[[], [process]]) as scan, \
             patch("app_icons.extract_icon", return_value=Image.new("RGBA", (64, 64), "red")) as extract:
            cache = AppIconCache()
            fallback = cache.get("game.exe")
            for _ in range(30):
                self.assertIs(cache.get("game.exe"), fallback)
            self.assertEqual(scan.call_count, 1)
            cache.refresh_for_apps(["game.exe"])
            real = cache.get("game.exe")
            self.assertIsNot(real, fallback)
            self.assertIs(cache.get("game.exe"), real)
            dimmed = cache.get("game.exe", dim=True)
            self.assertEqual(real.cget("size"), (28, 28))
            self.assertLess(dimmed.cget("dark_image").getchannel("A").getextrema()[1], 255)
            self.assertEqual(extract.call_count, 1)
            self.assertEqual(scan.call_count, 2)

    def test_denied_process_metadata_uses_a_cached_fallback(self):
        with patch("app_icons.psutil.process_iter", side_effect=psutil.AccessDenied(123)) as scan:
            cache = AppIconCache()
            icon = cache.get("protected.exe")
            self.assertIsNotNone(icon.cget("dark_image").getchannel("A").getbbox())
            self.assertIs(cache.get("protected.exe"), icon)
            self.assertEqual(scan.call_count, 1)

    def test_real_windows_executable_icon_does_not_leak_gdi_handles(self):
        user = ctypes.WinDLL("user32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.argtypes, kernel.GetCurrentProcess.restype = [], wintypes.HANDLE
        user.GetGuiResources.argtypes, user.GetGuiResources.restype = [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD
        image = extract_icon(sys.executable)
        self.assertIsNotNone(image)
        self.assertIsNotNone(image.getchannel("A").getbbox())
        process = kernel.GetCurrentProcess()
        before = (user.GetGuiResources(process, 0), user.GetGuiResources(process, 1))
        for _ in range(12):
            self.assertIsNotNone(extract_icon(sys.executable))
        after = (user.GetGuiResources(process, 0), user.GetGuiResources(process, 1))
        self.assertEqual(after, before)
