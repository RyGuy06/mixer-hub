"""Small rotating logs for windowed builds, including uncaught exceptions."""
import ctypes
import logging
from logging.handlers import RotatingFileHandler
import sys
import threading

from app_paths import user_data_dir


def configure_logging():
    directory = user_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "MixerHub.log"
    root = logging.getLogger()
    if not any(getattr(handler, "_mixer_hub", False) for handler in root.handlers):
        handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler._mixer_hub = True
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        logging.captureWarnings(True)
        sys.excepthook = lambda kind, value, tb: logging.critical(
            "Unhandled exception", exc_info=(kind, value, tb))
        threading.excepthook = lambda args: logging.error(
            "Unhandled exception in %s", args.thread.name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    return log_path


def show_startup_error(log_path):
    # Works even if importing Tk/the application itself failed in a --noconsole
    # build. No second Tk root or console is needed to explain the failure.
    location = f"Details were saved to:\n{log_path}" if log_path else "The application could not start."
    ctypes.windll.user32.MessageBoxW(None, "Mixer Hub could not start.\n\n" + location,
                                    "Mixer Hub", 0x10)
