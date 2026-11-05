"""Smoke-test the built EXE with isolated settings and no device connection.

Run on a Windows test/build machine with no other Mixer Hub instance running.
This checks startup only; it does not send input to another application.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="MixerHub-launch-") as temporary:
        directory = Path(temporary)
        settings = directory / "roaming/MixerHub"
        settings.mkdir(parents=True)
        (settings / "mixer_config.json").write_text(
            json.dumps({"auto_connect": False}), encoding="utf-8")
        environment = dict(os.environ, APPDATA=str(directory / "roaming"),
                           LOCALAPPDATA=str(directory / "local"))
        process = subprocess.Popen([str(ROOT / "dist/MixerHub.exe"), "--background"],
                                   cwd=directory, env=environment)
        try:
            deadline = time.monotonic() + 45
            log = ""
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError("EXE exited before readiness; close any existing Mixer Hub instance")
                path = settings / "MixerHub.log"
                if path.exists():
                    log = path.read_text(encoding="utf-8")
                if "Dashboard ready; product renders: side, top" in log:
                    time.sleep(2)
                    assert process.poll() is None
                    log = path.read_text(encoding="utf-8")
                    assert "Mixer Hub startup failed" not in log
                    assert "Unhandled exception" not in log
                    assert "Windows power notifications unavailable" not in log
                    assert "Could not start tray icon" not in log
                    print("PASS: real windowed EXE launched, dashboard and both renders loaded, background process remained running with isolated settings and Auto-connect off.")
                    return
                time.sleep(0.2)
            raise AssertionError("EXE startup timed out:\n" + log)
        finally:
            # Terminate only this isolated test process and its one-file child.
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    child.terminate()
                psutil.wait_procs(children, timeout=5)
                process.wait(timeout=10) if children else process.terminate()
            except (psutil.NoSuchProcess, subprocess.TimeoutExpired):
                if process.poll() is None:
                    process.kill()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
