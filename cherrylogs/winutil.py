"""Small Windows 11 integration helpers (all no-ops on other platforms)."""
from __future__ import annotations

import ctypes
import sys


def set_app_id(app_id: str = "CherryLogs.App") -> None:
    """Lets Windows show our own icon in the taskbar instead of python.exe's."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:  # noqa: BLE001
        pass


def _colorref(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r | (g << 8) | (b << 16)


def style_titlebar(hwnd: int, dark: bool, caption: str, text: str) -> None:
    """Match the native title bar to the theme (Windows 11 build 22000+)."""
    if sys.platform != "win32":
        return
    try:
        dwm = ctypes.windll.dwmapi

        def set_attr(attr: int, value: int) -> None:
            v = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attr,
                                      ctypes.byref(v), ctypes.sizeof(v))

        set_attr(20, 1 if dark else 0)      # DWMWA_USE_IMMERSIVE_DARK_MODE
        set_attr(35, _colorref(caption))    # DWMWA_CAPTION_COLOR
        set_attr(36, _colorref(text))       # DWMWA_TEXT_COLOR
    except Exception:  # noqa: BLE001
        pass
