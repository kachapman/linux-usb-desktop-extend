"""Main application window with system tray integration."""

import json
import logging
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QCursor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSystemTrayIcon,
    QTextEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from .backend import ConnectionManager
from .log_handler import LogEmitter, QtLogHandler

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
CONFIG_DIR = Path.home() / ".config" / "usb-desktop-extend"
CONFIG_FILE = CONFIG_DIR / "config.json"

# ── Terminal Theme Colors ──────────────────────────────────────────
C = {
    "bg":           "#0a0a0a",
    "panel":        "#0f0f0f",
    "border":       "#1a5a1a",
    "border_dim":   "#0d2e0d",
    "green":        "#33ff33",
    "green_dim":    "#1a8a1a",
    "green_darker": "#0d4a0d",
    "amber":        "#ffaa00",
    "red":          "#ff3333",
    "gray":         "#333333",
    "text":         "#33ff33",
    "text_dim":     "#1a8a1a",
    "text_muted":   "#0d4a0d",
    "black":        "#000000",
    "input_bg":     "#0a0a0a",
    "btn_bg":       "#1a5a1a",
    "btn_hover":    "#33ff33",
    "btn_disabled": "#0d2e0d",
}

# ── Stylesheet ─────────────────────────────────────────────────────
STYLESHEET = f"""
/* ── Global ── */
QMainWindow, QWidget {{
    background-color: {C['bg']};
    color: {C['text']};
    font-family: "Cascadia Code", "Fira Code", "JetBrains Mono", "Ubuntu Mono", monospace;
    font-size: 12px;
}}

/* ── Frames / Panels ── */
QFrame {{
    border: 1px solid {C['border']};
    border-radius: 2px;
    background-color: {C['panel']};
}}

/* ── Labels ── */
QLabel {{
    color: {C['text']};
    background: transparent;
    border: none;
}}
QLabel[class="title"] {{
    color: {C['green']};
    font-weight: bold;
    font-size: 13px;
}}
QLabel[class="info"] {{
    color: {C['green_dim']};
    font-size: 14px;
    padding: 0 2px;
}}
QLabel[class="info"]:hover {{
    color: {C['green']};
}}

/* ── Input Fields ── */
QLineEdit {{
    background-color: {C['input_bg']};
    color: {C['green']};
    border: 1px solid {C['border']};
    border-radius: 2px;
    padding: 6px 10px;
    font-family: "Cascadia Code", "Fira Code", monospace;
    font-size: 12px;
    selection-background-color: {C['green_darker']};
    selection-color: {C['green']};
}}
QLineEdit:focus {{
    border: 1px solid {C['green_dim']};
}}
QLineEdit:disabled {{
    color: {C['text_muted']};
    border-color: {C['border_dim']};
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {C['btn_bg']};
    color: {C['black']};
    border: 1px solid {C['green_dim']};
    border-radius: 2px;
    padding: 8px 16px;
    font-weight: bold;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: {C['btn_hover']};
    color: {C['black']};
    border-color: {C['green']};
}}
QPushButton:pressed {{
    background-color: {C['green_dim']};
}}
QPushButton:disabled {{
    background-color: {C['btn_disabled']};
    color: {C['text_muted']};
    border-color: {C['border_dim']};
}}

/* ── Log Area ── */
QTextEdit {{
    background-color: {C['black']};
    color: {C['green']};
    border: 1px solid {C['border']};
    border-radius: 2px;
    padding: 8px;
    font-family: "Cascadia Code", "Fira Code", "JetBrains Mono", monospace;
    font-size: 11px;
    selection-background-color: {C['green_darker']};
}}
QScrollBar:vertical {{
    background: {C['bg']};
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {C['border']};
    min-height: 20px;
    border-radius: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C['green_dim']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* ── Tooltips ── */
QToolTip {{
    background-color: {C['panel']};
    color: {C['green']};
    border: 1px solid {C['green_dim']};
    border-radius: 2px;
    padding: 8px 12px;
    font-family: "Cascadia Code", "Fira Code", monospace;
    font-size: 11px;
}}

/* ── System Tray Menu ── */
QMenu {{
    background-color: {C['panel']};
    color: {C['green']};
    border: 1px solid {C['border']};
    padding: 4px 0px;
}}
QMenu::item {{
    padding: 6px 24px;
    background: transparent;
}}
QMenu::item:selected {{
    background-color: {C['green_darker']};
    color: {C['green']};
}}
QMenu::separator {{
    height: 1px;
    background: {C['border']};
    margin: 4px 8px;
}}
"""

STATUS_COLORS = {
    "off": C["gray"],
    "connecting": C["amber"],
    "on": C["green"],
}


def load_credentials() -> tuple[str, str]:
    """Load saved credentials from config file."""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            return data.get("username", ""), data.get("password", "")
        except (json.JSONDecodeError, KeyError):
            pass
    return "", ""


def save_credentials(username: str, password: str):
    """Save credentials to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({
        "username": username,
        "password": password,
    }, indent=2))


class InfoIcon(QLabel):
    """Small clickable info icon that shows a tooltip on hover."""

    def __init__(self, text: str):
        super().__init__("\u24d8")  # ⓘ
        self.setProperty("class", "info")
        self.setCursor(QCursor(Qt.CursorShape.WhatsThisCursor))
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class StatusIndicator(QWidget):
    """A colored dot indicator for connection status."""

    def __init__(self, label: str, tooltip: str = ""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._dot = QLabel("\u25cf")
        self._dot.setFixedWidth(16)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._dot)

        self._label = QLabel(label)
        layout.addWidget(self._label)

        if tooltip:
            info = InfoIcon(tooltip)
            layout.addWidget(info)

        self.set_status("off")

    def set_status(self, status: str):
        color = STATUS_COLORS.get(status, STATUS_COLORS["off"])
        self._dot.setStyleSheet(
            f"color: {color}; font-size: 16px; background: transparent; border: none;"
        )


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, sudo_password: str):
        super().__init__()
        self.sudo_password = sudo_password
        self._manager: ConnectionManager | None = None
        self._connected = False

        self.setStyleSheet(STYLESHEET)
        QToolTip.setShowDelay(100)
        self._setup_ui()
        self._setup_tray()
        self._setup_logging()

    def _setup_ui(self):
        self.setWindowTitle("USB Desktop Extend")
        self.setMinimumSize(540, 460)
        self.setWindowIcon(self._get_icon())

        # Load saved credentials
        saved_user, saved_pass = load_credentials()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel("USB DESKTOP EXTEND")
        title.setProperty("class", "title")
        title.setStyleSheet(f"font-size: 15px; color: {C['green']}; letter-spacing: 2px;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # ── Credentials ──
        creds_frame = QFrame()
        creds_layout = QVBoxLayout(creds_frame)
        creds_layout.setSpacing(8)

        creds_header = QHBoxLayout()
        creds_title = QLabel("CREDENTIALS")
        creds_title.setProperty("class", "title")
        creds_header.addWidget(creds_title)
        creds_header.addWidget(InfoIcon(
            "RDP credentials used by the tablet to connect.\n"
            "Saved to ~/.config/usb-desktop-extend/config.json"
        ))
        creds_header.addStretch()
        creds_layout.addLayout(creds_header)

        user_row = QHBoxLayout()
        user_label = QLabel("Username:")
        user_label.setFixedWidth(80)
        user_row.addWidget(user_label)
        self._username_input = QLineEdit(saved_user)
        self._username_input.setPlaceholderText("RDP username")
        user_row.addWidget(self._username_input)
        creds_layout.addLayout(user_row)

        pass_row = QHBoxLayout()
        pass_label = QLabel("Password:")
        pass_label.setFixedWidth(80)
        pass_row.addWidget(pass_label)
        self._password_input = QLineEdit(saved_pass)
        self._password_input.setPlaceholderText("RDP password")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        pass_row.addWidget(self._password_input)
        creds_layout.addLayout(pass_row)

        layout.addWidget(creds_frame)

        # ── Status ──
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setSpacing(20)

        self._adb_indicator = StatusIndicator(
            "ADB",
            "Android Debug Bridge — detects your tablet via USB.\n"
            "Enable USB Debugging in:\n"
            "  Settings → Developer Options → USB Debugging"
        )
        self._rdp_indicator = StatusIndicator(
            "RDP",
            "GNOME Remote Desktop — streams your desktop to the tablet.\n"
            "Uses the extend mode to create a virtual second monitor."
        )
        self._tunnel_indicator = StatusIndicator(
            "Tunnel",
            "ADB reverse tunnel — routes tablet's RDP client\n"
            "to your laptop over USB (bypasses Android firewall)."
        )

        status_layout.addWidget(self._adb_indicator)
        status_layout.addWidget(self._rdp_indicator)
        status_layout.addWidget(self._tunnel_indicator)
        status_layout.addStretch()

        layout.addWidget(status_frame)

        # ── Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self._connect_btn = QPushButton("\u25b6  START CONNECTION")
        self._connect_btn.setMinimumHeight(38)
        self._connect_btn.setToolTip(
            "Runs the 4-step setup:\n"
            "  1. Detect tablet via ADB\n"
            "  2. Disable conflicting Remote Login service\n"
            "  3. Enable Desktop Sharing in extend mode\n"
            "  4. Create USB reverse tunnel"
        )
        self._connect_btn.clicked.connect(self._on_connect)
        btn_layout.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("\u25a0  STOP CONNECTION")
        self._disconnect_btn.setMinimumHeight(38)
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.setToolTip(
            "Tears down the connection:\n"
            "  - Removes ADB tunnel\n"
            "  - Disables RDP sharing\n"
            "  - Stops gnome-remote-desktop service"
        )
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        btn_layout.addWidget(self._disconnect_btn)

        layout.addLayout(btn_layout)

        # ── Log ──
        log_header = QHBoxLayout()
        log_label = QLabel("LOG")
        log_label.setProperty("class", "title")
        log_header.addWidget(log_label)
        log_header.addWidget(InfoIcon("Real-time log of all connection steps and errors."))
        log_header.addStretch()
        layout.addLayout(log_header)

        self._log_area = QTextEdit()
        self._log_area.setReadOnly(True)
        layout.addWidget(self._log_area, stretch=1)

        # ── Footer ──
        footer = QLabel("Ready. Plug in tablet and click Start.")
        footer.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; padding: 4px 0;")
        layout.addWidget(footer)
        self._footer = footer

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self._get_icon(), self)
        self._tray.setToolTip("USB Desktop Extend")

        menu = QMenu()
        menu.addAction("Show Window", self._show_window)
        menu.addSeparator()
        menu.addAction("Connect", self._on_connect)
        menu.addAction("Disconnect", self._on_disconnect)
        menu.addSeparator()
        menu.addAction("Quit", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _setup_logging(self):
        emitter = LogEmitter()
        handler = QtLogHandler(emitter)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(handler)
        emitter.message.connect(self._on_log_message)

    def _get_icon(self) -> QIcon:
        icon_path = ASSETS_DIR / "icon.png"
        if icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon()

    @pyqtSlot(str, str, str)
    def _on_log_message(self, timestamp: str, level: str, message: str):
        color_map = {
            "info": C["text"],
            "warning": C["amber"],
            "error": C["red"],
            "success": C["green"],
            "debug": C["text_muted"],
        }
        color = color_map.get(level, C["text"])
        html = (
            f'<span style="color: {C["text_dim"]};">[{timestamp}]</span> '
            f'<span style="color: {color};">{message}</span>'
        )
        self._log_area.append(html)
        scrollbar = self._log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot(dict)
    def _on_status_changed(self, status: dict):
        adb_status = "on" if status.get("adb") else "off"
        rdp_status = "on" if status.get("rdp") else "off"
        tunnel_status = "on" if status.get("tunnel") else "off"

        self._adb_indicator.set_status(adb_status)
        self._rdp_indicator.set_status(rdp_status)
        self._tunnel_indicator.set_status(tunnel_status)

        if tunnel_status == "on":
            self._tray.setToolTip("USB Desktop Extend — Connected")
            self._footer.setText("Tunnel Connected. Connect with your RDP app on the tablet.")
            self._footer.setStyleSheet(f"color: {C['green']}; font-size: 11px; padding: 4px 0;")
        else:
            self._tray.setToolTip("USB Desktop Extend")

    @pyqtSlot(bool)
    def _on_finished(self, success: bool):
        self._connected = success
        self._set_buttons_enabled(connected=success)

        if success:
            self._tray.showMessage(
                "USB Desktop Extend",
                "Connection established successfully!",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        else:
            self._tray.showMessage(
                "USB Desktop Extend",
                "Connection failed. Check the log for details.",
                QSystemTrayIcon.MessageIcon.Warning,
                3000,
            )
            self._footer.setText("Connection failed. See log above.")
            self._footer.setStyleSheet(f"color: {C['red']}; font-size: 11px; padding: 4px 0;")

    @pyqtSlot(str)
    def _on_connection_lost(self, reason: str):
        self._connected = False
        self._set_buttons_enabled(connected=False)
        self._footer.setText(f"Connection lost: {reason}")
        self._footer.setStyleSheet(f"color: {C['red']}; font-size: 11px; padding: 4px 0;")
        self._tray.showMessage(
            "USB Desktop Extend",
            f"Connection lost: {reason}",
            QSystemTrayIcon.MessageIcon.Warning,
            5000,
        )

    def _set_buttons_enabled(self, connected: bool):
        self._connect_btn.setEnabled(not connected)
        self._disconnect_btn.setEnabled(connected)
        self._username_input.setEnabled(not connected)
        self._password_input.setEnabled(not connected)

    def _on_connect(self):
        if self._manager and self._manager.isRunning():
            return

        username = self._username_input.text().strip()
        password = self._password_input.text().strip()

        if not username or not password:
            self._log_area.append(
                f'<span style="color: {C["amber"]};">Please enter both username and password.</span>'
            )
            return

        # Save credentials for next launch
        save_credentials(username, password)

        self._set_buttons_enabled(connected=False)
        self._adb_indicator.set_status("connecting")
        self._rdp_indicator.set_status("connecting")
        self._tunnel_indicator.set_status("connecting")

        self._footer.setText("Connecting...")
        self._footer.setStyleSheet(f"color: {C['amber']}; font-size: 11px; padding: 4px 0;")

        self._manager = ConnectionManager(username, password, self.sudo_password)
        self._manager.log_message.connect(self._on_backend_log)
        self._manager.status_changed.connect(self._on_status_changed)
        self._manager.finished.connect(self._on_finished)
        self._manager.connection_lost.connect(self._on_connection_lost)
        self._manager.start()

    def _on_disconnect(self):
        if self._manager and self._manager.isRunning():
            self._manager.request_stop()

        self._disconnect_thread = ConnectionManager(
            self._username_input.text(),
            self._password_input.text(),
            self.sudo_password,
        )
        self._disconnect_thread.log_message.connect(self._on_backend_log)
        self._disconnect_thread.status_changed.connect(self._on_status_changed)

        self._disconnect_thread.run = self._disconnect_thread.disconnect
        self._disconnect_thread.finished.connect(self._on_disconnect_finished)
        self._disconnect_thread.start()

        self._connected = False
        self._set_buttons_enabled(connected=False)

    def _on_disconnect_finished(self, success: bool):
        self._footer.setText("Disconnected.")
        self._footer.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; padding: 4px 0;")
        self._tray.showMessage(
            "USB Desktop Extend",
            "Disconnected.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    @pyqtSlot(str, str)
    def _on_backend_log(self, level: str, message: str):
        color_map = {
            "info": C["text"],
            "warning": C["amber"],
            "error": C["red"],
            "success": C["green"],
        }
        color = color_map.get(level, C["text"])
        timestamp = datetime.now().strftime("%H:%M:%S")
        html = (
            f'<span style="color: {C["text_dim"]};">[{timestamp}]</span> '
            f'<span style="color: {color};">{message}</span>'
        )
        self._log_area.append(html)
        scrollbar = self._log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _show_window(self):
        self.showNormal()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _quit(self):
        if self._connected:
            self._on_disconnect()
        QApplication.quit()

    def closeEvent(self, event):
        if self._connected:
            msg = QMessageBox(self)
            msg.setWindowTitle("USB Desktop Extend")
            msg.setText("Connection is active.")
            msg.setInformativeText("What would you like to do?")
            msg.setIcon(QMessageBox.Icon.Question)
            quit_btn = msg.addButton("Disconnect && Quit", QMessageBox.ButtonRole.AcceptRole)
            minimize_btn = msg.addButton("Minimize to Tray", QMessageBox.ButtonRole.RejectRole)
            msg.addButton(QMessageBox.StandardButton.Cancel)
            msg.exec()

            clicked = msg.clickedButton()
            if clicked == quit_btn:
                self._on_disconnect()
                event.accept()
            elif clicked == minimize_btn:
                event.ignore()
                self.hide()
                self._tray.showMessage(
                    "USB Desktop Extend",
                    "Minimized to tray. Right-click to quit.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
            else:
                event.ignore()
        else:
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "USB Desktop Extend",
                "Minimized to tray. Right-click to quit.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
