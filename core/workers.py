"""
workers.py
Generic QThread worker so blocking yt-dlp calls never freeze the UI.
"""

from __future__ import annotations

from typing import Any, Callable

from PyQt5.QtCore import QThread, pyqtSignal


class CallableWorker(QThread):
    """Runs `func(*args, **kwargs)` on a background thread.

    Emits:
        succeeded(result)
        failed(error_message)
    """

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, func: Callable, *args: Any, **kwargs: Any):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._func(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - surface any extraction error to UI
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)
