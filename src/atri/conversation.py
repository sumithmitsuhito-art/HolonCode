import json
from pathlib import Path
from atri.models import Message, ToolCall, FunctionCall
from atri import DATA_DIR

_SESSIONS_DIR = DATA_DIR / "sessions"


class ConversationManager:
    """Per-session conversation history backed by data/sessions/{id}.json."""

    def __init__(self):
        self.history: list[Message] = []
        self._session_id: str | None = None

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @session_id.setter
    def session_id(self, value: str | None):
        self._session_id = value

    @property
    def _file_path(self) -> Path:
        return _SESSIONS_DIR / f"{self._session_id}.json"

    def content_init(self):
        self._load_history()

    def save_history(self):
        if not self._session_id:
            return
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        messages = [_msg_to_dict(msg) for msg in self.history]
        self._file_path.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load_history(self):
        if not self._session_id:
            return
        self._migrate_old_format()
        p = self._file_path
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return
            for item in data:
                msg = _dict_to_msg(item)
                if msg is not None:
                    self.history.append(msg)
        except (json.JSONDecodeError, OSError):
            pass

    def _migrate_old_format(self):
        """Split old ConversationHistory.json into per-session files."""
        old = DATA_DIR / "ConversationHistory.json"
        if not old.exists():
            return
        try:
            all_data = json.loads(old.read_text(encoding="utf-8"))
            if not isinstance(all_data, dict):
                old.unlink()
                return
            _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            for sid, messages in all_data.items():
                if not isinstance(messages, list):
                    continue
                dst = _SESSIONS_DIR / f"{sid}.json"
                if not dst.exists():
                    dst.write_text(
                        json.dumps(messages, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
            old.rename(DATA_DIR / "ConversationHistory.json.bak")
        except (json.JSONDecodeError, OSError):
            pass

    @staticmethod
    def delete_session_history(session_id: str):
        p = _SESSIONS_DIR / f"{session_id}.json"
        if p.exists():
            p.unlink()


def _msg_to_dict(msg: Message) -> dict:
    d: dict = {"role": msg.role, "content": msg.content}
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                } if tc.function else None,
            }
            for tc in msg.tool_calls
        ]
    if msg.tool_call_id:
        d["tool_call_id"] = msg.tool_call_id
    return d


def _dict_to_msg(item: dict) -> Message | None:
    role = item.get("role")
    if role == "system" and "【历史对话摘要】" not in str(item.get("content", "")):
        return None
    msg = Message(
        role=role,
        content=item.get("content"),
        tool_call_id=item.get("tool_call_id"),
    )
    if item.get("tool_calls"):
        msg.tool_calls = [
            ToolCall(
                id=tc["id"],
                type=tc.get("type", "function"),
                function=FunctionCall(
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                ),
            )
            for tc in item["tool_calls"]
        ]
    return msg
