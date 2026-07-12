"""Message display area with Markdown + code highlighting.

Uses setHtml() to fully replace content on each streaming update,
avoiding the cursor-manipulation bugs that caused text repetition.
"""

import re
from html import escape
import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from PySide6.QtWidgets import QFrame, QTextBrowser, QVBoxLayout
from atri.ui.theme import (
    BG_CODE,
    BUBBLE_AI,
    BUBBLE_USER,
    BUBBLE_USER_BORDER,
    FONT_SANS,
    FONT_SIZE,
    TEXT_PRIMARY,
)

_CODE_BLOCK_RE = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)


def _highlight_code(lang: str, code: str) -> str:
    try:
        lexer = get_lexer_by_name(lang, stripall=True) if lang else guess_lexer(code)
    except Exception:
        lexer = guess_lexer(code)
    formatter = HtmlFormatter(style="friendly", noclasses=True)
    return highlight(code, lexer, formatter)


def _md_to_html(text: str) -> str:
    parts = []
    last_end = 0
    for match in _CODE_BLOCK_RE.finditer(text):
        parts.append(text[last_end:match.start()])
        lang = match.group(1) or ""
        code = match.group(2).strip()
        highlighted = _highlight_code(lang, code)
        parts.append(
            f'<pre style="background:{BG_CODE};padding:12px;border-radius:12px;'
            f'overflow-x:auto;font-family:monospace;font-size:12px;">'
            f"{highlighted}</pre>"
        )
        last_end = match.end()
    parts.append(text[last_end:])

    md_text = "".join(parts)
    return markdown.markdown(md_text, extensions=["fenced_code", "tables", "codehilite"])


_USER_BUBBLE = (
    '<div style="display:flex;justify-content:flex-end;margin:16px 16px;">'
    '<div style="max-width:70%;background:{bg};color:{fg};'
    'border:1px solid {border};'
    'border-radius:16px 16px 4px 16px;padding:10px 16px;'
    'font-family:{font};font-size:{size}px;'
    'line-height:1.5;word-wrap:break-word;white-space:pre-wrap;">'
    "{content}"
    "</div></div>"
)

_AI_BUBBLE = (
    '<div style="display:flex;justify-content:flex-start;margin:16px 16px;">'
    '<div style="max-width:85%;background:{bg};color:{fg};'
    'border-radius:16px 16px 16px 4px;padding:12px 16px;'
    'font-family:{font};font-size:{size}px;'
    'line-height:1.6;word-wrap:break-word;">'
    "{content}"
    "</div></div>"
)

_SYSTEM_MSG = (
    '<div style="text-align:left;margin:4px 16px;color:{fg};'
    'font-family:{font};font-size:11px;opacity:0.55;">{content}</div>'
)


class Thread(QFrame):
    """Scrollable message display with user/AI bubbles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("thread")
        self.setStyleSheet(
            f"#thread {{"
            f"background: qradialgradient(cx:0.15, cy:0.1, radius:1.6,"
            f"fx:0.15, fy:0.1,"
            f"stop:0 #FAFDF5, stop:0.3 #F7FBF2,"
            f"stop:0.6 #F3F8EF, stop:1 #ECF2E8);"
            f"}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setReadOnly(True)
        self._browser.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; }"
        )
        layout.addWidget(self._browser)

        # Messages stored as (type, text) tuples.
        # type ∈ {'user', 'ai', 'ai-progress', 'system'}
        self._messages: list[tuple[str, str]] = []

    # ── public API ───────────────────────────────────────────────────

    def add_user_message(self, text: str):
        self._messages.append(("user", text))
        self._render_all()

    def add_ai_message(self, text: str):
        self._messages.append(("ai", text))
        self._render_all()

    def add_system_message(self, text: str):
        self._messages.append(("system", text))
        self._render_all()

    def add_ai_message_in_progress(self, partial_text: str):
        if self._messages and self._messages[-1][0] == "ai-progress":
            self._messages[-1] = ("ai-progress", partial_text)
        else:
            self._messages.append(("ai-progress", partial_text))
        self._render_all()
        self._scroll_to_bottom()

    def finalize_ai_message(self, final_text: str):
        if self._messages and self._messages[-1][0] == "ai-progress":
            self._messages[-1] = ("ai", final_text)
        else:
            if final_text:
                self._messages.append(("ai", final_text))
        self._render_all()

    def clear(self):
        self._messages.clear()
        self._browser.clear()

    def load_history(self, messages: list[tuple[str, str]]):
        """Batch-load messages for session restore (renders once)."""
        self._messages = list(messages)
        self._render_all()

    # ── internal ─────────────────────────────────────────────────────

    def _render_all(self):
        """Rebuild the complete HTML from _messages and set it."""
        parts = [f'<div style="padding:8px 0;">']
        for msg_type, text in self._messages:
            if msg_type == "user":
                parts.append(
                    _USER_BUBBLE.format(
                        bg=BUBBLE_USER,
                        fg=TEXT_PRIMARY,
                        border=BUBBLE_USER_BORDER,
                        font=FONT_SANS,
                        size=FONT_SIZE,
                        content=escape(text),
                    )
                )
            elif msg_type in ("ai", "ai-progress"):
                parts.append(
                    _AI_BUBBLE.format(
                        bg=BUBBLE_AI,
                        fg=TEXT_PRIMARY,
                        font=FONT_SANS,
                        size=FONT_SIZE,
                        content=_md_to_html(text),
                    )
                )
            elif msg_type == "system":
                parts.append(
                    _SYSTEM_MSG.format(
                        fg=TEXT_PRIMARY,
                        font=FONT_SANS,
                        content=escape(text),
                    )
                )
        parts.append("</div>")
        self._browser.setHtml("".join(parts))
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        bar = self._browser.verticalScrollBar()
        bar.setValue(bar.maximum())
