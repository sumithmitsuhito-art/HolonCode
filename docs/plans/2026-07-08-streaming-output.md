# ATRI 流式输出 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 ATRI CLI 聊天应用从"等待完整响应 → 一次性输出"改造为 ChatGPT 式的逐 token 实时流式输出。

**Architecture:** 核心改造在 `ai_service.py` 的 `ai_chat()` 方法：从 `stream: False` + 完整 JSON 返回，改为 `stream: True` + SSE chunk 解析 + `AsyncGenerator[StreamEvent]`。`main.py` 改为 `async for` 迭代生成器事件，用 `console.print(chunk, end="")` 逐字打印。工具调用通过跨 chunk 累积 `tool_calls_buffer` 来处理增量到达的碎片。**零新依赖**，只使用已有的 `httpx` + `rich`。

**Tech Stack:** Python 3.12+, httpx (streaming via `aiter_lines()`), rich (终端实时输出), DeepSeek API (OpenAI 兼容 SSE 格式)

---

## 流式 Tool Call 协议分析（核心难点）

### DeepSeek SSE 流式格式

DeepSeek 的流式响应遵循 OpenAI SSE 协议。每个 chunk 格式：

```json
{
  "choices": [{
    "index": 0,
    "delta": { ... },
    "finish_reason": null   // 只在最后一个 chunk 有值
  }]
}
```

流以 `data: [DONE]` 结束。

### 纯文本响应（简单情况）

```
data: {"choices":[{"delta":{"role":"assistant"},"finish_reason":null}]}
data: {"choices":[{"delta":{"content":"你好"},"finish_reason":null}]}
data: {"choices":[{"delta":{"content":"，我"},"finish_reason":null}]}
data: {"choices":[{"delta":{"content":"是ATRI"},"finish_reason":null}]}
data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
data: [DONE]
```

处理：每个 `delta.content` 直接产出 `StreamEvent(type="content")`。

### 工具调用响应（复杂情况）

```
data: {"choices":[{"delta":{"role":"assistant"},"finish_reason":null}]}
data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_abc","type":"function","function":{"name":"web_search","arguments":""}}]},"finish_reason":null}]}
data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\"q"}}]},"finish_reason":null}]}
data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"uery\":"}}]},"finish_reason":null}]}
data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\"天气\"}"}}]},"finish_reason":null}]}
data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}
data: [DONE]
```

处理：
1. 遇到 `delta.tool_calls[0].function.name` → 产出 `StreamEvent(type="tool_start")`
2. 后续 chunk 的 `arguments` 碎片 → **只累积不产出**，拼接到 `tool_calls_buffer[0]["arguments"]`
3. `finish_reason == "tool_calls"` → 此时 arguments 完整，构建 `ToolCall` 对象，执行工具

### 并行工具调用（多个 tool_call 交错）

```
data: {"choices":[{"delta":{"tool_calls":[
  {"index":0,"id":"c1","function":{"name":"read_file","arguments":""}},
  {"index":1,"id":"c2","function":{"name":"web_search","arguments":""}}
]},"finish_reason":null}]}
data: {"choices":[{"delta":{"tool_calls":[
  {"index":0,"function":{"arguments":"{\"path\":\"/tmp\"}"}},
  {"index":1,"function":{"arguments":"{\"query\":\"新闻\"}"}}
]},"finish_reason":"tool_calls"}]}
```

处理：用 `dict[int, dict]` 按 index 分桶，`sorted()` 保证执行顺序。

### finish_reason 所有可能值

| finish_reason | 含义 | 处理 |
|---|---|---|
| `stop` | 正常完成，有 content | 保存 assistant 消息，产出 `done`，return |
| `tool_calls` | 模型要调用工具 | 执行工具后 `continue` 重调 API |
| `length` | token 上限截断 | 当作 stop 处理 + 产出 error 提示 |
| `content_filter` | 内容违规被拦截 | 产出 error 事件 |
| `insufficient_system_resource` | 服务端过载 | 产出 error 事件（可重试） |
| `null`（非最后 chunk） | 流未结束 | 继续读取 |

---

### Task 1: Add `StreamEvent` dataclass to models.py

**Files:**
- Modify: `src/atri/models.py`

**Step 1: Add the dataclass**

在文件末尾（`RequestBody` 类之后）添加：

```python
from typing import Literal


@dataclass
class StreamEvent:
    """流式输出事件。

    type 决定哪些字段有效：
    - content:      text=文本片段
    - tool_start:   tool_name=工具名
    - tool_result:  tool_name=工具名, text=执行结果
    - message:      text=提示信息（技能切换等）
    - done:         全部字段无效
    - error:        text=错误信息
    """
    type: Literal["content", "tool_start", "tool_result", "message", "done", "error"]
    text: str = ""
    tool_name: str = ""
```

**Step 2: Verify import**

```bash
python -c "from atri.models import StreamEvent; e = StreamEvent(type='content', text='hi'); print(e)"
```
Expected: `StreamEvent(type='content', text='hi', tool_name='')`

---

### Task 2: Extract SSE delta accumulation as static method + refactor ai_chat()

**Files:**
- Modify: `src/atri/ai_service.py`

**Step 1: Update imports**

在文件顶部，将现有 import 行替换为：

```python
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
```

**Step 2: Add `_accumulate_sse_delta` static method**

在 `_msg_to_dict` 方法之前插入：

```python
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

        # 文本内容
        if delta.get("content"):
            events.append(StreamEvent(type="content", text=delta["content"]))

        # 推理内容（thinking=disabled 时不应出现，但防御性跳过）
        # reasoning_content 直接忽略

        # 工具调用碎片累积
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
```

**Step 3: Replace `ai_chat()` method**

完整替换第 47-144 行的 `ai_chat` 方法：

```python
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
                # 外层循环：工具调用后重新请求
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

                    # 内层：流式读取一个 API 响应
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
                            # 防御：API 声称 tool_calls 但没有累积到任何工具
                            yield StreamEvent(
                                type="error",
                                text="API 返回 tool_calls 但未包含工具调用数据",
                            )
                            return

                        # 构建 assistant 消息（含 tool_calls）
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

                        # 执行每个工具
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

                        # 继续外层循环（工具结果已在 history 中）
                        continue

                    elif finish_reason == "length":
                        # token 达到上限，保存已有内容
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
                        # 未知 finish_reason（含 None，说明流异常终止）
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
```

**关键设计要点：**
- `tool_calls_buffer` 用 `dict[int, dict]` 按 index 分桶，支持并行工具调用
- `finish_reason == "tool_calls"` 后检查 buffer 是否为空（防御性）
- 工具执行加了 try/except，单个工具失败不影响其他工具
- `continue` 关键字触发外层循环重试（工具结果已在 history 中）
- 所有 `finish_reason` 值都有明确分支处理
- 流异常终止（finish_reason=None 且已到 [DONE]）时，如果有已收到的内容就保存并正常结束

**Step 4: Verify syntax**

```bash
python -c "import ast; ast.parse(open('src/atri/ai_service.py', encoding='utf-8').read()); print('Syntax OK')"
```

---

### Task 3: Update `main.py` for streaming event display

**Files:**
- Modify: `src/atri/main.py`

**Step 1: Remove unused imports**

将第 4-5 行删除（不再需要 Live 和 Spinner）：

```python
from rich.console import Console
```

**Step 2: Replace the main loop response handling**

将第 91-98 行：

```python
        console.print()
        with Live(Spinner("dots", text=""), console=console, transient=True):
            response = await service.ai_chat(user_input)

        if not response:
            console.print("(未能获取回复，请检查网络或 API 配置)", style="red")
        else:
            console.print(response, style="magenta")
        console.print()
```

替换为：

```python
        console.print()
        # 流式输出
        console.print("[magenta]ATRI > [/magenta]", end="")
        has_content = False

        try:
            async for event in service.ai_chat(user_input):
                if event.type == "content":
                    console.print(event.text, end="", style="magenta")
                    has_content = True
                elif event.type == "tool_start":
                    if has_content:
                        console.print()
                        has_content = False
                    console.print(f"  [工具] 调用: {event.tool_name}", style="dim")
                elif event.type == "tool_result":
                    pass  # 简洁模式：不显示工具执行结果
                elif event.type == "message":
                    console.print(event.text, style="dim")
                elif event.type == "done":
                    if has_content:
                        console.print()
                elif event.type == "error":
                    if has_content:
                        console.print(f"\n({event.text})", style="red")
                    else:
                        console.print(f"(错误: {event.text})", style="red")
        except (KeyboardInterrupt, EOFError):
            if has_content:
                console.print("(已中断)", style="red")
            raise
        except Exception:
            if has_content:
                console.print("(连接中断)", style="red")
            else:
                console.print("(未能获取回复，请检查网络或 API 配置)", style="red")
        console.print()
```

**Step 3: Verify syntax**

```bash
python -c "import ast; ast.parse(open('src/atri/main.py', encoding='utf-8').read()); print('Syntax OK')"
```

---

### Task 4: Update and run tests

**Files:**
- Modify: `tests/test_ai_service.py`

**Step 1: Add StreamEvent test**

```python
def test_stream_event_creation():
    from atri.models import StreamEvent
    e = StreamEvent(type="content", text="hello")
    assert e.type == "content"
    assert e.text == "hello"
    assert e.tool_name == ""

    e2 = StreamEvent(type="tool_start", tool_name="web_search")
    assert e2.type == "tool_start"
    assert e2.tool_name == "web_search"
    assert e2.text == ""
```

**Step 2: Add `_accumulate_sse_delta` unit tests**

```python
def test_accumulate_sse_delta_content():
    """纯内容 delta 应产出 content 事件。"""
    from atri.ai_service import AIService
    buffer: dict = {}
    events = AIService._accumulate_sse_delta({"content": "你好"}, buffer)
    assert len(events) == 1
    assert events[0].type == "content"
    assert events[0].text == "你好"


def test_accumulate_sse_delta_tool_call_fragments():
    """工具调用：id/name 在第一帧，arguments 分多帧到达，逐帧累积。"""
    from atri.ai_service import AIService
    buffer: dict = {}

    # Frame 1: id + name
    e1 = AIService._accumulate_sse_delta(
        {"tool_calls": [{"index": 0, "id": "call_001", "type": "function",
                          "function": {"name": "web_search", "arguments": ""}}]},
        buffer,
    )
    assert len(e1) == 1
    assert e1[0].type == "tool_start"
    assert e1[0].tool_name == "web_search"
    assert buffer[0]["id"] == "call_001"
    assert buffer[0]["name"] == "web_search"
    assert buffer[0]["arguments"] == ""

    # Frame 2: arguments 碎片 1
    e2 = AIService._accumulate_sse_delta(
        {"tool_calls": [{"index": 0, "function": {"arguments": '{"query":'}}]},
        buffer,
    )
    assert len(e2) == 0  # 不产出事件
    assert buffer[0]["arguments"] == '{"query":'

    # Frame 3: arguments 碎片 2
    e3 = AIService._accumulate_sse_delta(
        {"tool_calls": [{"index": 0, "function": {"arguments": ' "天气"}'}}]},
        buffer,
    )
    assert len(e3) == 0
    assert buffer[0]["arguments"] == '{"query": "天气"}'


def test_accumulate_sse_delta_parallel_tools():
    """两个工具调用在同一帧到达，按 index 分桶。"""
    from atri.ai_service import AIService
    buffer: dict = {}

    events = AIService._accumulate_sse_delta(
        {"tool_calls": [
            {"index": 0, "id": "c1", "function": {"name": "read_file", "arguments": ""}},
            {"index": 1, "id": "c2", "function": {"name": "web_search", "arguments": ""}},
        ]},
        buffer,
    )
    assert len(buffer) == 2
    assert buffer[0]["name"] == "read_file"
    assert buffer[1]["name"] == "web_search"
    assert len(events) == 2
    assert events[0].tool_name == "read_file"
    assert events[1].tool_name == "web_search"


def test_accumulate_sse_delta_no_index_defaults_zero():
    """无 index 字段时应默认到 index 0。"""
    from atri.ai_service import AIService
    buffer: dict = {}

    AIService._accumulate_sse_delta(
        {"tool_calls": [{"id": "call_x", "function": {"name": "search", "arguments": ""}}]},
        buffer,
    )
    assert 0 in buffer
    assert buffer[0]["name"] == "search"
```

**Step 3: Run all tests**

```bash
pytest tests/test_ai_service.py -v
```
Expected: 7 tests passed (3 existing + 4 new)

```bash
pytest tests/ -v
```
Expected: All tests pass

---

### Task 5: Manual smoke test

**Step 1: 启动应用**

```bash
python -m atri.main
```

**Step 2: 测试纯文本流式输出**

输入：`你好，介绍一下你自己`

期望：
- 看到 `ATRI > ` 前缀后文字逐 token 出现（品红色）
- 无 spinner
- 完整回复正常显示

**Step 3: 测试工具调用**

输入：`帮我搜索一下今天北京的天气`

期望（如果模型调用 web_search）：
- 看到 `  [工具] 调用: web_search`（dim 样式）
- 工具调用期间不显示内容
- 工具完成后继续流式输出天气相关信息

**Step 4: 测试网络错误**

临时把 `data/UserSettings.json` 里的 URL 改成 `https://invalid.example.com/v1/chat/completions`，发一条消息。

期望：看到红色错误提示，不崩溃。

恢复 URL 后继续测试。

---

### Rollback Plan

回滚只需两步：

```bash
git checkout src/atri/ai_service.py src/atri/main.py src/atri/models.py tests/test_ai_service.py
pytest tests/ -v
```

`ConversationHistory.json` 格式不变，无需回滚数据。
