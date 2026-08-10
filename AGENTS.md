# Agents

This document describes how AI coding agents should work with this codebase.

## Project Overview

**USB Desktop Extend** is a Python/PyQt6 GUI application that turns an Android tablet into a second monitor over USB. It wraps GNOME Remote Desktop's extend mode + ADB reverse tunneling into a one-click interface.

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python -m usb_desktop_extend` | Run the app directly |
| `pip install -e .` | Install in development mode |
| `usb-desktop-extend` | Run the installed command |

## Architecture

### Core Modules

- **`backend.py`** — All subprocess calls (adb, grdctl, gsettings, systemctl). Runs in a QThread. Emits `log_message`, `status_changed`, `finished` signals.
- **`app.py`** — PyQt6 GUI. Main window, system tray, status indicators, log area. Contains the terminal theme stylesheet (`STYLESHEET` constant).
- **`log_handler.py`** — Bridges Python logging to Qt signals for real-time GUI updates.
- **`main.py`** — Entry point. Prompts for sudo, validates it, launches window.

### Connection Flow (backend.py)

```
1. Poll adb devices → detect tablet
2. sudo grdctl --system rdp disable → stop system service
3. grdctl rdp enable → extend mode → set credentials → restart
4. adb reverse tcp:3389 tcp:3389 → verify tunnel
```

### Key Constants

- `RDP_PORT = 3389` — used throughout backend
- `POLL_INTERVAL = 2` — seconds between ADB device polls
- `C` dict in `app.py` — all theme colors
- `STYLESHEET` in `app.py` — full CSS for the terminal theme

## Code Style

- **Python 3.10+** — use `str | None` union syntax, `match` statements if needed
- **No comments** unless explicitly requested
- **Type hints** on all function signatures
- **f-strings** for all string formatting
- **Qt signals** for all cross-thread communication
- **Subprocess** — always use `capture_output=True`, handle errors with try/except

## Common Tasks

### Adding a new connection step

1. Add the step method in `backend.py` (`ConnectionManager`)
2. Call it from `_connect()` in order
3. Use `self._log()` for output
4. Emit `status_changed` if it affects indicators

### Modifying the theme

1. Edit the `C` dict (colors) and `STYLESHEET` constant in `app.py`
2. Widget-specific styles are inline in `_setup_ui()` — move to global stylesheet when possible

### Adding tooltips

1. Add `InfoIcon("tooltip text")` next to the relevant widget in `_setup_ui()`
2. Or use `widget.setToolTip("text")` for standard hover tooltips

### Building the binary

```bash
pyinstaller --onefile --windowed --name usb-desktop-extend \
  --icon=assets/icon.png --add-data "assets/icon.png:assets" \
  run_app.py
```

## Testing

No test suite yet. Manual testing:

1. Run `python -m usb_desktop_extend`
2. Verify sudo prompt works
3. Verify GUI renders with terminal theme
4. Connect a tablet and verify the 4-step flow
5. Verify tray icon and minimize behavior

## File Map

```
usb_desktop_extend/
├── __init__.py      # __version__ = "1.0.0"
├── __main__.py      # python -m entry point
├── main.py          # sudo prompt → MainWindow
├── app.py           # GUI + theme + tray
├── backend.py       # ADB/RDP/GNOME commands in QThread
└── log_handler.py   # logging.Handler → Qt signals
```
