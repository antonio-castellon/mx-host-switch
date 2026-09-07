#!/usr/bin/env python3
"""MX Host Switch — tray app that uses HID++ CHANGE HOST on MX Anywhere 2.

Double-click the tray icon to switch the mouse to the preselected Easy-Switch
channel. Right-click the icon to pick that channel (tick = default target).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow `python mx_host_switch.py` without installing the package.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mxhost import APP_NAME, VERSION  # noqa: E402
from mxhost import config as app_config  # noqa: E402
from mxhost import hidpp  # noqa: E402


def _configure_logging() -> None:
    log_file = app_config.log_path()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


def _stdout_works() -> bool:
    try:
        if sys.stdout is None:
            return False
        sys.stdout.write("")
        sys.stdout.flush()
        return True
    except Exception:
        return False


def _attach_console() -> None:
    """Give CLI flags a console when running the windowed Windows .exe."""
    if sys.platform != "win32":
        return
    if _stdout_works():
        return
    if not getattr(sys, "frozen", False):
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        if not kernel32.AttachConsole(-1):
            kernel32.AllocConsole()
        sys.stdout = open("CONOUT$", "w", encoding="utf-8")  # noqa: SIM115
        sys.stderr = open("CONOUT$", "w", encoding="utf-8")  # noqa: SIM115
        try:
            sys.stdin = open("CONIN$", "r", encoding="utf-8")  # noqa: SIM115
        except Exception:
            pass
    except Exception:
        pass


def _print(text: str) -> None:
    logging.getLogger("mxhost").info(text)
    try:
        print(text)
    except Exception:
        pass


def cmd_list() -> int:
    interfaces = hidpp.enumerate_hidpp_interfaces()
    _print(f"HID++ interfaces: {len(interfaces)}")
    for iface in interfaces:
        kind = "receiver" if iface.is_receiver else "direct"
        _print(
            f"  {iface.product_string or '(unnamed)'}  "
            f"pid={iface.product_id:04X}  usage={iface.usage_page:04X}:{iface.usage:04X}  "
            f"{kind}"
        )
    devices = hidpp.find_change_host_devices()
    if not devices:
        extra = ""
        if hidpp.options_plus_running():
            extra = " Logi Options+ is running; quit it if discovery fails."
        _print("No device with CHANGE HOST (0x1814) found." + extra)
        return 1
    _print(f"CHANGE HOST devices: {len(devices)}")
    for dev in devices:
        mark = "  [MX Anywhere 2]" if dev.is_anywhere2 else ""
        _print(
            f"  {dev.name}{mark}  WPID={dev.wpid}  HID++ {dev.protocol}  "
            f"feature_index={dev.change_host_index}  "
            f"current=Channel {dev.current_host + 1}/{dev.host_count}"
        )
        for slot in dev.hosts:
            flags = []
            if slot.current:
                flags.append("this PC")
            if not slot.paired:
                flags.append("empty")
            suffix = f" ({', '.join(flags)})" if flags else ""
            name = f" {slot.name}" if slot.name else ""
            _print(f"      Channel {slot.index + 1}{name}{suffix}")
    return 0


def cmd_switch(channel: int) -> int:
    host = channel - 1
    devices = hidpp.find_change_host_devices()
    cfg = app_config.load()
    device = hidpp.pick_device(
        devices,
        preferred_wpid=str(cfg.get("preferred_wpid") or ""),
        preferred_name=str(cfg.get("preferred_name") or "Anywhere 2"),
    )
    if not device:
        _print("MX Anywhere 2 not found.")
        return 1
    try:
        hidpp.switch_host(device, host)
    except hidpp.HidppError as exc:
        _print(str(exc))
        return 1
    _print(f"Switching {device.name} to Channel {channel}")
    return 0


def cmd_tray() -> int:
    from mxhost.tray import run_tray

    run_tray()
    return 0


def _acquire_single_instance() -> bool:
    """Prevent two tray icons. Returns False if another instance is already running."""
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.CreateMutexW(None, False, "Local\\MXHostSwitch")
            last = kernel32.GetLastError()
            _acquire_single_instance._handle = handle  # type: ignore[attr-defined]
            return last != 183  # ERROR_ALREADY_EXISTS
        except Exception:
            return True
    try:
        import fcntl

        lock_path = app_config.app_data_dir() / "mxhost.lock"
        handle = lock_path.open("w")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _acquire_single_instance._handle = handle  # type: ignore[attr-defined]
        return True
    except OSError:
        return False
    except Exception:
        return True


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(prog="MXHostSwitch", description=APP_NAME)
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List HID++ devices and Easy-Switch channels",
    )
    parser.add_argument(
        "--switch",
        type=int,
        metavar="N",
        help="Switch the mouse to Easy-Switch channel N (1-based) and exit",
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    args = parser.parse_args(argv)

    if args.version or args.list or args.switch is not None:
        _attach_console()

    if args.version:
        _print(f"{APP_NAME} {VERSION}")
        return 0
    if args.list:
        return cmd_list()
    if args.switch is not None:
        if args.switch < 1 or args.switch > 6:
            _print("Channel must be between 1 and 6.")
            return 2
        return cmd_switch(args.switch)
    if not _acquire_single_instance():
        _attach_console()
        _print(f"{APP_NAME} is already running in the tray.")
        return 0
    return cmd_tray()


if __name__ == "__main__":
    raise SystemExit(main())
