"""Read-only Windows executable icons, cached for presentation on the Tk thread."""
import ctypes
from ctypes import wintypes
import time

import customtkinter as ctk
from PIL import Image, ImageDraw
import psutil


class BitmapInfoHeader(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("width", wintypes.LONG), ("height", wintypes.LONG),
                ("planes", wintypes.WORD), ("bits", wintypes.WORD), ("compression", wintypes.DWORD),
                ("image_size", wintypes.DWORD), ("xppm", wintypes.LONG), ("yppm", wintypes.LONG),
                ("used", wintypes.DWORD), ("important", wintypes.DWORD)]


def extract_icon(path, size=64):
    """Render an owned HICON into an RGBA DIB; release every native handle."""
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    user = ctypes.WinDLL("user32", use_last_error=True)
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    handle = wintypes.HANDLE
    for library, name, args, result in (
        (shell, "SHDefExtractIconW", [wintypes.LPCWSTR, ctypes.c_int, wintypes.UINT,
                                     ctypes.POINTER(handle), ctypes.POINTER(handle), wintypes.UINT], ctypes.c_long),
        (user, "DestroyIcon", [handle], wintypes.BOOL),
        (user, "GetDC", [handle], handle), (user, "ReleaseDC", [handle, handle], ctypes.c_int),
        (user, "DrawIconEx", [handle, ctypes.c_int, ctypes.c_int, handle, ctypes.c_int,
                              ctypes.c_int, wintypes.UINT, handle, wintypes.UINT], wintypes.BOOL),
        (gdi, "CreateCompatibleDC", [handle], handle),
        (gdi, "CreateDIBSection", [handle, ctypes.POINTER(BitmapInfoHeader), wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), handle, wintypes.DWORD], handle),
        (gdi, "SelectObject", [handle, handle], handle),
        (gdi, "DeleteObject", [handle], wintypes.BOOL), (gdi, "DeleteDC", [handle], wintypes.BOOL),
    ):
        function = getattr(library, name)
        function.argtypes, function.restype = args, result
    icon = handle()
    dc = memory = bitmap = previous = None
    try:
        result = shell.SHDefExtractIconW(str(path), 0, 0, ctypes.byref(icon), None, size)
        if result != 0 or not icon.value:
            return None
        dc = user.GetDC(None)
        memory = gdi.CreateCompatibleDC(dc)
        info = BitmapInfoHeader(ctypes.sizeof(BitmapInfoHeader), size, -size, 1, 32, 0,
                                size * size * 4, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        bitmap = gdi.CreateDIBSection(dc, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
        if not dc or not memory or not bitmap or not bits.value:
            return None
        previous = gdi.SelectObject(memory, bitmap)
        ctypes.memset(bits, 0, info.image_size)
        if not user.DrawIconEx(memory, 0, 0, icon, size, size, 0, None, 3):
            return None
        raw = ctypes.string_at(bits, info.image_size)
        image = Image.frombytes("RGBA", (size, size), raw, "raw", "BGRA")
        if image.getchannel("A").getbbox() is None:
            # Legacy mask icons: draw against white to recover their alpha mask.
            ctypes.memset(bits, 255, info.image_size)
            user.DrawIconEx(memory, 0, 0, icon, size, size, 0, None, 3)
            white = Image.frombytes("RGBA", (size, size), ctypes.string_at(bits, info.image_size), "raw", "BGRA")
            pixels = []
            for black_pixel, white_pixel in zip(image.get_flattened_data(), white.get_flattened_data()):
                alpha = 255 - max(white_pixel[i] - black_pixel[i] for i in range(3))
                pixels.append((*black_pixel[:3], max(0, min(255, alpha))))
            image.putdata(pixels)
        else:
            # DrawIconEx stores premultiplied RGB; Pillow/Tk expect straight RGBA.
            image.putdata([tuple(min(255, round(value * 255 / a)) for value in (r, g, b)) + (a,)
                           if a else (0, 0, 0, 0) for r, g, b, a in image.get_flattened_data()])
        return image if image.getchannel("A").getbbox() else None
    finally:
        if previous and memory:
            gdi.SelectObject(memory, previous)
        if bitmap:
            gdi.DeleteObject(bitmap)
        if memory:
            gdi.DeleteDC(memory)
        if dc:
            user.ReleaseDC(None, dc)
        if icon.value:
            user.DestroyIcon(icon)


def fallback_icon(master=False):
    image = Image.new("RGBA", (64, 64))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((3, 3, 61, 61), radius=15, fill="#30303A")
    if master:
        draw.polygon([(16, 26), (23, 26), (33, 18), (33, 46), (23, 38), (16, 38)], fill="#C7C7D2")
        draw.arc((24, 18, 48, 46), -60, 60, fill="#C7C7D2", width=3)
    else:
        draw.rounded_rectangle((15, 15, 49, 49), radius=5, outline="#B5B5C2", width=3)
        draw.line((16, 24, 48, 24), fill="#B5B5C2", width=2)
        draw.line((23, 39, 28, 39, 31, 31, 35, 43, 39, 35, 44, 35), fill="#B5B5C2", width=2)
    return image


class AppIconCache:
    def __init__(self):
        self.paths, self.images, self.photos = {}, {}, {}
        self.next_scan = 0.0
        self.failures = set()
        self.looked_up = set()

    def _scan_paths(self, *, force=False):
        if not force and time.monotonic() < self.next_scan:
            return
        self.next_scan = time.monotonic() + 10
        try:
            for process in psutil.process_iter(["name", "exe"]):
                name, path = process.info.get("name"), process.info.get("exe")
                if name and path:
                    self.paths[name.lower()] = path
        except (psutil.Error, OSError):
            pass

    def refresh_for_apps(self, names):
        if any(name != "master" and name not in self.paths for name in names):
            self._scan_paths(force=True)

    def get(self, app_name, *, dim=False):
        name = (app_name or "").lower()
        if name and name != "master" and name not in self.paths and name not in self.looked_up:
            self._scan_paths()
            self.looked_up.add(name)
        path = self.paths.get(name)
        key = path or ("master" if name == "master" else "fallback")
        if key not in self.images:
            try:
                icon = extract_icon(path) if path else None
            except (OSError, AttributeError, ValueError):
                icon = None
            if icon is None and path:
                self.failures.add(path)
            self.images[key] = icon if icon is not None else fallback_icon(name == "master")
        photo_key = (key, dim)
        if photo_key not in self.photos:
            image = self.images[key]
            if dim:
                image = image.copy()
                image.putalpha(image.getchannel("A").point(lambda value: round(value * 0.48)))
            self.photos[photo_key] = ctk.CTkImage(light_image=image, dark_image=image, size=(28, 28))
        return self.photos[photo_key]
