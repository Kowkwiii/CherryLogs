"""Background threads so the UI stays responsive on big logs."""
from __future__ import annotations

import os

from PySide6.QtCore import QThread, Signal

from .parser import Cancelled, parse_file
from .storage import Storage, file_sha256


class ImportWorker(QThread):
    """Parses and stores one or more files."""

    progress = Signal(str, int, int, int)   # file name, percent, index, total
    file_done = Signal(int, str, int, bool)  # import id, name, entries, was_duplicate
    file_failed = Signal(str, str)           # file name, error message

    def __init__(self, paths: list, db_path: str, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.db_path = db_path
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        storage = Storage(self.db_path)  # connections are per-thread
        total = len(self.paths)
        try:
            for index, path in enumerate(self.paths):
                if self._cancel:
                    break
                name = os.path.basename(path)
                try:
                    self.progress.emit(name, 0, index, total)
                    sha = file_sha256(path)
                    existing = storage.find_import_by_hash(sha)
                    if existing is not None:
                        self.file_done.emit(existing, name, 0, True)
                        continue

                    last = [-1]

                    def report(frac: float) -> None:
                        pct = int(frac * 100)
                        if pct != last[0]:
                            last[0] = pct
                            self.progress.emit(name, pct, index, total)

                    parsed = parse_file(path, report, lambda: self._cancel)
                    self.progress.emit(name, 100, index, total)
                    import_id = storage.add_import(
                        name, path, sha, os.path.getsize(path), parsed)
                    self.file_done.emit(import_id, name, len(parsed.entries),
                                        False)
                except Cancelled:
                    break
                except Exception as exc:  # noqa: BLE001 - report, keep going
                    self.file_failed.emit(name, f"{type(exc).__name__}: {exc}")
        finally:
            storage.close()


class LoadWorker(QThread):
    """Loads stored entries for the selected imports."""

    loaded = Signal(list)
    failed = Signal(str)

    def __init__(self, import_ids: list, db_path: str, parent=None):
        super().__init__(parent)
        self.import_ids = import_ids
        self.db_path = db_path

    def run(self) -> None:
        storage = Storage(self.db_path)
        try:
            self.loaded.emit(storage.load_entries(self.import_ids))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            storage.close()
