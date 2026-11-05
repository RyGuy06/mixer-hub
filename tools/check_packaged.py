"""Launch the real EXE with isolated data; exercise tray and duplicate launches.

No serial connection is made and no Windows startup registration is changed.
Use --pause-development-copy to quit/reopen this checkout's running Python app.
"""
import argparse
import copy
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pefile
import psutil
from PIL import ImageGrab
from PyInstaller.archive.readers import CArchiveReader
from single_instance import SingleInstance


USER = ctypes.WinDLL("user32", use_last_error=True)
USER.SetProcessDPIAware()  # GetWindowRect and injected mouse coordinates must agree.
ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
for name, args, result in (
    ("EnumWindows", [ENUM_PROC, wintypes.LPARAM], wintypes.BOOL),
    ("GetWindowThreadProcessId", [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
    ("GetWindowTextW", [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
    ("GetClassNameW", [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
    ("IsWindowVisible", [wintypes.HWND], wintypes.BOOL),
    ("GetForegroundWindow", [], wintypes.HWND),
    ("PostMessageW", [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], wintypes.BOOL),
    ("GetWindowRect", [wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
    ("SetWindowPos", [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                      ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL),
    ("GetCursorPos", [ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
    ("SetCursorPos", [ctypes.c_int, ctypes.c_int], wintypes.BOOL),
    ("mouse_event", [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t], None),
):
    function = getattr(USER, name)
    function.argtypes, function.restype = args, result


def windows():
    found = []

    @ENUM_PROC
    def collect(window, _):
        pid, title, kind = wintypes.DWORD(), ctypes.create_unicode_buffer(512), ctypes.create_unicode_buffer(256)
        USER.GetWindowThreadProcessId(window, ctypes.byref(pid))
        USER.GetWindowTextW(window, title, len(title))
        USER.GetClassNameW(window, kind, len(kind))
        found.append((window, pid.value, title.value, kind.value))
        return True

    USER.EnumWindows(collect, 0)
    return found


def wait_for(predicate, description, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("Timed out: " + description)


def tray_windows(pid):
    # pystray creates a notification window AND a menu-owner window with the
    # same class. Only the notification window dispatches these messages.
    return [window for window, process, _, kind in windows()
            if process == pid and kind.startswith("MixerHub") and kind.endswith("SystemTrayIcon")]


def notify_tray(pid, mouse_message):
    for window in tray_windows(pid):
        USER.PostMessageW(window, 0x400 + 11, 0, mouse_message)


def quit_via_tray(pid):
    wait_for(lambda: tray_windows(pid), "tray window")
    notify_tray(pid, 0x205)  # pystray WM_NOTIFY / right-button-up
    popup = wait_for(lambda: next((window for window, process, _, kind in windows()
                                  if process == pid and kind == "#32768"), None), "tray popup menu")
    # Click the final row inside this exact popup. Keyboard messages do not
    # reliably select a menu item from an external automation process.
    rectangle, cursor = wintypes.RECT(), wintypes.POINT()
    USER.GetWindowRect(popup, ctypes.byref(rectangle))
    USER.GetCursorPos(ctypes.byref(cursor))
    try:
        USER.SetCursorPos((rectangle.left + rectangle.right) // 2, rectangle.bottom - 13)
        USER.mouse_event(2, 0, 0, 0, 0)
        USER.mouse_event(4, 0, 0, 0, 0)
        time.sleep(0.25)
    finally:
        USER.SetCursorPos(cursor.x, cursor.y)
    wait_for(lambda: not psutil.pid_exists(pid), "clean tray quit")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pause-development-copy", action="store_true")
    args = parser.parse_args()
    executable = ROOT / "dist/MixerHub.exe"
    assert executable.is_file(), "Build the EXE first with build.py"
    with pefile.PE(str(executable), fast_load=True) as image:
        assert image.OPTIONAL_HEADER.Subsystem == 2, "EXE must use the Windows GUI subsystem"
        assert image.FILE_HEADER.Machine == 0x8664, "Expected a 64-bit Windows EXE"
    bundle = CArchiveReader(str(executable))
    assert not any("mixer_config.json" in name.lower() or "previews/" in name.lower() for name in bundle.toc)
    for resource in ("assets/app_icon.ico", "assets/app_icon.png", "assets/product/top 1.png", "assets/product/side 1.png"):
        assert resource.replace("/", "\\") in bundle.toc or resource in bundle.toc, resource

    guard = SingleInstance()
    restart_background = None
    if not guard.acquire(show_existing=False):
        existing = next(((window, pid) for window, pid, title, kind in windows()
                         if title == "Mixer Hub" and kind == "TkTopLevel"), None)
        if not args.pause_development_copy or not existing:
            raise RuntimeError("Quit the running Mixer Hub from its tray menu, then repeat this check.")
        window, pid = existing
        command = psutil.Process(pid).cmdline()
        if not any(Path(argument).resolve() == ROOT / "app.py" for argument in command[1:] if not argument.startswith("--")):
            raise RuntimeError("The running Mixer Hub is not this checkout's development copy; it was left alone.")
        restart_background = not bool(USER.IsWindowVisible(window))
        print("Temporarily quitting the development copy through its tray menu.", flush=True)
        quit_via_tray(pid)
        wait_for(lambda: guard.acquire(show_existing=False), "instance lock released")
    guard.close()
    original_config = (ROOT / "mixer_config.json").read_bytes() if (ROOT / "mixer_config.json").exists() else None
    process = None
    temporary = tempfile.TemporaryDirectory(prefix="mixerhub-packaged-")
    results = {}
    try:
        directory = Path(temporary.name)
        portable = directory / "app"
        portable.mkdir()
        copy_exe = portable / "MixerHub.exe"
        shutil.copy2(executable, copy_exe)
        # Explicit fixture, with auto-connect OFF. Never seed from user settings.
        config = {"auto_connect": False, "brightness": 45,
                  "channels": [{"app": name, "color": colour} for name, colour in
                               (("master", "#91BFFF"), ("spotify.exe", "#1ED760"),
                                ("chrome.exe", "#EB3223"), ("discord.exe", "#5865F2"))],
                  "hotkeys": {"mute": "ctrl+shift+f11", "deafen": "ctrl+shift+f12"},
                  "known_apps": ["packaged-test.exe"]}
        config["profiles"] = {"V1 Smoke": {name: copy.deepcopy(config[name]) for name in ("channels", "brightness", "hotkeys")}}
        config["active_profile"] = "V1 Smoke"
        legacy = portable / "mixer_config.json"
        fixture_bytes = json.dumps(config, indent=2).encode()
        legacy.write_bytes(fixture_bytes)
        environment = os.environ.copy()
        environment.update(APPDATA=str(directory / "roaming"), LOCALAPPDATA=str(directory / "local"),
                           PATH=str(Path(os.environ["SystemRoot"]) / "System32"))
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        settings = directory / "roaming/MixerHub/mixer_config.json"
        log_file = directory / "roaming/MixerHub/MixerHub.log"
        process = subprocess.Popen([str(copy_exe)], cwd=directory, env=environment)

        def primary_window():
            descendants = {process.pid}
            try:
                descendants.update(child.pid for child in psutil.Process(process.pid).children(recursive=True))
            except psutil.NoSuchProcess:
                pass
            return next(((window, pid) for window, pid, title, kind in windows()
                         if pid in descendants and title == "Mixer Hub" and kind == "TkTopLevel"), None)

        window, pid = wait_for(primary_window, "packaged dashboard")
        wait_for(lambda: log_file.exists() and "Dashboard ready; product renders: side, top" in log_file.read_text(encoding="utf-8"),
                 "bundled product artwork loaded")
        wait_for(lambda: USER.IsWindowVisible(window) and tray_windows(pid), "visible dashboard and real tray")
        print("PASS: packaged launch, artwork and isolated settings migration.", flush=True)
        migrated = json.loads(settings.read_text(encoding="utf-8-sig"))
        assert migrated["active_profile"] == "V1 Smoke" and migrated["profiles"] == config["profiles"]
        assert legacy.read_bytes() == fixture_bytes
        assert not any(kind == "ConsoleWindowClass" and process_id == pid for _, process_id, _, kind in windows())
        time.sleep(0.6)
        # Tk's nested custom canvases do not all paint into PrintWindow. Briefly
        # expose this window and capture its actual pixels, then remove topmost.
        rectangle = wintypes.RECT()
        USER.SetWindowPos(window, wintypes.HWND(-1), 0, 0, 0, 0, 0x13)
        try:
            time.sleep(0.4)
            USER.GetWindowRect(window, ctypes.byref(rectangle))
            ImageGrab.grab(bbox=(rectangle.left, rectangle.top, rectangle.right, rectangle.bottom)).save(ROOT / "previews/packaged-mixer.png")
        finally:
            USER.SetWindowPos(window, wintypes.HWND(-2), 0, 0, 0, 0, 0x13)

        USER.PostMessageW(window, 0x10, 0, 0)  # Same WM_CLOSE as the title-bar X.
        wait_for(lambda: not USER.IsWindowVisible(window), "X hides to tray")
        assert process.poll() is None
        duplicate = subprocess.Popen([str(copy_exe), "--background"], cwd=directory, env=environment)
        assert duplicate.wait(timeout=25) == 0
        assert not USER.IsWindowVisible(window), "Background duplicate must keep the window hidden"
        duplicate = subprocess.Popen([str(copy_exe)], cwd=directory, env=environment)
        assert duplicate.wait(timeout=25) == 0
        wait_for(lambda: USER.IsWindowVisible(window), "second launch restores original dashboard")
        focus_deadline = time.monotonic() + 2
        while time.monotonic() < focus_deadline and USER.GetForegroundWindow() != window:
            time.sleep(0.05)
        foreground = USER.GetForegroundWindow() == window
        print(f"PASS: duplicate restore (foreground observed: {foreground}).", flush=True)
        assert len([1 for _, process_id, title, kind in windows() if process_id == pid and title == "Mixer Hub" and kind == "TkTopLevel"]) == 1
        quit_via_tray(pid)
        assert process.wait(timeout=15) == 0
        print("PASS: clean tray Quit.", flush=True)

        # Start quietly from the same writable settings, then restore and quit.
        process = subprocess.Popen([str(copy_exe), "--background"], cwd=directory, env=environment)
        window, pid = wait_for(primary_window, "background startup")
        wait_for(lambda: tray_windows(pid), "background tray ready")
        time.sleep(0.4)
        assert not USER.IsWindowVisible(window)
        notify_tray(pid, 0x202)  # Left-button-up: Open.
        wait_for(lambda: USER.IsWindowVisible(window), "tray Open restores background launch")
        quit_via_tray(pid)
        assert process.wait(timeout=15) == 0
        log = log_file.read_text(encoding="utf-8")
        assert "startup failed" not in log and "Interface callback failed" not in log
        results = {"result": "PASS", "executable": executable.name, "size_mb": round(executable.stat().st_size / 1024**2, 1),
                   "foreground_observed": foreground,
                   "foreground_note": "Windows may refuse focus from a background automation runner; duplicate launches pass foreground permission when available.",
                   "checks": ["64-bit GUI subsystem; no terminal window", "single EXE copied away from the checkout",
                              "Python removed from PATH", "bundled icons and top/side renders", "isolated APPDATA logs/settings",
                              "legacy config migration retains named profiles and original file", "X hides to tray",
                              "background duplicate exits quietly", "normal duplicate restores the same window",
                              "tray Quit exits cleanly", "background startup and tray Open"]}
        print(json.dumps(results, indent=2), flush=True)
    finally:
        if process and process.poll() is None:
            children = psutil.Process(process.pid).children(recursive=True)
            for child in children:
                child.kill()
            psutil.wait_procs(children, timeout=10)
            process.kill()
            process.wait(timeout=10)
        if 'log_file' in locals() and log_file.exists():
            shutil.copy2(log_file, ROOT / "previews/packaged-run.log")
        if original_config is not None:
            assert (ROOT / "mixer_config.json").read_bytes() == original_config, "Development settings changed"
        for attempt in range(10):
            try:
                temporary.cleanup()
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.25)
        if restart_background is not None:
            command = [str(ROOT / ".venv/Scripts/pythonw.exe"), str(ROOT / "app.py")]
            if restart_background:
                command.append("--background")
            subprocess.Popen(command, cwd=ROOT)
            print("Reopened the development copy.", flush=True)
        if results:
            (ROOT / "previews/packaged-check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
