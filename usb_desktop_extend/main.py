"""USB Desktop Extend - Entry point."""

import atexit
import signal
import subprocess
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QInputDialog,
    QLineEdit,
    QMessageBox,
)

from .app import MainWindow


def cleanup_tunnel():
    """Remove all ADB reverse tunnels on exit."""
    try:
        subprocess.run(
            ["adb", "reverse", "--remove-all"],
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def verify_sudo(password: str) -> bool:
    """Verify sudo password works."""
    try:
        result = subprocess.run(
            ["sudo", "-S", "true"],
            input=password.encode(),
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def main():
    atexit.register(cleanup_tunnel)

    def handle_sigterm(signum, frame):
        cleanup_tunnel()
        sys.exit(0)

    def handle_sigint(signum, frame):
        cleanup_tunnel()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigint)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running when minimized to tray

    # Prompt for sudo password
    sudo_password, ok = QInputDialog.getText(
        None,
        "USB Desktop Extend",
        "Enter your sudo password\n(needed to disable system Remote Login):",
        QLineEdit.EchoMode.Password,
    )

    if not ok or not sudo_password:
        sys.exit(0)

    if not verify_sudo(sudo_password):
        QMessageBox.critical(
            None,
            "USB Desktop Extend",
            "Invalid sudo password. Please try again.",
        )
        sys.exit(1)

    window = MainWindow(sudo_password)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
