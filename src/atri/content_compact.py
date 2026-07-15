import json
from datetime import datetime
from atri.models import Message
import httpx


class ContentCompact:
    keep_rounds: int = 10
    compress_batch: int = 5
    max_summaries: int = 10
    summary_prefix: str = "【历史对话摘要】"

    def __init__(self, api_key: str, api_url: str, model: str):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model

    async def compact_async(self, history: list[Message]) -> bool:
        sys_end = 0
        if history and history[0].role == "system":
            sys_end = 1
        rounds = self._split_rounds(history, sys_end)
        if len(rounds) <= self.keep_rounds:
            return False
        compress_count = min(self.compress_batch, len(rounds) - self.keep_rounds)
        to_compress = []
        for i in range(compress_count):
            to_compress.extend(rounds[i])
        summary = await self._generate_summary(to_compress)
        if not summary:
            return False
        remove_start = history.index(rounds[0][0])
        remove_count = sum(len(r) for r in rounds[:compress_count])
        del history[remove_start : remove_start + remove_count]
        now = datetime.now()
        time = now.strftime("%m-%d %H:%M")
        history.insert(sys_end, Message(
            role="system",
            content=f"({time}) {self.summary_prefix}{summary}"
        ))
        self._trim_summaries(history, sys_end)
        return True

    @classmethod
    def _split_rounds(cls, history: list[Message], start_idx: int) -> list[list[Message]]:
        rounds = []
        current = None
        for i in range(start_idx, len(history)):
            if history[i].role == "user":
                current = []
                rounds.append(current)
            if current is not None:
                current.append(history[i])
        return rounds

    @classmethod
    def count_rounds(cls, history: list[Message]) -> int:
        start = 0
        if history and history[0].role == "system":
            start = 1
        return len(cls._split_rounds(history, start))

    @classmethod
    def should_compact(cls, history: list[Message]) -> bool:
        return cls.count_rounds(history) >= cls.keep_rounds + cls.compress_batch

    @classmethod
    def _trim_summaries(cls, history: list[Message], start_idx: int):
        indices = []
        for i in range(start_idx, len(history)):
            msg = history[i]
            if msg.role == "system" and msg.content and cls.summary_prefix in msg.content:
                indices.append(i)
            else:
                break
        excess = len(indices) - cls.max_summaries
        for _ in range(excess):
            oldest = indices[-1]
            history.pop(oldest)
            indices.pop()

    async def _generate_summary(self, messages: list[Message]) -> str | None:
        try:
            summary_msgs = [
                Message(
                    role="system",
                    content="你是一个摘要助手。请用简洁的中文总结以下对话，保留关键信息（用户问题、AI操作、重要结论），控制在200字以内。"
                )
            ]
            summary_msgs.extend(m for m in messages if m.role != "system")
            summary_msgs.append(Message(role="user", content="请总结以上对话。"))
            body = {
                "model": self.model,
                "messages": [
                    {"role": m.role, "content": m.content}
                    for m in summary_msgs
                ],
                "stream": False,
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.api_url,
                    json=body,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception:
            return None
