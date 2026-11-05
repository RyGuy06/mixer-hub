import ast
from pathlib import Path
import unittest

from colour_editor import QUICK_PICKS, parse_hex


class ColourInputTests(unittest.TestCase):
    def test_pasted_hex_is_validated_and_normalized(self):
        for value in ("#5865F2", "5865f2", "  #5865f2 \n"):
            self.assertEqual(parse_hex(value), "#5865f2")
        for value in ("", "#123", "##123456", "#GG0000", "#1234567", "rgb(0,0,0)"):
            self.assertIsNone(parse_hex(value))

    def test_eight_unique_quick_picks_include_white(self):
        self.assertEqual(len(QUICK_PICKS), 8)
        self.assertEqual(len({value for _, value in QUICK_PICKS}), 8)
        self.assertTrue(all(parse_hex(value) for _, value in QUICK_PICKS))
        self.assertEqual(dict(QUICK_PICKS)["Pure White"], "#FFFFFF")

    def test_audio_and_serial_frame_contracts_match_original_worker(self):
        root = Path(__file__).resolve().parents[1]
        baseline = root / "mixer_runtime.before-button-monitor.py.bak"
        if not baseline.exists():
            self.skipTest("Optional pre-monitor worker backup not present")
        before = ast.parse(baseline.read_text(encoding="utf-8"))
        after = ast.parse((root / "mixer_runtime.py").read_text(encoding="utf-8"))
        for name in ("WindowsAudio", "send_button", "parse_frame", "eq_level"):
            original = next(node for node in before.body if getattr(node, "name", "") == name)
            current = next(node for node in after.body if getattr(node, "name", "") == name)
            self.assertEqual(ast.dump(original), ast.dump(current))
        # The loop now deliberately also owns heartbeat/blackout writes.
        # Runtime tests cover that behaviour rather than freezing the old loop.
