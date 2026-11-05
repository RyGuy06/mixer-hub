"""Per-user Windows startup registration, changed only by the settings switch."""
from pathlib import Path
import subprocess
import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "MixerHub"


def startup_command(script_path, *, executable=None, frozen=None):
    executable = Path(executable or sys.executable).resolve()
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if frozen:
        args = [str(executable), "--background"]
    else:
        pythonw = executable.with_name("pythonw.exe")
        if not pythonw.is_file():
            raise FileNotFoundError("The windowed Python launcher (pythonw.exe) could not be found.")
        script_path = Path(script_path).resolve()
        if not script_path.is_file():
            raise FileNotFoundError("Mixer Hub's app.py could not be found.")
        args = [str(pythonw), str(script_path), "--background"]
    command = subprocess.list2cmdline(args)
    if len(command) > 260:
        raise ValueError("This installation path is too long for Windows startup. Move the app to a shorter path.")
    return command


class WindowsStartup:
    def __init__(self, script_path):
        self.script_path = Path(script_path)

    def is_enabled(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
                command, _ = winreg.QueryValueEx(key, VALUE_NAME)
                return bool(command)
        except FileNotFoundError:
            return False

    def set_enabled(self, enabled):
        if enabled:
            command = startup_command(self.script_path)
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass


class AutoConnect:
    """Retry with a cheap timer; a deliberate Disconnect pauses retries."""
    def __init__(self, enabled=False, interval=5.0):
        self.enabled = enabled
        self.interval = interval
        self.paused = False
        self.next_attempt = 0.0

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.paused = False
        self.next_attempt = 0.0

    def manual_disconnect(self):
        self.paused = True

    def manual_connect(self, now):
        self.paused = False
        self.next_attempt = now + self.interval

    def should_connect(self, now, *, running, connected):
        if not self.enabled or self.paused or running or connected or now < self.next_attempt:
            return False
        self.next_attempt = now + self.interval
        return True
