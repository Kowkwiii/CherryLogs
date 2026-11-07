"""CherryLogs main window."""
from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox,
                               QProgressBar, QPushButton, QSplitter,
                               QStackedWidget, QTabWidget, QToolButton,
                               QVBoxLayout, QWidget)

from .. import __app_name__, __version__, exporter, winutil
from ..branding import blossom_icon, blossom_pixmap
from ..filters import FilterResult, apply_filters
from ..stats import compute_stats
from ..storage import Storage
from ..theme import build_qss, palette_for
from ..workers import ImportWorker, LoadWorker
from .filter_bar import FilterBar
from .side_panels import HistoryPanel, PlayersPanel
from .stats_view import StatsView
from .timeline import TimelinePanel
from .widgets import DropOverlay, EmptyState, EntryTable

ACCEPTED = (".log", ".gz", ".txt")

TAB_SERVER, TAB_COMMANDS, TAB_CHAT, TAB_ALL, TAB_TIMELINE, TAB_STATS = range(6)


def collect_paths(urls_or_paths: list) -> list:
    """Expand folders and keep only log-like files."""
    out = []
    for path in urls_or_paths:
        if os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for name in sorted(files):
                    if name.lower().endswith(ACCEPTED):
                        out.append(os.path.join(root, name))
        elif path.lower().endswith(ACCEPTED) and os.path.isfile(path):
            out.append(path)
    return out


class MainWindow(QMainWindow):
    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
        self.storage = Storage(db_path)
        self.settings = QSettings("CherryLogs", "CherryLogs")
        self.dark = self.settings.value("dark", False, type=bool)

        self.entries: list = []
        self.markers: list = []
        self.result: FilterResult | None = None
        self.stats: dict = {}
        self.sources: dict = {}
        self.active_ids: set = set()
        self._stats_dirty = True
        self._stats_shown = False
        self._timeline_dirty = True
        self._overview = None

        self._importer: ImportWorker | None = None
        self._loader: LoadWorker | None = None
        self._reload_pending = False
        self._queued_paths: list = []
        self._new_ids: list = []
        self._import_errors: list = []
        self._import_summary = {"files": 0, "entries": 0, "dups": 0}

        self.setWindowTitle(f"{__app_name__} - Minecraft log investigator")
        self.setWindowIcon(blossom_icon())
        self.resize(1440, 880)
        self.setMinimumSize(1020, 640)
        self.setAcceptDrops(True)

        self._build_ui()
        self._build_shortcuts()
        for edit in self.findChildren(QLineEdit):
            edit.setAcceptDrops(False)  # so file drops reach the window

        self._refilter_timer = QTimer(self, singleShot=True, interval=250)
        self._refilter_timer.timeout.connect(self.refilter)
        self._reload_timer = QTimer(self, singleShot=True, interval=450)
        self._reload_timer.timeout.connect(self.load_active)

        self.apply_theme()
        self._restore_state()
        self.refresh_history()
        self.load_active()

    # ================================================================== UI
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("Central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(12, 12, 12, 8)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        body_lay.addWidget(self.splitter)
        root.addWidget(body, 1)

        # ---- left: players + history
        self.players = PlayersPanel()
        self.history = HistoryPanel()
        self.left_tabs = QTabWidget()
        self.left_tabs.addTab(self.players, "Players")
        self.left_tabs.addTab(self.history, "History")
        self.left_tabs.setMinimumWidth(250)
        self.left_tabs.setMaximumWidth(420)
        self.splitter.addWidget(self.left_tabs)

        # ---- right: empty state or investigation workspace
        self.stack = QStackedWidget()
        self.empty = EmptyState()
        self.stack.addWidget(self.empty)

        work = QWidget()
        work_lay = QVBoxLayout(work)
        work_lay.setContentsMargins(0, 0, 0, 0)
        work_lay.setSpacing(10)
        self.filter_bar = FilterBar()
        work_lay.addWidget(self.filter_bar)

        self.tabs = QTabWidget()
        self.table_server = EntryTable("server")
        self.table_command = EntryTable("command")
        self.table_chat = EntryTable("chat")
        self.table_all = EntryTable("all")
        self.timeline = TimelinePanel()
        self.stats_view = StatsView()
        self.tabs.addTab(self.table_server, "Server Logs")
        self.tabs.addTab(self.table_command, "Commands")
        self.tabs.addTab(self.table_chat, "Chat")
        self.tabs.addTab(self.table_all, "All Activity")
        self.tabs.addTab(self.timeline, "Timeline")
        self.tabs.addTab(self.stats_view, "Statistics")
        work_lay.addWidget(self.tabs, 1)
        self.stack.addWidget(work)
        self.splitter.addWidget(self.stack)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([300, 1100])

        # ---- overlay + status bar
        self.overlay = DropOverlay(central)
        self.status_label = QLabel("Drop log files anywhere to begin")
        self.statusBar().addWidget(self.status_label, 1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(260)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)

        # ---- signals
        self.empty.browse.connect(self.choose_files)
        self.players.selectionChanged.connect(self.schedule_refilter)
        self.filter_bar.changed.connect(self.schedule_refilter)
        self.history.importRequested.connect(self.choose_files)
        self.history.checkedChanged.connect(self._history_checked)
        self.history.deleteRequested.connect(self._delete_imports)
        self.tabs.currentChanged.connect(self._tab_changed)
        for table in (self.table_server, self.table_command, self.table_chat,
                      self.table_all):
            table.investigate.connect(self.investigate_player)
        self.stats_view.investigate.connect(self.investigate_player)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("Header")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(blossom_pixmap(46, self.devicePixelRatioF()))
        title = QLabel(__app_name__)
        title.setObjectName("AppTitle")
        sub = QLabel("Minecraft server log investigator")
        sub.setObjectName("AppSubtitle")
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(title)
        text.addWidget(sub)
        lay.addWidget(logo)
        lay.addLayout(text)
        lay.addStretch(1)

        open_btn = QPushButton("Import logs\u2026")
        open_btn.setObjectName("Primary")
        open_btn.setMinimumHeight(36)
        open_btn.clicked.connect(self.choose_files)

        self.export_btn = QToolButton()
        self.export_btn.setText("Export \u25BE")
        self.export_btn.setMinimumHeight(36)
        self.export_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.export_btn)
        a1 = menu.addAction("Export current tab\u2026")
        a1.triggered.connect(self.export_current_tab)
        a2 = menu.addAction("Export all filtered activity\u2026")
        a2.triggered.connect(self.export_all_filtered)
        menu.addSeparator()
        a3 = menu.addAction("Export player statistics (CSV)\u2026")
        a3.triggered.connect(self.export_stats)
        self.export_btn.setMenu(menu)

        self.theme_btn = QPushButton()
        self.theme_btn.setMinimumHeight(36)
        self.theme_btn.clicked.connect(self.toggle_theme)

        for w in (open_btn, self.export_btn, self.theme_btn):
            lay.addWidget(w)
        return header

    def _build_shortcuts(self) -> None:
        def sc(keys, fn):
            QShortcut(QKeySequence(keys), self, activated=fn)

        sc("Ctrl+O", self.choose_files)
        sc("Ctrl+E", self.export_current_tab)
        sc("Ctrl+D", self.toggle_theme)
        sc("Ctrl+F", self._focus_search)

    def _focus_search(self) -> None:
        self.filter_bar.search.setFocus()
        self.filter_bar.search.selectAll()

    # ============================================================== theme
    def apply_theme(self) -> None:
        pal = palette_for(self.dark)
        self.setStyleSheet(build_qss(pal))
        for table in (self.table_server, self.table_command, self.table_chat,
                      self.table_all):
            table.entry_model.set_palette(pal)
        self.timeline.set_palette(pal)
        self.overlay.pal = pal
        self.empty.pal = pal
        self.empty.update()
        self.theme_btn.setText("\u2600  Light mode" if self.dark else "\u263E  Dark mode")
        self._style_titlebar()
        self.settings.setValue("dark", self.dark)

    def toggle_theme(self) -> None:
        self.dark = not self.dark
        self.apply_theme()

    def _style_titlebar(self) -> None:
        pal = palette_for(self.dark)
        winutil.style_titlebar(int(self.winId()), self.dark, pal["header"],
                               pal["header_text"])

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._style_titlebar()

    # ====================================================== state / close
    def _restore_state(self) -> None:
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        ids = self.settings.value("active_ids", [])
        if isinstance(ids, (str, int)):
            ids = [ids]
        try:
            valid = self.storage.existing_ids(int(i) for i in (ids or []))
        except (TypeError, ValueError):
            valid = []
        self.active_ids = set(valid)

    def _save_active(self) -> None:
        self.settings.setValue("active_ids", sorted(self.active_ids))

    def closeEvent(self, event) -> None:
        self.settings.setValue("geometry", self.saveGeometry())
        for worker in (self._importer, self._loader):
            if worker is not None and worker.isRunning():
                if isinstance(worker, ImportWorker):
                    worker.cancel()
                worker.wait(5000)
        self.storage.close()
        super().closeEvent(event)

    # ===================================================== drag and drop
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.overlay.setGeometry(self.centralWidget().rect())

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.overlay.setGeometry(self.centralWidget().rect())
            self.overlay.show()
            self.overlay.raise_()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self.overlay.hide()

    def dropEvent(self, event) -> None:
        self.overlay.hide()
        local = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        paths = collect_paths(local)
        if paths:
            event.acceptProposedAction()
            self.start_import(paths)
        else:
            self.status_label.setText("Nothing to import - drop .log, .gz or .txt files")

    # ============================================================= import
    def choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Minecraft logs", self.settings.value("last_dir", ""),
            "Minecraft logs (*.log *.gz *.txt);;All files (*)")
        if paths:
            self.settings.setValue("last_dir", os.path.dirname(paths[0]))
            self.start_import(collect_paths(paths) or paths)

    def start_import(self, paths: list) -> None:
        if self._importer is not None and self._importer.isRunning():
            self._queued_paths.extend(paths)
            self.status_label.setText(f"Queued {len(paths)} more file(s)\u2026")
            return
        self._new_ids = []
        self._import_errors = []
        self._import_summary = {"files": 0, "entries": 0, "dups": 0}
        worker = ImportWorker(paths, self.db_path, self)
        worker.progress.connect(self._on_import_progress)
        worker.file_done.connect(self._on_file_done)
        worker.file_failed.connect(lambda n, m: self._import_errors.append(f"{n}: {m}"))
        worker.finished.connect(self._on_import_finished)
        self._importer = worker
        self.progress.setVisible(True)
        self.progress.setValue(0)
        worker.start()

    def _on_import_progress(self, name: str, pct: int, index: int, total: int) -> None:
        self.progress.setValue(pct)
        self.status_label.setText(f"Importing {name}  ({index + 1}/{total})\u2026")

    def _on_file_done(self, import_id: int, name: str, entries: int, dup: bool) -> None:
        self._new_ids.append(import_id)
        s = self._import_summary
        s["files"] += 1
        s["entries"] += entries
        s["dups"] += 1 if dup else 0

    def _on_import_finished(self) -> None:
        self.progress.setVisible(False)
        s = self._import_summary
        self.active_ids.update(self._new_ids)
        self._save_active()
        self.refresh_history()
        if s["files"]:
            msg = f"Imported {s['files'] - s['dups']} file(s), {s['entries']:,} entries"
            if s["dups"]:
                msg += f" ({s['dups']} already in history - activated)"
            self.status_label.setText(msg)
        if self._import_errors:
            QMessageBox.warning(self, "Some files could not be imported",
                                "\n".join(self._import_errors))
        self._importer = None
        if self._queued_paths:
            queued, self._queued_paths = self._queued_paths, []
            self.start_import(queued)
        else:
            self.load_active()

    # ============================================================ history
    def refresh_history(self) -> None:
        self.history.set_imports(self.storage.list_imports(), self.active_ids)
        self.sources = self.storage.import_names()

    def _history_checked(self, ids: list) -> None:
        self.active_ids = set(ids)
        self._save_active()
        self._reload_timer.start()

    def _delete_imports(self, ids: list) -> None:
        box = QMessageBox.question(
            self, "Delete saved logs",
            f"Remove {len(ids)} saved log(s) from CherryLogs?\n"
            "Your original files are not touched.")
        if box != QMessageBox.StandardButton.Yes:
            return
        self.storage.delete_imports(ids)
        self.active_ids.difference_update(ids)
        self._save_active()
        self.refresh_history()
        self.load_active()

    # ============================================================ loading
    def load_active(self) -> None:
        if self._loader is not None and self._loader.isRunning():
            self._reload_pending = True
            return
        if not self.active_ids:
            self._set_entries([])
            return
        self.status_label.setText("Loading saved logs\u2026")
        self.setCursor(Qt.CursorShape.BusyCursor)
        worker = LoadWorker(sorted(self.active_ids), self.db_path, self)
        worker.loaded.connect(self._set_entries)
        worker.failed.connect(lambda m: QMessageBox.critical(self, "Load failed", m))
        worker.finished.connect(self._on_load_finished)
        self._loader = worker
        worker.start()

    def _on_load_finished(self) -> None:
        self.unsetCursor()
        self._loader = None
        if self._reload_pending:
            self._reload_pending = False
            self.load_active()

    def _set_entries(self, entries: list) -> None:
        if self._reload_pending:
            return  # a newer load is about to replace this one
        self.entries = entries
        self.markers = [e for e in entries if e.event in ("start", "stop")]
        self.sources = self.storage.import_names()
        counts = Counter(p for e in entries for p in e.players)
        self.players.set_players(counts)
        if entries:
            self.filter_bar.set_range(entries[0].ts, entries[-1].ts)
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)
            self.status_label.setText("Drop log files anywhere to begin")
        self.refilter()

    # ========================================================== filtering
    def schedule_refilter(self) -> None:
        self._refilter_timer.start()

    def current_filters(self):
        return self.filter_bar.filters(self.players.selected())

    def refilter(self) -> None:
        f = self.current_filters()
        self.result = apply_filters(self.entries, f)
        r = self.result
        self.table_server.entry_model.set_entries(r.server)
        self.table_command.entry_model.set_entries(r.command)
        self.table_chat.entry_model.set_entries(r.chat)
        self.table_all.entry_model.set_entries(r.everything)
        self._stats_dirty = True
        self._timeline_dirty = True
        self._update_tab_titles()
        self._refresh_analytics()
        if self.entries:
            who = (f"{len(f.players)} player(s) selected" if f.players
                   else f"{self.players.list.count():,} players")
            self.status_label.setText(
                f"Showing {len(r.everything):,} of {len(self.entries):,} entries"
                f"  \u00b7  {who}  \u00b7  {len(self.active_ids)} log file(s)")

    def _update_tab_titles(self) -> None:
        r = self.result
        self.tabs.setTabText(TAB_SERVER, f"Server Logs ({len(r.server):,})")
        self.tabs.setTabText(TAB_COMMANDS, f"Commands ({len(r.command):,})")
        self.tabs.setTabText(TAB_CHAT, f"Chat ({len(r.chat):,})")
        self.tabs.setTabText(TAB_ALL, f"All Activity ({len(r.everything):,})")

    def _tab_changed(self, _index: int) -> None:
        self._refresh_analytics()

    def _ensure_stats(self) -> None:
        if not self._stats_dirty or self.result is None:
            return
        f = self.current_filters()
        self.stats, self._overview = compute_stats(
            self.result.base, self.markers, f.players, f.start, f.end)
        self._stats_dirty = False
        self._stats_shown = False

    def _refresh_analytics(self) -> None:
        """Statistics and timeline are computed lazily, only when visible."""
        if self.result is None:
            return
        tab = self.tabs.currentIndex()
        if tab == TAB_STATS:
            self._ensure_stats()
            if not self._stats_shown:
                self.stats_view.set_data(self.stats, self._overview)
                self._stats_shown = True
        elif tab == TAB_TIMELINE and self._timeline_dirty:
            self._ensure_stats()
            f = self.current_filters()
            markers = [m for m in self.markers
                       if (f.start is None or m.ts >= f.start)
                       and (f.end is None or m.ts <= f.end)]
            self.timeline.set_data(self.result.everything, markers,
                                   {n: s.sessions for n, s in self.stats.items()})
            self._timeline_dirty = False

    def investigate_player(self, name: str) -> None:
        self.left_tabs.setCurrentWidget(self.players)
        self.players.select_player(name)

    # ============================================================= export
    def _ask_path(self, title: str, base: str, csv_only: bool = False):
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("_")
        folder = self.settings.value("export_dir", "")
        default = os.path.join(folder, f"CherryLogs_{safe}_{stamp}")
        filters = "CSV file (*.csv)" if csv_only else \
            "Text file (*.txt);;CSV file (*.csv)"
        path, chosen = QFileDialog.getSaveFileName(self, title, default, filters)
        if not path:
            return None, None
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".txt", ".csv"):
            ext = ".csv" if "csv" in chosen.lower() else ".txt"
            path += ext
        self.settings.setValue("export_dir", os.path.dirname(path))
        return path, ext

    def _players_label(self) -> str:
        sel = sorted(self.players.selected())
        if not sel:
            return "all_players"
        return "-".join(sel[:3]) + ("+more" if len(sel) > 3 else "")

    def _active_sources(self) -> dict:
        return {k: v for k, v in self.sources.items() if k in self.active_ids}

    def _export_entries(self, entries: list, title: str) -> None:
        if not entries:
            QMessageBox.information(self, "Nothing to export",
                                    "There are no entries for the current filters.")
            return
        path, ext = self._ask_path(f"Export {title}", f"{title}_{self._players_label()}")
        if not path:
            return
        try:
            if ext == ".csv":
                exporter.export_csv(path, entries, self.sources)
            else:
                exporter.export_txt(path, entries, title,
                                    self.current_filters().describe(),
                                    self._active_sources())
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.status_label.setText(f"Exported {len(entries):,} entries to {path}")

    def export_current_tab(self) -> None:
        if self.result is None or not self.entries:
            return
        tab = self.tabs.currentIndex()
        if tab == TAB_STATS:
            self.export_stats()
            return
        r = self.result
        mapping = {TAB_SERVER: (r.server, "server_logs"),
                   TAB_COMMANDS: (r.command, "commands"),
                   TAB_CHAT: (r.chat, "chat"),
                   TAB_ALL: (r.everything, "all_activity"),
                   TAB_TIMELINE: (r.everything, "all_activity")}
        entries, title = mapping[tab]
        self._export_entries(entries, title)

    def export_all_filtered(self) -> None:
        if self.result is not None:
            self._export_entries(self.result.everything, "all_activity")

    def export_stats(self) -> None:
        if self.result is None or not self.entries:
            return
        self._ensure_stats()
        if not self.stats:
            QMessageBox.information(self, "Nothing to export",
                                    "No player statistics for the current filters.")
            return
        path, _ext = self._ask_path("Export player statistics",
                                    f"player_stats_{self._players_label()}",
                                    csv_only=True)
        if not path:
            return
        try:
            exporter.export_stats_csv(path, self.stats)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.status_label.setText(f"Exported statistics for {len(self.stats)} player(s)")
