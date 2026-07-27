## 部署方法

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

**唯一要求：目标电脑有网络连接。**

---

## 功能

- **Function Calling 工具系统** — 文件读写、搜索、记忆管理、贴吧浏览，AI 自动调用工具完成任务
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
| `delete_file` | 删除文件（需确认） |
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

- `code-reviewer` — 傲娇编程导师
- `translator` — 中/英/日三语翻译
- `storyteller` — 交互式故事创作
- `confidant` — 深度倾听模式

---

## QQ Bot 配置

1. 前往 [QQ 开放平台](https://q.qq.com) 创建机器人应用
2. 获取 AppId 和 ClientSecret
3. 运行 `atri-setup` 或 `python boot.py`，在第五步输入凭据
4. 或直接在 `data/UserSettings.json` 中添加：
```json
"QQBot": {
  "AppId": "你的AppId",
  "ClientSecret": "你的ClientSecret"
}
```
5. 启动 `atri-ui`，底部状态栏会显示连接状态
6. 在 QQ 中向你的机器人发送消息，消息会出现在桌面 GUI 的 `[QQ] QQ聊天` 会话中

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
│   ├── UserSettings.json       ← API + QQ Bot + 贴吧配置（boot.py 生成）
│   ├── SOUL.json               ← 角色设定
│   ├── RULES.json              ← 行为准则
│   ├── CAPABILITY.json         ← 能力描述
│   ├── MemoryForUser.json      ← 用户画像（自动生成）
│   ├── sessions.json           ← 会话索引
│   └── sessions/               ← 每个会话的对话历史
├── workspace/                  ← 文件操作沙箱
├── skills/                     ← 技能文件
├── src/
│   ├── atri/                   ← 核心后端 + GUI
│   │   ├── main.py             ← CLI 入口
│   │   ├── ai_service.py       ← AI 对话引擎
│   │   ├── tool_manager.py     ← 工具注册调度
│   │   ├── ui/                 ← PySide6 桌面 GUI
│   │   └── setup.py            ← 配置向导
│   └── qqbot/                  ← QQ Bot 模块
│       ├── __init__.py         ← QQBotRunner 线程
│       ├── config.py           ← 配置读取
│       ├── connection.py        ← WebSocket 网关
│       └── handler.py          ← 消息处理
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
