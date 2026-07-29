# HolonCode 项目全貌

> 本文档供 AI 快速理解项目，包含结构、架构、技术栈等必要信息。

---

## 项目身份

| 项 | 值 |
|---|-----|
| 名称 | HolonCode（原名 ATRI / 亚托莉） |
| 定位 | DeepSeek 驱动的角色扮演 AI 聊天机器人，带桌面 GUI + QQ Bot |
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
│   │   ├── __init__.py       # 定义路径，所有数据存 exe 同级目录
│   │   ├── main.py           # CLI 入口（rich 终端界面）
│   │   ├── ai_service.py     # AI 对话引擎 — 流式 SSE 请求 + 工具调用循环
│   │   ├── models.py         # 数据模型: Message, ToolCall, StreamEvent 等 dataclass
│   │   ├── conversation.py   # 对话历史管理 — 按 session 存入 data/sessions/{id}.json
│   │   ├── prompt_manager.py # 系统提示词组装: 人设 + 行为准则 + 能力 + 技能 + 用户画像 + 难度
│   │   ├── tool_manager.py   # 工具注册 & 调度 — 文件/记忆/技能/贴吧/联网搜索
│   │   ├── file_tool.py      # 文件操作工具（限定 workspace/ 目录，安全路径校验）
│   │   ├── memory_tool.py    # 用户画像记忆 CRUD（存 data/MemoryForUser.json）
│   │   ├── skill_loader.py   # 技能系统：扫描 skills/ 目录，解析 frontmatter
│   │   ├── content_compact.py# 长对话自动摘要压缩（避免超 token 限制）
│   │   ├── web_tools.py      # 联网搜索 & 网页提取（Parallel MCP + SSRF 防护）
│   │   ├── rag.py            # C 语言知识库搜索 — Agentic Search（全文匹配 + LLM 多轮改写）
│   │   ├── tieba_tool.py     # 百度贴吧浏览（可选依赖 aiotieba）
│   │   ├── setup.py          # 初始化向导（含 QQ Bot 配置）
│   │   └── ui/               # PySide6 桌面 GUI
│   │       ├── app.py        # GUI 入口 — QApplication 启动
│   │       ├── app_shell.py  # 主窗口 — 三栏布局 + 会话管理 + 消息流 + QQ Bot 集成
│   │       ├── chat_view.py  # 中间聊天区 — Thread(消息列表) + Composer(输入框)
│   │       ├── thread.py     # 消息气泡渲染 — Markdown + 代码高亮
│   │       ├── composer.py   # 底部输入栏 — 多行输入 + 发送按钮
│   │       ├── sidebar.py    # 左侧会话列表 — 新建/切换/删除/重命名
│   │       ├── file_panel.py # 右侧文件面板 + 文件预览对话框
│   │       │                 #   含语法高亮/自动补全/错误检测/Markdown预览/代码运行
│   │       ├── worker.py     # 后台线程 — 异步 AI 对话不阻塞 UI（含 session_lock）
│   │       ├── settings_dialog.py # 设置对话框
│   │       ├── status_bar.py # 底部状态栏
│   │       └── theme.py      # 全局样式主题（露早 绿色系）
│   │
│   ├── qqbot/                # QQ Bot 集成模块
│   │   ├── __init__.py       # QQBotRunner — QThread + asyncio 事件循环，信号桥接
│   │   ├── config.py         # 配置读取 — UserSettings.json / 环境变量
│   │   ├── connection.py      # WebSocket 网关客户端 — 连接/心跳/重连/Token 管理
│   │   └── handler.py        # 消息处理 — 解析/去重/ACL/AI 回复/REST 发送
│   │
│   └── code_runner/          # 独立 AI 代码执行模块
│       ├── __init__.py
│       └── runner.py         # 调用 DeepSeek API 模拟编译运行，支持交互式输入
│
├── data/                     # 运行时数据
│   ├── UserSettings.json     # DeepSeek API + QQ Bot + 贴吧配置 + 学习难度
│   ├── SOUL.json             # AI 人设（当前: 小洛 知性学姐）
│   ├── RULES.json            # AI 行为准则
│   ├── CAPABILITY.json       # AI 能力描述（文件操作/记忆/联网）
│   ├── MemoryForUser.json    # 用户画像记忆列表
│   ├── sessions.json         # 会话索引（ID/标题/创建时间/最后活跃）
│   ├── sessions/             # 每个会话的对话历史 {session_id}.json
│   ├── c-learn-progress.json # C 语言学习进度（27 知识点掌握等级）
│   ├── c-tutor-progress.json # C 语言闯关进度（70 关卡）
│   └── knowledge_base/       # C 语言知识库
│       └── c/                # 27 个知识点 Markdown 文档（00_声明语法 ~ 26_综合实战项目）
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
│   ├── test_tool_manager.py
│   ├── test_qqbot_config.py
│   ├── test_qqbot_connection.py
│   └── test_qqbot_handler.py
│
└── docs/                     # 设计文档 & 实施计划
    └── plans/                # 历史计划文件
```

---

## 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                   桌面 GUI (PySide6)                      │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐     │
│  │ Sidebar  │  │  ChatView    │  │  FilePanel    │     │
│  │ 会话列表  │  │  Thread+     │  │  文件树       │     │
│  │          │  │  Composer    │  │  预览+运行    │     │
│  └──────────┘  └──────┬───────┘  └───────────────┘     │
│                       │ 信号/槽                           │
│              ┌────────▼────────┐                         │
│              │   AppShell      │                         │
│              │  主窗口控制器     │                         │
│              └──┬─────────┬────┘                         │
│                 │         │                              │
│     ┌───────────┘         └──────────┐                  │
│     ▼                                ▼                  │
│  ┌─────────┐                  ┌──────────┐              │
│  │AIWorker │                  │QQBotRunner│             │
│  │桌面对话  │                  │QQ 消息收发 │             │
│  └────┬────┘                  └────┬─────┘              │
└───────┼────────────────────────────┼────────────────────┘
        │                            │
┌───────┼────────────────────────────┼────────────────────┐
│       ▼             后端服务层       ▼                    │
│  ┌─────────────────────────────────────────┐           │
│  │              AIService                   │           │
│  │  对话引擎 (session_lock 保证线程安全)      │           │
│  │  - 流式 SSE                              │           │
│  │  - 工具调用循环                           │           │
│  └──┬─────┬─────┬──────────────────────────┘           │
│     │     │     │                                      │
│  ┌──▼──┐ ┌▼───┐ ┌▼──────────┐                         │
│  │Prompt│ │Tool│ │Conversation│                        │
│  │Mgr   │ │Mgr │ │Mgr         │                        │
│  └─────┘ └────┘ └───────────┘                         │
│                                                        │
│  ┌──────────────┐  ┌────────────────────┐             │
│  │ QQBotConnection│  │ QQBotHandler      │             │
│  │ WebSocket 网关 │  │ 消息解析+ACL+回复  │             │
│  └──────────────┘  └────────────────────┘             │
└────────────────────────────────────────────────────────┘
                        │
                  ┌─────▼─────┐
                  │ DeepSeek  │
                  │ API       │
                  └───────────┘
```

---

## 核心数据流

### 桌面对话流程

1. **用户输入** → Composer 发出 `submitted` 信号 → AppShell._on_user_message()
2. **AppShell** 创建 AIWorker 线程，传入 AIService + 用户文本
3. **AIWorker.run()** 获取 session_lock，创建 asyncio 事件循环，调用 `AIService.ai_chat(user_input)`
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

### QQ Bot 消息流程

1. **QQBotRunner** 线程启动 → 创建 asyncio 事件循环 → 连接 QQ WebSocket 网关
2. QQ 消息到达 → `_dispatch_payload` → 回调 `on_message`
3. `on_message` 发射 Qt 信号到 UI，同时调用 `QQBotHandler.handle_message()`
4. **QQBotHandler**：解析消息 → 去重 → ACL 检查 → 获取 session_lock →
   切换 conversation 到 QQ 会话 → 调用 `ai_chat()` → 保存历史 →
   恢复原会话 → 释放 lock → 通过 REST API 发送回复
5. `session_lock` 确保桌面对话和 QQ 消息不会同时操作 ConversationManager

### 代码运行流程（独立模块）

1. FilePanel 双击文件 → FilePreviewDialog
2. 点击"运行" → 保存文件 → 打开 RunResultDialog
3. RunResultDialog 创建 _RunWorker 后台线程
4. _RunWorker 调用 `CodeRunner.run(file_path, on_output=, on_input=)`
5. CodeRunner 向 DeepSeek API 发送模拟终端执行的请求
6. 完成后关闭按钮启用，用户关闭窗口

---

## 技术栈

| 类别 | 技术 |
|------|------|
| GUI 框架 | **PySide6**（Qt for Python） |
| HTTP 客户端 | **httpx**（同步 + 异步） |
| WebSocket | **aiohttp** |
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
| `atri-setup` | `atri.setup:main` | 初始化配置向导（含 QQ Bot） |

---

## 关键设计决策

### 1. 会话管理
- 每个会话独立存储为 `data/sessions/{session_id}.json`
- `sessions.json` 维护会话索引（ID/标题/创建时间/最后活跃）
- 切换会话时先保存当前 history，再加载目标 history
- 首次启动自动创建 `[QQ] QQ聊天` 会话并设为默认

### 2. 工具调用循环
- AIService 内部维护 while True 循环：API 返回 tool_calls → 执行工具 → 追加结果 → 再次调 API → 直到 stop
- 所有工具定义在 ToolManager._total_tool_list（约 30 个工具）
- FileTool 限定 workspace/ 目录，防止路径穿越

### 3. 流式输出
- SSE 的 delta 累积处理：content 片段实时产出，tool_calls 按 index 分桶拼接
- GUI 端 AIWorker 用 QThread + asyncio 桥接异步流到 Qt 信号

### 4. 线程安全
- `AIService._session_lock` 是 `threading.Lock`，确保桌面 AIWorker 和 QQBotHandler 不会同时操作 ConversationManager
- AIWorker 在 `run()` 开始时获取锁，结束时释放
- QQBotHandler 在切换会话前获取锁（`blocking=False`），失败则跳过该条消息

### 5. 上下文压缩
- ContentCompact 在 >=15 轮对话时触发
- 取最早 5 轮调用 AI 生成摘要，插入为 system 消息
- 最多保留 10 条摘要 + 最近 10 轮完整对话

### 6. 技能系统
- 技能存储在 `skills/{name}/SKILL.md`，含 YAML frontmatter
- 运行时动态激活/关闭，最多 3 个同时生效
- 激活后技能内容直接注入 system prompt

### 7. C 语言学习系统

三种学习模式，共用一套知识库：

**技能：**

| 技能 | 模式 | 特点 |
|------|------|------|
| `c-learn` | 答疑解惑 | 小洛讲解，必须先用 c_knowledge_search 搜知识库，不足时联网并标注来源 |
| `c-qa` | 角色互换复习 | 小洛假装对知识点"记不清"，通过提问引导用户讲解（教别人=最好的学习） |
| `c-tutor` | 闯关教学 | 70 关，编程/改错/选择/填空四种题型，难度递增 |

**知识库（`data/knowledge_base/c/`）：** 27 个 Markdown 文档，00_声明语法 到 26_综合实战项目。

**Agentic Search（`rag.py`）：** 不使用向量索引或 embedding API。全文子串匹配 + LLM 多轮改写：
1. 精确子串搜索（等于 grep）
2. 无结果时自动拆 2-gram 宽松匹配
3. LLM 判断结果不够 → 自己推理换词 → 再次调用 c_knowledge_search

**学习进度：** `c-learn-progress.json` 记录 27 个知识点掌握等级（1=了解/2=理解/3=掌握/4=熟练），跨会话持久化。

**难度系统：** 四档（easy/medium/hard/adaptive），存储在 `UserSettings.json` 的 `Learning.Difficulty`。PromptManager 将对应难度指令注入 system prompt。对话中可通过 `c_set_difficulty` 工具动态调整。

### 8. QQ Bot 集成
- 基于 QQ Bot API v2 — WebSocket 网关接收事件 + REST API 发送消息
- QQBotRunner 运行在独立 QThread 上，使用自己的 asyncio 事件循环
- 连接管理：自动 token 刷新、心跳保活、指数退避重连、致命错误码停止
- 消息处理：5 分钟去重窗口、ACL（开放/白名单/禁用）、@提及剥离
- QQ 消息写入专用 `[QQ] QQ聊天` 会话，与桌面对话互不干扰
- 配置：`UserSettings.json` 中 `QQBot.AppId` / `QQBot.ClientSecret`，或环境变量 `QQ_APP_ID` / `QQ_CLIENT_SECRET`

### 9. 代码运行（code_runner）
- **独立模块**，不保存对话历史
- 通过精心构造的 system prompt 让 AI 伪装成终端
- 工具调用机制实现交互式输入（request_input tool）

### 10. 安全设计

**路径沙箱（FileTool）：**
- `get_safe_path()` 五层防护：拒绝绝对路径 → 拒绝 `..` → 拒绝 Windows 保留设备名（CON/NUL/PRN/COM1-9/LPT1-9）→ 拒绝 NTFS ADS（`:`）→ resolve 后 `relative_to(work_dir)` 二次验证
- 文件大小上限 10MB（防止磁盘写满）
- 所有文件操作的路径参数经过 get_safe_path() 校验
- **C 盘保护**：`delete_file` 额外检查 `Path.drive`，C 盘文件一律拒绝删除
- **软删除**：`delete_file` 将文件移入系统回收站（`send2trash`），而非永久删除

**会话管理安全：**
- `delete_session_history()` 正则校验 session_id（仅允许 `[\w\-]+`），resolve 后验证在 sessions/ 目录内
- `_migrate_old_format()` 同样对旧 JSON 中的 session ID 做正则 + resolve 校验

**技能系统安全：**
- `validate_name()` 拦截 `..`、`/`、`\`、`:`、超过 64 字符
- `_safe_skill_path()` 对技能路径做 resolve + relative_to 纵深防御
- `write_skill()`、`delete_skill()`、`load_plugin()` 均经过路径安全校验

**代码运行安全：**
- `CodeRunner.run()` 和 `needs_input()` 通过 `resolve + relative_to` 校验文件路径（兼容绝对路径）
- `FilePreviewDialog` 构造时同样通过 `resolve + relative_to` 验证路径在 workspace 内

**网络安全：**
- web_tools 内置 SSRF 防护（阻塞私有 IP、环回、链路本地、CGNAT、云元数据 IP）
- URL 中检测 API key/token 泄露

**数据目录安全：**
- PyInstaller 打包后所有数据（配置、会话、技能）均存储在 exe 同级目录，不写入 C 盘或用户目录
- 删除文件夹即完全清除所有数据

---

## 数据文件格式

### UserSettings.json
```json
{
  "DeepSeek": {
    "ApiKey": "sk-xxx",
    "Url": "https://api.deepseek.com/chat/completions",
    "Model": "deepseek-v4-pro"
  },
  "Learning": {
    "Difficulty": "medium"
  },
  "QQBot": {
    "AppId": "你的AppId",
    "ClientSecret": "你的ClientSecret"
  },
  "Tieba": {
    "BDUSS": "...",
    "STOKEN": "..."
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
