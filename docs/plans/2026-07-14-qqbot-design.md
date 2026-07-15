# DSPark-Code QQ Bot 接入设计

> 2026-07-14 | 状态：已批准

## 目标

让用户可以在 QQ 中与小洛对话。桌面端启动时自动连接 QQ Bot，首次连接自动创建 QQ 专用会话。

## 技术方案

采用**腾讯官方 QQ Bot API v2**，参考 Hermes 的 QQBot adapter 实现。

- **协议：** WebSocket（接收事件）+ REST API（发送消息）
- **支持场景：** 私聊(C2C)、群@消息
- **依赖：** `aiohttp`（WebSocket）、`httpx`（已有依赖，用于 REST）

## 架构

```
腾讯 QQ 服务器
  ├─ WebSocket 推送事件
  └─ REST API 回复消息
        │
src/qqbot/ (独立模块，不混入 atri)
  ├─ __init__.py      — 模块导出
  ├─ connection.py    — WebSocket 连接 + 心跳 + 重连
  ├─ handler.py       — 消息解析 + ACL + 调用 AIService
  └─ config.py        — 配置加载
        │
AppShell (桌面端，通过导入 qqbot 模块使用)
  └─ 首次启动 → 自动创建 "[QQ] QQ聊天" 会话
     QQ 消息流入该会话 → AI 回复 → 发送到 QQ
```

## 文件规划

| 文件 | 职责 |
|------|------|
| `src/qqbot/__init__.py` | 模块导出，对外暴露 `start_bot()` / `stop_bot()` |
| `src/qqbot/connection.py` | WebSocket 网关客户端：连接、心跳、重连、消息接收 |
| `src/qqbot/handler.py` | 消息解析、ACL 白名单、调用 AIService 生成回复、通过 REST 发送 |
| `src/qqbot/config.py` | 从 UserSettings.json 读取 QQ Bot 配置 |

改动点：
- `src/atri/ui/app_shell.py` — 启动时导入并启动 qqbot，首次运行时创建 QQ 专用会话

其余 atri 模块不受影响。

## 启动流程

1. 桌面端 AppShell 初始化
2. QQBot 自动连接（异步，不阻塞 UI）
3. 收到 QQ 消息 → 查找/创建 "[QQ] QQ聊天" 会话
4. 消息追加到会话 history
5. 调用 AIService 生成回复
6. 回复显示在桌面端 QQ 会话 + 通过 REST 发送到 QQ

## 配置

在 `data/UserSettings.json` 中新增：

```json
{
  "QQBot": {
    "AppId": "your-app-id",
    "ClientSecret": "your-secret",
    "DmPolicy": "open",
    "GroupPolicy": "open"
  }
}
```

## 注意事项

- QQ Bot API v2 需要提前在 QQ 开放平台注册应用
- 私聊和群@消息都能触发 AI 回复
- 桌面端关闭时 Bot 也断开连接
- Hermes 的 `adapter.py`（~3200 行）作为参考实现，DSPark-Code 版本做大幅精简
