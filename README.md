# USB Desktop Extend

Turn your Android tablet into a second monitor over USB — no WiFi, no dummy adapters, no extra hardware.

Uses GNOME Remote Desktop's extend mode + ADB reverse tunneling to create a virtual second display that you can drag windows to, just like a real monitor.

![Terminal Theme](https://img.shields.io/badge/theme-terminal%20green-black) ![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **One-click connect** — detect tablet, configure RDP, create tunnel
- **Real-time log** — see exactly what's happening at each step
- **System tray** — minimize to tray, quick connect/disconnect
- **Terminal theme** — green-on-black aesthetic with info tooltips
- **Credentials in UI** — editable RDP username/password with defaults

## How It Works

```
┌─────────────┐    USB Cable    ┌─────────────┐
│   Laptop    │◄───────────────►│   Tablet    │
│  (Fedora)   │    ADB tunnel   │ (Android)   │
│             │    :3389        │  RDP Client │
│  GNOME RDP  │────────────────►│             │
│  Extend Mode│  display stream │  127.0.0.1  │
└─────────────┘                 └─────────────┘
```

1. **ADB detection** — finds your tablet via USB
2. **Service setup** — disables conflicting system RDP, enables user-level Desktop Sharing in extend mode
3. **Tunnel** — `adb reverse tcp:3389 tcp:3389` routes the tablet's RDP client to your laptop
4. **Extend** — GNOME creates a virtual monitor; drag windows between screens freely

## Requirements

- **OS:** Fedora 40+ (GNOME/Wayland)
- **Python:** 3.10+
- **Tablet:** Android with USB Debugging enabled
- **USB cable:** USB-C to USB-C (or adapter)

### System Packages

```bash
# ADB (Android Debug Bridge)
sudo dnf install -y android-tools

# GNOME Remote Desktop (usually pre-installed)
sudo dnf install -y gnome-remote-desktop
```

### Tablet Setup

1. Enable **Developer Options** (tap Build Number 7 times)
2. Enable **USB Debugging** in Developer Options
3. Connect USB cable and tap **Allow** on the authorization prompt

## Installation

### Option 1: pip install (recommended)

```bash
git clone https://github.com/kachapman/linux-usb-desktop-extend.git
cd linux-usb-desktop-extend
pip install -e .
```

This installs the `usb-desktop-extend` command globally.

### Option 2: Run directly

```bash
python -m usb_desktop_extend
```

### Option 3: Pre-built binary

Download `usb-desktop-extend` from [Releases](https://github.com/kachapman/linux-usb-desktop-extend/releases) and run it directly — no Python needed.

## Usage

1. Connect your tablet via USB
2. Run the app:
   ```bash
   usb-desktop-extend
   ```
3. Enter your sudo password when prompted
4. Click **START CONNECTION**
5. On your tablet, open an RDP client and connect to:
   - **PC Name:** `127.0.0.1`
   - **Port:** `3389`
   - **Username:** (set in the app)
   - **Password:** (set in the app)
6. Accept the certificate warning on first connect
7. Drag windows to the tablet — it's your second screen!

Credentials are saved to `~/.config/usb-desktop-extend/config.json` after the first successful connection.

### Disconnecting

Click **STOP CONNECTION** in the app, or disconnect the USB cable.

## Building the Binary

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name usb-desktop-extend \
  --icon=assets/icon.png --add-data "assets/icon.png:assets" \
  run_app.py
```

Output: `dist/usb-desktop-extend` (~62 MB)

## Project Structure

```
linux-usb-desktop-extend/
├── usb_desktop_extend/
│   ├── __init__.py          # Package metadata
│   ├── __main__.py          # python -m entry point
│   ├── main.py              # CLI entry point with sudo prompt
│   ├── app.py               # PyQt6 GUI (terminal theme)
│   ├── backend.py           # Connection logic (ADB/RDP/GNOME)
│   └── log_handler.py       # Logging → GUI signal bridge
├── assets/
│   └── icon.png             # App icon
├── run_app.py               # Standalone entry point for PyInstaller
├── setup.py                 # pip install support
├── requirements.txt         # Dependencies
├── usb-desktop-extend.desktop  # Linux desktop entry
├── CHANGELOG.md
└── README.md
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Port 3389 conflict | Both system and user RDP running | The app disables system-level Remote Login automatically |
| Tablet not detected | USB Debugging off | Enable in Settings → Developer Options |
| "unauthorized" in ADB | Tablet not authorized | Tap "Allow" on tablet's USB debugging prompt |
| Connection refused | RDP not enabled | Check `grdctl status` — app handles this automatically |
| Black screen on tablet | Wrong RDP mode | App sets extend mode; restart if needed |

## Credits

- Built for Fedora 43 + GNOME 47
- Tested with Xiaomi tablets and Microsoft RDP client
- Terminal theme inspired by classic CRT monitors

## License

MIT
