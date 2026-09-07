"""Watch the pointer at the left/right screen edges and request a host switch.

Windows clamps the cursor to the desktop, so “outside” means sitting on the
virtual-screen edge. A short dwell plus inland hysteresis avoids switching
again the moment the mouse comes back to this PC.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Callable, Optional

log = logging.getLogger("mxhost.edge")

POLL_S = 0.03
DWELL_S = 0.28
EDGE_PX = 2
CORNER_PX = 48
INLAND_PX = 50


def screen_bounds() -> Optional[tuple[int, int, int, int]]:
    """Return (left, top, right, bottom) inclusive, virtual desktop."""
    if sys.platform == "win32":
        return _bounds_win()
    if sys.platform == "darwin":
        return _bounds_mac()
    if sys.platform.startswith("linux"):
        return _bounds_x11()
    return None


def cursor_pos() -> Optional[tuple[int, int]]:
    if sys.platform == "win32":
        return _cursor_win()
    if sys.platform == "darwin":
        return _cursor_mac()
    if sys.platform.startswith("linux"):
        return _cursor_x11()
    return None


def _bounds_win() -> Optional[tuple[int, int, int, int]]:
    import ctypes

    user32 = ctypes.windll.user32
    left = int(user32.GetSystemMetrics(76))  # SM_XVIRTUALSCREEN
    top = int(user32.GetSystemMetrics(77))
    width = int(user32.GetSystemMetrics(78))
    height = int(user32.GetSystemMetrics(79))
    if width <= 0 or height <= 0:
        return None
    return left, top, left + width - 1, top + height - 1


def _cursor_win() -> Optional[tuple[int, int]]:
    import ctypes

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
        return None
    return int(pt.x), int(pt.y)


def _quartz():
    import ctypes

    return ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
    )


def _bounds_mac() -> Optional[tuple[int, int, int, int]]:
    try:
        import ctypes

        class CGRect(ctypes.Structure):
            _fields_ = [
                ("x", ctypes.c_double),
                ("y", ctypes.c_double),
                ("w", ctypes.c_double),
                ("h", ctypes.c_double),
            ]

        quartz = _quartz()
        quartz.CGDisplayBounds.restype = CGRect
        quartz.CGMainDisplayID.restype = ctypes.c_uint32
        r = quartz.CGDisplayBounds(quartz.CGMainDisplayID())
        return int(r.x), int(r.y), int(r.x + r.w - 1), int(r.y + r.h - 1)
    except Exception:
        log.debug("macOS screen bounds failed", exc_info=True)
        return None


def _cursor_mac() -> Optional[tuple[int, int]]:
    try:
        import ctypes

        class CGPoint(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

        quartz = _quartz()
        quartz.CGEventCreate.restype = ctypes.c_void_p
        quartz.CGEventCreate.argtypes = [ctypes.c_void_p]
        quartz.CGEventGetLocation.restype = CGPoint
        quartz.CGEventGetLocation.argtypes = [ctypes.c_void_p]
        quartz.CFRelease.argtypes = [ctypes.c_void_p]
        ev = quartz.CGEventCreate(None)
        if not ev:
            return None
        try:
            pt = quartz.CGEventGetLocation(ev)
        finally:
            quartz.CFRelease(ev)
        return int(pt.x), int(pt.y)
    except Exception:
        log.debug("macOS cursor failed", exc_info=True)
        return None


def _x11_display():
    import ctypes
    from ctypes import c_char_p, c_int, c_uint, c_ulong, c_void_p, POINTER

    x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
    x11.XOpenDisplay.restype = c_void_p
    x11.XOpenDisplay.argtypes = [c_char_p]
    x11.XDefaultRootWindow.restype = c_ulong
    x11.XDefaultRootWindow.argtypes = [c_void_p]
    x11.XDisplayWidth.restype = c_int
    x11.XDisplayWidth.argtypes = [c_void_p, c_int]
    x11.XDisplayHeight.restype = c_int
    x11.XDisplayHeight.argtypes = [c_void_p, c_int]
    x11.XDefaultScreen.restype = c_int
    x11.XDefaultScreen.argtypes = [c_void_p]
    x11.XQueryPointer.restype = c_int
    x11.XQueryPointer.argtypes = [
        c_void_p,
        c_ulong,
        POINTER(c_ulong),
        POINTER(c_ulong),
        POINTER(c_int),
        POINTER(c_int),
        POINTER(c_int),
        POINTER(c_int),
        POINTER(c_uint),
    ]
    dpy = x11.XOpenDisplay(None)
    if not dpy:
        return None
    return x11, dpy


_x11_state = None


def _x11():
    global _x11_state
    if _x11_state is False:
        return None
    if _x11_state is None:
        try:
            _x11_state = _x11_display()
        except Exception:
            log.debug("X11 load failed", exc_info=True)
            _x11_state = False
            return None
        if _x11_state is None:
            _x11_state = False
            return None
    return _x11_state


def _bounds_x11() -> Optional[tuple[int, int, int, int]]:
    packed = _x11()
    if not packed:
        return None
    x11, dpy = packed
    screen = x11.XDefaultScreen(dpy)
    w = int(x11.XDisplayWidth(dpy, screen))
    h = int(x11.XDisplayHeight(dpy, screen))
    if w <= 0 or h <= 0:
        return None
    return 0, 0, w - 1, h - 1


def _cursor_x11() -> Optional[tuple[int, int]]:
    import ctypes
    from ctypes import c_int, c_uint, c_ulong, byref

    packed = _x11()
    if not packed:
        return None
    x11, dpy = packed
    root = x11.XDefaultRootWindow(dpy)
    root_r = c_ulong()
    child = c_ulong()
    root_x = c_int()
    root_y = c_int()
    win_x = c_int()
    win_y = c_int()
    mask = c_uint()
    ok = x11.XQueryPointer(
        dpy,
        root,
        byref(root_r),
        byref(child),
        byref(root_x),
        byref(root_y),
        byref(win_x),
        byref(win_y),
        byref(mask),
    )
    if not ok:
        return None
    return int(root_x.value), int(root_y.value)


class EdgeWatcher:
    """Background poller. `on_edge(side, host_index)` is called from this thread."""

    def __init__(
        self,
        assignments: Callable[[], tuple[Optional[int], Optional[int]]],
        on_edge: Callable[[str, int], None],
        dwell_s: float = DWELL_S,
    ):
        self._assignments = assignments
        self._on_edge = on_edge
        self._dwell_s = dwell_s
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._armed = False
        self._edge_since: Optional[float] = None
        self._edge_side: Optional[str] = None

    def start(self) -> bool:
        if screen_bounds() is None or cursor_pos() is None:
            log.info("Edge switch unavailable on this desktop")
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="edge-watch", daemon=True)
        self._thread.start()
        log.info("Edge watcher started")
        return True

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        self._thread = None

    def _loop(self) -> None:
        while not self._stop.wait(POLL_S):
            try:
                self._tick()
            except Exception:
                log.exception("Edge watcher tick failed")

    def _tick(self) -> None:
        bounds = screen_bounds()
        pos = cursor_pos()
        if bounds is None or pos is None:
            return
        left, top, right, bottom = bounds
        x, y = pos
        left_host, right_host = self._assignments()

        at_corner = y <= top + CORNER_PX or y >= bottom - CORNER_PX
        side: Optional[str] = None
        if not at_corner:
            if x <= left + EDGE_PX:
                side = "left"
            elif x >= right - EDGE_PX:
                side = "right"

        inland = left + INLAND_PX < x < right - INLAND_PX
        if inland:
            self._armed = True
            self._edge_since = None
            self._edge_side = None
            return

        if side is None or not self._armed:
            self._edge_since = None
            self._edge_side = None
            return

        host = left_host if side == "left" else right_host
        if host is None:
            self._edge_since = None
            self._edge_side = None
            return

        now = time.monotonic()
        if self._edge_side != side:
            self._edge_side = side
            self._edge_since = now
            return
        if self._edge_since is None:
            self._edge_since = now
            return
        if now - self._edge_since < self._dwell_s:
            return

        self._armed = False
        self._edge_since = None
        self._edge_side = None
        log.info("Edge %s dwell reached, requesting channel %s", side, host + 1)
        self._on_edge(side, host)
