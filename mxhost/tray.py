"""System-tray UI: pick the target channel, then switch (double-click on Windows)."""

from __future__ import annotations

import logging
import sys
import threading
import webbrowser
from typing import Callable, Optional

import pystray
from pystray import Menu, MenuItem

from . import APP_NAME, AUTHOR_EMAIL, AUTHOR_NAME, AUTHOR_URL, VERSION, hidpp
from .config import channel_label, load, save
from .edge import EdgeWatcher
from .icon import render_tray_image

log = logging.getLogger("mxhost.tray")
WM_LBUTTONDBLCLK = 0x0203
WM_LBUTTONUP = 0x0202


class DoubleClickIcon(pystray.Icon):
    """pystray Windows backend: double-click runs a callback; left-click does nothing."""

    def __init__(self, *args, on_double_click: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_double_click = on_double_click

    def _on_notify(self, wparam, lparam):  # noqa: N802 - pystray API
        if lparam == WM_LBUTTONDBLCLK:
            if self._on_double_click:
                threading.Thread(target=self._on_double_click, daemon=True).start()
            return
        if lparam == WM_LBUTTONUP:
            return
        return super()._on_notify(wparam, lparam)


class TrayApp:
    def __init__(self) -> None:
        self.cfg = load()
        self.devices: list[hidpp.ChangeHostDevice] = []
        self.device: Optional[hidpp.ChangeHostDevice] = None
        self.icon: Optional[pystray.Icon] = None
        self._lock = threading.Lock()
        self._edge = EdgeWatcher(self._edge_assignments, self._on_edge)
        self.refresh(notify=False)

    @property
    def target_host(self) -> int:
        return int(self.cfg.get("target_host", 1))

    @target_host.setter
    def target_host(self, value: int) -> None:
        self.cfg["target_host"] = int(value)
        save(self.cfg)

    def refresh(self, notify: bool = True) -> None:
        with self._lock:
            try:
                self.devices = hidpp.find_change_host_devices()
                self.device = hidpp.pick_device(
                    self.devices,
                    preferred_wpid=str(self.cfg.get("preferred_wpid") or ""),
                    preferred_name=str(self.cfg.get("preferred_name") or "Anywhere 2"),
                )
            except Exception:
                log.exception("Device refresh failed")
                self.devices = []
                self.device = None
            self._ensure_target()
        if self.icon:
            self.icon.title = self._tooltip()
            self.icon.menu = self._menu()
            try:
                self.icon.update_menu()
            except Exception:
                pass
        if notify:
            if self.device:
                self._notify(f"Found {self.device.name} on Channel {self.device.current_host + 1}")
            else:
                extra = ""
                if hidpp.options_plus_running():
                    extra = " Logi Options+ is running and may be blocking HID++."
                self._notify("No Logitech mouse with CHANGE HOST was found." + extra, error=True)

    def _ensure_target(self) -> None:
        if not self.device:
            return
        target = self.target_host
        if target < 0 or target >= self.device.host_count:
            target = 1 if self.device.host_count > 1 else 0
        if target == self.device.current_host and self.device.host_count > 1:
            target = 0 if self.device.current_host != 0 else 1
        if target != self.target_host:
            self.cfg["target_host"] = target
            save(self.cfg)

    def _switch_label(self) -> str:
        if sys.platform == "win32":
            return "Switch now (double-click)"
        return "Switch now"

    def _tooltip(self) -> str:
        action = "Double-click" if sys.platform == "win32" else "Switch now"
        if not self.device:
            return f"{APP_NAME} — no mouse found\n{action} after the mouse is on this computer"
        return (
            f"{APP_NAME}\n"
            f"{self.device.name} on Channel {self.device.current_host + 1}\n"
            f"{action} → {self._target_text()}"
        )

    def _target_text(self) -> str:
        if not self.device:
            return f"Channel {self.target_host + 1}"
        custom = (self.cfg.get("channel_names") or {}).get(str(self.target_host), "")
        slot = next((h for h in self.device.hosts if h.index == self.target_host), None)
        name = custom or (slot.name if slot else "")
        if name:
            return f"Channel {self.target_host + 1} ({name})"
        return f"Channel {self.target_host + 1}"

    def _status_item(self, item=None) -> str:  # noqa: ARG002 - pystray text callback
        if not self.device:
            return "No MX Anywhere 2 found"
        return f"{self.device.name}  ·  Channel {self.device.current_host + 1}"

    def _menu(self) -> Menu:
        items: list[MenuItem] = [
            MenuItem(lambda item: self._status_item(item), lambda *_: None, enabled=False),
            Menu.SEPARATOR,
            MenuItem(self._switch_label(), lambda *_: self.switch_to_selected(), default=True),
            Menu.SEPARATOR,
            MenuItem("Switch target", Menu(*self._channel_items())),
            MenuItem("Edge switch", Menu(*self._edge_menu_items())),
            Menu.SEPARATOR,
            MenuItem("Refresh mouse", lambda *_: self.refresh(notify=True)),
            MenuItem(
                "Show notifications",
                self._toggle_notifications,
                checked=lambda item: bool(self.cfg.get("show_notifications")),
            ),
            MenuItem("About", Menu(*self._about_items())),
            MenuItem("Quit", self._quit),
        ]
        return Menu(*items)

    def _channel_items(self) -> list[MenuItem]:
        device = self.device
        count = device.host_count if device else 3
        items: list[MenuItem] = []
        names = self.cfg.get("channel_names") or {}
        for index in range(count):
            label = self._channel_menu_label(index, names.get(str(index), ""))
            items.append(
                MenuItem(
                    label,
                    self._make_select_handler(index),
                    checked=self._make_checked(index),
                    radio=True,
                )
            )
        return items

    def _channel_menu_label(self, index: int, custom: str) -> str:
        if self.device:
            return self.device.host_label(index, custom=custom)
        return channel_label(self.cfg, index)

    def _make_select_handler(self, index: int):
        def _handler(icon, item):  # noqa: ARG001
            self.target_host = index
            if self.icon:
                self.icon.title = self._tooltip()
                self.icon.menu = self._menu()
                try:
                    self.icon.update_menu()
                except Exception:
                    pass
            action = "Double-click" if sys.platform == "win32" else "Switch now"
            self._notify(f"{action} will switch to Channel {index + 1}")

        return _handler

    def _make_checked(self, index: int):
        return lambda item, i=index: self.target_host == i

    def _edge_host(self, side: str) -> Optional[int]:
        key = "edge_left_host" if side == "left" else "edge_right_host"
        value = self.cfg.get(key)
        return None if value is None else int(value)

    def _set_edge_host(self, side: str, host: Optional[int]) -> None:
        key = "edge_left_host" if side == "left" else "edge_right_host"
        self.cfg[key] = host
        save(self.cfg)
        if self.icon:
            self.icon.menu = self._menu()
            try:
                self.icon.update_menu()
            except Exception:
                pass
        label = "None (no action)" if host is None else f"Channel {host + 1}"
        self._notify(f"{side.capitalize()} edge → {label}")

    def _edge_assignments(self) -> tuple[Optional[int], Optional[int]]:
        return self._edge_host("left"), self._edge_host("right")

    def _edge_menu_items(self) -> list[MenuItem]:
        return [
            MenuItem("Left", Menu(*self._edge_side_items("left"))),
            MenuItem("Right", Menu(*self._edge_side_items("right"))),
        ]

    def _edge_side_items(self, side: str) -> list[MenuItem]:
        count = self.device.host_count if self.device else 3
        names = self.cfg.get("channel_names") or {}
        items = [
            MenuItem(
                "None (no action)",
                lambda *_ , s=side: self._set_edge_host(s, None),
                checked=lambda item, s=side: self._edge_host(s) is None,
                radio=True,
            )
        ]
        for index in range(count):
            label = self._channel_menu_label(index, names.get(str(index), ""))
            items.append(
                MenuItem(
                    label,
                    lambda *_, s=side, i=index: self._set_edge_host(s, i),
                    checked=lambda item, s=side, i=index: self._edge_host(s) == i,
                    radio=True,
                )
            )
        return items

    def _about_items(self) -> list[MenuItem]:
        return [
            MenuItem(f"{APP_NAME}  {VERSION}", lambda *_: self._show_about(), default=False),
            MenuItem(AUTHOR_NAME, lambda *_: None, enabled=False),
            MenuItem(AUTHOR_EMAIL, lambda *_: webbrowser.open(f"mailto:{AUTHOR_EMAIL}")),
            MenuItem(AUTHOR_URL.replace("https://", ""), lambda *_: webbrowser.open(AUTHOR_URL)),
        ]

    def _show_about(self) -> None:
        text = (
            f"{APP_NAME} {VERSION}\n\n"
            f"{AUTHOR_NAME}\n"
            f"{AUTHOR_EMAIL}\n"
            f"{AUTHOR_URL}"
        )
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.MessageBoxW(None, text, f"About {APP_NAME}", 0x40)
                return
            except Exception:
                log.debug("About dialog failed", exc_info=True)
        self._notify(text.replace("\n\n", " — ").replace("\n", " · "))

    def _on_edge(self, side: str, host: int) -> None:
        self.switch_to_host(host, reason=f"{side} edge")

    def switch_to_selected(self) -> None:
        self.switch_to_host(self.target_host, reason="menu")

    def switch_to_host(self, target: int, reason: str = "menu") -> None:
        with self._lock:
            try:
                devices = hidpp.find_change_host_devices()
                device = hidpp.pick_device(
                    devices,
                    preferred_wpid=str(self.cfg.get("preferred_wpid") or ""),
                    preferred_name=str(self.cfg.get("preferred_name") or "Anywhere 2"),
                )
            except Exception as exc:
                log.exception("Rediscovery failed")
                self._notify(f"Could not talk to the mouse: {exc}", error=True)
                return
            self.devices = devices
            self.device = device
            if not device:
                extra = ""
                if hidpp.options_plus_running():
                    extra = " Close Logi Options+ and try again."
                self._notify("MX Anywhere 2 not found on this PC." + extra, error=True)
                return
            if target == device.current_host:
                if reason == "menu":
                    self._notify(f"Already on Channel {target + 1}. Pick another target in the menu.")
                return
            try:
                hidpp.switch_host(device, target)
            except hidpp.HidppError as exc:
                self._notify(str(exc), error=True)
                return
            except Exception as exc:
                log.exception("CHANGE HOST failed")
                extra = ""
                if hidpp.options_plus_running():
                    extra = " Logi Options+ may be locking the HID++ interface."
                self._notify(f"Switch failed: {exc}.{extra}", error=True)
                return
            log.info("Switching %s to Channel %s (%s)", device.name, target + 1, reason)

    def _toggle_notifications(self, icon, item) -> None:  # noqa: ARG002
        self.cfg["show_notifications"] = not bool(self.cfg.get("show_notifications"))
        save(self.cfg)
        if self.icon:
            self.icon.menu = self._menu()
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def _notify(self, message: str, *, error: bool = False) -> None:
        log.info(message)
        if not error and not self.cfg.get("show_notifications"):
            return
        icon = self.icon
        if icon is None:
            return
        try:
            icon.notify(message, APP_NAME)
        except Exception:
            log.debug("notify failed", exc_info=True)

    def _quit(self, icon, item) -> None:  # noqa: ARG002
        self._edge.stop()
        icon.visible = False
        icon.stop()

    def run(self) -> None:
        self._edge.start()
        kwargs = {
            "name": "MXHostSwitch",
            "icon": render_tray_image(64),
            "title": self._tooltip(),
            "menu": self._menu(),
        }
        if sys.platform == "win32":
            self.icon = DoubleClickIcon(on_double_click=self.switch_to_selected, **kwargs)
        else:
            self.icon = pystray.Icon(**kwargs)
        try:
            self.icon.run()
        finally:
            self._edge.stop()


def run_tray() -> None:
    TrayApp().run()
