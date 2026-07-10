import sys
import asyncio

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import QThread, Signal

from atri.ai_service import AIService
from atri.ui.chat_ui import Ui_MainWindow


class AIWorker(QThread):
    content_received = Signal(str)
    tool_start = Signal(str)
    message_received = Signal(str)
    error_received = Signal(str)
    done = Signal()

    def __init__(self, ai_service: AIService, message: str):
        super().__init__()
        self.ai_service = ai_service
        self.message = message
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def handle_chat():
            gen = self.ai_service.ai_chat(self.message)
            try:
                async for event in gen:
                    if self._stop_flag:
                        break
                    if event.type == "content":
                        self.content_received.emit(event.text)
                    elif event.type == "tool_start":
                        self.tool_start.emit(event.tool_name)
                    elif event.type == "message":
                        self.message_received.emit(event.text)
                    elif event.type == "done":
                        self.done.emit()
                        break
                    elif event.type == "error":
                        self.error_received.emit(event.text)
                        break
            except Exception as e:
                self.error_received.emit(f"发生错误: {str(e)}")
            finally:
                await gen.aclose()

        try:
            loop.run_until_complete(handle_chat())
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.ai_service = AIService()
        self.ai_service.initialization()
        self._worker = None

        self.knowledge_points = [
            "变量与数据类型", "运算符与表达式", "控制流", "数组",
            "指针", "函数与递归", "结构体", "文件操作"
        ]
        self.knowledge_combo.addItems(self.knowledge_points)

        self.send_btn.clicked.connect(self.send_message)
        self.input_edit.returnPressed.connect(self.send_message)
        self.start_btn.clicked.connect(self.start_teaching)
        self.input_edit.textChanged.connect(lambda t: self.send_btn.setEnabled(bool(t.strip())))

        self.append_message("🧑‍🎓", "学长，你好！我是你的C语言学弟，今天想学习什么呀？")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.quit()
            self._worker.wait(3000)
        super().closeEvent(event)

    def append_message(self, avatar: str, text: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(f"{avatar} {text}\n\n")
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def send_message(self):
        message = self.input_edit.text().strip()
        if not message:
            return
        self.append_message("👤", message)
        self.input_edit.clear()

        self._worker = AIWorker(self.ai_service, message)
        self._worker.content_received.connect(self.append_content)
        self._worker.tool_start.connect(lambda n: self.append_message("🔧", f"调用工具: {n}"))
        self._worker.message_received.connect(lambda t: self.append_message("📢", t))
        self._worker.error_received.connect(lambda e: self.append_message("❌", f"错误: {e}"))
        self._worker.done.connect(lambda: self.chat_display.append("\n"))
        self._worker.start()

    def append_content(self, text: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def start_teaching(self):
        knowledge = self.knowledge_combo.currentText()
        if not knowledge:
            QMessageBox.warning(self, "提示", "请先选择一个知识点！")
            return
        self.input_edit.setText(f"我们开始学习「{knowledge}」吧！")
        self.send_message()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
