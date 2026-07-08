import json
from datetime import datetime
from typing import AsyncGenerator
import httpx
from atri import DATA_DIR
from atri.models import Message, ToolCall, FunctionCall, StreamEvent
from atri.prompt_manager import PromptManager
from atri.tool_manager import ToolManager
from atri.conversation import ConversationManager
from atri.content_compact import ContentCompact


class AIService:
    def __init__(self):
        self.api_key: str = ""
        self.url: str = ""
        self.model: str = ""
        self.active_skills: list[str] = []
        self.prompt_manager = PromptManager()
        self.tool = ToolManager()
        self.conversation = ConversationManager()
        self.content_compact: ContentCompact | None = None

    def initialization(self):
        self.tool.tool_init()
        self.conversation.content_init()
        config_path = DATA_DIR / "UserSettings.json"
        if not config_path.exists():
            print("api配置错误：找不到 data/UserSettings.json")
            return
        config = json.loads(config_path.read_text(encoding="utf-8"))
        ds = config.get("DeepSeek", {})
        self.api_key = ds.get("ApiKey", "")
        self.url = ds.get("Url", "")
        self.model = ds.get("Model", "")
        if not self.api_key:
            print("api配置错误")
            return
        if not self.url:
            print("url配置错误")
            return
        if not self.model:
            print("model配置错误")
            return
        self.content_compact = ContentCompact(self.api_key, self.url, self.model)

    async def ai_chat(self, user_input: str) -> AsyncGenerator[StreamEvent, None]:
        """流式对话，逐 token 产出 StreamEvent。

        内部维护工具调用循环：如果模型返回 tool_calls，
        执行工具后自动重新调用 API，直到获得文本回复。
        """
        try:
            now = datetime.now()
            time = now.strftime("%m-%d %H:%M")
            self.conversation.history.append(Message(
                role="user", content=f"({time})：{user_input}"
            ))

            async with httpx.AsyncClient(timeout=60) as client:
                while True:
                    system_msg = Message(
                        role="system",
                        content=self.prompt_manager.build_system_prompt(self.active_skills),
                    )
                    messages = [self._msg_to_dict(system_msg)] + [
                        self._msg_to_dict(m)
                        for m in self.conversation.history
                    ]
                    body = {
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                        "thinking": {"type": "disabled"},
                        "tools": [
                            {
                                "type": t.type,
                                "function": {
                                    "name": t.function.name,
                                    "description": t.function.description,
                                    "parameters": t.function.parameters,
                                },
                            }
                            for t in self.tool.tool_list
                        ],
                    }

                    tool_calls_buffer: dict[int, dict] = {}
                    content_parts: list[str] = []
                    finish_reason: str | None = None

                    async with client.stream(
                        "POST",
                        self.url,
                        json=body,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    ) as resp:
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            delta = chunk["choices"][0].get("delta", {})
                            finish_reason = chunk["choices"][0].get("finish_reason")

                            for event in self._accumulate_sse_delta(delta, tool_calls_buffer):
                                if event.type == "content":
                                    content_parts.append(event.text)
                                yield event

                    # --- 处理本轮结果 ---
                    if finish_reason == "stop":
                        full_content = "".join(content_parts)
                        self.conversation.history.append(Message(
                            role="assistant", content=full_content
                        ))
                        self.conversation.save_history()
                        if ContentCompact.should_compact(self.conversation.history):
                            await self.content_compact.compact_async(
                                self.conversation.history
                            )
                            self.conversation.save_history()
                        yield StreamEvent(type="done")
                        return

                    elif finish_reason == "tool_calls":
                        if not tool_calls_buffer:
                            yield StreamEvent(
                                type="error",
                                text="API 返回 tool_calls 但未包含工具调用数据",
                            )
                            return

                        tool_calls = []
                        for idx in sorted(tool_calls_buffer.keys()):
                            buf = tool_calls_buffer[idx]
                            tool_calls.append(ToolCall(
                                id=buf["id"],
                                type="function",
                                function=FunctionCall(
                                    name=buf["name"],
                                    arguments=buf["arguments"],
                                ),
                            ))
                        self.conversation.history.append(Message(
                            role="assistant", tool_calls=tool_calls
                        ))

                        for tc in tool_calls:
                            name = tc.function.name
                            prev_skills = set(self.active_skills)
                            try:
                                result = self.tool.tool_actor(
                                    name,
                                    tc.function.arguments or "{}",
                                    self.active_skills,
                                )
                            except Exception as exc:
                                result = f"工具执行异常: {exc}"
                                yield StreamEvent(
                                    type="message",
                                    text=f"  [警告] {name} 执行失败: {exc}",
                                )

                            if name == "activate_skill":
                                added = set(self.active_skills) - prev_skills
                                if added:
                                    yield StreamEvent(
                                        type="message",
                                        text=f"  [技能] 已激活: {', '.join(added)}",
                                    )
                            elif name == "deactivate_skill":
                                removed = prev_skills - set(self.active_skills)
                                if removed:
                                    yield StreamEvent(
                                        type="message",
                                        text=f"  [技能] 已关闭: {', '.join(removed)}",
                                    )

                            self.conversation.history.append(Message(
                                role="tool",
                                tool_call_id=tc.id,
                                content=result,
                            ))
                            yield StreamEvent(
                                type="tool_result",
                                tool_name=name,
                                text=result or "",
                            )

                        continue

                    elif finish_reason == "length":
                        if content_parts:
                            full_content = "".join(content_parts)
                            self.conversation.history.append(Message(
                                role="assistant", content=full_content
                            ))
                            self.conversation.save_history()
                        yield StreamEvent(
                            type="error",
                            text="响应达到 token 上限，回复可能不完整",
                        )
                        return

                    elif finish_reason == "content_filter":
                        yield StreamEvent(
                            type="error",
                            text="响应被内容过滤器拦截",
                        )
                        return

                    elif finish_reason == "insufficient_system_resource":
                        yield StreamEvent(
                            type="error",
                            text="服务端资源不足，请稍后重试",
                        )
                        return

                    else:
                        if content_parts:
                            full_content = "".join(content_parts)
                            self.conversation.history.append(Message(
                                role="assistant", content=full_content
                            ))
                            self.conversation.save_history()
                            yield StreamEvent(type="done")
                        else:
                            yield StreamEvent(
                                type="error",
                                text=f"流意外终止 (finish_reason={finish_reason})",
                            )
                        return

        except httpx.HTTPStatusError as e:
            yield StreamEvent(type="error", text=f"API 请求失败 ({e.response.status_code})")
        except httpx.HTTPError as e:
            yield StreamEvent(type="error", text=f"网络请求失败：{e}")
        except (json.JSONDecodeError, KeyError) as e:
            yield StreamEvent(type="error", text=f"返回数据解析失败：{e}")
        except Exception as e:
            yield StreamEvent(type="error", text=f"未知错误：{e}")

    @staticmethod
    def _accumulate_sse_delta(
        delta: dict,
        tool_calls_buffer: dict[int, dict],
    ) -> list[StreamEvent]:
        """处理单个 SSE delta chunk。

        更新 tool_calls_buffer（按 index 分桶累积 tool_call 碎片），
        返回本 chunk 产出的 StreamEvent 列表。
        """
        events: list[StreamEvent] = []

        if delta.get("content"):
            events.append(StreamEvent(type="content", text=delta["content"]))

        if "tool_calls" in delta:
            for tc in delta["tool_calls"]:
                idx = tc.get("index", 0)
                if idx not in tool_calls_buffer:
                    tool_calls_buffer[idx] = {"id": None, "name": None, "arguments": ""}

                buf = tool_calls_buffer[idx]
                if tc.get("id"):
                    buf["id"] = tc["id"]

                func = tc.get("function", {})
                if func.get("name"):
                    buf["name"] = func["name"]
                    events.append(StreamEvent(type="tool_start", tool_name=func["name"]))
                if func.get("arguments"):
                    buf["arguments"] += func["arguments"]

        return events

    @staticmethod
    def _msg_to_dict(msg: Message) -> dict:
        d: dict = {"role": msg.role}
        if msg.content is not None:
            d["content"] = msg.content
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        return d
