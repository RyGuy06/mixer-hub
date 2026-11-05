import subprocess
import sys
import unittest
import uuid

from single_instance import SingleInstance


class InstanceTests(unittest.TestCase):
    def test_second_process_signals_first_and_exits(self):
        guard = SingleInstance("MixerHub.Test." + uuid.uuid4().hex)
        try:
            self.assertTrue(guard.acquire())
            code = ("import sys; from single_instance import SingleInstance; "
                    "guard=SingleInstance(sys.argv[1]); "
                    "print(guard.acquire()); guard.close()")
            result = subprocess.run([sys.executable, "-c", code, guard.name],
                                    check=True, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.stdout.strip(), "False")
            self.assertTrue(guard.restore_requested())
            self.assertFalse(guard.restore_requested())
        finally:
            guard.close()
        replacement = SingleInstance(guard.name)
        try:
            self.assertTrue(replacement.acquire())
        finally:
            replacement.close()

    def test_background_duplicate_does_not_open_existing_window(self):
        first = SingleInstance("MixerHub.Test." + uuid.uuid4().hex)
        second = SingleInstance(first.name)
        try:
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire(show_existing=False))
            self.assertFalse(first.restore_requested())
            first.close()
            self.assertTrue(second.acquire())
        finally:
            first.close()
            second.close()
