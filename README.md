# MX Host Switch

Tray app that moves a Logitech multi-host mouse between computers the way **Logi Flow** does: push the pointer off the left or right edge of the screen, and the mouse follows to the machine assigned to that side. No button on the underside, no double-click.

It talks to the mouse over HID++ **CHANGE HOST** (`0x1814`). Assign **Left** and **Right** under **Edge switch** (default is **None** — no action). Double-click on the tray icon is still there if you want a manual jump.

![Tray menu: Edge switch, right edge assigned to Channel 1](assets/tray-menu.png)

## Download (no compile)

Get a ready-made program from **[Releases](https://github.com/antonio-castellon/mx-host-switch/releases/latest)**:

| File | Who it is for |
| --- | --- |
| `MXHostSwitch-windows-x64.exe` | Windows 10/11, 64-bit |
| `MXHostSwitch-linux-x64` | Linux x86_64 |
| `MXHostSwitch-macos-x64.zip` | macOS Intel |
| `MXHostSwitch-macos-arm64.zip` | macOS Apple Silicon (M1/M2/M3/M4) |

No Python, no installer, no compile.

**Windows:** double-click the `.exe`. If **Windows protected your PC** appears, choose **More info** → **Run anyway**. The icon may sit behind `^` in the notification area.

**macOS:** unzip, then right-click the app → **Open** (Gatekeeper). The binary is not notarized.

**Linux:** `chmod +x MXHostSwitch-linux-x64` and run it from a desktop session. Install AppIndicator/GTK if the tray icon does not appear (`gir1.2-ayatanaappindicator3-0.1` on Debian/Ubuntu). HID access may need a udev rule for vendor `046d` or membership in `plugdev`.

The source in this repository is for people who want to build it themselves.

## Why this exists

The MX Anywhere 2 is an older multi-channel mouse. Logitech’s current **Logi Options+** app does not support it, and **Logi Flow** (move the mouse off the screen to another computer) was never offered for this model.

Switching machines meant flipping the mouse over and pressing the Easy-Switch button every time. This tray app sends the same HID++ CHANGE HOST command Flow would use, so the pointer can leave the left or right edge of the display and land on the other PC.

## Compatibility

The app is written for **any Logitech HID++ 2.0+ mouse that exposes CHANGE HOST** (`0x1814` — Easy-Switch / multi-computer pairing), over Bluetooth or a Unifying / Bolt / Nano receiver.

It discovers devices at runtime: it does not hard-code a single model. Channel count, current host, and the CHANGE HOST feature index are read from the mouse.

### Tested

| Mouse | Connection | Result |
| --- | --- | --- |
| **MX Anywhere 2** | Bluetooth (PID `B01F`), HID++ 4.5, 3 channels | Works |

### Maybe compatible (not tested here)

These **Logitech** mice are multi-channel / Easy-Switch and, in Solaar dumps or Logitech docs, expose HID++ CHANGE HOST. They **should** work with this app, but nobody has verified them with MX Host Switch yet.

**MX Master**

- MX Master (original)
- MX Master 2S
- MX Master 3 / 3 for Mac / 3 for Business
- MX Master 3S / 3S for Mac / 3S for Business
- MX Master 4 / 4 for Mac / 4 for Business

**MX Anywhere**

- MX Anywhere 2 (Unifying variants `404A` / `4072`, Bluetooth `B013` / `B018` / `B01F`)
- MX Anywhere 2S
- MX Anywhere 3 / 3 for Mac / 3 for Business
- MX Anywhere 3S / 3S for Mac / 3S for Business

**Other Easy-Switch mice / trackballs**

- MX Vertical
- MX Ergo
- M720 Triathlon
- M585 / M590 Multi-Device
- Lift / Lift for Mac
- Pebble Mouse 2 (M350s)
- POP Mouse
- Signature M750 / Signature AI Edition M750

If several Logitech devices are connected, the tray app prefers a name matching `Anywhere 2`. For another model, set `preferred_name` in the config file (for example `"Master 3"`) or run `mx_host_switch.py -l` and confirm CHANGE HOST is listed.

### Probably not compatible

- First-generation **Anywhere MX** and **Performance MX** (HID++ 1.0, no CHANGE HOST)
- Single-computer mice with no Easy-Switch button (most M185 / M170 / G-series gaming mice)
- Keyboards (MX Keys, etc.): they speak the same HID++ feature, but this app is a **mouse** tray tool

### Other brands

**No.** Microsoft, Apple, Razer, Corsair, Dell, HP, Keychron, Elecom, and similar multi-device mice cannot use this app.

Channel switching here is not generic Bluetooth. It sends Logitech’s private **HID++ CHANGE HOST** command (`0x1814`) to vendor ID `046D`. Other brands either use the operating system’s Bluetooth stack or their own protocol (Synapse, iCUE, …). This tool does not speak those.

A mouse that “pairs with 3 computers” is not enough. It must be a Logitech HID++ Easy-Switch device.

### How to check your mouse

With the mouse on this PC:

```powershell
python mx_host_switch.py -l
```

If you see `CHANGE HOST devices:` and three channels, the app can drive it. If you only see `HID++ interfaces` and no CHANGE HOST device, this mouse is not supported (or Logi Options+ is locking the HID++ collection).

## Features

- Stays in the notification area (system tray)
- **Edge switch** (Flow-style): push the pointer off the left or right of the screen to jump to the channel assigned to that side (`None` = no action)
- Manual **Switch now** / double-click still available
- Right-click menu lists channels; a tick marks the selection
- Prefers a device named like “Anywhere 2” when several HID++ devices are present
- Optional channel labels in a JSON config file
- CLI to list devices or switch without the tray

## Requirements

- Windows 10/11, Linux, or macOS
- Python 3.13 (3.10+ should work) to run from source
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

The built binary is **not** stored in git. Pre-built copies for Windows, Linux, and macOS are attached to [GitHub Releases](https://github.com/antonio-castellon/mx-host-switch/releases).

Local build:

```powershell
# Windows
.\build.ps1
```

```bash
# Linux / macOS
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build.py
```

GitHub Actions (`.github/workflows/release.yml`) builds all four artifacts when you push a `v*` tag.

## Tray usage

| Action | Result |
| --- | --- |
| Right-click the icon | Open the menu |
| **Edge switch → Left / Right** | Flow-style: push the pointer off that screen edge to jump to the assigned channel. **None (no action)** is the default |
| Click a channel under **Switch target** | Manual jump target (tick moves) |
| **Switch now** or **double-click** | Optional manual CHANGE HOST (not required once edges are assigned) |
| Refresh mouse | Re-scan HID++ devices |
| **About** | App version, author, email, website |
| Quit | Exit the tray app |

After a successful switch the mouse leaves this PC. The icon stays in the tray so you can switch again when you come back.

Windows 11 often hides the icon behind the `^` overflow in the notification area.

This PC’s current channel is labelled **(this PC)** in the menu.

### Edge switch

Windows (and other desktops that report a cursor position) cannot place the pointer *outside* the screen, so the app treats “pushed against the left or right edge for a short moment” as leaving that side.

- Assign **Left** and **Right** independently under **Edge switch**
- **None (no action)** means that edge does nothing
- After a switch, the edge is ignored until the pointer moves back inland, so coming back to this PC does not immediately bounce away again
- Top and bottom corners are ignored (Start menu / clock)

## Configuration

Settings are stored in:

- Windows: `%APPDATA%\MXHostSwitch\config.json`
- macOS: `~/Library/Application Support/MXHostSwitch/config.json`
- Linux: `~/.config/mxhostswitch/config.json`

```json
{
  "target_host": 0,
  "preferred_wpid": "B01F",
  "preferred_name": "Anywhere 2",
  "channel_names": {
    "0": "Home PC",
    "1": "Work laptop",
    "2": ""
  },
  "edge_left_host": null,
  "edge_right_host": 0
}
```

| Field | Meaning |
| --- | --- |
| `target_host` | 0-based Easy-Switch slot used by double-click |
| `preferred_wpid` | Prefer this wireless/Bluetooth product ID when several devices exist |
| `preferred_name` | Substring match on the device name (default `Anywhere 2`) |
| `channel_names` | Optional labels (`"0"` = Channel 1, `"1"` = Channel 2, …) |
| `edge_left_host` | Channel for the left screen edge, or `null` for none |
| `edge_right_host` | Channel for the right screen edge, or `null` for none |

Log file: `mxhost.log` in the same folder.

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
  edge.py           # left/right screen-edge host switch
  config.py         # settings (AppData / Application Support / ~/.config)
  icon.py           # generated tray / exe icon
build.ps1           # Windows PyInstaller one-file build
scripts/build.py    # cross-platform PyInstaller build (CI)
.github/workflows/release.yml
requirements.txt
```

## License

Personal / source-available. No warranty: sending CHANGE HOST disconnects the mouse from this computer by design.
