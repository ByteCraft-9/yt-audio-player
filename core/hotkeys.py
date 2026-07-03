"""
hotkeys.py
Global (system-wide) hotkeys using the `keyboard` library, marshalled onto
Qt signals so they can safely drive the UI/audio engine from the main thread.

Note (Linux): the `keyboard` library reads raw input devices and typically
needs the process to run as root (or the user to be in the `input` group)
for GLOBAL hotkeys to work outside the app's own window.
Note (macOS): requires granting Accessibility permissions to the terminal
or the packaged app.
Note (Windows): works out of the box for a normal user.
"""

from __future__ import annotations

from PyQt5.QtCore import QObject, pyqtSignal

try:
    import keyboard  # type: ignore
    HOTKEYS_AVAILABLE = True
except Exception:  # pragma: no cover - missing lib / no permission on import
    keyboard = None  # type: ignore
    HOTKEYS_AVAILABLE = False


DEFAULT_BINDINGS = {
    "play_pause": "ctrl+alt+p",
    "seek_forward": "ctrl+alt+right",
    "seek_backward": "ctrl+alt+left",
    "next_track": "ctrl+alt+n",
    "previous_track": "ctrl+alt+b",
}


class HotkeyManager(QObject):
    play_pause_triggered = pyqtSignal()
    seek_forward_triggered = pyqtSignal()
    seek_backward_triggered = pyqtSignal()
    next_triggered = pyqtSignal()
    previous_triggered = pyqtSignal()
    registration_failed = pyqtSignal(str)

    def __init__(self, parent: QObject = None): # type: ignore
        super().__init__(parent)
        self._registered = False

    def start(self) -> None:
        if not HOTKEYS_AVAILABLE:
            self.registration_failed.emit(
                "The 'keyboard' package is not available/permitted; "
                "global hotkeys are disabled."
            )
            return
        try:
            keyboard.add_hotkey( # type: ignore
                DEFAULT_BINDINGS["play_pause"],
                lambda: self.play_pause_triggered.emit(),
            )
            keyboard.add_hotkey( # type: ignore
                DEFAULT_BINDINGS["seek_forward"],
                lambda: self.seek_forward_triggered.emit(),
            )
            keyboard.add_hotkey( # type: ignore
                DEFAULT_BINDINGS["seek_backward"],
                lambda: self.seek_backward_triggered.emit(),
            )
            keyboard.add_hotkey( # type: ignore
                DEFAULT_BINDINGS["next_track"],
                lambda: self.next_triggered.emit(),
            )
            keyboard.add_hotkey( # type: ignore
                DEFAULT_BINDINGS["previous_track"],
                lambda: self.previous_triggered.emit(),
            )
            self._registered = True
        except Exception as exc:  # noqa: BLE001
            self.registration_failed.emit(str(exc))

    def stop(self) -> None:
        if HOTKEYS_AVAILABLE and self._registered:
            try:
                keyboard.unhook_all_hotkeys() # type: ignore
            except Exception:  # noqa: BLE001
                pass
