"""Logging handler that bridges Python logging to Qt signals."""

import logging
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal


class LogEmitter(QObject):
    """Emits log messages as Qt signals for GUI consumption."""

    message = pyqtSignal(str, str, str)  # (timestamp, level, message)


class QtLogHandler(logging.Handler):
    """Custom logging handler that emits messages via LogEmitter."""

    def __init__(self, emitter: LogEmitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        timestamp = datetime.now().strftime("%H:%M:%S")
        level = record.levelname.lower()
        self.emitter.message.emit(timestamp, level, msg)
