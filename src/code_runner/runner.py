"""Call DeepSeek API to simulate code execution with interactive input support."""

import json
import re
from pathlib import Path
from typing import Callable
import httpx
from atri import DATA_DIR

_LANG_MAP = {
    ".py": "Python", ".c": "C", ".cpp": "C++", ".h": "C",
    ".js": "JavaScript", ".ts": "TypeScript", ".go": "Go",
    ".java": "Java", ".rs": "Rust", ".rb": "Ruby", ".lua": "Lua",
    ".sh": "Shell", ".bat": "Batch", ".ps1": "PowerShell",
    ".html": "HTML", ".css": "CSS", ".json": "JSON", ".xml": "XML",
    ".sql": "SQL", ".r": "R", ".m": "MATLAB/Octave",
}

_RUN_PROMPT = """你是一个终端模拟器。用户会给你一段{lang}代码，请你完全模拟真实编译运行的过程。

## 核心规则
- 你就是一个真实的编译器/解释器，输出与终端完全一致的内容
- 不要输出任何分析、建议、解释，不要说"这段代码有问题"
- 编译型语言（C/C++/Go/Rust/Java）先输出编译命令和结果，再输出运行结果
- 解释型语言（Python/JS/Lua/Ruby）直接输出运行结果
- 如果有编译错误，只输出真实的编译错误信息
- 输出格式如同用户在终端中看到的一模一样
- **严禁在内容中输出任何 JSON、工具调用格式、或伪造的函数调用**
- 所有工具调用必须通过系统的 function calling 机制，不要用文本模拟

## 遇到输入语句时的处理
- 当程序执行到 scanf、input()、cin、gets、readline 等需要用户输入的语句时
- **立即**调用 request_input 工具，将提示文字作为参数传入
- 不要在调用工具前提前输出后续内容
- 不要在工具调用时附带任何额外文本，只调用工具
- 收到用户输入后，**直接继续执行后续代码，严禁重复输出之前已经显示过的提示文字和用户输入**
- 用户输入的回显由终端自动处理，你不需要再输出一遍"""

_COMPILE_CMDS = {
    "C": "gcc -Wall -o /tmp/a.out {file} && /tmp/a.out",
    "C++": "g++ -Wall -o /tmp/a.out {file} && /tmp/a.out",
    "Go": "go run {file}",
    "Java": "javac {file} && java {base}",
    "Rust": "rustc {file} -o /tmp/a.out && /tmp/a.out",
    "Python": "python {file}",
    "JavaScript": "node {file}",
    "TypeScript": "npx ts-node {file}",
    "Ruby": "ruby {file}",
    "Lua": "lua {file}",
    "Shell": "bash {file}",
    "Batch": "{file}",
    "PowerShell": "pwsh {file}",
}

_INPUT_TOOL = {
    "type": "function",
    "function": {
        "name": "request_input",
        "description": "向用户请求输入。当程序执行到需要用户输入的语句（scanf/input/cin等）时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "程序在等待输入前显示的提示文字",
                },
            },
            "required": ["prompt"],
        },
    },
}

_INPUT_PATTERNS = {
    "C":     [r"\bscanf\b", r"\bgets\b", r"\bfgets\b", r"\bgetchar\b"],
    "C++":   [r"\bstd::cin\b", r"\bcin\b", r"\bscanf\b", r"\bgetline\b"],
    "Python": [r"\binput\s*\("],
    "Java":  [r"\bScanner\b", r"\bBufferedReader\b", r"\bConsole\b"],
    "Go":    [r"\bfmt\.Scan", r"\bbufio\b"],
    "JavaScript": [r"\bprompt\s*\(", r"\breadline\b", r"\bquestion\s*\("],
    "TypeScript": [r"\bprompt\s*\(", r"\breadline\b"],
    "Ruby":  [r"\bgets\b", r"\breadline\b"],
    "Lua":   [r"\bio\.read\b"],
}


class CodeRunner:
    """Calls DeepSeek API to simulate code execution, with interactive input."""

    def __init__(self):
        cfg = self._load_config()
        self.api_key = cfg.get("ApiKey", "")
        self.url = cfg.get("Url", "")
        self.model = cfg.get("Model", "")

    @staticmethod
    def needs_input(file_path: str) -> bool:
        lang = _LANG_MAP.get(Path(file_path).suffix, "")
        patterns = _INPUT_PATTERNS.get(lang, [])
        if not patterns:
            return False
        try:
            code = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return False
        return any(re.search(p, code) for p in patterns)

    @staticmethod
    def _load_config() -> dict:
        path = DATA_DIR / "UserSettings.json"
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("DeepSeek", {})
        except (json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def _detect_lang(file_path: str) -> str:
        return _LANG_MAP.get(Path(file_path).suffix, "未知语言")

    def run(self, file_path: str,
            on_input: Callable[[str], str] | None = None,
            on_output: Callable[[str], None] | None = None) -> str:
        """Run code simulation.

        `on_output(text)` is called with each chunk of terminal output.
        `on_input(prompt)` is called when input is needed, must return user input.
        """
        code = Path(file_path).read_text(encoding="utf-8")
        lang = self._detect_lang(file_path)
        system_prompt = _RUN_PROMPT.format(lang=lang)
        cmd = _COMPILE_CMDS.get(lang, "")
        cmd_line = f"\n$ {cmd}" if cmd else ""

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"运行这段{lang}代码，输出终端内容：\n\n```\n{code}\n```{cmd_line}"},
        ]

        full_output: list[str] = []

        with httpx.Client(timeout=120) as client:
            while True:
                body: dict = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "thinking": {"type": "disabled"},
                    "tools": [_INPUT_TOOL],
                }

                resp = client.post(
                    self.url,
                    json=body,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]
                msg = choice["message"]
                finish = choice.get("finish_reason", "")

                if msg.get("content"):
                    content = msg["content"]
                    # Strip fake JSON tool calls that the model may output as text
                    import re as _re
                    content = _re.sub(
                        r'\{\s*"tool_calls"\s*:\s*\[.*?\]\s*\}',
                        '',
                        content,
                        flags=_re.DOTALL,
                    ).strip()
                    if content:
                        full_output.append(content)
                        if on_output:
                            on_output(content)

                if finish == "stop":
                    break

                if finish == "tool_calls" and msg.get("tool_calls"):
                    messages.append({"role": "assistant", "content": msg.get("content"), "tool_calls": msg["tool_calls"]})
                    for tc in msg["tool_calls"]:
                        func = tc["function"]
                        if func["name"] == "request_input" and on_input:
                            args = json.loads(func["arguments"])
                            user_input = on_input(args.get("prompt", ""))
                        else:
                            user_input = ""
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": user_input,
                        })
                    continue

                if finish == "tool_calls":
                    full_output.append("\n[错误: API 返回了空的 tool_calls]")
                    break

                if msg.get("content"):
                    break
                break

        return "".join(full_output)
