"""Main application window: three-panel shell with AI integration."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from atri.ai_service import AIService
from atri.ui.chat_view import ChatView
from atri.ui.file_panel import FilePanel
from atri.ui.settings_dialog import SettingsDialog
from atri.ui.sidebar import (
    Sidebar,
    create_session,
    get_last_active_session,
    list_sessions,
    save_last_active_session,
)
from atri.ui.status_bar import StatusBar
from atri.ui.progress_dialog import ProgressDialog
from atri.ui import theme as _theme
from atri.ui.theme import (
    BG_MAIN,
    BG_TITLEBAR,
    FONT_SANS,
    FONT_SIZE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from atri.ui.worker import AIWorker


class AppShell(QMainWindow):
    """Hermes-style three-panel desktop chat window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HolonCode")
        self.setMinimumSize(1024, 640)
        self.resize(1400, 860)

        # --- Core services ---
        self.ai_service = AIService()
        self.ai_service.initialization()
        self._worker: AIWorker | None = None
        self._current_session_id: str | None = None
        self._current_ai_text: str = ""

        # --- Build UI ---
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Titlebar
        titlebar = QWidget()
        titlebar.setFixedHeight(40)
        titlebar.setStyleSheet(
            f"background-color: {BG_TITLEBAR};"
            f"color: {TEXT_PRIMARY};"
            f"font-family: {FONT_SANS};"
            f"font-size: {FONT_SIZE}px;"
            f"padding-left: 12px;"
        )
        tb_layout = QHBoxLayout(titlebar)
        tb_layout.setContentsMargins(12, 0, 12, 0)
        title_label = QLabel("HolonCode")
        title_label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold;")
        tb_layout.addWidget(title_label)
        tb_layout.addStretch()
        settings_btn = QPushButton("设置")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet(
            f"QPushButton {{"
            f"background: transparent;"
            f"color: {TEXT_SECONDARY};"
            f"border: none;"
            f"font-size: {FONT_SIZE - 1}px;"
            f"font-weight: normal;"
            f"}}"
            f"QPushButton:hover {{ color: {TEXT_PRIMARY}; }}"
        )
        settings_btn.clicked.connect(self._on_open_settings)
        tb_layout.addWidget(settings_btn)
        root.addWidget(titlebar)

        # Three-panel splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self.sidebar = Sidebar()
        self.sidebar.session_selected.connect(self._on_session_selected)
        self.sidebar.session_deleted.connect(self._on_session_deleted)
        self.sidebar.new_session.connect(self._on_new_session)
        self.sidebar.skill_activated.connect(self._on_skill_activated)
        self.sidebar.c_qa_topic_selected.connect(self._on_c_qa_topic)
        self.sidebar.view_progress.connect(self._on_view_progress)
        self.sidebar.level_selected.connect(self._on_level_selected)

        self.chat_view = ChatView()
        self.chat_view.message_submitted.connect(self._on_user_message)

        self.file_panel = FilePanel()
        self.file_panel.file_submit_requested.connect(self._on_file_submit)

        self._splitter.addWidget(self.sidebar)
        self._splitter.addWidget(self.chat_view)
        self._splitter.addWidget(self.file_panel)
        self._splitter.setSizes([260, 880, 260])
        root.addWidget(self._splitter, 1)

        # Status bar
        self.status_bar = StatusBar()
        root.addWidget(self.status_bar)

        # --- Bootstrap: restore last session, or default to QQ session ---
        def _find_or_create_qq_session() -> str:
            sessions = list_sessions()
            for s in sessions:
                if "[QQ]" in s.get("title", ""):
                    return s["id"]
            sid = create_session("[QQ] QQ聊天")
            self.sidebar.refresh()
            return sid

        last_sid = get_last_active_session()
        if last_sid:
            self._switch_session(last_sid)
        else:
            qq_sid = _find_or_create_qq_session()
            self.sidebar.refresh()
            self._switch_session(qq_sid)
        self.sidebar.select_session(self._current_session_id)

        # Wire skill autocomplete
        from atri.skill_loader import SkillLoader
        skills = SkillLoader.list_skills()
        self.chat_view.set_slash_commands(skills)

        # --- QQ Bot ---
        from qqbot import QQBotRunner
        from qqbot.config import QQBotConfig
        self._qq_bot = None
        self._qq_session_id = _find_or_create_qq_session()
        qq_cfg = QQBotConfig.load()
        if qq_cfg.is_configured():
            self._qq_bot = QQBotRunner(
                self.ai_service,
                lambda: self._qq_session_id,
            )
            self._qq_bot.message_received.connect(self._on_qq_message)
            self._qq_bot.status_update.connect(self._on_qq_status)
            self._qq_bot.start()

        # Restore selection in case QQ session creation refreshed the sidebar
        self.sidebar.select_session(self._current_session_id)

    # ── session management ──────────────────────────────────────────

    def _switch_session(self, session_id: str):
        """Save current session, load a different one."""
        if self._current_session_id:
            self._save_current_history()
        self._current_session_id = session_id
        self._current_ai_text = ""
        self.chat_view.thread.clear()
        self._load_history(session_id)
        save_last_active_session(session_id)
        self._update_status()

    def _on_session_selected(self, session_id: str):
        if session_id == self._current_session_id:
            return
        self._switch_session(session_id)

    def _on_session_deleted(self, session_id: str):
        """Handle session deletion: switch away if current session was deleted."""
        if session_id != self._current_session_id:
            return
        remaining = [s for s in list_sessions() if s["id"] != session_id]
        if remaining:
            self._switch_session(remaining[0]["id"])
            self.sidebar.select_session(remaining[0]["id"])
        else:
            sid = create_session("[QQ] QQ聊天")
            self.sidebar.refresh()
            self._switch_session(sid)
            self.sidebar.select_session(sid)

    def _on_new_session(self):
        pass  # handled by sidebar signal → create_session already called

    def _save_current_history(self):
        if not self._current_session_id:
            return
        self.ai_service.conversation.save_history()

    def _load_history(self, session_id: str):
        self.ai_service.conversation.session_id = session_id
        self.ai_service.conversation.history.clear()
        self.ai_service.conversation.content_init()
        # Populate UI from loaded history
        ui_messages = []
        for msg in self.ai_service.conversation.history:
            role = msg.role
            if role == "user":
                ui_messages.append(("user", msg.content or ""))
            elif role == "assistant" and msg.content:
                ui_messages.append(("ai", msg.content))
        self.chat_view.thread.load_history(ui_messages)

    def _update_status(self):
        self.status_bar.set_model(self.ai_service.model)
        turn_count = len(
            [m for m in self.ai_service.conversation.history if m.role == "user"]
        )
        self.status_bar.set_turn_count(turn_count)
        self.status_bar.set_status("就绪")

    def _on_skill_activated(self, skill_name: str):
        """Activate a skill from the sidebar button and kick off the session."""
        from atri.skill_loader import SkillLoader
        if not SkillLoader.skill_exists(skill_name):
            return
        result = self.ai_service.tool.tool_actor(
            "activate_skill",
            f'{{"name":"{skill_name}"}}',
            self.ai_service.active_skills,
        )
        self.chat_view.thread.add_skill_message(result)
        self.status_bar.set_status(f"技能已激活: {skill_name}")
        self._update_status()
        if skill_name == "c-tutor":
            self.chat_view.submit_text("开始C语言知识闯关，先查看我的学习进度，然后从上次的进度继续")
        elif skill_name == "c-learn":
            self.chat_view.submit_text("开始C语言学习，我准备好了，请开始吧")
        elif skill_name == "c-qa":
            self.chat_view.submit_text("开始角色互换学习，我准备好了，你出题吧")

    def _on_c_qa_topic(self, topic: str):
        """Activate c-learn skill and send the topic question to AI."""
        result = self.ai_service.tool.tool_actor(
            "activate_skill",
            '{"name":"c-learn"}',
            self.ai_service.active_skills,
        )
        self.chat_view.thread.add_skill_message(result)
        self.status_bar.set_status("技能已激活: c-learn")
        self._update_status()
        self.chat_view.submit_text(topic)

    def _on_view_progress(self):
        """Open the progress viewer dialog."""
        dlg = ProgressDialog(self)
        dlg.exec()

    def _on_level_selected(self, level_id: str, level_name: str):
        """Activate c-tutor skill with specific level selected."""
        from atri.skill_loader import SkillLoader
        if not SkillLoader.skill_exists("c-tutor"):
            return
        result = self.ai_service.tool.tool_actor(
            "activate_skill",
            '{"name":"c-tutor"}',
            self.ai_service.active_skills,
        )
        self.chat_view.thread.add_skill_message(result)
        self.status_bar.set_status("技能已激活: c-tutor")
        self._update_status()
        if level_id.startswith("debug"):
            level_label = f"改错关卡 {level_id.replace('debug', '')}"
        elif level_id.startswith("choice"):
            level_label = f"选择题关卡 {level_id.replace('choice', '')}"
        elif level_id.startswith("fill"):
            level_label = f"填空题关卡 {level_id.replace('fill', '')}"
        else:
            level_label = f"关卡 {level_id}"
        self.chat_view.submit_text(f"开始闯关{level_label} — {level_name}")

    def _on_file_submit(self, file_path: str):
        """Handle file submit from preview dialog: send '写好了，代码在 {path}' to AI."""
        text = f"写好了，代码在 {file_path}"
        self.chat_view.submit_text(text)

    # ── message flow ─────────────────────────────────────────────────

    def _handle_slash_command(self, text: str) -> bool:
        """Handle slash commands. Returns True if intercepted, False to pass to AI."""
        stripped = text.strip()
        if not stripped.startswith("/"):
            return False

        parts = stripped.split(maxsplit=1)
        command = parts[0][1:]
        trailing = parts[1] if len(parts) > 1 else ""

        # /skills
        if command == "skills":
            from atri.skill_loader import SkillLoader
            skills_list = SkillLoader.list_skills()
            if skills_list:
                msg = "【可用技能】\n" + "\n".join(
                    f"  /{s['name']} — {s['description']}" for s in skills_list
                )
            else:
                msg = "当前没有可用技能"
            self.chat_view.thread.add_system_message(msg)
            return True

        # /skill-name
        from atri.skill_loader import SkillLoader
        if SkillLoader.skill_exists(command):
            result = self.ai_service.tool.tool_actor(
                "activate_skill",
                f'{{"name":"{command}"}}',
                self.ai_service.active_skills,
            )
            self.chat_view.thread.add_skill_message(result)
            self.status_bar.set_status(f"技能已激活: {command}")
            self._update_status()
            if trailing:
                self._dispatch_to_ai(trailing)
            return True

        # Unknown /xxx, pass to AI
        return False

    def _dispatch_to_ai(self, text: str):
        """Send text to AI worker for processing."""
        self.chat_view.thread.add_user_message(text)
        self.chat_view.set_input_enabled(False)
        self.status_bar.set_status("思考中...", busy=True)
        self._current_ai_text = ""

        self._worker = AIWorker(self.ai_service, text)
        self._worker.content_chunk.connect(self._on_content_chunk)
        self._worker.tool_start.connect(self._on_tool_start)
        self._worker.tool_result.connect(self._on_tool_result)
        self._worker.message.connect(self._on_worker_message)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_user_message(self, text: str):
        """User pressed send — intercept slash commands, else dispatch to AI."""
        if self._handle_slash_command(text):
            return
        self._dispatch_to_ai(text.strip())

    def _on_content_chunk(self, text: str):
        self._current_ai_text += text
        self.chat_view.thread.add_ai_message_in_progress(self._current_ai_text)

    def _on_tool_start(self, tool_name: str):
        self.status_bar.set_status(f"调用工具: {tool_name}", busy=True)
        self.chat_view.thread.add_system_message(f"🔧 调用工具: {tool_name}")
        if tool_name in ("web_search", "web_extract"):
            self.chat_view.thread.mark_web_sourced()

    def _on_tool_result(self, tool_name: str, result: str):
        self.status_bar.set_status("思考中...", busy=True)

    def _on_worker_message(self, text: str):
        stripped = text.strip()
        if stripped.startswith("[技能]"):
            self.chat_view.thread.add_skill_message(stripped[4:])
        else:
            self.chat_view.thread.add_system_message(text)

    def _on_error(self, error_text: str):
        self.chat_view.thread.add_system_message(f"❌ {error_text}")
        self.chat_view.thread.finalize_ai_message(self._current_ai_text)
        self._current_ai_text = ""
        self.chat_view.set_input_enabled(True)
        self.status_bar.set_status(f"错误: {error_text}")
        self._save_current_history()
        self._update_status()

    def _on_finished(self):
        self.chat_view.thread.finalize_ai_message(self._current_ai_text)
        self._current_ai_text = ""
        self._save_current_history()
        self.chat_view.set_input_enabled(True)
        self._update_status()

    def _on_qq_message(self, author_name: str, content: str):
        """QQ message received — the handler module manages session + AI reply."""
        pass  # AI reply is handled by QQBotHandler internally

    def _on_qq_status(self, text: str):
        self.status_bar.set_status(f"[QQ] {text}")

    # ── lifecycle ────────────────────────────────────────────────────

    def _on_open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            # Rebuild global stylesheet with new font size
            from PySide6.QtWidgets import QApplication
            from atri.ui.theme import global_stylesheet
            QApplication.instance().setStyleSheet(global_stylesheet())
            # Refresh chat display
            self.chat_view.composer.apply_chat_font_size()
            self.chat_view.thread._full_render()

    def closeEvent(self, event):
        self._save_current_history()
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.quit()
            self._worker.wait(3000)
        if self._qq_bot and self._qq_bot.isRunning():
            self._qq_bot.stop_bot()
        super().closeEvent(event)
