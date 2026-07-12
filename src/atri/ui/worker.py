"""Background thread that runs AIService.ai_chat() without blocking the UI."""

import asyncio
from PySide6.QtCore import QThread, Signal
from atri.ai_service import AIService


class AIWorker(QThread):
    """Runs the async AI chat loop on a background QThread.

    Emits signals for each StreamEvent type so the UI thread stays responsive.
    """

    content_chunk = Signal(str)
    tool_start = Signal(str)
    tool_result = Signal(str, str)
    message = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, ai_service: AIService, user_input: str):
        super().__init__()
        self.ai_service = ai_service
        self.user_input = user_input
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def handle_chat():
            gen = self.ai_service.ai_chat(self.user_input)
            try:
                async for event in gen:
                    if self._stop_flag:
                        break
                    if event.type == "content":
                        self.content_chunk.emit(event.text)
                    elif event.type == "tool_start":
                        self.tool_start.emit(event.tool_name or "")
                    elif event.type == "tool_result":
                        self.tool_result.emit(
                            event.tool_name or "",
                            event.text or "",
                        )
                    elif event.type == "message":
                        self.message.emit(event.text)
                    elif event.type == "done":
                        self.finished.emit()
                        return
                    elif event.type == "error":
                        self.error.emit(event.text)
                        return
            except Exception as exc:
                self.error.emit(str(exc))
            finally:
                await gen.aclose()

        try:
            loop.run_until_complete(handle_chat())
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
