"""Connection manager - wraps all ADB/RDP/GNOME shell commands."""

import logging
import subprocess
import time

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

RDP_PORT = 3389
POLL_INTERVAL = 2
HEALTH_CHECK_INTERVAL = 10


class ConnectionManager(QThread):
    """Manages the USB desktop extend connection in a background thread."""

    log_message = pyqtSignal(str, str)  # (level, message)
    status_changed = pyqtSignal(dict)   # {"adb": bool, "rdp": bool, "tunnel": bool}
    finished = pyqtSignal(bool)         # success
    connection_lost = pyqtSignal(str)   # reason

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
        """Execute the full connection sequence, then monitor."""
        try:
            self._log("info", "=== Starting USB Desktop Extend Connection ===")
            self._connect()
            self._log("success", "=== Connection Established Successfully ===")
            self.finished.emit(True)
            self._monitor()
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

        # Step 5: Verify actual connectivity
        self._log("info", "[5/5] Verifying RDP connectivity...")
        if not self._verify_rdp_connectivity():
            self._log("warning", "  RDP connectivity check failed, attempting restart...")
            self._restart_grd_service()
            time.sleep(3)
            if not self._verify_rdp_connectivity():
                self._log("warning", "  RDP still not responding after restart")

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

    def _verify_rdp_connectivity(self) -> bool:
        """Verify RDP port is actually accepting connections."""
        try:
            result = subprocess.run(
                ["nc", "-z", "127.0.0.1", str(RDP_PORT)],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                self._log("success", f"  RDP port {RDP_PORT} is accepting connections")
                return True
            else:
                self._log("warning", f"  RDP port {RDP_PORT} is not accepting connections")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._log("warning", "  RDP connectivity check skipped (nc not available)")
            return True  # Assume OK if we can't check

    def _restart_grd_service(self):
        """Restart gnome-remote-desktop service."""
        self._log("info", "  Restarting gnome-remote-desktop service...")
        try:
            self._run_cmd(["systemctl", "--user", "restart", "gnome-remote-desktop"])
            time.sleep(2)
            self._log("success", "  gnome-remote-desktop restarted")
        except Exception as e:
            self._log("warning", f"  Failed to restart gnome-remote-desktop: {e}")

    def _check_health(self) -> dict:
        """Check health of all connection components."""
        health = {"adb": False, "tunnel": False, "rdp": False}

        # Check ADB device
        tablet = self._detect_tablet()
        if tablet:
            health["adb"] = True

        # Check tunnel
        try:
            result = subprocess.run(
                ["adb", "reverse", "--list"],
                capture_output=True, text=True, timeout=5,
            )
            if f"tcp:{RDP_PORT}" in result.stdout:
                health["tunnel"] = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Check RDP port
        try:
            result = subprocess.run(
                ["ss", "-tlnp"],
                capture_output=True, text=True, timeout=5,
            )
            if f":{RDP_PORT}" in result.stdout:
                health["rdp"] = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return health

    def _monitor(self):
        """Monitor connection health after successful setup."""
        self._log("info", "=== Monitoring connection (health check every 10s) ===")
        consecutive_failures = 0

        while not self._stop_requested:
            time.sleep(HEALTH_CHECK_INTERVAL)

            if self._stop_requested:
                break

            health = self._check_health()

            # Log state changes
            if not health["adb"]:
                self._log("warning", "Health check: tablet disconnected")
            if not health["tunnel"]:
                self._log("warning", "Health check: ADB tunnel broken")
            if not health["rdp"]:
                self._log("warning", "Health check: RDP port not listening")

            self.status_changed.emit(health)

            # If everything is fine, reset failure counter
            if health["adb"] and health["tunnel"] and health["rdp"]:
                consecutive_failures = 0
                continue

            consecutive_failures += 1

            # Try to reconnect once
            if consecutive_failures == 1:
                self._log("info", "Attempting automatic reconnection...")
                if self._reconnect():
                    self._log("success", "Reconnection successful")
                    consecutive_failures = 0
                    continue

            # If reconnection failed or we've already retried, give up
            if consecutive_failures >= 2:
                reason = self._get_failure_reason(health)
                self._log("error", f"Connection lost: {reason}")
                self.connection_lost.emit(reason)
                break

    def _reconnect(self) -> bool:
        """Attempt to reconnect after failure."""
        try:
            # Check if tablet is still connected
            if not self._detect_tablet():
                self._log("warning", "  Tablet not found, cannot reconnect")
                return False

            # Restart gnome-remote-desktop if RDP port is down
            health = self._check_health()
            if not health["rdp"]:
                self._restart_grd_service()
                time.sleep(3)

            # Re-establish ADB tunnel if broken
            if not health["tunnel"]:
                self._log("info", "  Re-establishing ADB tunnel...")
                try:
                    subprocess.run(
                        ["adb", "reverse", "--remove-all"],
                        capture_output=True, timeout=5,
                    )
                except Exception:
                    pass

                try:
                    result = subprocess.run(
                        ["adb", "reverse", f"tcp:{RDP_PORT}", f"tcp:{RDP_PORT}"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if result.returncode != 0:
                        self._log("warning", f"  Failed to create tunnel: {result.stderr}")
                        return False
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    self._log("warning", f"  Failed to create tunnel: {e}")
                    return False

            # Verify everything is working now
            time.sleep(2)
            final_health = self._check_health()
            if final_health["adb"] and final_health["tunnel"] and final_health["rdp"]:
                return True

            self._log("warning", "  Reconnection incomplete")
            return False

        except Exception as e:
            self._log("warning", f"  Reconnection error: {e}")
            return False

    def _get_failure_reason(self, health: dict) -> str:
        """Generate a human-readable failure reason."""
        reasons = []
        if not health["adb"]:
            reasons.append("tablet disconnected")
        if not health["tunnel"]:
            reasons.append("ADB tunnel broken")
        if not health["rdp"]:
            reasons.append("RDP service not running")
        return "; ".join(reasons) if reasons else "unknown error"

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
