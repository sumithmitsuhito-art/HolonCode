# Web Search / Web Extract 复刻设计

## 日期
2026-07-09

## 目标
将 Hermes 的 `web_search` 和 `web_extract` 工具精简复刻到 ATRI (DSPark-Code) 项目中，替换现有脆弱的 Bing HTML 爬虫方案。

## 源参考
- Hermes `tools/web_tools.py` — 工具入口
- Hermes `plugins/web/parallel/provider.py` — Parallel MCP 实现
- Hermes `tools/url_safety.py` — SSRF 防护
- Hermes `agent/web_search_provider.py` — Provider ABC

## 设计决策

### 范围
- **精简复刻**: 仅使用 Parallel 免费 MCP 作为唯一后端，不需要多 provider 插件体系
- **不加 LLM 摘要**: 页面内容原样返回
- **Hermes 同款工具 schema**: 参数名、返回格式完全对齐

### 新建文件
- `src/atri/web_tools.py` — 所有搜索/提取逻辑

### 修改文件
- `src/atri/tool_manager.py` — 注册 web_search + web_extract 工具，添加 dispatch 分支

## 架构

```
tool_manager.py (注册 + tool_actor 调度)
       ↓
web_tools.py (新建模块)
       ↓
Parallel 免费 MCP (search.parallel.ai/mcp)
   ├── web_search  → 网页搜索
   └── web_fetch   → 网页内容提取 (markdown)
```

## web_tools.py 函数清单

| 函数 | 类型 | 说明 |
|------|------|------|
| `web_search_tool(query, limit=5)` | 同步 | 搜网页，返回 JSON |
| `web_extract_tool(urls, format)` | 异步 | 提取网页内容，返回 JSON |
| `_mcp_call(tool_name, arguments)` | 同步 | MCP JSON-RPC 客户端 |
| `_mcp_web_search(query, limit)` | 同步 | 调 MCP web_search |
| `_mcp_web_fetch(urls)` | 同步 | 调 MCP web_fetch |
| `_normalize_url(url)` | 同步 | URL 规范化 |
| `_check_secrets_in_url(url)` | 同步 | 密钥泄露检测 |
| `is_safe_url(url)` | 同步 | SSRF 防护 (DNS+IP检查) |
| `async_is_safe_url(url)` | 异步 | is_safe_url 的异步包装 |

## 安全防护（直接移植 Hermes）

1. **密钥泄露检测**: 对 URL 原始值 + URL-decode 值做 `_PREFIX_RE` 正则检查
2. **SSRF 防护**: DNS 解析 → 检查私有/环回/链路本地/CGNAT/云 metadata IP
3. **URL 规范化**: 非 ASCII 域名 Punycode 编码，路径 percent-encoding

## 依赖
- `httpx` (已有) — HTTP 请求
- Python 标准库 — `asyncio`, `socket`, `ipaddress`, `urllib.parse`, `re`, `json`, `uuid`

## 零配置启动
Parallel 免费 MCP 端点 `https://search.parallel.ai/mcp` 匿名可用，不需要 API Key，不需要注册。
