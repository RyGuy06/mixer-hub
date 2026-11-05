"""Validate release files without a desktop, USB hardware or Windows audio I/O."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mixer_version import VERSION
import pefile
from PyInstaller.archive.readers import CArchiveReader


def main():
    executable = ROOT / "dist/MixerHub.exe"
    manifest = json.loads((ROOT / "dist/build-manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == VERSION
    assert manifest["sha256"] == hashlib.sha256(executable.read_bytes()).hexdigest()
    assert manifest["bytes"] == executable.stat().st_size
    with pefile.PE(str(executable), fast_load=True) as image:
        assert image.OPTIONAL_HEADER.Subsystem == 2, "Release must have no console"
        assert image.FILE_HEADER.Machine == 0x8664, "Expected Windows x64"
    bundle = CArchiveReader(str(executable))
    names = {name.replace("\\", "/") for name in bundle.toc}
    for expected in ("assets/app_icon.ico", "assets/app_icon.png", "assets/product/top 1.png", "assets/product/side 1.png"):
        assert expected in names, expected
    assert not any("mixer_config.json" in name or name.startswith("previews/") for name in names)
    pyz_name = next(name for name in bundle.toc if name.endswith(".pyz"))
    modules = bundle.open_embedded_archive(pyz_name).toc
    for module in ("app", "mixer_runtime", "power_events", "mixer_version"):
        assert module in modules, module
    firmware = ROOT / "dist" / manifest["firmware"]["file"]
    assert manifest["firmware"]["sha256"] == hashlib.sha256(firmware.read_bytes()).hexdigest()
    with zipfile.ZipFile(firmware) as archive:
        assert set(archive.namelist()) == {"MixerHub/MixerHub.ino", "MixerHub/startup_animation.h", "INSTALL.txt"}
        for name in ("MixerHub.ino", "startup_animation.h"):
            assert archive.read(f"MixerHub/{name}") == (ROOT / "firmware/MixerHub" / name).read_bytes()
    print(f"PASS: release {VERSION}, EXE and firmware checksums, Windows x64 GUI subsystem, bundled resources/power code, and personal config excluded.")


if __name__ == "__main__":
    main()
