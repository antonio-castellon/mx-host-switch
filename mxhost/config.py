"""Persistent settings for the tray app."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("mxhost.config")

APP_DIR_NAME = "MXHostSwitch"
DEFAULTS: dict[str, Any] = {
    "target_host": 1,
    "preferred_wpid": "B01F",
    "preferred_name": "Anywhere 2",
    "channel_names": {
        "0": "",
        "1": "",
        "2": "",
    },
}


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return app_data_dir() / "config.json"


def log_path() -> Path:
    return app_data_dir() / "mxhost.log"


def load() -> dict[str, Any]:
    path = config_path()
    data = dict(DEFAULTS)
    data["channel_names"] = dict(DEFAULTS["channel_names"])
    if path.is_file():
        try:
            with path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                names = loaded.pop("channel_names", None)
                data.update(loaded)
                if isinstance(names, dict):
                    merged = dict(data["channel_names"])
                    for key, value in names.items():
                        merged[str(key)] = str(value) if value is not None else ""
                    data["channel_names"] = merged
        except Exception:
            log.exception("Failed to read %s", path)
    data["target_host"] = int(data.get("target_host", 1))
    return data


def save(data: dict[str, Any]) -> None:
    path = config_path()
    try:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        log.exception("Failed to write %s", path)


def channel_label(cfg: dict[str, Any], host_index: int, device_name: str | None = None) -> str:
    names = cfg.get("channel_names") or {}
    custom = str(names.get(str(host_index), "") or "").strip()
    if custom:
        return custom
    if device_name:
        return f"Channel {host_index + 1} — {device_name}"
    return f"Channel {host_index + 1}"
