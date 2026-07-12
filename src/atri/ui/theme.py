"""Light theme colors — matching Hermes default "luzao" (露早) preset."""

# ── backgrounds ──────────────────────────────────────────────────────
BG_MAIN = "#F5FAF5"           # main window — soft green-white
BG_SIDEBAR = "#F0F7F0"        # sidebar + file panel — slightly greener
BG_CHAT = "#F5FAF5"           # chat thread area
BG_INPUT = "#FFFFFF"          # composer input — card white
BG_TITLEBAR = "#F0F7F0"       # titlebar — matches sidebar
BG_STATUSBAR = "#F0F7F0"      # statusbar
BG_CODE = "#F0F7F0"           # code block — subtle off-white green

# ── bubbles ──────────────────────────────────────────────────────────
BUBBLE_USER = "#E8F5E9"          # user message — soft green
BUBBLE_USER_BORDER = "#C8E6C9"   # subtle green border
BUBBLE_AI = "#FFFFFF"            # AI message — card white (subtle differentiation)

# ── text ─────────────────────────────────────────────────────────────
TEXT_PRIMARY = "#1A2E1A"      # dark green, for body text
TEXT_SECONDARY = "#5C8A5F"    # muted green, for captions
TEXT_WHITE = "#FFFFFF"        # on accent buttons

# ── borders & accents ────────────────────────────────────────────────
BORDER = "#C8E6C9"            # green-tinted border (luzao border)
ACCENT = "#66BB6A"            # primary green — softer
ACCENT_HOVER = "#4CAF50"      # darker green on hover
RING = "#66BB6A"              # focus ring = primary

# ── status ───────────────────────────────────────────────────────────
STATUS_SUCCESS = "#43A047"
STATUS_WARNING = "#F9A825"
STATUS_ERROR = "#C72E4D"

# ── typography (matching Hermes font stack) ───────────────────────────
FONT_SANS = '"Segoe UI", -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
FONT_MONO = '"Cascadia Code", "JetBrains Mono", "SF Mono", ui-monospace, Menlo, Monaco, Consolas, monospace'
FONT_SIZE = 14
FONT_SIZE_SMALL = 11


def global_stylesheet() -> str:
    """Return the app-wide QSS stylesheet."""
    return f"""
    QMainWindow {{
        background-color: {BG_MAIN};
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
        border-radius: 10px;
    }}
    QListWidget::item:hover {{
        background-color: {BUBBLE_USER};
    }}
    QListWidget::item:selected {{
        background-color: {ACCENT};
        color: {TEXT_WHITE};
    }}
    QTextEdit {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 10px;
        font-family: {FONT_SANS};
        font-size: {FONT_SIZE}px;
    }}
    QTextBrowser {{
        background-color: {BG_CHAT};
        color: {TEXT_PRIMARY};
        border: none;
        font-family: {FONT_SANS};
        font-size: {FONT_SIZE}px;
    }}
    QPushButton {{
        background-color: {ACCENT};
        color: {TEXT_WHITE};
        border: none;
        border-radius: 12px;
        padding: 8px 16px;
        font-family: {FONT_SANS};
        font-size: {FONT_SIZE}px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {ACCENT_HOVER};
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
        background-color: {BUBBLE_USER};
    }}
    QTreeView::item:selected {{
        background-color: {ACCENT};
        color: {TEXT_WHITE};
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
        border-radius: 8px;
    }}
    QMenu::item:selected {{
        background-color: {ACCENT};
        color: {TEXT_WHITE};
    }}
    """
