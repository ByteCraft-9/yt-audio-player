"""
main_window.py
Tiny, fixed-size main window. Audio only -- no video surface is ever
created, so the footprint stays minimal.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from core.audio_engine import AudioEngine
from core.hotkeys import HotkeyManager
from core.workers import CallableWorker
from core.yt_service import TrackInfo, extract_playlist, looks_like_url, resolve_stream, search
from ui.search_dialog import SearchResultsDialog
import core.db as db
from ui.favorites_dialog import FavoritesDialog

SPEED_OPTIONS = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]


def format_ms(ms: int) -> str:
    if ms < 0:
        ms = 0
    total_seconds = ms // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YT Audio")
        self.setFixedSize(340, 232)

        self.engine = AudioEngine(self)
        self.hotkeys = HotkeyManager(self)
        self._active_worker: CallableWorker | None = None
        self._seeking = False

        self._build_ui()
        self._wire_engine_signals()
        self._wire_hotkeys()
        self._build_tray_icon()

    # ---------------------------------------------------------------- UI --

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # -- input row: URL or search query --
        input_row = QHBoxLayout()
        input_row.setSpacing(4)
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Paste YouTube URL or type to search…")
        self.input_field.returnPressed.connect(self._on_go_clicked)
        self.go_button = QPushButton("Go", self)
        self.go_button.setFixedWidth(40)
        self.go_button.clicked.connect(self._on_go_clicked)
        
        self.fav_button = QPushButton("🤍", self)
        self.fav_button.setFixedWidth(30)
        self.fav_button.setToolTip("Toggle Favorite")
        self.fav_button.clicked.connect(self._on_fav_toggled)
        self.fav_button.setEnabled(False)

        self.fav_list_button = QPushButton("⭐", self)
        self.fav_list_button.setFixedWidth(30)
        self.fav_list_button.setToolTip("Favorites List")
        self.fav_list_button.clicked.connect(self._on_show_favorites)

        input_row.addWidget(self.input_field)
        input_row.addWidget(self.go_button)
        input_row.addWidget(self.fav_button)
        input_row.addWidget(self.fav_list_button)
        root.addLayout(input_row)

        # -- now playing title --
        self.title_label = QLabel("Nothing loaded", self)
        self.title_label.setStyleSheet("font-weight: 600;")
        self.title_label.setWordWrap(False)
        self.title_label.setTextInteractionFlags(Qt.TextSelectableByMouse) # type: ignore
        self._set_elided_title("Nothing loaded")
        root.addWidget(self.title_label)

        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        root.addWidget(self.status_label)

        # -- seek slider + time labels --
        seek_row = QHBoxLayout()
        seek_row.setSpacing(4)
        self.elapsed_label = QLabel("00:00", self)
        self.elapsed_label.setFixedWidth(38)
        self.seek_slider = QSlider(Qt.Horizontal, self) # type: ignore
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        self.duration_label = QLabel("00:00", self)
        self.duration_label.setFixedWidth(38)
        self.duration_label.setAlignment(Qt.AlignRight) # type: ignore
        seek_row.addWidget(self.elapsed_label)
        seek_row.addWidget(self.seek_slider)
        seek_row.addWidget(self.duration_label)
        root.addLayout(seek_row)

        # -- transport controls --
        transport_row = QHBoxLayout()
        transport_row.setSpacing(4)
        self.prev_button = QPushButton("⏮", self)
        self.back_button = QPushButton("⏪3", self)
        self.play_button = QPushButton("▶", self)
        self.fwd_button = QPushButton("3⏩", self)
        self.next_button = QPushButton("⏭", self)
        for btn in (
            self.prev_button,
            self.back_button,
            self.play_button,
            self.fwd_button,
            self.next_button,
        ):
            btn.setFixedHeight(30)
            transport_row.addWidget(btn)
        self.prev_button.clicked.connect(self._on_prev_clicked)
        self.back_button.clicked.connect(self.engine.seek_backward)
        self.play_button.clicked.connect(self.engine.toggle_play_pause)
        self.fwd_button.clicked.connect(self.engine.seek_forward)
        self.next_button.clicked.connect(self._on_next_clicked)
        root.addLayout(transport_row)

        # -- volume + speed --
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)
        vol_icon = QLabel("🔊", self)
        self.volume_slider = QSlider(Qt.Horizontal, self) # type: ignore
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(110)
        self.volume_slider.valueChanged.connect(self.engine.set_volume)
        self.engine.set_volume(80)

        self.speed_combo = QComboBox(self)
        for s in SPEED_OPTIONS:
            self.speed_combo.addItem(f"{s}x", s)
        self.speed_combo.setCurrentIndex(SPEED_OPTIONS.index(1.0))
        self.speed_combo.currentIndexChanged.connect(
            lambda _i: self.engine.set_playback_rate(self.speed_combo.currentData())
        )

        bottom_row.addWidget(vol_icon)
        bottom_row.addWidget(self.volume_slider)
        bottom_row.addStretch(1)
        bottom_row.addWidget(self.speed_combo)
        root.addLayout(bottom_row)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #444;")
        root.addWidget(sep)

    def _set_elided_title(self, text: str) -> None:
        metrics = self.title_label.fontMetrics()
        elided = metrics.elidedText(text, Qt.ElideRight, self.width() - 16) # type: ignore
        self.title_label.setText(elided)
        self.title_label.setToolTip(text)

    # ------------------------------------------------------- engine wiring --

    def _wire_engine_signals(self) -> None:
        self.engine.track_changed.connect(self._on_track_changed)
        self.engine.position_changed.connect(self._on_position_changed)
        self.engine.duration_changed.connect(self._on_duration_changed)
        self.engine.playing_state_changed.connect(self._on_playing_state_changed)
        self.engine.error_occurred.connect(self._on_engine_error)
        self.engine.playlist_index_changed.connect(self._on_playlist_index_changed)
        self.engine.track_needs_resolution.connect(self._resolve_and_play)

    def _wire_hotkeys(self) -> None:
        self.hotkeys.play_pause_triggered.connect(self.engine.toggle_play_pause)
        self.hotkeys.seek_forward_triggered.connect(self.engine.seek_forward)
        self.hotkeys.seek_backward_triggered.connect(self.engine.seek_backward)
        self.hotkeys.next_triggered.connect(self._on_next_clicked)
        self.hotkeys.previous_triggered.connect(self._on_prev_clicked)
        self.hotkeys.registration_failed.connect(
            lambda msg: self.status_label.setText(msg)
        )
        self.hotkeys.start()

    # ------------------------------------------------------------ tray icon --

    def _build_tray_icon(self) -> None:
        icon = self.style().standardIcon(QStyle.SP_MediaVolume) # type: ignore
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("YT Audio")

        menu = QMenu()
        show_action = menu.addAction("Show / Hide")
        show_action.triggered.connect(self._toggle_visibility) # type: ignore
        play_action = menu.addAction("Play / Pause")
        play_action.triggered.connect(self.engine.toggle_play_pause) # type: ignore
        next_action = menu.addAction("Next")
        next_action.triggered.connect(self._on_next_clicked) # type: ignore
        prev_action = menu.addAction("Previous")
        prev_action.triggered.connect(self._on_prev_clicked) # type: ignore
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_app) # type: ignore

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger: # type: ignore
            self._toggle_visibility()

    def _toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _quit_app(self) -> None:
        self.hotkeys.stop()
        self.tray_icon.hide()
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().quit() # type: ignore

    def closeEvent(self, event) -> None:  # type: ignore # noqa: N802 (Qt override)
        # Quit the application when the window is closed.
        from PyQt5.QtWidgets import QApplication
        self.hotkeys.stop()
        self.tray_icon.hide()
        QApplication.instance().quit() # type: ignore

    # --------------------------------------------------------- input / load --

    def _on_go_clicked(self) -> None:
        text = self.input_field.text().strip()
        if not text:
            return
        if looks_like_url(text):
            self._load_url(text)
        else:
            self._run_search(text)

    def _load_url(self, url: str) -> None:
        self.status_label.setText("Loading…")
        self._run_worker(extract_playlist, self._on_playlist_extracted, url)

    def _on_playlist_extracted(self, tracks: list[TrackInfo]) -> None:
        if not tracks:
            self.status_label.setText("Nothing found at that URL.")
            return
        self.status_label.setText("")
        self.engine.load_queue(tracks, start_index=0)
        first = tracks[0]
        if not first.is_resolved:
            self._resolve_and_play(first)

    def _run_search(self, query: str) -> None:
        self.status_label.setText("Searching…")
        self._run_worker(search, self._on_search_done, query)

    def _on_search_done(self, results: list[TrackInfo]) -> None:
        self.status_label.setText("")
        if not results:
            self.status_label.setText("No results.")
            return
        dialog = SearchResultsDialog(results, self)
        if dialog.exec_() == dialog.Accepted:
            chosen = dialog.selected_track()
            if chosen is not None:
                self.engine.load_queue([chosen], start_index=0)
                self._resolve_and_play(chosen)

    def _resolve_and_play(self, track: TrackInfo) -> None:
        self.status_label.setText("Resolving audio…")
        self._run_worker(resolve_stream, self._on_stream_resolved, track.webpage_url)

    def _on_stream_resolved(self, resolved: TrackInfo) -> None:
        self.status_label.setText("")
        self.engine.update_resolved_track(resolved)

    # -------------------------------------------------------- favorites --

    def _on_fav_toggled(self) -> None:
        track = self.engine.current_track()
        if not track or not track.video_id:
            return
        
        if db.is_favorite(track.video_id):
            db.remove_favorite(track.video_id)
            self.fav_button.setText("🤍")
        else:
            db.add_favorite(track)
            self.fav_button.setText("❤️")

    def _on_show_favorites(self) -> None:
        dialog = FavoritesDialog(self)
        dialog.play_selected_requested.connect(self._play_favorite_single)
        dialog.play_all_requested.connect(self._play_favorite_all)
        dialog.exec_()

    def _play_favorite_single(self, track: TrackInfo) -> None:
        self.engine.load_queue([track], start_index=0)
        self._resolve_and_play(track)

    def _play_favorite_all(self, tracks: list[TrackInfo]) -> None:
        if not tracks:
            return
        self.engine.load_queue(tracks, start_index=0)
        first = tracks[0]
        if not first.is_resolved:
            self._resolve_and_play(first)
        else:
            self.engine._set_media(first)

    # -------------------------------------------------------- worker helper --

    def _run_worker(self, func, on_success, *args) -> None:
        worker = CallableWorker(func, *args)
        worker.succeeded.connect(on_success)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(worker.deleteLater)
        self._active_worker = worker  # keep a reference alive
        worker.start()

    def _on_worker_failed(self, message: str) -> None:
        self.status_label.setText("")
        QMessageBox.warning(self, "YT Audio", f"Something went wrong:\n{message}")

    # ------------------------------------------------------- transport UI --

    def _on_prev_clicked(self) -> None:
        unresolved = self.engine.previous_track_needs_resolution()
        if unresolved is not None:
            self._resolve_and_play(unresolved)

    def _on_next_clicked(self) -> None:
        unresolved = self.engine.next_track_needs_resolution()
        if unresolved is not None:
            self._resolve_and_play(unresolved)

    def _on_seek_pressed(self) -> None:
        self._seeking = True

    def _on_seek_released(self) -> None:
        self.engine.set_position(self.seek_slider.value())
        self._seeking = False

    # ------------------------------------------------------ engine callbacks --

    def _on_track_changed(self, track: TrackInfo) -> None:
        self._set_elided_title(track.title)
        self.status_label.setText(track.uploader)
        
        self.fav_button.setEnabled(True)
        if db.is_favorite(track.video_id):
            self.fav_button.setText("❤️")
        else:
            self.fav_button.setText("🤍")

    def _on_position_changed(self, position_ms: int) -> None:
        if not self._seeking:
            self.seek_slider.setValue(position_ms)
        self.elapsed_label.setText(format_ms(position_ms))

    def _on_duration_changed(self, duration_ms: int) -> None:
        self.seek_slider.setRange(0, max(duration_ms, 0))
        self.duration_label.setText(format_ms(duration_ms))

    def _on_playing_state_changed(self, is_playing: bool) -> None:
        self.play_button.setText("⏸" if is_playing else "▶")

    def _on_playlist_index_changed(self, current: int, total: int) -> None:
        if total > 1:
            self.status_label.setText(f"Track {current + 1} of {total}")

    def _on_engine_error(self, message: str) -> None:
        if message:
            self.status_label.setText(f"Playback error: {message}")
