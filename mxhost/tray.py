"""System-tray UI: pick the target channel, then switch (double-click on Windows)."""

from __future__ import annotations

import logging
import sys
import threading
from typing import Callable, Optional

import pystray
from pystray import Menu, MenuItem

from . import APP_NAME, hidpp
from .config import channel_label, load, save
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
                self._notify("No Logitech mouse with CHANGE HOST was found." + extra)

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
            Menu.SEPARATOR,
            MenuItem("Refresh mouse", lambda *_: self.refresh(notify=True)),
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

    def switch_to_selected(self) -> None:
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
                self._notify(f"Could not talk to the mouse: {exc}")
                return
            self.devices = devices
            self.device = device
            if not device:
                extra = ""
                if hidpp.options_plus_running():
                    extra = " Close Logi Options+ and try again."
                self._notify("MX Anywhere 2 not found on this PC." + extra)
                return
            target = self.target_host
            if target == device.current_host:
                self._notify(f"Already on Channel {target + 1}. Pick another target in the menu.")
                return
            try:
                hidpp.switch_host(device, target)
            except hidpp.HidppError as exc:
                self._notify(str(exc))
                return
            except Exception as exc:
                log.exception("CHANGE HOST failed")
                extra = ""
                if hidpp.options_plus_running():
                    extra = " Logi Options+ may be locking the HID++ interface."
                self._notify(f"Switch failed: {exc}.{extra}")
                return
            self._notify(f"Switching {device.name} to Channel {target + 1}")

    def _notify(self, message: str) -> None:
        log.info(message)
        icon = self.icon
        if icon is None:
            return
        try:
            icon.notify(message, APP_NAME)
        except Exception:
            log.debug("notify failed", exc_info=True)

    def _quit(self, icon, item) -> None:  # noqa: ARG002
        icon.visible = False
        icon.stop()

    def run(self) -> None:
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
        self.icon.run()


def run_tray() -> None:
    TrayApp().run()
