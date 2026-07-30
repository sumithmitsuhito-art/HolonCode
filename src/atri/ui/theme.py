"""Light theme colors — matching Hermes default "luzao" (露早) preset."""
import json
from pathlib import Path

# ── backgrounds ──────────────────────────────────────────────────────
BG_MAIN = "#F3F8F3"           # main window — soft green paper
BG_SIDEBAR = "#EDF7EF"        # sidebar + file panel — pale green zone
BG_CHAT = "#F5FAF5"           # chat thread — soft green-white
BG_INPUT = "#FFFFFF"          # composer input — card white
BG_TITLEBAR = "#EDF7EF"       # titlebar — matches sidebar
BG_STATUSBAR = "#EDF7EF"      # statusbar
BG_CODE = "#F4F7F4"           # code block — soft green-gray

# ── bubbles ──────────────────────────────────────────────────────────
BUBBLE_USER = "#FFF0F3"          # user message — soft pink
BUBBLE_USER_BORDER = "#F5D5DC"   # subtle pink border
BUBBLE_AI = "#F1FAF2"            # AI message — light green

# ── text ─────────────────────────────────────────────────────────────
TEXT_PRIMARY = "#243024"      # deep green, for body text
TEXT_SECONDARY = "#6B7B6D"    # muted green, for captions
TEXT_WHITE = "#FFFFFF"        # on accent buttons

# ── borders & accents ────────────────────────────────────────────────
BORDER = "#D8E9DA"            # soft green border
ACCENT = "#55B86A"            # primary green — product-feel, not garish
ACCENT_HOVER = "#46A95B"      # deeper green on hover
ACCENT_PRESSED = "#398D4B"    # pressed state
RING = "#55B86A"              # focus ring = primary

# ── status ───────────────────────────────────────────────────────────
STATUS_SUCCESS = "#4CAF50"
STATUS_WARNING = "#E9B949"
STATUS_ERROR = "#E57373"

# ── semantic aliases ──────────────────────────────────────────────────
CARD_BG = "#FAFDFA"            # card background — barely-there green tint
CARD_HOVER = "#E8F5E9"         # card hover — slightly deeper green
CARD_RADIUS = 12               # card corner radius
DANGER = STATUS_ERROR          # destructive action color
DANGER_HOVER = "#E0556A"       # destructive action hover
DANGER_BG = "#FFE0E0"          # destructive action background
FILE_SELECTION = "#DDF3DF"     # file panel selected item highlight
FILE_SELECTION_BORDER = ACCENT # file panel selection left bar

# ── page surface ───────────────────────────────────────────────────────────
PAGE_BG = "#F3F8F3"            # page-level — matches main bg

# ── dialog surfaces ─────────────────────────────────────────────────────
DIALOG_BG = PAGE_BG            # dialogs share page background

# ── row / list item ─────────────────────────────────────────────────────
ROW_BG = "#FFFFFF"
ROW_HOVER = "#EDF7EF"
ROW_STRIPE = ACCENT

# ── badges ─────────────────────────────────────────────────────────────────
BADGE_DONE_BG = "#E8F5E9"      # light green pill for completed
BADGE_DONE_TEXT = "#2E7D32"    # dark green text
BADGE_PENDING_BG = "#F5F5F5"   # light gray pill for in-progress
BADGE_PENDING_TEXT = "#9E9E9E" # gray text

# ── tab bar ─────────────────────────────────────────────────────────────
TAB_HOVER_BG = "#F0F7F0"

# ── spacing scale ──────────────────────────────────────────────────────
PADDING_XL = 20
PADDING_LG = 16
PADDING_MD = 12
PADDING_SM = 8

# ── typography (matching Hermes font stack) ───────────────────────────
FONT_SANS = '"Segoe UI", "Microsoft YaHei", system-ui, -apple-system, sans-serif'
FONT_MONO = '"Cascadia Code", "JetBrains Mono", "Fira Code", "SF Mono", ui-monospace, Consolas, "Courier New", monospace'
FONT_SIZE = 14
FONT_SIZE_SMALL = 11

# ── radii ─────────────────────────────────────────────────────────────
RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 14


def _load_chat_font_size() -> int:
    """Read chat font size from UserSettings.json, default 14."""
    try:
        from atri import DATA_DIR
        settings_path = DATA_DIR / "UserSettings.json"
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            ui = data.get("UI", {})
            size = ui.get("ChatFontSize", 14)
            if 10 <= size <= 24:
                return size
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return 14


CHAT_FONT_SIZE = _load_chat_font_size()


def global_stylesheet() -> str:
    """Return the app-wide QSS stylesheet."""
    return f"""
    QMainWindow {{
        background-color: {BG_MAIN};
    }}
    QDialog {{
        background-color: {PAGE_BG};
    }}
    QListWidget {{
        background-color: {BG_SIDEBAR};
        color: {TEXT_PRIMARY};
        border: none;
        font-family: {FONT_SANS};
        font-size: {FONT_SIZE}px;
    }}
    QListWidget::item {{
        padding: 8px 12px;
        border-radius: {RADIUS_MD}px;
    }}
    QListWidget::item:hover {{
        background-color: {FILE_SELECTION};
    }}
    QListWidget::item:selected {{
        background-color: {ACCENT};
        color: {TEXT_WHITE};
    }}
    QTextEdit {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {RADIUS_LG}px;
        padding: 10px;
        font-family: {FONT_SANS};
        font-size: {CHAT_FONT_SIZE}px;
    }}
    QTextEdit:focus {{
        border-color: {ACCENT};
    }}
    QTextBrowser {{
        background-color: {BG_CHAT};
        color: {TEXT_PRIMARY};
        border: none;
        font-family: {FONT_SANS};
        font-size: {CHAT_FONT_SIZE}px;
    }}
    QPushButton {{
        background-color: {ACCENT};
        color: {TEXT_WHITE};
        border: none;
        border-radius: {RADIUS_MD}px;
        padding: 8px 16px;
        font-family: {FONT_SANS};
        font-size: {FONT_SIZE}px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {ACCENT_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {ACCENT};
    }}
    QPushButton:disabled {{
        background-color: {BORDER};
        color: {TEXT_SECONDARY};
    }}
    QTreeView {{
        background-color: {BG_SIDEBAR};
        color: {TEXT_PRIMARY};
        border: none;
        font-family: {FONT_SANS};
        font-size: {FONT_SIZE}px;
    }}
    QTreeView::item:hover {{
        background-color: {FILE_SELECTION};
    }}
    QTreeView::item:selected {{
        background-color: {ACCENT};
        color: {TEXT_WHITE};
        border-radius: 6px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        border-radius: 6px;
        min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QSplitter::handle {{
        background-color: {BORDER};
        width: 1px;
    }}
    QLabel {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_SANS};
        font-size: {FONT_SIZE}px;
    }}
    QMenu {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 24px;
        border-radius: {RADIUS_SM}px;
    }}
    QMenu::item:selected {{
        background-color: {ACCENT};
        color: {TEXT_WHITE};
    }}
    QTabWidget::pane {{
        border: none;
        background: transparent;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {TEXT_SECONDARY};
        border: none;
        border-radius: {RADIUS_MD}px;
        padding: 8px 18px;
        font-family: {FONT_SANS};
        font-size: {FONT_SIZE}px;
    }}
    QTabBar::tab:selected {{
        background: {ACCENT};
        color: {TEXT_WHITE};
        font-weight: 600;
    }}
    QTabBar::tab:hover:!selected {{
        background: {TAB_HOVER_BG};
        color: {TEXT_PRIMARY};
    }}
    """
