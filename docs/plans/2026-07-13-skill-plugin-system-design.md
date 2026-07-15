# 技能插件系统改造设计

> 日期：2026-07-13
> 状态：设计完成，待实施

## 目标

让 DSPark-Code 的技能从"纯 Prompt 注入"升级为**"Prompt + 自定义工具"的复合插件**。激活一个技能时，其提示词和自定义工具同时注册到上下文中，供 AI 调用。

## 技能目录新结构

```
skills/{skill-name}/
  SKILL.md          ← 提示词（必须）
  plugin.py         ← 工具实现（可选，有则动态注册工具）
```

plugin.py 是可选的——不写 plugin.py 的技能和现有行为完全一致。

## plugin.py 规范

```python
# 元信息（可选）
__skill_name__ = "browser"
__version__ = "1.0.0"

# 工具函数 —— 用 @tool 装饰器标记
@tool
def web_open(url: str, timeout: int = 30):
    """用浏览器打开指定 URL 并返回页面文本内容"""
    import httpx
    resp = httpx.get(url, timeout=timeout)
    return {"status": resp.status_code, "text": resp.text[:5000]}

# 生命周期钩子（可选）
def on_activate():
    """技能激活时调用"""
    pass

def on_deactivate():
    """技能停用时调用"""
    pass
```

### @tool 装饰器约定

| 信息 | 来源 |
|------|------|
| 工具名 | 函数名（或 `@tool(name="xxx")`） |
| 工具描述 | docstring 第一行 |
| 参数 Schema | 函数参数的类型注解 + 默认值自动生成 JSON Schema |
| 返回值 | 任意 Python 对象，自动 `json.dumps` 后作为工具结果传给 LLM |

类型映射：`str→string`, `int→integer`, `float→number`, `bool→boolean`, `dict→object`, `list→array`

## 加载与注册机制

### 激活流程

```
activate_skill(name):
  1. 名称校验
  2. 检查 SKILL.md 存在
  3. 检查 plugin.py 是否存在
     ├── 有 → importlib 动态加载
     │         ├── 扫描 @tool 函数 → 构建 FunctionDef 列表
     │         ├── 注册到 ToolManager._skill_tools[name]
     │         └── 调用 on_activate()
     └── 无 → 跳过
  4. 加入 active_skills 列表
  5. 返回结果（含注册的工具列表）
```

### 停用流程

```
deactivate_skill(name):
  1. 调用 on_deactivate()
  2. 从 ToolManager._skill_tools 卸载该技能的工具
  3. 从 active_skills 移除
  4. 返回结果
```

### ToolManager 改进

当前 `_total_tool_list` 是一个扁平静态列表。改造为两层：

```
_base_tools: list[Tool]                ← 系统内置工具（不变）
_skill_tools: dict[str, list[Tool]]    ← 技能注册的工具 {技能名: [Tool, ...]}
```

`get_all_tools(active_skills)` 方法：

```python
def get_all_tools(self, active_skills: list[str]) -> list[Tool]:
    tools = list(self._base_tools)
    for name in active_skills:
        tools.extend(self._skill_tools.get(name, []))
    return tools
```

AIService 每次调 API 时传 `ToolManager.get_all_tools(active_skills)` 即可获得完整工具列表。

## 提示词集成（不变）

- `PromptManager._get_active_skill_bodies()` 继续拼接激活技能的 SKILL.md 正文
- `_get_skill_catalog()` 小幅增强：展示每个技能注册了哪些工具

## 需改动的文件

| 文件 | 改动内容 |
|------|---------|
| `src/atri/skill_loader.py` | + `load_plugin(name)` 动态加载 plugin.py；+ `extract_tools(module)` 扫描 `@tool` 函数生成 `list[FunctionDef]`；+ `@tool` 装饰器定义 |
| `src/atri/tool_manager.py` | `_total_tool_list` 拆为 `_base_tools` + `_skill_tools`；`activate_skill`/`deactivate_skill` 增加工具注册/卸载逻辑；+ `get_all_tools(active_skills)` |
| `src/atri/ai_service.py` | 调 API 时改用 `ToolManager.get_all_tools(self.active_skills)` 获取工具列表 |
| `src/atri/prompt_manager.py` | `_get_skill_catalog()` 增加每技能注册的工具列表展示 |
| `src/atri/ui/app_shell.py` | `_on_user_message()` 开头增加 `/` 斜杠指令拦截：匹配技能名→直接激活，`/skills`→客户端展示列表 |
| `skills/browser/` | 新增：示例浏览器技能（SKILL.md + plugin.py） |

## 不需改动的文件

- `models.py` — 已有 `FunctionDef`/`Tool`/`Message` dataclass，完全够用
- `conversation.py` — 对话管理不涉及工具
- `file_tool.py` / `memory_tool.py` — 系统工具不变
- `prompt_manager.py` 中除 `_get_skill_catalog()` 以外的部分 — 不动

## 安全

技能由开发者审查后添加，用户层不可修改 skill 文件。plugin.py 在进程内执行，无额外沙箱隔离。

## 斜杠指令（桌面端快捷激活）

用户可以在输入框直接输入 `/skill-name` 来激活技能，**不经过 AI，客户端直接调用 `activate_skill`**。

### 行为

```
用户输入 "/browser"
  │
  ▼
Composer._on_send() 检测以 "/" 开头
  │
  ├── "/browser" → 匹配到技能 "browser"
  │     ├── 直接调用 ai_service.tool.tool_actor("activate_skill", '{"name":"browser"}', active_skills)
  │     ├── UI 显示 "[技能] 已激活: browser"
  │     └── 清空输入框，不发送给 AI
  │
  ├── "/browser 帮我打开xxx" → 匹配到技能 + 附带消息
  │     ├── 先直接激活技能（同上）
  │     └── 再把 "帮我打开xxx" 作为普通消息发送给 AI
  │
  └── "/xyz" → 不匹配任何技能
        └── 当作普通消息发送给 AI（AI 可以自行判断是否激活）
```

### 斜杠指令一览

| 输入 | 行为 |
|------|------|
| `/skill-name` | 直接激活该技能，不发消息 |
| `/skill-name 文本` | 激活技能 + 发送"文本"给 AI |
| `/skills` | 显示可用技能列表（客户端直接展示，不经过 AI） |
| 其他任意文本 | 正常发送给 AI |

### 改动文件

| 文件 | 改动内容 |
|------|---------|
| `src/atri/ui/composer.py` | `_on_send()` 中不做 `/` 判断——保持纯 UI，把文本原样 emit |
| `src/atri/ui/app_shell.py` | `_on_user_message()` 开头增加斜杠指令拦截逻辑，匹配技能名则直接激活，否则正常走 AI |

## 与 MCP 的关系（后续）

本设计为纯 Python 插件方案。后续可增加一个"MCP Bridge"技能，其 plugin.py 负责启动 MCP server 进程并将 MCP tools 桥接为 `@tool` 函数，从而兼容社区 MCP 生态。
