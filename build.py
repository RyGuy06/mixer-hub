"""Repeatable Windows one-file build: .venv\\Scripts\\python.exe build.py."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from mixer_version import VERSION


ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
HIDDEN_IMPORTS = (
    "pycaw", "pycaw.pycaw", "pycaw.api.endpointvolume",
    "comtypes", "comtypes.client", "comtypes.gen",
    "pystray", "pystray._win32", "PIL", "PIL.Image", "PIL.ImageTk",
    "PIL.PngImagePlugin", "PIL.IcoImagePlugin", "serial", "serial.serialwin32",
    "serial.tools.list_ports", "serial.tools.list_ports_windows",
    "keyboard", "keyboard._winkeyboard", "psutil",
)


def generate_icon():
    from branding import render_icon
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    image = render_icon(1024)
    image.save(assets / "app_icon.ico", format="ICO", sizes=[(size, size) for size in ICON_SIZES])
    image.resize((512, 512)).save(assets / "app_icon.png")


def build_command():
    command = [str(VENV_PYTHON), "-m", "PyInstaller", "--noconfirm", "--clean",
               "--onefile", "--noconsole", "--noupx", "--name", "MixerHub",
               "--icon", str(ROOT / "assets" / "app_icon.ico"),
               "--version-file", str(ROOT / "packaging" / "windows-version.txt"),
               "--collect-all", "customtkinter",
               "--distpath", str(ROOT / "dist"),
               "--workpath", str(ROOT / "build" / "pyinstaller"),
               "--specpath", str(ROOT / "build")]
    # Explicit allowlist: never bundle mixer_config.json, logs, previews, .venv,
    # or the developer's profiles alongside the read-only product artwork.
    for source, destination in (("assets/app_icon.ico", "assets"),
                                ("assets/app_icon.png", "assets"),
                                ("assets/product", "assets/product")):
        command.extend(("--add-data", f"{ROOT / source}:{destination}"))
    for module in HIDDEN_IMPORTS:
        command.extend(("--hidden-import", module))
    command.append(str(ROOT / "launcher.py"))
    return command


def bundle_firmware():
    destination = ROOT / "dist" / f"MixerHub-firmware-v{VERSION}.zip"
    instructions = f"""Mixer Hub {VERSION} firmware

Keep MixerHub.ino and startup_animation.h together inside the MixerHub folder.
Install Arduino AVR Boards and Adafruit NeoPixel in Arduino IDE. Quit Mixer Hub
from the system tray and close Serial Monitor before uploading. Open MixerHub.ino,
select the classic Nano / matching bootloader and USB port, then Verify and Upload.

Install the matching MixerHub.exe {VERSION} and connect to the mixer. This firmware
turns the LEDs off five seconds after heartbeats stop, including if USB stays powered
during sleep/shutdown. The older EXE does not send heartbeats. The new app restores
your saved brightness on reconnect. A blue boot animation is not a PC-ready signal.

Full instructions: https://github.com/RyGuy06/mixer-hub/blob/main/firmware/POWER.md
"""
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ("MixerHub.ino", "startup_animation.h"):
            archive.write(ROOT / "firmware" / "MixerHub" / name, f"MixerHub/{name}")
        archive.writestr("INSTALL.txt", instructions)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icon-only", action="store_true", help="Regenerate the shared PNG/ICO without building")
    parser.add_argument("--smoke-test", action="store_true", help="Also launch the EXE and verify tray/duplicate restore")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("Build this Windows application on Windows.")
    if not VENV_PYTHON.is_file():
        parser.error("Create .venv and install requirements-build.txt first.")
    if Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        return subprocess.call([str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]], cwd=ROOT)
    try:
        metadata.version("PyInstaller")
    except metadata.PackageNotFoundError:
        parser.error("Install the build tools: .venv\\Scripts\\python.exe -m pip install -r requirements-build.txt")
    generate_icon()
    if args.icon_only:
        print("Generated assets/app_icon.ico and assets/app_icon.png")
        return 0
    print(f"Building Mixer Hub {VERSION} with", sys.executable, flush=True)
    subprocess.run(build_command(), cwd=ROOT, check=True)
    executable = ROOT / "dist" / "MixerHub.exe"
    with executable.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    firmware = bundle_firmware()
    manifest = {"product": "Mixer Hub", "version": VERSION, "python": sys.version,
                "built_utc": datetime.now(timezone.utc).isoformat(),
                "file": executable.name, "bytes": executable.stat().st_size,
                "sha256": checksum,
                "source_commit": os.environ.get("GITHUB_SHA"),
                "firmware": {"file": firmware.name, "sha256": hashlib.sha256(firmware.read_bytes()).hexdigest()},
                "packages": {distribution.metadata["Name"]: distribution.version
                             for distribution in metadata.distributions()}}
    (ROOT / "dist" / "build-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Built {executable} ({executable.stat().st_size / 1024**2:.1f} MB)", flush=True)
    if args.smoke_test:
        subprocess.run([str(VENV_PYTHON), str(ROOT / "tools" / "check_packaged.py")], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
