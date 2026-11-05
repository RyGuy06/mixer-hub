"""Separate read-only bundle resources from writable, per-user settings."""
import json
import logging
import os
from pathlib import Path
import sys


SOURCE_ROOT = Path(__file__).resolve().parent


def resource_path(relative_path):
    """Resolve an asset in source checkouts and PyInstaller one-file bundles."""
    return Path(getattr(sys, "_MEIPASS", SOURCE_ROOT)) / relative_path


def user_data_dir():
    return Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "MixerHub"


def config_path():
    if getattr(sys, "frozen", False):
        return user_data_dir() / "mixer_config.json"
    return SOURCE_ROOT / "mixer_config.json"


def legacy_config_paths():
    """Older packaged settings, a portable config, then this project's dist/."""
    candidates = []
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "MixerHub" / "mixer_config.json")
    executable_dir = Path(sys.executable).resolve().parent
    candidates.append(executable_dir / "mixer_config.json")
    # A locally built EXE can inherit the developer's existing settings without
    # putting those personal profiles into the distributable executable.
    checkout = executable_dir.parent
    if executable_dir.name.casefold() == "dist" and (checkout / "app.py").is_file():
        candidates.append(checkout / "mixer_config.json")
    return candidates


def migrate_legacy_config(destination=None, candidates=None):
    """Copy the first readable JSON config once; never delete or overwrite one."""
    destination = Path(destination) if destination is not None else config_path()
    if destination.exists() or (candidates is None and not getattr(sys, "frozen", False)):
        return None
    for candidate in candidates if candidates is not None else legacy_config_paths():
        candidate = Path(candidate)
        try:
            contents = candidate.read_bytes()
            if not isinstance(json.loads(contents.decode("utf-8-sig")), dict):
                raise ValueError("Settings must be a JSON object")
        except FileNotFoundError:
            continue
        except (OSError, ValueError, UnicodeError):
            logging.warning("Could not migrate settings from %s", candidate, exc_info=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".json.tmp")
        try:
            temporary.write_bytes(contents)
            temporary.replace(destination)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise
        logging.info("Migrated settings from %s to %s; original retained", candidate, destination)
        return candidate
    return None
