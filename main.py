"""CherryLogs entry point."""
import sys

from PySide6.QtWidgets import QApplication

from cherrylogs import __app_name__, winutil
from cherrylogs.branding import blossom_icon
from cherrylogs.storage import default_db_path
from cherrylogs.ui.main_window import MainWindow


def main() -> int:
    winutil.set_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setOrganizationName("CherryLogs")
    app.setStyle("Fusion")  # consistent base for the cherry blossom style sheet
    app.setWindowIcon(blossom_icon())

    window = MainWindow(default_db_path())
    window.show()

    # Files passed on the command line (e.g. "Open with CherryLogs").
    args = [a for a in sys.argv[1:]]
    if args:
        from cherrylogs.ui.main_window import collect_paths
        paths = collect_paths(args)
        if paths:
            window.start_import(paths)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
