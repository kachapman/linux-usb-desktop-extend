"""Connection manager - wraps all ADB/RDP/GNOME shell commands."""

import logging
import subprocess
import time

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

RDP_PORT = 3389
POLL_INTERVAL = 2


class ConnectionManager(QThread):
    """Manages the USB desktop extend connection in a background thread."""

    log_message = pyqtSignal(str, str)  # (level, message)
    status_changed = pyqtSignal(dict)   # {"adb": bool, "rdp": bool, "tunnel": bool}
    finished = pyqtSignal(bool)         # success

    def __init__(self, username: str, password: str, sudo_password: str):
        super().__init__()
        self.username = username
        self.password = password
        self.sudo_password = sudo_password
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def _log(self, level: str, msg: str):
        self.log_message.emit(level, msg)
        getattr(logger, level if level != "success" else "info")(msg)

    def _run_cmd(self, cmd: list[str], check: bool = True, sudo: bool = False) -> subprocess.CompletedProcess:
        """Run a command, optionally with sudo. Returns CompletedProcess."""
        if sudo:
            cmd = ["sudo", "-S"] + cmd

        self._log("info", f"  $ {' '.join(cmd)}")

        proc = subprocess.run(
            cmd,
            input=self.sudo_password.encode() if sudo else None,
            capture_output=True,
            timeout=30,
        )

        if proc.returncode != 0 and check:
            stderr = proc.stderr.decode().strip()
            raise RuntimeError(f"Command failed (exit {proc.returncode}): {stderr}")

        return proc

    def _run_cmd_streaming(self, cmd: list[str], sudo: bool = False) -> tuple[int, str]:
        """Run a command and stream output via log signals. Returns (returncode, combined output)."""
        if sudo:
            cmd = ["sudo", "-S"] + cmd

        self._log("info", f"  $ {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if sudo else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if sudo and self.sudo_password:
            proc.stdin.write(self.sudo_password + "\n")
            proc.stdin.flush()

        output_lines = []
        for line in proc.stdout:
            line = line.rstrip("\n")
            if line:
                self._log("info", f"  {line}")
                output_lines.append(line)

        proc.wait()
        return proc.returncode, "\n".join(output_lines)

    def run(self):
        """Execute the full connection sequence."""
        try:
            self._log("info", "=== Starting USB Desktop Extend Connection ===")
            self._connect()
            self._log("success", "=== Connection Established Successfully ===")
            self.finished.emit(True)
        except Exception as e:
            self._log("error", f"Connection failed: {e}")
            self.finished.emit(False)

    def _connect(self):
        # Step 1: Wait for tablet
        self._log("info", "[1/4] Waiting for tablet USB connection...")
        self.status_changed.emit({"adb": False, "rdp": False, "tunnel": False})

        tablet_serial = None
        while not self._stop_requested:
            tablet_serial = self._detect_tablet()
            if tablet_serial:
                break
            time.sleep(POLL_INTERVAL)

        if self._stop_requested:
            raise RuntimeError("Cancelled by user")

        self._log("success", f"  Tablet detected: {tablet_serial}")
        self.status_changed.emit({"adb": True, "rdp": False, "tunnel": False})

        # Step 2: Disable system-level Remote Login
        self._log("info", "[2/4] Disabling Remote Login (system-level)...")
        self._disable_system_rdp()

        # Step 3: Enable user-level Desktop Sharing with EXTEND mode
        self._log("info", "[3/4] Configuring Desktop Sharing in EXTEND mode...")
        self._enable_user_rdp()
        self.status_changed.emit({"adb": True, "rdp": True, "tunnel": False})

        # Step 4: Set up ADB reverse tunnel
        self._log("info", "[4/4] Setting up ADB reverse tunnel...")
        self._setup_adb_tunnel()
        self.status_changed.emit({"adb": True, "rdp": True, "tunnel": True})

    def _detect_tablet(self) -> str | None:
        """Poll adb devices for a connected tablet."""
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("List") or "daemon" in line:
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    return parts[0]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def _disable_system_rdp(self):
        """Disable system-level Remote Login (conflicts with user-level)."""
        cmds = [
            ["grdctl", "--system", "rdp", "disable"],
            ["systemctl", "stop", "gnome-remote-desktop.service"],
            ["systemctl", "disable", "gnome-remote-desktop.service"],
        ]
        for cmd in cmds:
            try:
                self._run_cmd(cmd, check=False, sudo=True)
            except Exception:
                pass  # These are best-effort; may fail if already disabled

    def _enable_user_rdp(self):
        """Enable user-level Desktop Sharing with extend mode."""
        # Enable RDP
        self._run_cmd(["grdctl", "rdp", "enable"])

        # Disable view-only (allows control from tablet)
        self._run_cmd(["grdctl", "rdp", "disable-view-only"])

        # THE KEY SETTING - creates a virtual extended monitor
        self._run_cmd([
            "gsettings", "set",
            "org.gnome.desktop.remote-desktop.rdp",
            "screen-share-mode", "extend",
        ])

        # Set credentials
        self._run_cmd([
            "grdctl", "rdp", "set-credentials", self.username, self.password,
        ])

        # Restart the user service
        self._run_cmd(["systemctl", "--user", "daemon-reload"])
        self._run_cmd(["systemctl", "--user", "restart", "gnome-remote-desktop"])

        # Verify configuration
        time.sleep(2)
        result = self._run_cmd(["grdctl", "status"])
        status_output = result.stdout.decode()
        if "Status: enabled" not in status_output or "View-only: no" not in status_output:
            self._log("warning", "  RDP status verification failed, but continuing...")

        # Verify extend mode
        result = self._run_cmd([
            "gsettings", "get",
            "org.gnome.desktop.remote-desktop.rdp",
            "screen-share-mode",
        ])
        mode = result.stdout.decode().strip()
        self._log("success", f"  Screen share mode: {mode}")

        # Verify port is listening
        result = self._run_cmd(["ss", "-tlnp"], check=False)
        if f":{RDP_PORT}" in result.stdout.decode():
            self._log("success", f"  Port {RDP_PORT} is listening")
        else:
            self._log("warning", f"  Port {RDP_PORT} may not be listening yet")

    def _setup_adb_tunnel(self):
        """Create ADB reverse tunnel for RDP."""
        self._run_cmd([
            "adb", "reverse", f"tcp:{RDP_PORT}", f"tcp:{RDP_PORT}",
        ])

        # Verify tunnel
        result = self._run_cmd(["adb", "reverse", "--list"], check=False)
        if f"tcp:{RDP_PORT}" in result.stdout.decode():
            self._log("success", f"  Tunnel established: tablet 127.0.0.1:{RDP_PORT} -> laptop :{RDP_PORT}")
        else:
            raise RuntimeError("Failed to verify ADB tunnel")

    def disconnect(self):
        """Tear down the connection."""
        self._log("info", "=== Disconnecting ===")

        try:
            self._run_cmd(["adb", "reverse", "--remove-all"], check=False)
            self._log("info", "  ADB tunnels removed")
        except Exception as e:
            self._log("warning", f"  Error removing ADB tunnels: {e}")

        try:
            self._run_cmd(["grdctl", "rdp", "disable"], check=False)
            self._log("info", "  RDP disabled")
        except Exception as e:
            self._log("warning", f"  Error disabling RDP: {e}")

        try:
            self._run_cmd(["systemctl", "--user", "stop", "gnome-remote-desktop"], check=False)
            self._log("info", "  gnome-remote-desktop service stopped")
        except Exception as e:
            self._log("warning", f"  Error stopping service: {e}")

        self.status_changed.emit({"adb": False, "rdp": False, "tunnel": False})
        self._log("success", "=== Disconnected ===")
