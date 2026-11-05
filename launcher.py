"""PyInstaller entry point: log startup failures before importing UI packages."""
import logging

from diagnostics import configure_logging, show_startup_error


def main():
    log_path = None
    try:
        log_path = configure_logging()
        from app import main as run_app
        return run_app()
    except Exception:
        logging.exception("Mixer Hub startup failed")
        show_startup_error(log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
