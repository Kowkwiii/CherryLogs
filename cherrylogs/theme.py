"""Cherry blossom light / dark themes (Qt style sheets + colour palettes)."""
from __future__ import annotations

LIGHT = {
    "name": "light",
    "bg": "#FFF6F9", "panel": "#FFFFFF", "panel_alt": "#FFF0F5",
    "header": "#FBD3E1", "header_text": "#5A1E37",
    "text": "#3D2A33", "muted": "#8D6F7C", "border": "#F2C9D7",
    "accent": "#D6336C", "accent_hover": "#E64980", "accent_text": "#FFFFFF",
    "soft": "#FFE0EA", "select": "#FFD0E0", "select_text": "#3D2A33",
    "input": "#FFFFFF", "grid": "#FBE3EB",
    "c_chat": "#E64980", "c_command": "#845EF7", "c_server": "#51A87A",
    "c_join": "#2F9E44", "c_leave": "#868E96", "c_death": "#E03131",
    "c_adv": "#F08C00", "c_warn": "#E67700", "c_error": "#C92A2A",
}

DARK = {
    "name": "dark",
    "bg": "#1B1217", "panel": "#261A21", "panel_alt": "#2E2028",
    "header": "#3A1F2C", "header_text": "#FFD6E4",
    "text": "#F3E4EA", "muted": "#B79AA7", "border": "#46303A",
    "accent": "#F06595", "accent_hover": "#FF85AE", "accent_text": "#2A0E1A",
    "soft": "#3A2430", "select": "#5A2A40", "select_text": "#FFFFFF",
    "input": "#1F151B", "grid": "#33232B",
    "c_chat": "#FF85AE", "c_command": "#B197FC", "c_server": "#69DB9C",
    "c_join": "#69DB7C", "c_leave": "#9AA0A6", "c_death": "#FF6B6B",
    "c_adv": "#FFC145", "c_warn": "#FFA94D", "c_error": "#FF6B6B",
}

EVENT_COLOR_KEY = {
    "chat": "c_chat", "command": "c_command", "feedback": "c_command",
    "join": "c_join", "login": "c_join", "uuid": "c_leave",
    "leave": "c_leave", "disconnect": "c_leave", "death": "c_death",
    "advancement": "c_adv", "warning": "c_warn", "error": "c_error",
}


def palette_for(dark: bool) -> dict:
    return DARK if dark else LIGHT


def event_color(event: str, pal: dict):
    key = EVENT_COLOR_KEY.get(event)
    return pal[key] if key else None


def build_qss(p: dict) -> str:
    return f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {p['bg']}; }}
QWidget {{ color: {p['text']}; }}
QWidget#Central, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {p['bg']}; }}

QFrame#Header {{ background: {p['header']}; border-bottom: 1px solid {p['border']}; }}
QLabel#AppTitle {{ color: {p['header_text']}; font-size: 20pt; font-weight: 700; }}
QLabel#AppSubtitle {{ color: {p['header_text']}; font-size: 9pt; }}
QLabel#Muted {{ color: {p['muted']}; }}
QLabel#SectionTitle {{ font-weight: 600; color: {p['accent']}; }}

QFrame#Card {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 12px; }}
QLabel#CardValue {{ font-size: 18pt; font-weight: 700; color: {p['accent']}; background: transparent; }}
QLabel#CardLabel {{ color: {p['muted']}; background: transparent; }}

QPushButton, QToolButton {{
    background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 8px;
    padding: 6px 14px; color: {p['text']};
}}
QPushButton:hover, QToolButton:hover {{ background: {p['soft']}; border-color: {p['accent']}; }}
QPushButton:disabled {{ color: {p['muted']}; }}
QPushButton#Primary {{ background: {p['accent']}; color: {p['accent_text']}; border: none; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {p['accent_hover']}; }}
QToolButton::menu-indicator {{ image: none; width: 0px; }}

QLineEdit, QComboBox, QDateTimeEdit {{
    background: {p['input']}; border: 1px solid {p['border']}; border-radius: 8px;
    padding: 5px 8px; selection-background-color: {p['accent']}; selection-color: {p['accent_text']};
}}
QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus {{ border: 1px solid {p['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {p['panel']}; border: 1px solid {p['border']};
    selection-background-color: {p['select']}; selection-color: {p['select_text']};
}}
QDateTimeEdit:disabled {{ color: {p['muted']}; background: {p['panel_alt']}; }}

QCheckBox {{ spacing: 7px; background: transparent; }}
QCheckBox::indicator, QListWidget::indicator {{
    width: 16px; height: 16px; border: 1.5px solid {p['accent']}; border-radius: 5px; background: {p['input']};
}}
QCheckBox::indicator:checked, QListWidget::indicator:checked {{ background: {p['accent']}; }}
QCheckBox::indicator:hover, QListWidget::indicator:hover {{ border-color: {p['accent_hover']}; }}

QTabWidget::pane {{ border: 1px solid {p['border']}; border-radius: 10px; background: {p['panel']}; top: -1px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    background: transparent; color: {p['muted']}; padding: 8px 16px; margin-right: 2px;
    border-top-left-radius: 8px; border-top-right-radius: 8px; border: 1px solid transparent;
}}
QTabBar::tab:hover {{ color: {p['accent']}; }}
QTabBar::tab:selected {{
    background: {p['panel']}; color: {p['accent']}; font-weight: 600;
    border: 1px solid {p['border']}; border-bottom: 1px solid {p['panel']};
}}

QTableView, QTableWidget, QListWidget {{
    background: {p['panel']}; alternate-background-color: {p['panel_alt']};
    border: none; gridline-color: {p['grid']};
    selection-background-color: {p['select']}; selection-color: {p['select_text']};
}}
QTableView::item {{ padding: 2px 6px; }}
QListWidget::item {{ padding: 5px 4px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {p['select']}; color: {p['select_text']}; }}
QListWidget::item:hover {{ background: {p['soft']}; }}
QHeaderView::section {{
    background: {p['soft']}; color: {p['text']}; padding: 6px 8px; border: none;
    border-right: 1px solid {p['border']}; font-weight: 600;
}}
QTableCornerButton::section {{ background: {p['soft']}; border: none; }}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle {{ background: {p['border']}; border-radius: 4px; min-height: 28px; min-width: 28px; }}
QScrollBar::handle:hover {{ background: {p['accent']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSplitter::handle {{ background: {p['bg']}; width: 6px; }}
QStatusBar {{ background: {p['header']}; color: {p['header_text']}; }}
QStatusBar::item {{ border: none; }}
QProgressBar {{
    background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 7px;
    text-align: center; height: 14px; color: {p['text']};
}}
QProgressBar::chunk {{ background: {p['accent']}; border-radius: 6px; }}

QMenu {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p['select']}; color: {p['select_text']}; }}
QMenu::separator {{ height: 1px; background: {p['border']}; margin: 4px 8px; }}
QToolTip {{ background: {p['panel']}; color: {p['text']}; border: 1px solid {p['accent']}; padding: 4px; }}
QMessageBox {{ background: {p['bg']}; }}
"""
