# HolonCode 项目全貌

> 本文档供 AI 快速理解项目，包含结构、架构、技术栈等必要信息。

---

## 项目身份

| 项 | 值 |
|---|-----|
| 名称 | HolonCode（原名 ATRI / 亚托莉） |
| 定位 | DeepSeek 驱动的角色扮演 AI 聊天机器人，带桌面 GUI |
| Python 版本 | >= 3.12 |
| 包管理器 | uv |
| 建置系统 | setuptools |

---

## 目录结构

```
DSPark-Code/
├── boot.py                  # 一键启动脚本（CLI + UI 入口选择）
├── pyproject.toml            # 项目配置 & 依赖 & 脚本入口
├── uv.lock                   # uv 锁定依赖版本
│
├── src/
│   ├── atri/                 # 核心后端
│   │   ├── __init__.py       # 定义 BASE_DIR / DATA_DIR / WORKSPACE_DIR
│   │   ├── main.py           # CLI 入口（rich 终端界面）
│   │   ├── ai_service.py     # AI 对话引擎 — 流式 SSE 请求 + 工具调用循环
│   │   ├── models.py         # 数据模型: Message, ToolCall, StreamEvent 等 dataclass
│   │   ├── conversation.py   # 对话历史管理 — 按 session 存入 data/sessions/{id}.json
│   │   ├── prompt_manager.py # 系统提示词组装: 人设 + 行为准则 + 能力 + 技能 + 用户画像
│   │   ├── tool_manager.py   # 工具注册 & 调度 — 文件/记忆/技能/贴吧/联网搜索
│   │   ├── file_tool.py      # 文件操作工具（限定 workspace/ 目录，安全路径校验）
│   │   ├── memory_tool.py    # 用户画像记忆 CRUD（存 data/MemoryForUser.json）
│   │   ├── skill_loader.py   # 技能系统：扫描 skills/ 目录，解析 frontmatter
│   │   ├── content_compact.py# 长对话自动摘要压缩（避免超 token 限制）
│   │   ├── web_tools.py      # 联网搜索 & 网页提取（Parallel MCP + SSRF 防护）
│   │   ├── tieba_tool.py     # 百度贴吧浏览（可选依赖 aiotieba）
│   │   ├── setup.py          # 初始化向导
│   │   └── ui/               # PySide6 桌面 GUI
│   │       ├── app.py        # GUI 入口 — QApplication 启动
│   │       ├── app_shell.py  # 主窗口 — 三栏布局 + 会话管理 + 消息流
│   │       ├── chat_view.py  # 中间聊天区 — Thread(消息列表) + Composer(输入框)
│   │       ├── thread.py     # 消息气泡渲染 — Markdown + 代码高亮
│   │       ├── composer.py   # 底部输入栏 — 多行输入 + 发送按钮
│   │       ├── sidebar.py    # 左侧会话列表 — 新建/切换/删除/重命名
│   │       ├── file_panel.py # 右侧文件面板 + 文件预览对话框
│   │       │                 #   含语法高亮/自动补全/错误检测/Markdown预览/代码运行
│   │       ├── worker.py     # 后台线程 — 异步 AI 对话不阻塞 UI
│   │       ├── settings_dialog.py # 设置对话框
│   │       ├── status_bar.py # 底部状态栏
│   │       └── theme.py      # 全局样式主题（露早 绿色系）
│   │
│   └── code_runner/          # 独立 AI 代码执行模块
│       ├── __init__.py
│       └── runner.py         # 调用 DeepSeek API 模拟编译运行，支持交互式输入
│
├── data/                     # 运行时数据
│   ├── UserSettings.json     # DeepSeek API 配置（ApiKey/Url/Model）
│   ├── SOUL.json             # AI 人设（当前: 小洛 知性学姐）
│   ├── RULES.json            # AI 行为准则
│   ├── CAPABILITY.json       # AI 能力描述（文件操作/记忆/联网）
│   ├── MemoryForUser.json    # 用户画像记忆列表
│   ├── sessions.json         # 会话索引（ID/标题/创建时间）
│   └── sessions/             # 每个会话的对话历史 {session_id}.json
│
├── workspace/                # AI 文件操作沙箱（所有文件工具限定此目录）
│
├── skills/                   # 用户安装的技能（每个子目录 = 一个技能，含 SKILL.md）
│
├── tests/                    # pytest 测试
│   ├── conftest.py
│   ├── test_ai_service.py
│   ├── test_conversation.py
│   ├── test_file_tool.py
│   ├── test_memory_tool.py
│   ├── test_models.py
│   ├── test_prompt_manager.py
│   ├── test_content_compact.py
│   └── test_tool_manager.py
│
└── docs/                     # 设计文档 & 实施计划
    └── plans/                # 历史计划文件
```

---

## 架构总览

```
┌─────────────────────────────────────────────────────┐
│                   桌面 GUI (PySide6)                  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ Sidebar  │  │  ChatView    │  │  FilePanel    │ │
│  │ 会话列表  │  │  Thread+     │  │  文件树       │ │
│  │          │  │  Composer    │  │  预览+运行    │ │
│  └──────────┘  └──────┬───────┘  └───────────────┘ │
│                       │ 信号/槽                       │
│              ┌────────▼────────┐                     │
│              │   AppShell      │                     │
│              │  主窗口控制器     │                     │
│              └────────┬────────┘                     │
└───────────────────────┼──────────────────────────────┘
                        │
┌───────────────────────┼──────────────────────────────┐
│                   后端服务层                            │
│              ┌────────▼────────┐                     │
│              │   AIService     │                     │
│              │  对话引擎        │                     │
│              │  - 流式 SSE      │                     │
│              │  - 工具调用循环   │                     │
│              └──┬─────┬─────┬──┘                     │
│          ┌──────┘     │     └──────┐                 │
│   ┌──────▼──────┐ ┌───▼────┐ ┌───▼──────────┐      │
│   │PromptManager│ │ToolMgr │ │ConversationMgr│      │
│   │系统提示词组装 │ │工具调度 │ │对话历史管理     │      │
│   └─────────────┘ └───┬────┘ └──────────────┘      │
│                  ┌─────┼─────┐                       │
│           ┌──────▼──┐┌▼──────▼──┐┌────────▼──────┐ │
│           │FileTool ││MemoryTool││ WebTools      │ │
│           │文件操作  ││用户画像   ││ 搜索+提取      │ │
│           └─────────┘└─────────┘└───────────────┘ │
└─────────────────────────────────────────────────────┘
                        │
                  ┌─────▼─────┐
                  │ DeepSeek  │
                  │ API       │
                  └───────────┘
```

---

## 核心数据流

### 一轮对话的完整流程

1. **用户输入** → Composer 发出 `submitted` 信号 → AppShell._on_user_message()
2. **AppShell** 创建 AIWorker 线程，传入 AIService + 用户文本
3. **AIWorker.run()** 创建 asyncio 事件循环，调用 `AIService.ai_chat(user_input)`
4. **AIService.ai_chat()** 是 async generator：
   - 把用户消息追加到 `self.conversation.history`
   - 组装 system prompt（PromptManager.build_system_prompt()）
   - POST 到 DeepSeek API（stream=True），携带所有已注册的 tools
   - 逐 SSE chunk 产出 `StreamEvent(type="content", text=...)` 
   - 如果 `finish_reason="tool_calls"`：执行工具，追加结果到 history，**继续循环**再调 API
   - 如果 `finish_reason="stop"`：保存 history，检查是否需要压缩，返回 done 事件
5. **AIWorker** 把 StreamEvent 翻译为 Qt 信号（content_chunk / tool_start / finished / error）
6. **AppShell** 接收信号，更新 UI（Thread 渲染气泡、StatusBar 状态）
7. **ContentCompact**：当对话轮数 >= 15 轮，自动调用 AI 生成摘要，替换早期消息

### 代码运行流程（独立模块）

1. FilePanel 双击文件 → FilePreviewDialog
2. 点击"运行" → 保存文件 → 打开 RunResultDialog
3. RunResultDialog 创建 _RunWorker 后台线程
4. _RunWorker 调用 `CodeRunner.run(file_path, on_output=, on_input=)`
5. CodeRunner 向 DeepSeek API 发送模拟终端执行的请求：
   - `on_output(text)` → 流式输出终端内容到 QPlainTextEdit
   - 遇到 scanf/input() → API 返回 tool_calls(request_input) → `on_input(prompt)` → QEventLoop 等待用户在终端中键入
   - 用户按回车 → 输入传给 AI → 继续执行直到结束
6. 完成后关闭按钮启用，用户关闭窗口

---

## 技术栈

| 类别 | 技术 |
|------|------|
| GUI 框架 | **PySide6**（Qt for Python） |
| HTTP 客户端 | **httpx**（同步 + 异步） |
| AI 模型 | **DeepSeek**（deepseek-v4-pro） |
| Markdown 渲染 | **markdown** 库 + **Pygments** 代码高亮 |
| CLI 界面 | **rich** |
| 测试 | **pytest** + pytest-asyncio |
| 包管理 | **uv** + setuptools |
| 环境管理 | .venv（uv 自动管理） |

---

## 入口点（pyproject.toml 注册）

| 命令 | 入口函数 | 说明 |
|------|---------|------|
| `atri` | `atri.main:cli` | CLI 终端对话 |
| `atri-ui` | `atri.ui.app:main` | 桌面 GUI |
| `atri-setup` | `atri.setup:main` | 初始化配置向导 |

---

## 关键设计决策

### 1. 会话管理
- 每个会话独立存储为 `data/sessions/{session_id}.json`
- `sessions.json` 维护会话索引（ID/标题/创建时间/最后活跃）
- 切换会话时先保存当前 history，再加载目标 history

### 2. 工具调用循环
- AIService 内部维护 while True 循环：API 返回 tool_calls → 执行工具 → 追加结果 → 再次调 API → 直到 stop
- 所有工具定义在 ToolManager._total_tool_list（约 30 个工具）
- FileTool 限定 workspace/ 目录，防止路径穿越

### 3. 流式输出
- SSE 的 delta 累积处理：content 片段实时产出，tool_calls 按 index 分桶拼接
- GUI 端 AIWorker 用 QThread + asyncio 桥接异步流到 Qt 信号

### 4. 上下文压缩
- ContentCompact 在 >=15 轮对话时触发
- 取最早 5 轮调用 AI 生成摘要，插入为 system 消息
- 最多保留 10 条摘要 + 最近 10 轮完整对话

### 5. 技能系统
- 技能存储在 `skills/{name}/SKILL.md`，含 YAML frontmatter
- 运行时动态激活/关闭，最多 3 个同时生效
- 激活后技能内容直接注入 system prompt

### 6. 代码运行（code_runner）
- **独立模块**，不保存对话历史
- 通过精心构造的 system prompt 让 AI 伪装成终端
- 工具调用机制实现交互式输入（request_input tool）
- 终端风格 UI：输出和输入在同一 QPlainTextEdit 中，用户直接在光标处输入

### 7. 安全设计
- FileTool 所有路径操作经过 get_safe_path() 校验（禁止绝对路径、禁止 ../）
- web_tools 内置 SSRF 防护（阻塞私有 IP、环回、链路本地、CGNAT、云元数据 IP）
- URL 中检测 API key/token 泄露

---

## 数据文件格式

### UserSettings.json
```json
{
  "DeepSeek": {
    "ApiKey": "sk-xxx",
    "Url": "https://api.deepseek.com/chat/completions",
    "Model": "deepseek-v4-pro"
  }
}
```

### 会话存储格式 (sessions/{id}.json)
```json
[
  {"role": "user", "content": "(07-12 22:10)：你好"},
  {"role": "assistant", "content": "你好呀～"},
  {"role": "assistant", "tool_calls": [{"id": "...", "type": "function", "function": {"name": "read_file", "arguments": "{\"filePath\":\"test.txt\"}"}}]},
  {"role": "tool", "tool_call_id": "...", "content": "文件内容..."}
]
```
