from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QListWidgetItem,
    QMessageBox
)
import core.db as db
from core.yt_service import TrackInfo

class FavoritesDialog(QDialog):
    play_all_requested = pyqtSignal(list)
    play_selected_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Favorites")
        self.resize(400, 300)
        
        self._tracks = db.get_all_favorites()

        self._build_ui()
        self._populate_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget(self)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        
        self.btn_up = QPushButton("Move Up", self)
        self.btn_down = QPushButton("Move Down", self)
        self.btn_remove = QPushButton("Remove", self)
        
        self.btn_play_selected = QPushButton("Play Selected", self)
        self.btn_play_all = QPushButton("Play All", self)
        
        self.btn_up.clicked.connect(self._on_move_up)
        self.btn_down.clicked.connect(self._on_move_down)
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_play_selected.clicked.connect(self._on_play_selected)
        self.btn_play_all.clicked.connect(self._on_play_all)
        
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_play_selected)
        btn_layout.addWidget(self.btn_play_all)
        
        layout.addLayout(btn_layout)

    def _populate_list(self):
        self.list_widget.clear()
        for track in self._tracks:
            item = QListWidgetItem(f"{track.title} - {track.uploader}")
            item.setData(Qt.UserRole, track)
            self.list_widget.addItem(item)

    def _on_move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            self.list_widget.setCurrentRow(row - 1)
            self._save_order()

    def _on_move_down(self):
        row = self.list_widget.currentRow()
        if row >= 0 and row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            self.list_widget.setCurrentRow(row + 1)
            self._save_order()

    def _save_order(self):
        video_ids = []
        new_tracks = []
        for i in range(self.list_widget.count()):
            track = self.list_widget.item(i).data(Qt.UserRole)
            video_ids.append(track.video_id)
            new_tracks.append(track)
        self._tracks = new_tracks
        db.update_order(video_ids)

    def _on_remove(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            track = self.list_widget.item(row).data(Qt.UserRole)
            db.remove_favorite(track.video_id)
            self.list_widget.takeItem(row)
            self._tracks.remove(track)

    def _on_play_selected(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            track = self.list_widget.item(row).data(Qt.UserRole)
            self.play_selected_requested.emit(track)
            self.accept()

    def _on_item_double_clicked(self, item):
        track = item.data(Qt.UserRole)
        self.play_selected_requested.emit(track)
        self.accept()

    def _on_play_all(self):
        if not self._tracks:
            QMessageBox.information(self, "Favorites", "No favorites to play.")
            return
        self.play_all_requested.emit(self._tracks)
        self.accept()
