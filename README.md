## 部署方法

### 方式一：源码运行

把项目文件夹复制到目标电脑，双击 `启动.bat` 即可。

脚本会自动：
1. 检查 Python 3.12+
2. 安装 uv 包管理器
3. 运行 `uv run python boot.py` 完成依赖安装和首次配置
4. 打开桌面端应用

或者手动执行：

```
cd 项目路径
uv run python boot.py
uv run atri-ui
```

**要求：目标电脑有网络连接。**

### 方式二：打包版 exe（绿色免安装）

1. 将 `dist/DSParkCode/` 文件夹压缩发给用户
2. 用户解压到任意目录，双击 `DSParkCode.exe` 运行
3. 首次运行会自动打开配置向导

所有数据（对话记录、配置、技能等）均存储在 exe 同级目录下，不写入 C 盘或用户目录，解压即用，删除即走。

### 方式三：pip 安装

```
pip install atri
atri-setup    # 首次配置
atri-ui       # 启动桌面 GUI
```

---

## 功能

- **Function Calling 工具系统** — 文件读写、搜索、记忆管理、贴吧浏览，AI 自动调用工具完成任务
- **C 语言学习系统** — 三大学习模式 + 27 模块知识库 + 四档难度调节，从零基础到进阶全覆盖
- **知识库智能搜索** — Agentic Search 架构，全文子串匹配 + LLM 多轮改写查询，无需向量索引
- **QQ Bot** — 通过 QQ 官方 API 连接机器人，在 QQ 中与小洛聊天（新增）
- **贴吧浏览** — 浏览任意贴吧帖子、搜索话题、查看用户信息
- **技能系统** — 可插拔的行为模块，AI 自主激活/关闭/创建技能，支持渐进式加载
- **联网搜索** — 通过 Bing 获取实时信息
- **用户画像** — 自动记录用户偏好和习惯
- **上下文压缩** — 长对话自动总结，不会丢失上下文
- **可定制提示词** — 通过 `data/SOUL.json`、`RULES.json`、`CAPABILITY.json` 自定义角色和行为
- **桌面 GUI** — PySide6 三栏布局：会话列表 + 对话区 + 文件面板

---

## 内置工具

### 文件工具
| 工具 | 说明 |
|------|------|
| `read_file` | 读取 workspace 下的文件 |
| `write_file` | 覆盖写入文件 |
| `append_file` | 追加内容到文件末尾 |
| `delete_file` | 删除文件（需确认，移入回收站） |
| `list_files` | 列出目录内容 |
| `search_files` | 在文件中搜索关键词 |
| `move_file` | 移动/重命名文件 |
| `create_directory` | 创建文件夹 |

### 贴吧工具
| 工具 | 说明 | 需登录 |
|------|------|--------|
| `tieba_get_threads` | 获取贴吧帖子列表 | 否 |
| `tieba_get_posts` | 查看帖子回复/评论 | 否 |
| `tieba_search_exact` | 在指定贴吧内搜索帖子 | 否 |
| `tieba_get_forum_info` | 查看贴吧详情（会员数、等级等） | 否 |
| `tieba_get_user_info` | 查看用户信息（昵称、粉丝等） | 是 |
| `tieba_get_hot_threads` | 获取贴吧热门帖子排行 | 否 |

### 记忆 & 技能工具
| 工具 | 说明 |
|------|------|
| `web_search` | 联网搜索 |
| `add_user_memory` | 记录用户信息 |
| `list_user_memories` | 查看已记录的用户画像 |
| `delete_user_memory` | 删除指定记忆 |
| `clear_user_memories` | 清空全部记忆 |
| `list_skills` | 查看可用技能 |
| `activate_skill` | 激活技能 |
| `deactivate_skill` | 关闭技能 |
| `read_skill_file` | 读取技能内容 |
| `write_skill_file` | 创建/修改技能 |

---

## 技能系统

技能是 `skills/<技能名>/SKILL.md` 文件，AI 可以自主调用工具来激活、关闭、创建和修改技能。

最多同时激活 3 个技能，超出时自动关掉最早的。

内置技能：

- `c-learn` — C 语言答疑，小洛以知性学姐身份讲解知识点
- `c-qa` — C 语言角色互换复习，小洛假装"记不清了"来提问，用户当小老师
- `c-tutor` — C 语言知识闯关，70 关渐进式教学（编程/改错/选择/填空）
- `code-reviewer` — 傲娇编程导师
- `translator` — 中/英/日三语翻译
- `storyteller` — 交互式故事创作
- `confidant` — 深度倾听模式

---

## C 语言学习系统

三种学习模式，共用一套 27 个 Markdown 文档组成的 C 语言知识库（`data/knowledge_base/c/`），覆盖声明语法到综合实战项目。

| 技能 | 模式 | 说明 |
|------|------|------|
| `c-learn` | 答疑解惑 | 小洛讲解知识点，必须先搜知识库再回答，不足时联网搜索并标注来源 |
| `c-qa` | 角色互换 | 小洛对知识点"记不太清"，通过提问引导用户讲解，教别人的过程中加深理解 |
| `c-tutor` | 闯关教学 | 70 个关卡，包含编程实战、改错、选择、填空四种题型，难度递增 |

### 难度选择

设置 → 学习设置 → 四档可选：

| 难度 | 风格 |
|------|------|
| 简单 | 生活比喻、简短示例、避开术语 |
| 中等 | 标准术语、完整示例、常见陷阱 |
| 困难 | C 标准术语、底层原理（内存布局/UB）、工业级实践 |
| 自适应 | AI 动态评估用户水平，自动升降难度 |

对话中也可随时说"讲简单点""讲深入点"来调整。难度持久化到 `UserSettings.json`。

### 知识库搜索

使用 **Agentic Search** 架构——全文子串匹配 + LLM 多轮改写：

1. 精确子串搜索（等于 grep）
2. 无结果时自动拆 2-gram 宽松匹配
3. 返回结果不够 → LLM 自己推理换词 → 再次搜索

无需向量索引，无需 embedding API，始终检索最新文件内容。

---

## QQ Bot 配置（可选）

> QQ Bot 是**完全可选**的功能。不配置 → 纯桌面聊天应用，一切正常运行。只在需要 QQ 机器人时才配置。

1. 前往 [QQ 开放平台](https://q.qq.com) 创建机器人应用
2. 获取 AppId 和 ClientSecret
3. 运行 `atri-setup` 或 `python boot.py`，在第五步输入凭据
4. 或在 `data/UserSettings.json` 中添加：
```json
"QQBot": {
  "AppId": "你的AppId",
  "ClientSecret": "你的ClientSecret"
}
```
5. 也可通过环境变量配置：`QQ_APP_ID` / `QQ_CLIENT_SECRET`
6. 启动 `atri-ui`，底部状态栏会显示连接状态
7. 在 QQ 中向你的机器人发送消息，消息会出现在桌面 GUI 的 `[QQ] QQ聊天` 会话中

---

## 聊天指令

| 指令 | 作用 |
|------|------|
| `/help` | 查看可用指令 |
| `/exit` | 退出 |
| `/clear` | 清屏（对话历史保留） |
| `/skills` | 查看可用技能列表 |
| `/status` | 查看当前状态（含工具数、对话轮次） |

---

## 文件结构

```
DSPark-Code/
├── boot.py                     ← 一键安装配置脚本
├── pyproject.toml              ← 项目依赖配置
├── README.md                   ← 本文件
├── data/
│   ├── UserSettings.json       ← API + QQ Bot + 贴吧配置 + 学习难度
│   ├── SOUL.json               ← 角色设定
│   ├── RULES.json              ← 行为准则
│   ├── CAPABILITY.json         ← 能力描述
│   ├── MemoryForUser.json      ← 用户画像（自动生成）
│   ├── sessions.json           ← 会话索引
│   ├── sessions/               ← 每个会话的对话历史
│   ├── c-learn-progress.json   ← C 语言学习进度（27 个知识点掌握等级）
│   ├── c-tutor-progress.json   ← C 语言闯关进度（70 个关卡）
│   └── knowledge_base/         ← C 语言知识库
│       └── c/                  ← 27 个知识点 Markdown 文档
├── workspace/                  ← AI 文件操作沙箱（所有文件工具限定此目录）
├── skills/                     ← 技能文件
├── src/
│   ├── atri/                   ← 核心后端 + GUI
│   │   ├── main.py             ← CLI 入口
│   │   ├── ai_service.py       ← AI 对话引擎
│   │   ├── tool_manager.py     ← 工具注册调度
│   │   ├── prompt_manager.py   ← 系统提示词 + 难度注入
│   │   ├── rag.py              ← 知识库搜索（Agentic Search）
│   │   ├── ui/                 ← PySide6 桌面 GUI
│   │   └── setup.py            ← 配置向导
│   ├── qqbot/                  ← QQ Bot 模块
│   │   ├── __init__.py         ← QQBotRunner 线程
│   │   ├── config.py           ← 配置读取（文件 + 环境变量）
│   │   ├── connection.py        ← WebSocket 网关
│   │   └── handler.py          ← 消息处理
│   └── code_runner/            ← AI 代码模拟运行
└── tests/                      ← pytest 测试
```

---

## 常见问题

**Q: 启动报 "api配置错误"** — 运行 `python boot.py` 重新走一遍配置，或单独运行 `atri-setup` 只改 API 配置。

**Q: 贴吧工具不可用** — 运行 `python boot.py` 选择安装 aiotieba，或手动 `uv pip install aiotieba`。

**Q: QQ Bot 连接不上** — 检查控制台 `[QQBot]` / `[qqbot:xxx]` 开头的调试输出，常见原因：
- 凭据错误（AppId/ClientSecret 不正确）
- `data/UserSettings.json` 中 QQBot 配置格式不对
- 网络问题（需访问 api.sgroup.qq.com 和 bots.qq.com）

**Q: QQ Bot 配置在哪里** — 运行 `atri-setup`，在第五步输入；或编辑 `data/UserSettings.json` 添加 `QQBot` 字段。

**Q: 网络请求失败** — 检查网络和 API URL 是否正确。

**Q: 如何重置对话** — 在侧栏右键会话选删除，或直接删 `data/sessions/` 下的对应文件。

**Q: 如何修改角色** — 编辑 `data/SOUL.json` 后重启。
