from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import winreg

import windows_startup as startup


class StartupTests(unittest.TestCase):
    def test_development_command_uses_windowed_python_and_quotes_spaces(self):
        with tempfile.TemporaryDirectory(prefix="Mixer Hub ") as directory:
            # Windows build runners may expose TEMP through an 8.3 alias.
            root = Path(directory).resolve()
            python = root / "python.exe"
            (root / "pythonw.exe").touch()
            script = root / "app.py"
            script.touch()
            command = startup.startup_command(script, executable=python, frozen=False)
            self.assertEqual(command, f'"{root / "pythonw.exe"}" "{script}" --background')

    def test_packaged_command_runs_the_exe_in_background(self):
        executable = Path("C:/Mixer Hub/Mixer Hub.exe")
        self.assertEqual(startup.startup_command("unused", executable=executable, frozen=True),
                         '"C:\\Mixer Hub\\Mixer Hub.exe" --background')

    def test_invalid_command_does_not_register_startup(self):
        with patch.object(startup, "startup_command", side_effect=FileNotFoundError), \
             patch.object(startup.winreg, "CreateKeyEx") as create:
            with self.assertRaises(FileNotFoundError):
                startup.WindowsStartup("app.py").set_enabled(True)
            create.assert_not_called()

    def test_only_own_current_user_run_value_is_changed(self):
        manager = startup.WindowsStartup("app.py")
        key = MagicMock()
        with patch.object(startup, "startup_command", return_value='"app.exe" --background'), \
             patch.object(startup.winreg, "CreateKeyEx", return_value=key) as create, \
             patch.object(startup.winreg, "SetValueEx") as set_value:
            manager.set_enabled(True)
            create.assert_called_once_with(winreg.HKEY_CURRENT_USER, startup.RUN_KEY, 0, winreg.KEY_SET_VALUE)
            set_value.assert_called_once_with(key.__enter__.return_value, "MixerHub", 0,
                                             winreg.REG_SZ, '"app.exe" --background')
        with patch.object(startup.winreg, "OpenKey", return_value=key), \
             patch.object(startup.winreg, "DeleteValue") as delete:
            manager.set_enabled(False)
            delete.assert_called_once_with(key.__enter__.return_value, "MixerHub")

    def test_missing_entry_is_disabled_and_can_be_removed_idempotently(self):
        with patch.object(startup.winreg, "OpenKey", side_effect=FileNotFoundError):
            manager = startup.WindowsStartup("app.py")
            self.assertFalse(manager.is_enabled())
            manager.set_enabled(False)

    def test_registration_read_does_not_rewrite_windows_settings(self):
        with patch.object(startup.winreg, "OpenKey"), \
             patch.object(startup.winreg, "QueryValueEx", return_value=("command", winreg.REG_SZ)), \
             patch.object(startup.winreg, "SetValueEx") as write:
            self.assertTrue(startup.WindowsStartup("app.py").is_enabled())
            write.assert_not_called()


class AutoConnectTests(unittest.TestCase):
    def test_retries_are_throttled_and_never_spawn_a_second_worker(self):
        auto = startup.AutoConnect(enabled=True)
        self.assertTrue(auto.should_connect(0, running=False, connected=False))
        self.assertFalse(auto.should_connect(4.9, running=False, connected=False))
        self.assertFalse(auto.should_connect(5, running=True, connected=False))
        self.assertFalse(auto.should_connect(5, running=False, connected=True))
        self.assertTrue(auto.should_connect(5, running=False, connected=False))

    def test_manual_disconnect_pauses_until_manual_connect_or_reenable(self):
        auto = startup.AutoConnect(enabled=True)
        auto.manual_disconnect()
        self.assertFalse(auto.should_connect(100, running=False, connected=False))
        auto.manual_connect(100)
        self.assertFalse(auto.should_connect(101, running=False, connected=False))
        self.assertTrue(auto.should_connect(105, running=False, connected=False))
        auto.manual_disconnect()
        auto.set_enabled(True)
        self.assertTrue(auto.should_connect(106, running=False, connected=False))

    def test_turning_option_off_stops_retrying(self):
        auto = startup.AutoConnect(enabled=True)
        auto.set_enabled(False)
        self.assertFalse(auto.should_connect(100, running=False, connected=False))


if __name__ == "__main__":
    unittest.main()
