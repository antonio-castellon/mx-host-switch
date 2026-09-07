#!/usr/bin/env python3
"""Cross-platform PyInstaller build used by CI and local packaging."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from mxhost.icon import write_assets

    write_assets()
    icon = ROOT / "assets" / "icon.ico"
    args = [
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "MXHostSwitch",
        "--hidden-import",
        "hid",
        "--collect-submodules",
        "pystray",
        str(ROOT / "mx_host_switch.py"),
    ]
    if sys.platform == "win32":
        args += ["--windowed", "--icon", str(icon), "--hidden-import", "pystray._win32"]
    elif sys.platform == "darwin":
        args += [
            "--windowed",
            "--osx-bundle-identifier",
            "ch.castellon.mxhostswitch",
            "--hidden-import",
            "pystray._darwin",
        ]
        if icon.is_file():
            args += ["--icon", str(icon)]
    else:
        args += ["--hidden-import", "pystray._appindicator", "--hidden-import", "pystray._gtk"]

    import PyInstaller.__main__

    PyInstaller.__main__.run(args)

    dist = ROOT / "dist"
    if sys.platform == "win32":
        built = dist / "MXHostSwitch.exe"
        if not built.is_file():
            raise SystemExit("Windows build missing dist/MXHostSwitch.exe")
        print(built)
        return 0

    if sys.platform == "darwin":
        app = dist / "MXHostSwitch.app"
        binary = dist / "MXHostSwitch"
        if app.is_dir():
            print(app)
            return 0
        if binary.is_file():
            print(binary)
            return 0
        raise SystemExit("macOS build missing dist/MXHostSwitch.app")

    built = dist / "MXHostSwitch"
    if not built.is_file():
        raise SystemExit("Linux build missing dist/MXHostSwitch")
    built.chmod(built.stat().st_mode | 0o111)
    print(built)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
