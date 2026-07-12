"""Right-side file browser showing workspace directory."""

from pathlib import Path
import re
from PySide6.QtCore import QDir, QEvent, QEventLoop, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QPlainTextEdit,
    QStackedWidget,
    QTextBrowser,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from pygments.lexers import get_lexer_for_filename, get_lexer_by_name
from pygments.token import Token
from pygments.util import ClassNotFound
import markdown as md_lib

from atri import WORKSPACE_DIR
from code_runner import CodeRunner
from atri.ui.theme import (
    BG_INPUT,
    BG_SIDEBAR,
    BORDER,
    FONT_MONO,
    FONT_SANS,
    FONT_SIZE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


# ── Syntax highlighting ──────────────────────────────────────────────────

_COLOR_MAP = {
    Token.Keyword:            "#0000FF",
    Token.Keyword.Constant:   "#0000FF",
    Token.Keyword.Declaration:"#0000FF",
    Token.Keyword.Namespace:  "#0000FF",
    Token.Name.Function:      "#795E26",
    Token.Name.Class:         "#267FB9",
    Token.Name.Decorator:     "#808000",
    Token.Name.Builtin:       "#267FB9",
    Token.Name.Builtin.Pseudo:"#0000FF",
    Token.String:             "#A31515",
    Token.String.Doc:         "#6A9955",
    Token.Number:             "#098658",
    Token.Comment:            "#6A9955",
    Token.Comment.Special:    "#6A9955",
    Token.Operator:           "#000000",
    Token.Punctuation:        "#000000",
    Token.Generic.Heading:    "#1A2E1A",
    Token.Generic.Subheading: "#1A2E1A",
    Token.Generic.Strong:     "#1A2E1A",
    Token.Generic.Emph:       "#1A2E1A",
    Token.Name.Tag:           "#0000FF",
    Token.Name.Attribute:     "#795E26",
    Token.Text:               "#1A2E1A",
}


def _token_to_format(token_type) -> QTextCharFormat:
    """Map a Pygments token to QTextCharFormat, walking up the hierarchy."""
    fmt = QTextCharFormat()
    color = None
    t = token_type
    while t and color is None:
        color = _COLOR_MAP.get(t)
        t = t.parent
    if color:
        fmt.setForeground(QColor(color))
    if token_type and Token.Keyword in token_type and token_type not in (Token.Keyword.Constant,):
        fmt.setFontWeight(QFont.Bold)
    if token_type and Token.Comment in token_type:
        fmt.setFontItalic(True)
    if token_type and Token.Generic.Heading in token_type:
        fmt.setFontWeight(QFont.Bold)
        fmt.setFontUnderline(True)
    if token_type and Token.Generic.Strong in token_type:
        fmt.setFontWeight(QFont.Bold)
    return fmt


def _get_lexer(file_path: str):
    """Get a Pygments lexer for the given file path, fall back to TextLexer."""
    try:
        return get_lexer_for_filename(file_path, stripnl=False)
    except ClassNotFound:
        return get_lexer_by_name("text", stripnl=False)


class PygmentsHighlighter(QSyntaxHighlighter):
    """QSyntaxHighlighter powered by Pygments lexers."""

    def __init__(self, parent, lexer):
        super().__init__(parent)
        self.lexer = lexer

    def highlightBlock(self, text: str):
        if not text:
            return
        for index, token, value in self.lexer.get_tokens_unprocessed(text):
            fmt = _token_to_format(token)
            self.setFormat(index, len(value), fmt)


# ── Autocomplete ──────────────────────────────────────────────────────────

_KEYWORDS: dict[str, list[str]] = {
    ".py": [
        "and", "as", "assert", "break", "class", "continue", "def", "del",
        "elif", "else", "except", "finally", "for", "from", "global",
        "if", "import", "in", "is", "lambda", "not", "or", "pass",
        "raise", "return", "try", "while", "with", "yield",
        "True", "False", "None", "self",
        "print", "range", "len", "str", "int", "float", "list", "dict", "set", "tuple",
        "open", "enumerate", "zip", "map", "filter", "sorted", "reversed",
        "__init__", "__str__", "__repr__", "__name__", "__main__",
    ],
    ".js": [
        "async", "await", "break", "case", "catch", "class", "const",
        "continue", "debugger", "default", "delete", "do", "else",
        "export", "extends", "finally", "for", "function", "if",
        "import", "in", "instanceof", "let", "new", "of", "return",
        "super", "switch", "this", "throw", "try", "typeof", "var",
        "void", "while", "with", "yield", "true", "false", "null", "undefined",
        "console", "document", "window", "fetch", "Promise", "async",
        "map", "filter", "reduce", "forEach", "find",
    ],
    ".ts": [
        "async", "await", "break", "case", "catch", "class", "const",
        "continue", "debugger", "default", "delete", "do", "else",
        "export", "extends", "finally", "for", "function", "if",
        "import", "in", "instanceof", "let", "new", "of", "return",
        "super", "switch", "this", "throw", "try", "typeof", "var",
        "void", "while", "with", "yield", "true", "false", "null", "undefined",
        "interface", "type", "enum", "readonly", "as", "any", "string",
        "number", "boolean", "void", "never", "unknown",
    ],
    ".html": [
        "DOCTYPE", "html", "head", "body", "meta", "title", "link",
        "script", "style", "div", "span", "p", "a", "img", "ul", "ol", "li",
        "table", "tr", "td", "th", "thead", "tbody", "form", "input",
        "button", "select", "option", "textarea", "label",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "header", "footer", "nav", "main", "section", "article", "aside",
        "class", "id", "href", "src", "alt", "type", "name", "value",
    ],
    ".css": [
        "color", "background", "background-color", "margin", "padding",
        "border", "border-radius", "font-size", "font-family", "font-weight",
        "display", "flex", "grid", "position", "width", "height",
        "top", "left", "right", "bottom", "opacity", "overflow",
        "text-align", "align-items", "justify-content", "flex-direction",
        "gap", "box-shadow", "transition", "transform", "cursor",
        "none", "block", "inline", "inline-block", "relative", "absolute", "fixed",
    ],
    ".java": [
        "abstract", "assert", "boolean", "break", "byte", "case", "catch",
        "char", "class", "continue", "default", "do", "double", "else",
        "enum", "extends", "final", "finally", "float", "for", "if",
        "implements", "import", "int", "interface", "long", "new",
        "package", "private", "protected", "public", "return", "short",
        "static", "super", "switch", "this", "throw", "throws", "try",
        "void", "while", "String", "System", "main",
    ],
    ".cpp": [
        "auto", "bool", "break", "case", "catch", "char", "class",
        "const", "continue", "default", "delete", "do", "double", "else",
        "enum", "false", "float", "for", "friend", "if", "include",
        "int", "long", "namespace", "new", "nullptr", "operator",
        "private", "protected", "public", "return", "short", "sizeof",
        "static", "struct", "switch", "template", "this", "throw",
        "true", "try", "typedef", "typename", "using", "virtual",
        "void", "while", "std", "vector", "string", "cout", "cin",
    ],
    ".c": [
        "auto", "break", "case", "char", "const", "continue", "default",
        "do", "double", "else", "enum", "extern", "float", "for",
        "if", "include", "int", "long", "register", "return", "short",
        "signed", "sizeof", "static", "struct", "switch", "typedef",
        "union", "unsigned", "void", "volatile", "while",
        "NULL", "EOF", "EXIT_SUCCESS", "EXIT_FAILURE",
        "printf", "scanf", "fprintf", "sprintf", "snprintf", "fopen", "fclose",
        "fread", "fwrite", "fgets", "fputs", "fseek", "ftell", "rewind",
        "malloc", "calloc", "realloc", "free",
        "memcpy", "memmove", "memset", "memcmp", "memchr",
        "strcpy", "strncpy", "strlen", "strcmp", "strncmp", "strcat", "strncat",
        "strchr", "strrchr", "strstr", "strtok", "strdup",
        "atoi", "atol", "atof", "itoa", "sprintf",
        "abs", "labs", "rand", "srand", "qsort", "bsearch",
        "time", "clock", "getchar", "putchar", "puts", "gets",
        "assert", "errno", "perror",
        "size_t", "FILE", "stdin", "stdout", "stderr",
        "int8_t", "int16_t", "int32_t", "int64_t", "uint8_t", "uint16_t",
        "uint32_t", "uint64_t", "bool", "true", "false",
    ],
    ".go": [
        "break", "case", "chan", "const", "continue", "default", "defer",
        "else", "fallthrough", "for", "func", "go", "goto", "if",
        "import", "interface", "map", "package", "range", "return",
        "select", "struct", "switch", "type", "var",
        "true", "false", "nil", "int", "string", "bool", "error",
        "fmt", "make", "len", "append", "panic", "recover",
    ],
}


class CompletionPopup(QFrame):
    """Frameless popup for keyword auto-completion."""

    selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip)
        self.setObjectName("completionPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet(
            f"#completionPopup {{"
            f"background-color: {BG_INPUT};"
            f"border: 1px solid {BORDER};"
            f"border-radius: 8px;"
            f"}}"
        )
        self.setFixedWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setStyleSheet(
            f"QListWidget {{"
            f"background: transparent;"
            f"border: none;"
            f"font-family: {FONT_MONO};"
            f"font-size: {FONT_SIZE - 1}px;"
            f"color: {TEXT_PRIMARY};"
            f"}}"
            f"QListWidget::item {{"
            f"padding: 4px 8px;"
            f"border-radius: 4px;"
            f"color: {TEXT_PRIMARY};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"background-color: #E8F5E9;"
            f"color: {TEXT_PRIMARY};"
            f"}}"
        )
        self._list.itemClicked.connect(self._on_clicked)
        layout.addWidget(self._list)

        self._prefix = ""

    def set_items(self, items: list[str], prefix: str):
        self._prefix = prefix
        self._list.clear()
        for item in items:
            self._list.addItem(QListWidgetItem(item))
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._list.setFixedHeight(
            min(self._list.count(), 8) * 28 + 4
        )

    def select_next(self):
        row = (self._list.currentRow() + 1) % self._list.count()
        self._list.setCurrentRow(row)

    def select_prev(self):
        row = (self._list.currentRow() - 1) % self._list.count()
        self._list.setCurrentRow(row)

    def current_text(self) -> str:
        item = self._list.currentItem()
        return item.text() if item else ""

    def _on_clicked(self, item: QListWidgetItem):
        self.selected.emit(item.text())


# ── Error detection ───────────────────────────────────────────────────────

def _check_brackets(text: str) -> str | None:
    """Check for unmatched brackets/parens/braces."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    closers = set(pairs.values())
    stack: list[tuple[str, int]] = []
    for i, ch in enumerate(text):
        if ch in pairs:
            stack.append((ch, i))
        elif ch in closers:
            if not stack:
                return f"多余的 '{ch}'"
            opener, _ = stack.pop()
            if ch != pairs[opener]:
                return f"括号不匹配: 需要 '{pairs[opener]}' 但找到 '{ch}'"
    if stack:
        opener, _ = stack[-1]
        return f"未闭合的 '{opener}'"
    return None


def _check_python_colon(text: str) -> str | None:
    """Check for missing colon after Python compound statements."""
    keywords = ["if", "elif", "else", "for", "while", "def", "class",
                "try", "except", "finally", "with", "match", "case"]
    for line_no, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for kw in keywords:
            if stripped.startswith(kw):
                after = stripped[len(kw):]
                if after == "" or (after[0] in (" ", "(") and not stripped.rstrip().endswith(":")):
                    return f"第 {line_no} 行: '{kw}' 语句可能缺少 ':'"
                break
    return None


def _check_c_errors(text: str) -> str | None:
    """Check for common C-specific errors."""
    lines = text.split("\n")
    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue
        if stripped.startswith("#") or stripped.startswith("*"):
            continue

        # 1) Missing semicolon after return/break/continue with value
        for kw in ("return", "break", "continue"):
            if re.match(rf"{kw}\s+\S", stripped) and not stripped.endswith(";"):
                return f"第 {line_no} 行: '{kw}' 语句可能缺少 ';'"

        # 2) int x = ... or char* p = ... without trailing ;
        m = re.match(
            r"(int|char|float|double|long|short|void|unsigned|signed|size_t|bool)"
            r"\s+[*\s]+\w+\s*=", stripped
        )
        if m and not stripped.endswith(";") and not stripped.endswith("{"):
            return f"第 {line_no} 行: 赋值语句可能缺少 ';'"

    return None


# ── Code editor with line numbers ─────────────────────────────────────────

class _LineNumberArea(QWidget):
    """Gutter widget that paints line numbers for a CodeEditor."""

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return self._editor._line_area_size()

    def paintEvent(self, event):
        self._editor._line_area_paint(event)


class CodeEditor(QPlainTextEdit):
    """QPlainTextEdit with a line number gutter on the left."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line_area = _LineNumberArea(self)

        self.blockCountChanged.connect(self._on_block_count_changed)
        self.updateRequest.connect(self._on_update_request)

        self._on_block_count_changed()

    # ── public for _LineNumberArea ─────────────────────────────────

    def _line_area_size(self):
        digits = max(3, len(str(self.blockCount())))
        w = 10 + self.fontMetrics().horizontalAdvance("9") * digits
        return w, 0

    def _line_area_paint(self, event):
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), QColor(BG_SIDEBAR))

        block = self.firstVisibleBlock()
        block_num = block.blockNumber() + 1
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        fm = self.fontMetrics()
        area_w = self._line_area.width()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor(TEXT_SECONDARY))
                painter.drawText(0, top, area_w - 4, fm.height(),
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                 str(block_num))
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_num += 1

    # ── internals ─────────────────────────────────────────────────

    def _on_block_count_changed(self):
        self.setViewportMargins(self._line_area_size()[0], 0, 0, 0)

    def _on_update_request(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(cr.left(), cr.top(),
                                    self._line_area_size()[0], cr.height())


# ── Run worker ─────────────────────────────────────────────────────────────

class _RunWorker(QThread):
    """Background thread for AI code execution with interactive input support."""
    partial_output = Signal(str)
    need_input = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._input_loop: QEventLoop | None = None
        self._input_value: str = ""

    def run(self):
        try:
            runner = CodeRunner()
            result = runner.run(
                self._file_path,
                on_input=self._on_input,
                on_output=lambda t: self.partial_output.emit(t),
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

    def _on_input(self, prompt: str) -> str:
        self.need_input.emit(prompt)
        self._input_loop = QEventLoop()
        self._input_loop.exec()
        return self._input_value

    def provide_input(self, value: str):
        self._input_value = value
        if self._input_loop and self._input_loop.isRunning():
            self._input_loop.quit()


class RunResultDialog(QDialog):
    """Terminal-style dialog: output and input merged in one editable text area."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"运行结果 — {Path(file_path).name}")
        self.resize(720, 520)
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._terminal = QPlainTextEdit()
        self._terminal.setReadOnly(True)
        self._terminal.setStyleSheet(
            f"background-color: #1E1E1E;"
            f"color: #D4D4D4;"
            f"border: 1px solid {BORDER};"
            f"border-radius: 10px;"
            f"padding: 12px;"
            f"font-family: {FONT_MONO};"
            f"font-size: {FONT_SIZE - 1}px;"
            f"selection-background-color: #264F78;"
        )
        self._terminal.installEventFilter(self)
        layout.addWidget(self._terminal, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._close_btn = QPushButton("关闭")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setEnabled(False)
        btn_layout.addWidget(self._close_btn)
        layout.addLayout(btn_layout)

        self._worker: _RunWorker | None = None
        self._accepting_input = False
        self._input_start = 0

    def start_run(self, file_path: str):
        """Start the code execution worker."""
        self._terminal.setPlainText("")
        self._close_btn.setEnabled(False)

        self._worker = _RunWorker(file_path, self)
        self._worker.partial_output.connect(self._on_partial_output)
        self._worker.need_input.connect(self._on_need_input)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_partial_output(self, text: str):
        cursor = self._terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._terminal.setTextCursor(cursor)
        self._terminal.ensureCursorVisible()

    def _on_need_input(self, prompt: str):
        cursor = self._terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if prompt:
            current = self._terminal.toPlainText()
            if not current.rstrip().endswith(prompt.rstrip()):
                cursor.insertText(prompt)
        self._terminal.setTextCursor(cursor)
        self._input_start = cursor.position()
        self._terminal.setReadOnly(False)
        self._accepting_input = True
        self._terminal.setFocus()

    def _on_finished(self, result: str):
        self._terminal.setReadOnly(True)
        self._close_btn.setEnabled(True)
        self._accepting_input = False

    def _on_error(self, error_text: str):
        cursor = self._terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(f"\n[错误] {error_text}")
        self._terminal.setTextCursor(cursor)
        self._terminal.setReadOnly(True)
        self._close_btn.setEnabled(True)
        self._accepting_input = False

    def eventFilter(self, obj, event):
        if obj == self._terminal and event.type() == QEvent.Type.KeyPress:
            if self._accepting_input and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                text = self._terminal.toPlainText()
                user_input = text[self._input_start:]
                cursor = self._terminal.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertText("\n")
                self._terminal.setTextCursor(cursor)
                self._terminal.setReadOnly(True)
                self._accepting_input = False
                if self._worker:
                    self._worker.provide_input(user_input)
                return True
        return super().eventFilter(obj, event)

    def reject(self):
        if self._worker and self._worker.isRunning():
            self._worker.provide_input("")
            self._worker.quit()
            self._worker.wait(3000)
        super().reject()


# ── File preview dialog ──────────────────────────────────────────────────

class FilePreviewDialog(QDialog):
    """Popup window for viewing and editing a file, with syntax highlighting and markdown preview."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        p = Path(file_path)
        self._file_path = file_path
        self._is_markdown = p.suffix in (".md", ".markdown")
        self._suffix = p.suffix
        self.setWindowTitle(f"预览 — {p.name}")
        self.resize(800, 600)
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Header ──────────────────────────────────────────────────
        header = QHBoxLayout()
        path_label = QLabel(str(p))
        path_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-family: {FONT_SANS};"
            f"font-size: {FONT_SIZE - 2}px;"
        )
        header.addWidget(path_label)
        header.addStretch()

        self._is_code = p.suffix in _KEYWORDS

        if self._is_markdown:
            self._preview_btn = QPushButton("预览")
            self._preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._preview_btn.clicked.connect(self._toggle_preview)
            header.addWidget(self._preview_btn)

        if self._is_code:
            self._run_btn = QPushButton("运行")
            self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._run_btn.clicked.connect(self._on_run)
            header.addWidget(self._run_btn)
        else:
            self._run_btn = None

        layout.addLayout(header)

        # ── Stacked: editor | preview ────────────────────────────────
        self._stack = QStackedWidget()

        # Page 0 — Editor
        self._editor = CodeEditor()
        self._editor.setStyleSheet(
            f"background-color: {BG_INPUT};"
            f"color: {TEXT_PRIMARY};"
            f"border: 1px solid {BORDER};"
            f"border-radius: 10px;"
            f"padding: 12px;"
            f"font-family: {FONT_MONO};"
            f"font-size: {FONT_SIZE - 1}px;"
        )
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            content = ""
        self._editor.setPlainText(content)
        self._stack.addWidget(self._editor)

        # Page 1 — Markdown preview
        self._preview = QTextBrowser()
        self._preview.setStyleSheet(
            f"background-color: {BG_INPUT};"
            f"color: {TEXT_PRIMARY};"
            f"border: 1px solid {BORDER};"
            f"border-radius: 10px;"
            f"padding: 12px;"
            f"font-family: {FONT_SANS};"
            f"font-size: {FONT_SIZE}px;"
        )
        self._preview.setOpenExternalLinks(True)
        self._stack.addWidget(self._preview)

        layout.addWidget(self._stack, 1)

        # ── Error indicator ────────────────────────────────────────
        self._error_label = QLabel()
        self._error_label.setStyleSheet(
            f"color: #C72E4D; font-family: {FONT_MONO};"
            f"font-size: {FONT_SIZE - 2}px; padding: 2px 4px;"
        )
        self._error_label.hide()
        layout.addWidget(self._error_label)

        # Apply syntax highlighting
        lexer = _get_lexer(file_path)
        self._highlighter = PygmentsHighlighter(self._editor.document(), lexer)

        # ── Autocomplete setup ───────────────────────────────────────
        self._keywords = _KEYWORDS.get(p.suffix, [])
        self._completion = CompletionPopup(self)
        self._completion.selected.connect(self._insert_completion)
        if self._keywords:
            self._editor.installEventFilter(self)
            self._editor.textChanged.connect(self._on_text_changed)

        # ── Error checking ──────────────────────────────────────────
        self._editor.textChanged.connect(self._check_errors)
        self._check_errors()

        # ── Buttons ─────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def eventFilter(self, obj, event):
        if obj == self._editor and event.type() == QEvent.Type.KeyPress:
            if self._completion.isVisible():
                key = event.key()
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                    self._insert_completion(self._completion.current_text())
                    return True
                if key == Qt.Key.Key_Escape:
                    self._completion.hide()
                    return True
                if key == Qt.Key.Key_Up:
                    self._completion.select_prev()
                    return True
                if key == Qt.Key.Key_Down:
                    self._completion.select_next()
                    return True
        return super().eventFilter(obj, event)

    def _on_text_changed(self):
        tc = self._editor.textCursor()
        tc.movePosition(QTextCursor.MoveOperation.StartOfWord, QTextCursor.MoveMode.KeepAnchor)
        prefix = tc.selectedText()
        if len(prefix) < 2:
            self._completion.hide()
            return
        matches = [kw for kw in self._keywords if kw.startswith(prefix) and kw != prefix]
        if not matches:
            self._completion.hide()
            return
        self._completion.set_items(matches, prefix)
        rect = self._editor.cursorRect()
        pos = self._editor.viewport().mapToGlobal(rect.bottomLeft())
        self._completion.move(pos)
        self._completion.show()

    def _insert_completion(self, text: str):
        if not text:
            return
        tc = self._editor.textCursor()
        tc.movePosition(QTextCursor.MoveOperation.StartOfWord, QTextCursor.MoveMode.KeepAnchor)
        tc.insertText(text)
        self._editor.setTextCursor(tc)
        self._completion.hide()

    def _check_errors(self):
        """Run simple syntax checks and show first error found."""
        text = self._editor.toPlainText()
        error = _check_brackets(text)
        if error is None and self._suffix == ".py":
            error = _check_python_colon(text)
        if error is None and self._suffix in (".c", ".cpp", ".h"):
            error = _check_c_errors(text)
        if error:
            self._error_label.setText(f"⚠ {error}")
            self._error_label.show()
        else:
            self._error_label.hide()

    def _toggle_preview(self):
        if self._stack.currentIndex() == 0:
            html = md_lib.markdown(
                self._editor.toPlainText(),
                extensions=["fenced_code", "codehilite", "tables"],
            )
            self._preview.setHtml(html)
            self._stack.setCurrentIndex(1)
            self._preview_btn.setText("编辑")
        else:
            self._stack.setCurrentIndex(0)
            self._preview_btn.setText("预览")

    def _on_run(self):
        """Save the file, then simulate execution via AI."""
        try:
            Path(self._file_path).write_text(
                self._editor.toPlainText(), encoding="utf-8"
            )
        except OSError as e:
            self._error_label.setText(f"⚠ 保存失败: {e}")
            self._error_label.show()
            return

        self._run_btn.setEnabled(False)
        self._run_btn.setText("运行中...")
        self._error_label.hide()

        dlg = RunResultDialog(self._file_path, self)
        dlg.start_run(self._file_path)
        dlg.exec()

        self._run_btn.setEnabled(True)
        self._run_btn.setText("运行")

    def _on_save(self):
        # Always save from editor content (whether in edit or preview mode)
        try:
            Path(self._file_path).write_text(
                self._editor.toPlainText(), encoding="utf-8"
            )
            self.accept()
        except OSError as e:
            self._editor.setPlaceholderText(f"保存失败: {e}")

    def reject(self):
        super().reject()


# ── File panel ────────────────────────────────────────────────────────────

class FilePanel(QFrame):
    """Tree view of workspace/ directory."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filePanel")
        self.setStyleSheet(f"#filePanel {{ background-color: {BG_SIDEBAR}; }}")
        self.setMinimumWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("workspace")
        title.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-weight: bold; padding: 4px 0;"
        )
        layout.addWidget(title)

        self._model = QFileSystemModel()
        self._model.setRootPath(str(WORKSPACE_DIR))
        self._model.setFilter(
            QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs | QDir.Filter.Files
        )

        self._tree = QTreeView()
        self._tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._tree.setModel(self._model)
        self._tree.setRootIndex(self._model.index(str(WORKSPACE_DIR)))
        self._tree.setHeaderHidden(True)
        self._tree.setColumnHidden(1, True)
        self._tree.setColumnHidden(2, True)
        self._tree.setColumnHidden(3, True)
        self._tree.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tree.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._tree, 1)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn)

        explorer_btn = QPushButton("在资源管理器中打开")
        explorer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        explorer_btn.clicked.connect(self._open_in_explorer)
        layout.addWidget(explorer_btn)

    def _on_double_click(self, index):
        file_path = self._model.filePath(index)
        p = Path(file_path)
        if p.is_file():
            dlg = FilePreviewDialog(file_path, self)
            dlg.exec()

    def _refresh(self):
        self._model.setRootPath(str(WORKSPACE_DIR))
        self._tree.setRootIndex(self._model.index(str(WORKSPACE_DIR)))

    def _open_in_explorer(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(WORKSPACE_DIR)))
