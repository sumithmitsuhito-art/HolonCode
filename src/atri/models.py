from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class FunctionCall:
    name: str | None = None
    arguments: str | None = None


@dataclass
class ToolCall:
    id: str | None = None
    type: str | None = "function"
    function: FunctionCall | None = None


@dataclass
class Message:
    role: str | None = None
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


@dataclass
class Thinking:
    type: str = "disabled"


@dataclass
class FunctionDef:
    name: str | None = None
    description: str | None = None
    parameters: dict[str, Any] | None = None


@dataclass
class Tool:
    type: str = "function"
    function: FunctionDef | None = None


@dataclass
class RequestBody:
    model: str | None = "deepseek-v4-pro"
    messages: list[Message] | None = None
    stream: bool = False
    thinking: Thinking = field(default_factory=Thinking)
    tools: list[Tool] | None = None


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
