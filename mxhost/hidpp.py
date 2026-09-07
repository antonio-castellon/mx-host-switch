"""HID++ 2.0 access for Logitech Unifying/Bolt/Bluetooth devices.

Talks to the vendor HID collection (usage page 0xFF00 or 0xFF43) and uses
feature 0x1814 (CHANGE HOST) to switch Easy-Switch channels.
"""

from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import hid

log = logging.getLogger("mxhost.hidpp")

LOGITECH_VID = 0x046D
SW_ID = 0x0B

FEATURE_ROOT = 0x0000
FEATURE_FEATURE_SET = 0x0001
FEATURE_FW_VERSION = 0x0003
FEATURE_DEVICE_NAME = 0x0005
FEATURE_CHANGE_HOST = 0x1814
FEATURE_HOSTS_INFO = 0x1815

REPORT_SHORT = 0x10
REPORT_LONG = 0x11
SHORT_LEN = 7
LONG_LEN = 20

ERROR_HIDPP10 = 0x8F
ERROR_HIDPP20 = 0xFF

# Unifying / Nano / Bolt / Lightspeed receivers (talk via slot 1-6).
RECEIVER_PIDS = {
    0xC52B, 0xC532, 0xC52F, 0xC534, 0xC539, 0xC53A, 0xC53D, 0xC53F,
    0xC541, 0xC542, 0xC545, 0xC547, 0xC548, 0xC52E, 0xC531, 0xC517,
    0xC518, 0xC51A, 0xC51B, 0xC521, 0xC525, 0xC526, 0xC537, 0xC53B,
}

# MX Anywhere 2 wireless / Bluetooth product IDs.
ANYWHERE2_WPIDS = {0x404A, 0x4072, 0xB013, 0xB018, 0xB01F}


class HidppError(RuntimeError):
    pass


@dataclass
class HidInterface:
    path: bytes
    vendor_id: int
    product_id: int
    usage_page: int
    usage: int
    interface_number: int
    product_string: str
    manufacturer_string: str
    serial: str
    is_receiver: bool

    @property
    def path_str(self) -> str:
        if isinstance(self.path, bytes):
            return self.path.decode("utf-8", errors="replace")
        return str(self.path)


@dataclass
class HostSlot:
    index: int
    paired: bool = True
    name: str = ""
    current: bool = False


@dataclass
class ChangeHostDevice:
    iface: HidInterface
    device_index: int
    name: str
    change_host_index: int
    hosts_info_index: Optional[int]
    host_count: int
    current_host: int
    wpid: str = ""
    protocol: str = ""
    hosts: list[HostSlot] = field(default_factory=list)

    @property
    def is_anywhere2(self) -> bool:
        if self.wpid:
            try:
                if int(self.wpid, 16) in ANYWHERE2_WPIDS:
                    return True
            except ValueError:
                pass
        return "anywhere 2" in (self.name or "").lower()

    def host_label(self, index: int, custom: str = "") -> str:
        slot = next((h for h in self.hosts if h.index == index), None)
        name = (custom or "").strip() or (slot.name if slot else "")
        label = f"Channel {index + 1}"
        if name:
            label = f"{label} — {name}"
        if slot and slot.current:
            label += "  (this PC)"
        elif slot and not slot.paired:
            label += "  (empty)"
        return label


def _decode_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _score_hidpp_collection(info: dict) -> int:
    up = int(info.get("usage_page") or 0)
    usage = int(info.get("usage") or 0)
    score = 0
    if up == 0xFF43 and usage == 0x0202:
        score = 100
    elif up == 0xFF00 and usage == 0x0002:
        score = 90
    elif up == 0xFF00 and usage == 0x0001:
        score = 80
    elif up == 0xFF43:
        score = 70
    elif up >= 0xFF00:
        score = 40
    product = _decode_str(info.get("product_string")).lower()
    if "download assistant" in product:
        score = max(score, 95)
    if "receiver" in product:
        score = max(score, 60)
    return score


def enumerate_hidpp_interfaces() -> list[HidInterface]:
    """Return one HID++ vendor collection per physical Logitech device."""
    grouped: dict[tuple, list[tuple[int, dict]]] = {}
    try:
        devices = hid.enumerate(LOGITECH_VID)
    except TypeError:
        devices = [d for d in hid.enumerate() if int(d.get("vendor_id") or 0) == LOGITECH_VID]

    for info in devices:
        score = _score_hidpp_collection(info)
        if score <= 0:
            continue
        serial = _decode_str(info.get("serial_number"))
        key = (
            int(info.get("vendor_id") or 0),
            int(info.get("product_id") or 0),
            serial,
        )
        grouped.setdefault(key, []).append((score, info))

    result: list[HidInterface] = []
    for (_vid, pid, serial), items in grouped.items():
        items.sort(key=lambda pair: pair[0], reverse=True)
        info = items[0][1]
        product = _decode_str(info.get("product_string"))
        is_receiver = pid in RECEIVER_PIDS or "receiver" in product.lower()
        result.append(
            HidInterface(
                path=info["path"],
                vendor_id=int(info.get("vendor_id") or 0),
                product_id=pid,
                usage_page=int(info.get("usage_page") or 0),
                usage=int(info.get("usage") or 0),
                interface_number=int(info.get("interface_number") or -1),
                product_string=product,
                manufacturer_string=_decode_str(info.get("manufacturer_string")),
                serial=serial,
                is_receiver=is_receiver,
            )
        )
    return result


class HidppConnection:
    def __init__(self, iface: HidInterface):
        self.iface = iface
        self._dev: Optional[hid.device] = None
        self.long_only = iface.usage_page == 0xFF43 or iface.usage == 0x0202

    def __enter__(self) -> "HidppConnection":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def open(self) -> None:
        if self._dev is not None:
            return
        dev = hid.device()
        try:
            dev.open_path(self.iface.path)
        except Exception as exc:
            raise HidppError(
                f"Could not open HID++ interface {self.iface.product_string or hex(self.iface.product_id)}: {exc}"
            ) from exc
        try:
            # Blocking reads with an explicit timeout are more reliable on BLE HID.
            dev.set_nonblocking(False)
        except Exception:
            pass
        self._dev = dev

    def close(self) -> None:
        if self._dev is None:
            return
        try:
            self._dev.close()
        except Exception:
            pass
        self._dev = None

    def _flush(self) -> None:
        assert self._dev is not None
        for _ in range(32):
            data = self._dev.read(64, 1)
            if not data:
                break

    def write_report(self, payload: bytes) -> int:
        assert self._dev is not None
        written = self._dev.write(payload)
        if written is None:
            return -1
        return int(written)

    def read_report(self, timeout_ms: int) -> bytes:
        assert self._dev is not None
        data = self._dev.read(64, timeout_ms)
        if not data:
            return b""
        return bytes(data)

    def request(
        self,
        device_index: int,
        feature_index: int,
        function: int,
        params: bytes = b"",
        timeout_ms: int = 600,
        no_reply: bool = False,
        prefer_long: bool = True,
    ) -> Optional[bytes]:
        """Send a HID++ 2.0 request. Returns parameter bytes (after the 4-byte header)."""
        header = bytes(
            [
                0,  # report id filled below
                device_index & 0xFF,
                feature_index & 0xFF,
                ((function & 0x0F) << 4) | (SW_ID & 0x0F),
            ]
        )
        body = header[1:] + params
        reports: list[bytes] = []
        long_report = bytes([REPORT_LONG]) + (body + bytes(LONG_LEN - 1 - len(body)))[: LONG_LEN - 1]
        short_ok = len(params) <= 3 and not getattr(self, "long_only", False)
        short_report = bytes([REPORT_SHORT]) + (body + bytes(SHORT_LEN - 1 - len(body)))[: SHORT_LEN - 1]
        if prefer_long:
            reports.append(long_report)
            if short_ok:
                reports.append(short_report)
        else:
            if short_ok:
                reports.append(short_report)
            reports.append(long_report)

        last_error: Optional[str] = None
        for report in reports:
            self._flush()
            try:
                written = self.write_report(report)
            except Exception as exc:
                last_error = str(exc)
                continue
            if written is not None and written < 0:
                last_error = "HID write failed"
                continue
            if no_reply:
                time.sleep(0.05)
                return b""
            deadline = time.monotonic() + (timeout_ms / 1000.0)
            while time.monotonic() < deadline:
                remaining = max(1, int((deadline - time.monotonic()) * 1000))
                data = self.read_report(min(remaining, 120))
                if not data:
                    continue
                parsed = self._match_response(data, device_index, feature_index, function)
                if parsed is None:
                    continue
                kind, payload = parsed
                if kind == "error":
                    raise HidppError(payload)
                return payload
        if last_error and last_error != "HID write failed":
            raise HidppError(last_error)
        return None

    def _match_response(
        self, data: bytes, device_index: int, feature_index: int, function: int
    ) -> Optional[tuple[str, bytes | str]]:
        if len(data) < 5:
            return None
        # Some stacks omit the report id; normalise.
        if data[0] not in (REPORT_SHORT, REPORT_LONG, 0x12):
            data = bytes([REPORT_LONG if len(data) >= 15 else REPORT_SHORT]) + data
        if len(data) < 5:
            return None
        if data[1] != (device_index & 0xFF):
            return None
        sw = data[3] & 0x0F
        if sw not in (SW_ID, 0):
            return None
        if data[2] == ERROR_HIDPP10:
            code = data[5] if len(data) > 5 else -1
            return ("error", f"HID++ 1.0 error 0x{code:02X}")
        if data[2] == ERROR_HIDPP20:
            code = data[6] if len(data) > 6 else -1
            return ("error", f"HID++ 2.0 error 0x{code:02X}")
        if data[2] != (feature_index & 0xFF):
            return None
        if ((data[3] >> 4) & 0x0F) != (function & 0x0F) and sw == SW_ID:
            # Notifications can share the feature; ignore mismatched functions.
            return None
        return ("ok", data[4:])

    def ping(self, device_index: int, timeout_ms: int = 500) -> Optional[str]:
        ping_byte = 0x5A
        try:
            reply = self.request(
                device_index,
                0x00,
                0x01,
                bytes([0x00, 0x00, ping_byte]),
                timeout_ms=timeout_ms,
            )
        except HidppError:
            return None
        if not reply or len(reply) < 3:
            return None
        if reply[2] != ping_byte and reply[0:1] == b"\x00":
            # Some stacks echo ping at the end; still treat as alive if we got a reply.
            pass
        major, minor = reply[0], reply[1]
        if major == 0 and minor == 0:
            return "1.0"
        return f"{major}.{minor}"

    def get_feature_index(self, device_index: int, feature_id: int) -> Optional[int]:
        params = bytes([(feature_id >> 8) & 0xFF, feature_id & 0xFF])
        try:
            reply = self.request(device_index, 0x00, 0x00, params)
        except HidppError:
            return None
        if not reply:
            return None
        index = reply[0]
        if index == 0 and feature_id != FEATURE_ROOT:
            return None
        return index

    def get_name(self, device_index: int, name_feature: Optional[int]) -> str:
        if not name_feature:
            return self.iface.product_string or "Logitech device"
        try:
            length_reply = self.request(device_index, name_feature, 0x00)
            if not length_reply:
                return self.iface.product_string or "Logitech device"
            length = length_reply[0]
            name = bytearray()
            offset = 0
            while offset < length:
                chunk = self.request(device_index, name_feature, 0x01, bytes([offset]))
                if not chunk:
                    break
                piece = chunk[: max(0, length - offset)]
                name.extend(piece.rstrip(b"\x00"))
                if len(piece) == 0:
                    break
                offset += len(piece)
            decoded = bytes(name).decode("utf-8", errors="replace").strip("\x00").strip()
            return decoded or self.iface.product_string or "Logitech device"
        except HidppError:
            return self.iface.product_string or "Logitech device"

    def get_wpid(self, device_index: int, fw_feature: Optional[int]) -> str:
        if not self.iface.is_receiver:
            return f"{self.iface.product_id:04X}"
        if not fw_feature:
            return ""
        try:
            reply = self.request(device_index, fw_feature, 0x01, bytes([0x01]))
        except HidppError:
            reply = None
        if reply and len(reply) >= 3:
            wpid = (reply[1] << 8) | reply[2]
            if wpid:
                return f"{wpid:04X}"
        return f"{self.iface.product_id:04X}"

    def get_host_info(self, device_index: int, ch_index: int) -> tuple[int, int]:
        reply = self.request(device_index, ch_index, 0x00)
        if not reply or len(reply) < 2:
            return 3, 0
        count = reply[0] or 3
        current = reply[1]
        return int(count), int(current)

    def get_cookies(self, device_index: int, ch_index: int, host_count: int) -> list[bool]:
        try:
            reply = self.request(device_index, ch_index, 0x02)
        except HidppError:
            return [True] * host_count
        if not reply:
            return [True] * host_count
        flags = []
        for i in range(host_count):
            flags.append(bool(reply[i]) if i < len(reply) else True)
        # Some mice (MX Anywhere 2) accept the call but return zeros.
        if not any(flags):
            return [True] * host_count
        return flags

    def get_host_names(
        self, device_index: int, hosts_info_index: int, host_count: int, current_host: int
    ) -> dict[int, str]:
        names: dict[int, str] = {}
        try:
            state = self.request(device_index, hosts_info_index, 0x00)
        except HidppError:
            return names
        if not state:
            return names
        capability = state[0]
        if not (capability & 0x01):
            return names
        for host in range(host_count):
            try:
                info = self.request(device_index, hosts_info_index, 0x01, bytes([host]))
            except HidppError:
                continue
            if not info or len(info) < 6:
                continue
            name_len = info[4]
            name = bytearray()
            remaining = name_len
            while remaining > 0:
                try:
                    piece = self.request(
                        device_index,
                        hosts_info_index,
                        0x03,
                        bytes([host, name_len - remaining]),
                    )
                except HidppError:
                    break
                if not piece:
                    break
                chunk = piece[2 : 2 + min(remaining, 14)]
                name.extend(chunk)
                remaining -= len(chunk)
            decoded = bytes(name).decode("utf-8", errors="replace").strip()
            if decoded:
                names[host] = decoded
        if current_host in names or True:
            hostname = socket.gethostname().partition(".")[0]
            names[current_host] = hostname
        return names

    def set_host(self, device_index: int, ch_index: int, host: int) -> None:
        self.request(
            device_index,
            ch_index,
            0x01,
            bytes([host & 0xFF]),
            timeout_ms=200,
            no_reply=True,
        )


def _probe_slot(conn: HidppConnection, device_index: int) -> Optional[ChangeHostDevice]:
    proto = conn.ping(device_index)
    if not proto:
        return None
    ch_index = conn.get_feature_index(device_index, FEATURE_CHANGE_HOST)
    if ch_index is None:
        return None
    name_index = conn.get_feature_index(device_index, FEATURE_DEVICE_NAME)
    fw_index = conn.get_feature_index(device_index, FEATURE_FW_VERSION)
    hosts_info = conn.get_feature_index(device_index, FEATURE_HOSTS_INFO)
    name = conn.get_name(device_index, name_index)
    wpid = conn.get_wpid(device_index, fw_index)
    count, current = conn.get_host_info(device_index, ch_index)
    count = max(1, min(int(count), 6))
    current = max(0, min(int(current), count - 1))
    paired = conn.get_cookies(device_index, ch_index, count)
    names: dict[int, str] = {}
    if hosts_info is not None:
        names = conn.get_host_names(device_index, hosts_info, count, current)
    hosts = [
        HostSlot(
            index=i,
            paired=paired[i] if i < len(paired) else True,
            name=names.get(i, ""),
            current=(i == current),
        )
        for i in range(count)
    ]
    return ChangeHostDevice(
        iface=conn.iface,
        device_index=device_index,
        name=name,
        change_host_index=ch_index,
        hosts_info_index=hosts_info,
        host_count=count,
        current_host=current,
        wpid=wpid,
        protocol=proto,
        hosts=hosts,
    )


def find_change_host_devices() -> list[ChangeHostDevice]:
    found: list[ChangeHostDevice] = []
    for iface in enumerate_hidpp_interfaces():
        try:
            with HidppConnection(iface) as conn:
                if iface.is_receiver:
                    indices: Iterable[int] = range(1, 7)
                else:
                    indices = (0xFF, 0x00)
                for idx in indices:
                    device = _probe_slot(conn, idx)
                    if device:
                        found.append(device)
                        if not iface.is_receiver:
                            break
        except HidppError as exc:
            log.warning("Skipping %s: %s", iface.product_string or hex(iface.product_id), exc)
        except Exception:
            log.exception("Failed probing %s", iface.product_string or hex(iface.product_id))
    found.sort(key=lambda d: (0 if d.is_anywhere2 else 1, d.name.lower()))
    return found


def pick_device(
    devices: list[ChangeHostDevice],
    preferred_wpid: str = "",
    preferred_name: str = "Anywhere 2",
) -> Optional[ChangeHostDevice]:
    if not devices:
        return None
    if preferred_wpid:
        for dev in devices:
            if dev.wpid.upper() == preferred_wpid.upper():
                return dev
    needle = (preferred_name or "").lower()
    if needle:
        for dev in devices:
            if needle in dev.name.lower():
                return dev
    for dev in devices:
        if dev.is_anywhere2:
            return dev
    return devices[0]


def switch_host(device: ChangeHostDevice, host_index: int) -> None:
    if host_index < 0 or host_index >= device.host_count:
        raise HidppError(f"Channel {host_index + 1} is out of range")
    if host_index == device.current_host:
        raise HidppError(f"Already on Channel {host_index + 1}")
    with HidppConnection(device.iface) as conn:
        conn.set_host(device.device_index, device.change_host_index, host_index)


def options_plus_running() -> bool:
    try:
        import subprocess

        output = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        lower = output.lower()
        return "logioptionsplus" in lower or "lghub" in lower
    except Exception:
        log.debug("Could not inspect process list", exc_info=True)
        return False
