# MX Host Switch

Windows tray app that switches a Logitech mouse to another Easy-Switch / multi-host channel using HID++ **CHANGE HOST** (`0x1814`).

Double-click the tray icon to jump to a preselected channel. Right-click to pick that target (the tick marks the default).

## Compatibility

The app is written for **any Logitech HID++ 2.0+ mouse that exposes CHANGE HOST** (Easy-Switch / multi-computer pairing), over Bluetooth or a Unifying / Bolt / Nano receiver.

It discovers devices at runtime: it does not hard-code a single model. Channel count, current host, and the CHANGE HOST feature index are read from the mouse.

**Tested only with Logitech MX Anywhere 2** (Bluetooth PID `B01F`, HID++ 4.5, three Easy-Switch channels). Other MX / multi-host mice (Anywhere 3, Master series, etc.) are expected to work but have not been verified.

## Features

- Stays in the Windows notification area (system tray)
- **Double-click** sends CHANGE HOST to the selected target channel
- **Right-click** menu lists channels; a **tick** shows the default target
- Prefers a device named like “Anywhere 2” when several HID++ devices are present
- Optional channel labels in a JSON config file
- CLI to list devices or switch without the tray

## Requirements

- Windows 10 or 11
- Python 3.13 (3.10+ should work)
- A Logitech mouse with Easy-Switch / CHANGE HOST, currently connected to this PC
- Close **Logi Options+** if HID++ access fails (it can lock the vendor HID collection)

Python packages (see `requirements.txt`):

- `hidapi` — HID++ I/O
- `Pillow` — tray icon
- `pystray` — notification-area UI
- `pyinstaller` — optional, for the standalone `.exe`

## Run from source

```powershell
cd C:\DEV.Personal\Mouse
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe mx_host_switch.py
```

List mice and channels:

```powershell
.\.venv\Scripts\python.exe mx_host_switch.py -l
```

Switch to channel `N` (1-based) and exit:

```powershell
.\.venv\Scripts\python.exe mx_host_switch.py --switch 1
```

## Standalone executable

`build.ps1` creates a one-file, no-install `dist\MXHostSwitch.exe`:

```powershell
.\build.ps1
```

The built binary is **not** in this repository. Build it locally if you want a single `.exe`.

## Tray usage

| Action | Result |
| --- | --- |
| Right-click the icon | Open the menu |
| Click a channel | Set it as the double-click target (tick moves) |
| **Switch now** or **double-click** | Send CHANGE HOST to the ticked channel |
| Refresh mouse | Re-scan HID++ devices |
| Quit | Exit the tray app |

After a successful switch the mouse leaves this PC. The icon stays in the tray so you can switch again when you come back.

Windows 11 often hides the icon behind the `^` overflow in the notification area.

This PC’s current channel is labelled **(this PC)** in the menu. Double-click does nothing useful if the ticked target is already the current channel.

## Configuration

Settings are stored in `%APPDATA%\MXHostSwitch\config.json`.

```json
{
  "target_host": 0,
  "preferred_wpid": "B01F",
  "preferred_name": "Anywhere 2",
  "channel_names": {
    "0": "Home PC",
    "1": "Work laptop",
    "2": ""
  }
}
```

| Field | Meaning |
| --- | --- |
| `target_host` | 0-based Easy-Switch slot used by double-click |
| `preferred_wpid` | Prefer this wireless/Bluetooth product ID when several devices exist |
| `preferred_name` | Substring match on the device name (default `Anywhere 2`) |
| `channel_names` | Optional labels (`"0"` = Channel 1, `"1"` = Channel 2, …) |

Log file: `%APPDATA%\MXHostSwitch\mxhost.log`.

## How it talks to the mouse

Logitech multi-host mice speak **HID++ 2.0+** on a vendor HID collection:

- Bluetooth / newer devices: usage page `0xFF43`, usage `0x0202`
- Unifying receivers: usage page `0xFF00`

The app:

1. Enumerates Logitech HID++ interfaces
2. Pings the device (or receiver slots 1–6)
3. Resolves feature **CHANGE HOST** (`0x1814`) via ROOT `GetFeature`
4. Reads host count and current host
5. On switch, writes function 1 (Set Host) with the 0-based channel index

On MX Anywhere 2 over Bluetooth, CHANGE HOST was at feature index `9` and this PC was Channel 2 of 3. Those values are discovered, not hard-coded.

## Project layout

```
mx_host_switch.py   # entry point (tray / CLI)
mxhost/
  hidpp.py          # HID++ discovery and CHANGE HOST
  tray.py           # system-tray UI
  config.py         # %APPDATA% settings
  icon.py           # generated tray / exe icon
build.ps1           # PyInstaller one-file build
requirements.txt
```

## License

Personal / source-available. No warranty: sending CHANGE HOST disconnects the mouse from this computer by design.
