# Changelog

All notable changes to USB Desktop Extend will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.1] - 2026-08-11

### Fixed

- **Connection loss after suspend/resume** — Added health check monitor that verifies ADB tunnel and RDP port every 10 seconds, with automatic reconnection
- **Stale tunnel on app exit** — Added atexit handler and SIGTERM/SIGINT signal handlers to always clean up ADB reverse tunnels
- **RDP service not restarting properly** — Added verification step after initial setup and automatic gnome-remote-desktop restart on failure

### Changed

- Footer text now says "Tunnel Connected. Connect with your RDP app on the tablet" instead of "Connected. Drag windows between screens freely"
- Tooltip hover delay reduced from ~700ms to 100ms
- Close button now shows dialog: "Disconnect & Quit" / "Minimize to Tray" / Cancel (instead of always minimizing)

### Added

- Health check monitor (10s interval) verifies tablet, tunnel, and RDP port after connection
- Auto-reconnect: restarts gnome-remote-desktop and re-establishes ADB tunnel on failure
- Connection lost notification with specific failure reason
- `connection_lost` signal for UI notification when connection fails permanently
- `_verify_rdp_connectivity()` tests actual TCP connection, not just port state

## [0.1.0] - 2026-08-10

### Added

- **GUI application** with PyQt6
  - Main window with credentials, status indicators, connect/disconnect buttons
  - Real-time log output with color-coded messages
  - System tray integration (minimize to tray, quick actions)
- **Terminal theme** (green-on-black aesthetic)
  - Full CSS stylesheet with monospace fonts
  - Styled input fields, buttons, scrollbars, tooltips
- **Info icons** with hover tooltips
  - Credentials section — explains RDP auth defaults
  - ADB indicator — "Enable USB Debugging in Settings → Developer Options"
  - RDP indicator — explains GNOME Remote Desktop extend mode
  - Tunnel indicator — explains ADB reverse tunnel bypass
  - Log area — describes what the log shows
  - Start/Stop buttons — detailed step-by-step descriptions
- **Footer status bar** showing connection state
- **Binary packaging** via PyInstaller (`dist/usb-desktop-extend`)
- **Installation** via `pip install -e .` with `usb-desktop-extend` command
- **Desktop entry** (`usb-desktop-extend.desktop`) for Linux app launchers
- **Documentation** — README, CHANGELOG, AGENTS.md

### Fixed

- Removed `self._emit_status.adb = False` bug that caused crash on connect
