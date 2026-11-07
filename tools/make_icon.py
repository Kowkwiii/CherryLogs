"""Generate assets/cherrylogs.ico and cherrylogs.png from the painted blossom."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from cherrylogs.branding import blossom_pixmap  # noqa: E402


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    out = os.path.join(ROOT, "assets")
    os.makedirs(out, exist_ok=True)
    px = blossom_pixmap(256)
    ok_png = px.save(os.path.join(out, "cherrylogs.png"), "PNG")
    ok_ico = px.save(os.path.join(out, "cherrylogs.ico"), "ICO")
    print("png:", ok_png, " ico:", ok_ico, "->", out)


if __name__ == "__main__":
    main()
