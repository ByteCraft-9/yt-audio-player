"""
search_dialog.py
Small popup listing search results as "Title — Channel" only.
No thumbnails, no extra chrome.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from core.yt_service import TrackInfo


class SearchResultsDialog(QDialog):
    def __init__(self, results: List[TrackInfo], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search results")
        self.setFixedSize(340, 260)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint) # type: ignore

        self._selected: Optional[TrackInfo] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.list_widget = QListWidget(self)
        self.list_widget.setAlternatingRowColors(True)
        for track in results:
            label = f"{track.title}\n{track.uploader}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, track) # type: ignore
            self.list_widget.addItem(item)
        self.list_widget.itemDoubleClicked.connect(self._on_item_chosen)

        layout.addWidget(self.list_widget)

    def _on_item_chosen(self, item: QListWidgetItem) -> None:
        self._selected = item.data(Qt.UserRole) # type: ignore
        self.accept()

    def selected_track(self) -> Optional[TrackInfo]:
        return self._selected
