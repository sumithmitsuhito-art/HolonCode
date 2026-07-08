import json
from pathlib import Path
from atri.models import Message, ToolCall, FunctionCall
from atri import DATA_DIR


class ConversationManager:
    history_file: str = str(DATA_DIR / "ConversationHistory.json")

    def __init__(self):
        self.history: list[Message] = []

    def content_init(self):
        """Load conversation history from disk. System prompt is built dynamically per-request."""
        self._load_history()

    def save_history(self):
        p = Path(self.history_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = []
        for msg in self.history:
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
            data.append(d)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_history(self):
        p = Path(self.history_file)
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for item in data:
                role = item.get("role")
                # Skip old bare system messages — system prompt is now built dynamically.
                # Keep "system" messages that are compressed summaries (contain the summary prefix).
                if role == "system" and "【历史对话摘要】" not in str(item.get("content", "")):
                    continue
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
                self.history.append(msg)
        except (json.JSONDecodeError, OSError, KeyError):
            pass
