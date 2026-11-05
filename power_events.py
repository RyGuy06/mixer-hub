"""Windows power notifications and reconnection intent; no serial I/O here."""
import ctypes
from ctypes import wintypes
import logging


WM_POWERBROADCAST = 0x0218
WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016
PBT_APMSUSPEND = 0x0004
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMEAUTOMATIC = 0x0012


class PowerSession:
    """Restore an existing connection after wake, without undoing Disconnect."""
    def __init__(self):
        self.suspended = False
        self._wanted = False
        self._pending = False
        self._deadline = 0.0
        self._next_attempt = 0.0

    def suspend(self, connection_requested):
        if not self.suspended:
            self._wanted = connection_requested or self._pending
            self._pending = False
            self.suspended = True

    def resume(self, now):
        if self.suspended:
            self.suspended = False
            self._pending = self._wanted
            self._wanted = False
            self._deadline = now + 30.0
            self._next_attempt = now

    def cancel_reconnect(self):
        self._wanted = self._pending = False

    def should_reconnect(self, now, *, running, connected):
        if connected and not self.suspended:
            self._pending = False
        if self.suspended or not self._pending:
            return False
        if now > self._deadline:
            self._pending = False
            return False
        if running or now < self._next_attempt:
            return False
        self._next_attempt = now + 2.0
        return True


class WindowsPowerMonitor:
    """Subclass this process's Tk HWND; always forward ordinary window messages."""
    def __init__(self, window_id, callback):
        self.callback = callback
        self.closed = False
        self.registration = None
        self._shutdown_queried = False
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        pointer = ctypes.c_ssize_t
        for name, args, result in (
            ("GetAncestor", [wintypes.HWND, wintypes.UINT], wintypes.HWND),
            ("GetWindowLongPtrW", [wintypes.HWND, ctypes.c_int], pointer),
            ("SetWindowLongPtrW", [wintypes.HWND, ctypes.c_int, pointer], pointer),
            ("CallWindowProcW", [pointer, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], pointer),
            ("RegisterSuspendResumeNotification", [wintypes.HANDLE, wintypes.DWORD], wintypes.HANDLE),
            ("UnregisterSuspendResumeNotification", [wintypes.HANDLE], wintypes.BOOL),
        ):
            function = getattr(self.user, name)
            function.argtypes, function.restype = args, result
        self.window = self.user.GetAncestor(window_id, 2) or window_id
        self._proc_type = ctypes.WINFUNCTYPE(pointer, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        self._proc = self._proc_type(self._window_proc)  # Keep callback alive.
        self._address = ctypes.cast(self._proc, ctypes.c_void_p).value
        ctypes.set_last_error(0)
        self._previous = self.user.SetWindowLongPtrW(self.window, -4, self._address)
        if not self._previous:
            raise ctypes.WinError(ctypes.get_last_error())
        self.registration = self.user.RegisterSuspendResumeNotification(self.window, 0)
        if not self.registration:
            # Classic broadcasts still work. Firmware timeout remains the
            # fallback even if Windows cannot deliver a notification.
            logging.warning("Could not register extended sleep notifications: %s", ctypes.get_last_error())

    def _window_proc(self, window, message, wparam, lparam):
        try:
            if not self.closed:
                if message == WM_POWERBROADCAST:
                    if wparam == PBT_APMSUSPEND:
                        self.callback("suspend")
                    elif wparam in (PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC):
                        self.callback("resume")
                elif message == WM_QUERYENDSESSION:
                    self._shutdown_queried = True
                    self.callback("shutdown")
                    return 1  # Never block shutdown or wait on serial in WndProc.
                elif message == WM_ENDSESSION:
                    if wparam:
                        self.callback("shutdown")
                    elif self._shutdown_queried:
                        self.callback("resume")  # Another app cancelled shutdown.
                    self._shutdown_queried = False
                    return 0
        except Exception:
            logging.exception("Could not handle Windows power notification")
        return self.user.CallWindowProcW(self._previous, window, message, wparam, lparam)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.registration:
            self.user.UnregisterSuspendResumeNotification(self.registration)
            self.registration = None
        if self.user.GetWindowLongPtrW(self.window, -4) == self._address:
            self.user.SetWindowLongPtrW(self.window, -4, self._previous)
