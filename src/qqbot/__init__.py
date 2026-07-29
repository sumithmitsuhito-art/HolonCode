import asyncio
import logging
from PySide6.QtCore import QThread, Signal
from .config import QQBotConfig
from .connection import QQBotConnection
from .handler import QQBotHandler

logger = logging.getLogger(__name__)

QQ_SESSION_TITLE = "[QQ] QQ聊天"


class QQBotRunner(QThread):
    """QThread that runs the QQ Bot asyncio event loop.

    Emits signals for AppShell to update the QQ session UI.
    """
    message_received = Signal(str, str)  # (author_name, content)
    reply_sent = Signal(str, str)  # (author_name, reply_text)
    status_update = Signal(str)  # connection status messages

    def __init__(self, ai_service, get_qq_session_id, parent=None):
        super().__init__(parent)
        self._ai_service = ai_service
        self._get_qq_session_id = get_qq_session_id
        self._connection: QQBotConnection | None = None
        self._handler: QQBotHandler | None = None
        self._loop = None

    def run(self):
        try:
            self._run()
        except Exception as e:
            print(f"[QQBot] 线程异常: {e}")
            logger.exception("QQ Bot runner crashed: %s", e)
            self.status_update.emit(f"QQ Bot 异常: {e}")

    def _run(self):
        cfg = QQBotConfig.load()
        if not cfg.is_configured():
            print("[QQBot] 未配置凭据，跳过 (请在 data/UserSettings.json 中设置 QQBot.AppId 和 QQBot.ClientSecret)")
            self.status_update.emit("QQ Bot 未配置，跳过")
            return

        print(f"[QQBot] 凭据已加载 AppId={cfg.app_id[:8]}***, 开始连接...")
        self.status_update.emit("QQ Bot 正在连接...")
        self._connection = QQBotConnection(cfg.app_id, cfg.client_secret)
        self._handler = QQBotHandler(
            cfg.app_id, cfg.client_secret,
            self._ai_service,
            self._get_qq_session_id,
        )

        async def on_message(event_type: str, payload: dict):
            parsed = self._parse_for_ui(event_type, payload)
            if parsed:
                self.message_received.emit(
                    parsed["author_name"], parsed["content"]
                )
            await self._handler.handle_message(event_type, payload)

        self._connection.set_message_callback(on_message)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            print("[QQBot] 事件循环已启动，开始 WebSocket 连接...")
            self.status_update.emit("QQ Bot 已连接")
            loop.run_until_complete(self._connection.connect())
        except Exception as e:
            print(f"[QQBot] 连接错误: {e}")
            logger.exception("QQ Bot connection error: %s", e)
            self.status_update.emit(f"QQ Bot 连接失败: {e}")
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
            self._loop = None
            print("[QQBot] 线程已退出")
            self.status_update.emit("QQ Bot 已断开")

    def stop_bot(self):
        print("[QQBot] 正在停止...")
        if self._connection:
            self._connection._running = False
            loop = self._loop
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._connection.stop(), loop
                )
        self.quit()
        self.wait(1000)
        print("[QQBot] 已停止")

    @staticmethod
    def _parse_for_ui(event_type: str, payload: dict) -> dict | None:
        from .handler import _parse_inbound
        return _parse_inbound(event_type, payload)
