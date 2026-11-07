"""Left-hand panels: automatic player list and import history."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget)


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


class PlayersPanel(QWidget):
    """Automatically detected players; tick one or more to investigate."""

    selectionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 10, 8, 8)
        self.summary = QLabel("No players detected yet")
        self.summary.setObjectName("Muted")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search players\u2026")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_search)
        self.list = QListWidget()
        self.list.itemChanged.connect(self._item_changed)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        row = QHBoxLayout()
        all_btn = QPushButton("Select shown")
        none_btn = QPushButton("Clear")
        all_btn.clicked.connect(self.select_shown)
        none_btn.clicked.connect(self.clear_selection)
        row.addWidget(all_btn)
        row.addWidget(none_btn)
        hint = QLabel("Tick several players to investigate them together.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(self.summary)
        lay.addWidget(self.search)
        lay.addWidget(self.list, 1)
        lay.addLayout(row)
        lay.addWidget(hint)
        self._loading = False

    # ------------------------------------------------------------ content
    def set_players(self, counts: dict) -> None:
        keep = self.selected()
        self._loading = True
        self.list.clear()
        for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
            item = QListWidgetItem(f"{name}    \u00b7 {count:,}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if name in keep
                               else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        self._loading = False
        self.summary.setText(f"{len(counts):,} players detected automatically"
                             if counts else "No players detected yet")
        self._apply_search()

    def selected(self) -> frozenset:
        names = set()
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                names.add(it.data(Qt.ItemDataRole.UserRole))
        return frozenset(names)

    # ----------------------------------------------------------- actions
    def select_player(self, name: str) -> None:
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == name:
                it.setHidden(False)
                it.setCheckState(Qt.CheckState.Checked)
                self.list.scrollToItem(it)
                return

    def select_shown(self) -> None:
        self._loading = True
        for i in range(self.list.count()):
            it = self.list.item(i)
            if not it.isHidden():
                it.setCheckState(Qt.CheckState.Checked)
        self._loading = False
        self.selectionChanged.emit()

    def clear_selection(self) -> None:
        self._loading = True
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self._loading = False
        self.selectionChanged.emit()

    def _apply_search(self) -> None:
        needle = self.search.text().strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            name = it.data(Qt.ItemDataRole.UserRole).lower()
            it.setHidden(bool(needle) and needle not in name)

    def _item_changed(self, _item) -> None:
        if not self._loading:
            self.selectionChanged.emit()


class HistoryPanel(QWidget):
    """Saved imports. Tick the logs you want loaded together."""

    checkedChanged = Signal(list)
    importRequested = Signal()
    deleteRequested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 10, 8, 8)
        self.summary = QLabel("No saved logs")
        self.summary.setObjectName("Muted")
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemChanged.connect(self._item_changed)
        row = QHBoxLayout()
        imp = QPushButton("Import\u2026")
        imp.setObjectName("Primary")
        imp.clicked.connect(self.importRequested)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_clicked)
        row.addWidget(imp)
        row.addWidget(self.delete_btn)
        hint = QLabel("Imported logs are saved. Tick the ones to investigate "
                      "together; select and Delete to remove them.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(self.summary)
        lay.addWidget(self.list, 1)
        lay.addLayout(row)
        lay.addWidget(hint)
        self._loading = False

    def set_imports(self, imports: list, checked_ids: set) -> None:
        self._loading = True
        self.list.clear()
        for info in imports:
            span = info.log_date or "unknown date"
            item = QListWidgetItem(
                f"{info.name}\n{span}  \u00b7  {info.entry_count:,} entries  \u00b7  "
                f"{human_size(info.size)}")
            item.setData(Qt.ItemDataRole.UserRole, info.id)
            item.setToolTip(f"{info.path}\nImported {info.imported_at}\n"
                            f"{info.first_ts}  \u2192  {info.last_ts}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if info.id in checked_ids
                               else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        self._loading = False
        self.summary.setText(f"{len(imports)} saved log(s)" if imports
                             else "No saved logs")

    def checked_ids(self) -> list:
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def _item_changed(self, _item) -> None:
        if not self._loading:
            self.checkedChanged.emit(self.checked_ids())

    def _delete_clicked(self) -> None:
        ids = [it.data(Qt.ItemDataRole.UserRole) for it in self.list.selectedItems()]
        if ids:
            self.deleteRequested.emit(ids)
