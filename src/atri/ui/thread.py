"""Message display area with Markdown + code highlighting.

Scroll behaviour (modelled after Hermes' use-stick-to-bottom):
- Auto-follows the bottom while the user hasn't scrolled up ("locked").
- Escapes on user scroll-up (wheel up) so they can re-read history undisturbed.
- Re-locks when the user scrolls back to the bottom or sends a new message.
- A floating "jump to bottom" button appears while escaped.

During streaming the last bubble is updated **in-place** via QTextCursor so
the document is never torn down and rebuilt while tokens are arriving.
This is the Qt equivalent of Hermes' React incremental render + ResizeObserver
scroll compensation — both happen before the next paint, so there is no frame
where old content has been destroyed and new content hasn't scrolled yet.
"""

import base64
import re
from html import escape

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt, Signal
from PySide6.QtGui import QPixmap, QTextCursor
from PySide6.QtWidgets import QFrame, QPushButton, QTextBrowser, QVBoxLayout
from atri import BASE_DIR
from atri.ui import theme as _theme
from atri.ui.theme import (
    BG_CODE,
    BUBBLE_AI,
    BUBBLE_USER,
    BUBBLE_USER_BORDER,
    FONT_SANS,
    FONT_SIZE,
    TEXT_PRIMARY,
)

_AVATAR_SIZE = 60
_ICON_DATA_URI: str | None = None


def _get_icon_data_uri() -> str:
    """Pre-scale avatar with smooth transform, cached after first call."""
    global _AVATAR_SIZE, _ICON_DATA_URI
    if _ICON_DATA_URI is not None:
        return _ICON_DATA_URI
    pix = QPixmap(str(BASE_DIR / "icon" / "头像.png"))
    pix = pix.scaled(
        _AVATAR_SIZE * 2, _AVATAR_SIZE * 2,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buf, "PNG")
    _ICON_DATA_URI = f"data:image/png;base64,{base64.b64encode(ba).decode()}"
    return _ICON_DATA_URI

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
        parts.append(text[last_end : match.start()])
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
    'font-family:{font};font-size:{chat_size}px;'
    'line-height:1.5;word-wrap:break-word;white-space:pre-wrap;">'
    "{content}"
    "</div></div>"
)

_AI_BUBBLE = (
    '<table style="margin:16px 16px;" cellpadding="0" cellspacing="0" border="0">'
    '<tr>'
    '<td style="vertical-align:top;padding-right:10px;padding-top:4px;">'
    '<img src="{icon}" width="60" height="60"'
    ' style="border-radius:30px;">'
    '</td>'
    '<td>'
    '<div style="max-width:85%;background:{bg};color:{fg};'
    'border-radius:16px 16px 16px 4px;padding:12px 16px;'
    'font-family:{font};font-size:{chat_size}px;'
    'line-height:1.6;word-wrap:break-word;">'
    "{content}"
    "</div>"
    "</td>"
    "</tr></table>"
)

_SYSTEM_MSG = (
    '<div style="text-align:left;margin:4px 16px;color:{fg};'
    'font-family:{font};font-size:11px;opacity:0.55;">{content}</div>'
)

_SKILL_MSG = (
    '<div style="text-align:left;margin:8px 0;">'
    '<span style="display:inline-block;background:#FDE8EC;color:{fg};'
    'font-family:{font};font-size:{chat_size}px;font-weight:500;'
    'padding:6px 16px;border-radius:12px;">{content}</span>'
    '</div>'
)

# Scrollbar threshold (px) — values within this distance of the maximum are
# treated as "at bottom".
_BOTTOM_THRESHOLD = 5


class _ScrollAwareBrowser(QTextBrowser):
    """QTextBrowser that detects user scroll-up / scroll-to-bottom intent."""

    scrolled_up = Signal()
    scrolled_to_bottom = Signal()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        super().wheelEvent(event)

        bar = self.verticalScrollBar()
        if delta > 0:
            self.scrolled_up.emit()
        elif delta < 0 and bar.maximum() > 0:
            if bar.value() >= bar.maximum() - _BOTTOM_THRESHOLD:
                self.scrolled_to_bottom.emit()


class Thread(QFrame):
    """Scrollable message display with user/AI bubbles.

    Scroll ownership follows the Hermes single-writer pattern: only the
    streaming in-place updater and the jump button write ``scrollTop``.
    """

    scrolled_up_changed = Signal(bool)

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

        self._browser = _ScrollAwareBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setReadOnly(True)
        self._browser.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; }"
        )
        self._browser.scrolled_up.connect(self._on_user_scrolled_up)
        self._browser.scrolled_to_bottom.connect(self._on_user_scrolled_to_bottom)
        layout.addWidget(self._browser)

        # Jump-to-bottom floating button (hidden while at bottom).
        self._jump_btn = QPushButton("↓ 回到底部")
        self._jump_btn.setParent(self._browser)
        self._jump_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._jump_btn.setStyleSheet(
            "QPushButton {"
            "  background: #3d3d3d;"
            "  color: #e0e0e0;"
            "  border: 1px solid #555;"
            "  border-radius: 16px;"
            "  padding: 6px 14px;"
            "  font-size: 12px;"
            "  font-family: " + FONT_SANS + ";"
            "}"
            "QPushButton:hover {"
            "  background: #555;"
            "  color: #fff;"
            "}"
        )
        self._jump_btn.clicked.connect(self._jump_to_bottom)
        self._jump_btn.hide()
        self._jump_btn.raise_()

        # type ∈ {'user', 'ai', 'ai-progress', 'system', 'skill'}
        self._messages: list[tuple[str, str]] = []
        self._user_scrolled_up = False
        self._web_sourced = False

        # When non-None, the next streaming update reuses the document from
        # this position to the end — avoiding a full setHtml() teardown.
        self._streaming_pos: int | None = None

    # ── public API ─────────────────────────────────────────────────────

    def add_user_message(self, text: str):
        self._set_escaped(False)
        self._web_sourced = False
        self._messages.append(("user", text))
        self._streaming_pos = None  # force full rebuild
        self._full_render()

    def add_ai_message(self, text: str):
        self._messages.append(("ai", text))
        self._streaming_pos = None
        self._full_render()

    def add_system_message(self, text: str):
        self._messages.append(("system", text))
        self._streaming_pos = None
        self._full_render()

    def add_skill_message(self, text: str):
        self._messages.append(("skill", text))
        self._streaming_pos = None
        self._full_render()

    def mark_web_sourced(self):
        self._web_sourced = True
        if self._messages and self._messages[-1][0] == "ai-progress":
            self._streaming_pos = None
            self._full_render()

    def add_ai_message_in_progress(self, partial_text: str):
        if self._messages and self._messages[-1][0] == "ai-progress":
            self._messages[-1] = ("ai-progress", partial_text)
        else:
            self._messages.append(("ai-progress", partial_text))
            self._streaming_pos = None  # new streaming sequence → full render first

        if self._streaming_pos is not None:
            # Already tracking the streaming bubble — update in-place.
            self._streaming_update(partial_text)
        else:
            self._full_render()

    def finalize_ai_message(self, final_text: str):
        if self._messages and self._messages[-1][0] == "ai-progress":
            self._messages[-1] = ("ai", final_text)
        else:
            if final_text:
                self._messages.append(("ai", final_text))
        self._streaming_pos = None
        self._full_render()

    def clear(self):
        self._messages.clear()
        self._browser.clear()
        self._streaming_pos = None
        self._web_sourced = False
        self._set_escaped(False)

    def load_history(self, messages: list[tuple[str, str]]):
        """Batch-load messages for session restore (renders once)."""
        self._messages = list(messages)
        self._streaming_pos = None
        self._set_escaped(False)
        self._full_render()

    # ── scroll state ──────────────────────────────────────────────────

    def _on_user_scrolled_up(self):
        self._set_escaped(True)

    def _on_user_scrolled_to_bottom(self):
        self._set_escaped(False)

    def _set_escaped(self, escaped: bool):
        if self._user_scrolled_up == escaped:
            return
        self._user_scrolled_up = escaped
        self.scrolled_up_changed.emit(escaped)
        if escaped:
            self._jump_btn.show()
            self._jump_btn.raise_()
        else:
            self._jump_btn.hide()

    def _jump_to_bottom(self):
        self._set_escaped(False)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """Scroll to document end via text cursor — reliable across setHtml()."""
        cursor = self._browser.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._browser.setTextCursor(cursor)

    # ── rendering ─────────────────────────────────────────────────────

    def _render_bubble_html(self, msg_type: str, text: str) -> str:
        if msg_type == "user":
            return _USER_BUBBLE.format(
                bg=BUBBLE_USER,
                fg=TEXT_PRIMARY,
                border=BUBBLE_USER_BORDER,
                font=FONT_SANS,
                chat_size=_theme.CHAT_FONT_SIZE,
                content=escape(text),
            )
        elif msg_type in ("ai", "ai-progress"):
            content_html = _md_to_html(text)
            if self._web_sourced:
                content_html = (
                    '<div style="margin-bottom:8px;">'
                    '<span style="display:inline-block;background:#E3F2FD;color:#1565C0;'
                    'font-size:11px;font-weight:500;padding:3px 10px;border-radius:10px;'
                    'border:1px solid #BBDEFB;">'
                    "\U0001f310 回答来自网络搜索"
                    '</span></div>'
                ) + content_html
            return _AI_BUBBLE.format(
                bg=BUBBLE_AI,
                fg=TEXT_PRIMARY,
                font=FONT_SANS,
                chat_size=_theme.CHAT_FONT_SIZE,
                icon=_get_icon_data_uri(),
                content=content_html,
            )
        elif msg_type == "skill":
            return _SKILL_MSG.format(
                fg=TEXT_PRIMARY,
                font=FONT_SANS,
                chat_size=_theme.CHAT_FONT_SIZE,
                content=escape(text),
            )
        else:  # system
            return _SYSTEM_MSG.format(
                fg=TEXT_PRIMARY,
                font=FONT_SANS,
                content=escape(text),
            )

    def _build_full_html(self) -> str:
        parts = ['<div style="padding:8px 0;">']
        for msg_type, text in self._messages:
            parts.append(self._render_bubble_html(msg_type, text))
        parts.append("</div>")
        return "".join(parts)

    def _full_render(self):
        """Tear down and rebuild the entire document via setHtml().

        Used for session switch, user message, system message, and the
        *first* frame of a new streaming sequence (so the user bubble
        and the empty AI shell appear together).  Painting is frozen
        until layout finishes so the user never sees a half-built document.
        """
        html = self._build_full_html()

        self._browser.setUpdatesEnabled(False)

        self._browser.setHtml(html)

        # Force the document to lay out synchronously so the scrollbar
        # range is valid before we read it.
        doc = self._browser.document()
        doc.setTextWidth(self._browser.viewport().width())

        # Record streaming anchor for subsequent in-place updates.
        if self._messages and self._messages[-1][0] == "ai-progress":
            block = doc.lastBlock()
            self._streaming_pos = block.position()

        self._browser.setUpdatesEnabled(True)

        if not self._user_scrolled_up:
            self._scroll_to_bottom()

    def _streaming_update(self, partial_text: str):
        """In-place update of the last bubble during streaming.

        Replaces everything from ``_streaming_pos`` to the end of the
        document using QTextCursor.  Because the rest of the document
        (user bubbles, earlier AI turns) is untouched, Qt only re-lays
        out the tail — no full-document teardown, no flicker.
        """
        doc = self._browser.document()
        cursor = QTextCursor(doc)
        cursor.setPosition(self._streaming_pos)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)

        new_html = self._render_bubble_html("ai-progress", partial_text)

        self._browser.setUpdatesEnabled(False)

        cursor.removeSelectedText()
        cursor.insertHtml(new_html)

        if not self._user_scrolled_up:
            self._scroll_to_bottom()

        self._browser.setUpdatesEnabled(True)

    # ── resize ────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_jump_button()

    def _reposition_jump_button(self):
        btn = self._jump_btn
        bw = self._browser.width()
        bh = self._browser.height()
        bw_btn = btn.sizeHint().width()
        x = (bw - bw_btn) // 2
        y = bh - 48
        btn.move(x, y)
