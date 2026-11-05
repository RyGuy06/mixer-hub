"""One mixer per Windows session; reopening signals the existing GUI."""
import ctypes
from ctypes import wintypes


def activate_window(window_id):
    """Activate Tk's native top-level after receiving a user restore request."""
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetAncestor.restype = wintypes.HWND
    user.SetForegroundWindow.argtypes = [wintypes.HWND]
    user.SetForegroundWindow.restype = wintypes.BOOL
    window = user.GetAncestor(window_id, 2) or window_id  # GA_ROOT
    return bool(user.SetForegroundWindow(window))


class SingleInstance:
    def __init__(self, name="MixerHub"):
        self.name = name
        self.mutex = self.event = None
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        for name, args, result in (
            ("CreateMutexW", [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            ("CreateEventW", [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            ("SetEvent", [wintypes.HANDLE], wintypes.BOOL),
            ("WaitForSingleObject", [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            ("CloseHandle", [wintypes.HANDLE], wintypes.BOOL),
        ):
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result

    def acquire(self, *, show_existing=True):
        if self.mutex:
            raise RuntimeError("Instance guard already acquired")
        try:
            # Create the shared event first so a simultaneous second launch can
            # signal it even while the primary window is still being built.
            self.event = self.kernel.CreateEventW(None, False, False, f"Local\\{self.name}.Open")
            if not self.event:
                raise ctypes.WinError(ctypes.get_last_error())
            self.mutex = self.kernel.CreateMutexW(None, False, f"Local\\{self.name}.Instance")
            error = ctypes.get_last_error()
            if not self.mutex:
                raise ctypes.WinError(error)
            if error == 183:  # ERROR_ALREADY_EXISTS
                if show_existing and self.name == "MixerHub":
                    self._allow_existing_foreground()
                if show_existing and not self.kernel.SetEvent(self.event):
                    raise ctypes.WinError(ctypes.get_last_error())
                self.close()
                return False
            return True
        except Exception:
            self.close()
            raise

    @staticmethod
    def _allow_existing_foreground():
        # A launch from Explorer has foreground permission. Pass that permission
        # to the hidden primary before it consumes the restore event, rather
        # than relying on Windows accepting a background focus request.
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user.FindWindowW.restype = wintypes.HWND
        user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user.GetWindowThreadProcessId.restype = wintypes.DWORD
        user.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
        user.AllowSetForegroundWindow.restype = wintypes.BOOL
        window = user.FindWindowW(None, "Mixer Hub")
        if window:
            process_id = wintypes.DWORD()
            user.GetWindowThreadProcessId(window, ctypes.byref(process_id))
            if process_id.value:
                user.AllowSetForegroundWindow(process_id.value)

    def restore_requested(self):
        if not self.event:
            return False
        result = self.kernel.WaitForSingleObject(self.event, 0)
        if result == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return result == 0  # Auto-reset event consumes the request.

    def close(self):
        for attribute in ("mutex", "event"):
            handle = getattr(self, attribute)
            if handle:
                self.kernel.CloseHandle(handle)
                setattr(self, attribute, None)
