# Web Search / Web Extract 复刻 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 Hermes 的 web_search + web_extract 精简复刻到 ATRI 项目，用 Parallel 免费 MCP 替代现有 Bing 爬虫。

**Architecture:** 新建 `src/atri/web_tools.py` 独立模块，包含 MCP JSON-RPC 客户端、SSRF 防护、密钥泄露检测。`tool_manager.py` 更新工具注册和调度。全部同步实现（匹配现有同步 agent loop）。

**Tech Stack:** Python stdlib (`json`, `re`, `socket`, `ipaddress`, `urllib.parse`, `uuid`), `httpx` (已有)

**依赖:** 零新增 pip 包

---

### Task 1: 创建 `src/atri/web_tools.py` — MCP 客户端 + URL 安全

**Files:**
- Create: `src/atri/web_tools.py`

**Step 1: 创建文件骨架**

```python
"""Web search and extract tools via Parallel free MCP.

Zero-config: uses the free hosted Search MCP at https://search.parallel.ai/mcp
with no API key required. Implements a minimal Streamable-HTTP JSON-RPC client
for the two MCP tools (web_search / web_fetch).

SSRF protection: blocks requests to private/internal IPs, loopback, link-local,
CGNAT (100.64.0.0/10), and cloud metadata endpoints (169.254.169.254).
"""

import ipaddress
import json
import logging
import re
import socket
import uuid
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)

_MCP_SEARCH_URL = "https://search.parallel.ai/mcp"
_MCP_PROTOCOL_VERSION = "2025-06-18"
_MCP_CLIENT_NAME = "mcp-web-client"
_MCP_CLIENT_VERSION = "1.0.0"
_MCP_USER_AGENT = f"{_MCP_CLIENT_NAME}/{_MCP_CLIENT_VERSION}"
_MCP_TIMEOUT = 30.0

# Cloud metadata IPs — always blocked, even if user opts out of SSRF
_ALWAYS_BLOCKED_IPS = frozenset({
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("169.254.170.2"),
    ipaddress.ip_address("169.254.169.253"),
    ipaddress.ip_address("fd00:ec2::254"),
    ipaddress.ip_address("100.100.100.200"),
    ipaddress.ip_address("::ffff:169.254.169.254"),
    ipaddress.ip_address("::ffff:169.254.170.2"),
    ipaddress.ip_address("::ffff:169.254.169.253"),
    ipaddress.ip_address("::ffff:100.100.100.200"),
})
_ALWAYS_BLOCKED_NETWORKS = (
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::ffff:169.254.0.0/112"),
)
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

# Regex for detecting API keys / tokens in URLs (from Hermes agent.redact._PREFIX_RE)
_SECRET_PATTERN = re.compile(
    r"(?:sk-|api_key|apikey|api-key|token|secret|password|auth|credential)s?\s*[=:]\s*\S",
    re.IGNORECASE,
)
```

**Step 2: Commit**

```bash
git add src/atri/web_tools.py
git commit -m "feat: add web_tools.py skeleton with constants and security sets"
```

---

### Task 2: 实现 MCP JSON-RPC 客户端

**Files:**
- Modify: `src/atri/web_tools.py`

**Step 1: 添加 `_new_session_id()` 和 `_mcp_headers()`**

```python
def _new_session_id() -> str:
    return f"{_MCP_CLIENT_NAME}-{uuid.uuid4().hex}"


def _mcp_headers(session_id: str | None, protocol_version: str | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": _MCP_USER_AGENT,
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    if protocol_version:
        headers["MCP-Protocol-Version"] = protocol_version
    return headers
```

**Step 2: 添加 `_mcp_response_envelope()` — 解析 SSE/JSON 响应**

```python
def _mcp_response_envelope(text: str, request_id: str) -> dict:
    """Select the JSON-RPC response for *request_id* from an MCP response body.
    
    Handles both plain JSON and SSE (text/event-stream) responses.
    """
    body = (text or "").strip()
    if not body:
        return {}

    # Plain JSON
    if body.startswith("{") or body.startswith("["):
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, list):
            for msg in parsed:
                if isinstance(msg, dict) and msg.get("id") == request_id:
                    return msg
            return parsed[-1] if isinstance(parsed[-1], dict) else {}
        return parsed if parsed.get("id") == request_id else parsed

    # SSE: scan for the matching result/error message
    fallback = {}
    data_lines = []
    for raw in body.split("\n"):
        line = raw.rstrip("\r")
        if line.startswith("data:"):
            data_lines.append(line[len("data:"):].lstrip())
        elif line.strip() == "" and data_lines:
            try:
                msg = json.loads("\n".join(data_lines))
            except json.JSONDecodeError:
                data_lines = []
                continue
            data_lines = []
            if isinstance(msg, dict) and ("result" in msg or "error" in msg):
                if msg.get("id") == request_id:
                    return msg
                fallback = msg
    return fallback


def _mcp_payload(envelope: dict) -> dict:
    """Extract tool result payload from a tools/call envelope."""
    if "error" in envelope:
        raise RuntimeError(f"Parallel MCP error: {str(envelope['error'])[:500]}")
    result = envelope.get("result") or {}
    if result.get("isError"):
        raise RuntimeError(f"Parallel MCP tool error: {str(result)[:500]}")

    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured

    for block in result.get("content", []) or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text = str(block.get("text") or "")
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    raise RuntimeError(f"Parallel MCP returned no parseable content: {str(result)[:500]}")
```

**Step 3: 添加 `_mcp_call()` — 完整的 MCP 握手 + 工具调用**

```python
def _mcp_call(tool_name: str, arguments: dict) -> dict:
    """Run the MCP handshake then a single tools/call and return its payload.
    
    initialize → capture Mcp-Session-Id → notifications/initialized → tools/call
    """
    with httpx.Client(timeout=_MCP_TIMEOUT) as client:
        # 1. initialize
        init_id = str(uuid.uuid4())
        init = client.post(
            _MCP_SEARCH_URL,
            headers=_mcp_headers(None),
            json={
                "jsonrpc": "2.0",
                "id": init_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": _MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": _MCP_CLIENT_NAME,
                        "version": _MCP_CLIENT_VERSION,
                    },
                },
            },
        )
        init.raise_for_status()
        mcp_session_id = init.headers.get("mcp-session-id")
        init_env = _mcp_response_envelope(init.text, init_id)
        negotiated_version = (
            (init_env.get("result") or {}).get("protocolVersion")
            or _MCP_PROTOCOL_VERSION
        )

        # 2. notifications/initialized
        client.post(
            _MCP_SEARCH_URL,
            headers=_mcp_headers(mcp_session_id, negotiated_version),
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )

        # 3. tools/call
        call_id = str(uuid.uuid4())
        call = client.post(
            _MCP_SEARCH_URL,
            headers=_mcp_headers(mcp_session_id, negotiated_version),
            json={
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
        )
        call.raise_for_status()
        return _mcp_payload(_mcp_response_envelope(call.text, call_id))
```

**Step 4: Commit**

```bash
git add src/atri/web_tools.py
git commit -m "feat: add MCP JSON-RPC client for Parallel free Search MCP"
```

---

### Task 3: 实现 URL 安全模块

**Files:**
- Modify: `src/atri/web_tools.py`

**Step 1: 添加 `normalize_url_for_request()`**

```python
def normalize_url_for_request(url: str) -> str:
    """Return an ASCII-safe HTTP URL. Encodes non-ASCII hostnames (IDNA)
    and percent-encodes path/query/fragment."""
    if not isinstance(url, str):
        return url
    raw = url.strip()
    if not raw:
        return raw

    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw

    if parsed.scheme.lower() not in {"http", "https"}:
        return raw

    netloc = parsed.netloc
    hostname = parsed.hostname
    if hostname:
        try:
            ascii_host = hostname.encode("idna").decode("ascii")
        except UnicodeError:
            ascii_host = hostname
        if ascii_host != hostname:
            netloc = netloc.replace(hostname, ascii_host, 1)

    path = quote(parsed.path, safe="/%:@!$&'()*+,;=")
    query = quote(parsed.query, safe="/%:@!$&'()*+,;=?")
    fragment = quote(parsed.fragment, safe="/%:@!$&'()*+,;=?")

    return urlunsplit((parsed.scheme, netloc, path, query, fragment))
```

**Step 2: 添加 `_check_url_for_secrets()`**

```python
def _check_url_for_secrets(url: str) -> str | None:
    """Return error message if URL contains embedded API keys/tokens, else None."""
    if _SECRET_PATTERN.search(url) or _SECRET_PATTERN.search(unquote(url)):
        return (
            "Blocked: URL contains what appears to be an API key or token. "
            "Secrets must not be sent in URLs."
        )
    return None
```

**Step 3: 添加 `_is_blocked_ip()` 和 `is_safe_url()`**

```python
def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the IP should be blocked for SSRF protection."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        embedded = ip.ipv4_mapped
        return (
            embedded.is_private or embedded.is_loopback
            or embedded.is_link_local or embedded.is_reserved
            or embedded.is_multicast or embedded.is_unspecified
            or embedded in _CGNAT_NETWORK
        )
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast or ip.is_unspecified:
        return True
    if ip in _CGNAT_NETWORK:
        return True
    return False


def is_safe_url(url: str) -> bool:
    """Return True if the URL does NOT target a private/internal address.
    
    Resolves hostname and checks against private/loopback/link-local/CGNAT
    ranges. Cloud metadata IPs are always blocked. Fails closed (DNS errors
    → blocked).
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").strip().lower().rstrip(".")
        scheme = (parsed.scheme or "").strip().lower()
        if scheme not in {"http", "https"}:
            return False
        if not hostname:
            return False

        # Literal IP check
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            ip = None

        if ip is not None:
            if ip in _ALWAYS_BLOCKED_IPS or any(
                ip in net for net in _ALWAYS_BLOCKED_NETWORKS
            ):
                return False
            return not _is_blocked_ip(ip)

        # DNS resolve
        try:
            addr_info = socket.getaddrinfo(
                hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
            )
        except socket.gaierror:
            return False  # fail closed

        for _family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                resolved = ipaddress.ip_address(ip_str)
            except ValueError:
                continue

            if resolved in _ALWAYS_BLOCKED_IPS or any(
                resolved in net for net in _ALWAYS_BLOCKED_NETWORKS
            ):
                return False
            if _is_blocked_ip(resolved):
                return False

        return True
    except Exception:
        return False  # fail closed
```

**Step 4: Commit**

```bash
git add src/atri/web_tools.py
git commit -m "feat: add URL safety — SSRF protection and secret leak detection"
```

---

### Task 4: 实现 `web_search_tool()` 和 `web_extract_tool()`

**Files:**
- Modify: `src/atri/web_tools.py`

**Step 1: 添加 `_mcp_web_search()` 和 `web_search_tool()`**

```python
def _mcp_web_search(query: str, limit: int) -> dict:
    """Run a web_search call against the hosted Search MCP."""
    payload = _mcp_call(
        "web_search",
        {
            "objective": query,
            "search_queries": [query],
            "session_id": _new_session_id(),
        },
    )

    web_results = []
    for i, result in enumerate((payload.get("results") or [])[: max(limit, 1)]):
        if not isinstance(result, dict):
            continue
        excerpts = result.get("excerpts") or []
        web_results.append({
            "title": result.get("title") or "",
            "url": result.get("url") or "",
            "description": " ".join(excerpts) if excerpts else "",
            "position": i + 1,
        })

    return {
        "success": True,
        "data": {"web": web_results},
        "provider": "parallel",
        "attribution": "Search powered by the free Parallel Web Search MCP (https://parallel.ai).",
    }


def web_search_tool(query: str, limit: int = 5) -> str:
    """Search the web. Returns JSON with titles, URLs, and descriptions.
    
    Args:
        query: The search query.
        limit: Max results (1-100, default 5).
    
    Returns:
        JSON string: {"success": true, "data": {"web": [{"title":..., "url":..., "description":..., "position":...}]}}
    """
    if not query or not query.strip():
        return json.dumps({"success": False, "error": "搜索关键词不能为空。"}, ensure_ascii=False)

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 5
    limit = min(max(limit, 1), 100)

    try:
        response_data = _mcp_web_search(query.strip(), limit)
        return json.dumps(response_data, indent=2, ensure_ascii=False)
    except httpx.HTTPError as e:
        return json.dumps({"success": False, "error": f"搜索请求失败：{e}"}, ensure_ascii=False)
    except Exception as e:
        logger.warning("web_search error: %s", e)
        return json.dumps({"success": False, "error": f"搜索失败：{e}"}, ensure_ascii=False)
```

**Step 2: 添加 `_mcp_web_fetch()` 和 `web_extract_tool()`**

```python
def _mcp_web_fetch(urls: list[str]) -> list[dict]:
    """Run a web_fetch call against the hosted Search MCP.
    
    Returns one result dict per input URL in request order.
    """
    payload = _mcp_call(
        "web_fetch",
        {
            "urls": list(urls),
            "full_content": True,
            "session_id": _new_session_id(),
        },
    )

    by_url = {}
    for item in payload.get("results") or []:
        if isinstance(item, dict) and item.get("url"):
            by_url.setdefault(item["url"], item)

    results = []
    for url in urls:
        item = by_url.get(url)
        if item is None:
            results.append({
                "url": url,
                "title": "",
                "content": "",
                "error": "extraction failed (no content returned)",
            })
            continue
        title = item.get("title") or ""
        content = item.get("full_content") or "\n\n".join(item.get("excerpts") or [])
        results.append({
            "url": url,
            "title": title,
            "content": content,
        })
    return results


def web_extract_tool(urls: list[str], format: str = "markdown") -> str:
    """Extract content from web pages. Returns JSON with page content.
    
    Args:
        urls: List of URLs to extract (max 5).
        format: Output format (ignored, always markdown from MCP).
    
    Returns:
        JSON string: {"results": [{"url":..., "title":..., "content":..., "error":...}]}
    """
    if not urls:
        return json.dumps({"success": False, "error": "URL 列表不能为空。"}, ensure_ascii=False)

    urls = urls[:5]

    # Secret leak detection
    for url in urls:
        err = _check_url_for_secrets(url)
        if err:
            return json.dumps({"success": False, "error": err}, ensure_ascii=False)

    # URL normalization
    normalized_urls = [normalize_url_for_request(u) for u in urls]

    # SSRF protection
    safe_urls = []
    ssrf_blocked = []
    for url in normalized_urls:
        if not is_safe_url(url):
            ssrf_blocked.append({
                "url": url,
                "title": "",
                "content": "",
                "error": "Blocked: URL targets a private or internal network address",
            })
        else:
            safe_urls.append(url)

    if not safe_urls:
        return json.dumps({"results": ssrf_blocked}, indent=2, ensure_ascii=False)

    try:
        results = _mcp_web_fetch(safe_urls)
    except httpx.HTTPError as e:
        return json.dumps({"success": False, "error": f"提取请求失败：{e}"}, ensure_ascii=False)
    except Exception as e:
        logger.warning("web_extract error: %s", e)
        return json.dumps({"success": False, "error": f"提取失败：{e}"}, ensure_ascii=False)

    if ssrf_blocked:
        results = ssrf_blocked + results

    trimmed = [{
        "url": r.get("url", ""),
        "title": r.get("title", ""),
        "content": r.get("content", ""),
        "error": r.get("error"),
    } for r in results]

    response = {"results": trimmed}
    if not any(r.get("content") for r in trimmed) and ssrf_blocked:
        # All blocked
        pass

    return json.dumps(response, indent=2, ensure_ascii=False)
```

**Step 3: Commit**

```bash
git add src/atri/web_tools.py
git commit -m "feat: add web_search_tool and web_extract_tool via Parallel MCP"
```

---

### Task 5: 更新 `tool_manager.py` — 工具注册和调度

**Files:**
- Modify: `src/atri/tool_manager.py`

**Step 1: 添加 import**

在文件顶部的 import 区域（第 1-10 行），添加:
```python
from atri.web_tools import web_search_tool, web_extract_tool
```

**Step 2: 替换 web_search 工具定义**

将第 204-214 行替换为与 Hermes 对齐的 schema:
```python
        _make_tool("web_search",
            "Search the web for information. Returns up to 5 results by default with titles, URLs, and descriptions. "
            "The query is passed through to the search backend, so operators such as site:domain, filetype:pdf, "
            "intitle:word, -term, and \"exact phrase\" may work when supported.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up on the web. You may include operators such as "
                                       "site:example.com, filetype:pdf, intitle:word, -term, or \"exact phrase\"."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return. Defaults to 5.",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 5,
                    },
                },
                "required": ["query"],
            }),
```

**Step 3: 在 web_search 后面添加 web_extract 工具定义**

```python
        _make_tool("web_extract",
            "Extract content from web page URLs. Returns page content in markdown format. "
            "Also works with PDF URLs — pass the PDF link directly. "
            "If a URL fails or times out, use the browser tool to access it instead.",
            {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of URLs to extract content from (max 5 URLs per call)",
                        "maxItems": 5,
                    },
                },
                "required": ["urls"],
            }),
```

**Step 4: 替换 dispatch 逻辑**

将第 407-408 行:
```python
        if name == "web_search":
            return self._web_search(str(args.get("query", "")))
```
替换为:
```python
        if name == "web_search":
            return web_search_tool(str(args.get("query", "")), int(args.get("limit", 5) or 5))
        if name == "web_extract":
            urls = args.get("urls", [])
            if isinstance(urls, list):
                urls = urls[:5]
            else:
                urls = []
            return web_extract_tool(urls)
```

**Step 5: 删除旧的 `_web_search` 静态方法**

删除第 428-491 行（整个 `_web_search` 方法）。

**Step 6: 删除不再需要的 import**

移除 `import re`（如果 `_web_search` 是唯一使用它的地方——检查确认 `re` 是否在其他地方使用）。`tool_manager.py` 中 `re` 仅被 `_web_search` 使用，可以删除。`from html import unescape` 和 `from urllib.parse import quote_plus` 也仅被 `_web_search` 使用，一并删除。

更新第 1-5 行 imports:
```python
import json
import httpx
from atri.models import Tool, FunctionDef
from atri.file_tool import FileTool
from atri.memory_tool import MemoryTool
from atri.skill_loader import SkillLoader, SKILLS_DIR
from atri.tieba_tool import TiebaTool
from atri.web_tools import web_search_tool, web_extract_tool
```

**Step 7: Commit**

```bash
git add src/atri/tool_manager.py
git commit -m "feat: integrate web_search (Parallel MCP) + add web_extract tool"
```

---

### Task 6: 更新测试

**Files:**
- Modify: `tests/test_tool_manager.py`

**Step 1: 更新工具计数**

将第 10 行 `assert len(tm.tool_list) == 21` 改为 `assert len(tm.tool_list) == 22`（删 1 个旧 web_search 定义 + 新 web_search + 新 web_extract = +1）。

**Step 2: 添加 web_search smoke test**

```python
def test_web_search_tool_registered():
    tm = ToolManager()
    tm.tool_init()
    names = {t.function.name for t in tm.tool_list}
    assert "web_search" in names
    assert "web_extract" in names


def test_web_search_empty_query():
    from atri.web_tools import web_search_tool
    result = web_search_tool("")
    import json
    data = json.loads(result)
    assert data["success"] is False


def test_web_extract_empty_urls():
    from atri.web_tools import web_extract_tool
    result = web_extract_tool([])
    import json
    data = json.loads(result)
    assert data["success"] is False
```

**Step 3: 添加 SSRF 防护测试**

```python
def test_is_safe_url_blocks_private():
    from atri.web_tools import is_safe_url
    assert not is_safe_url("http://127.0.0.1/test")
    assert not is_safe_url("http://192.168.1.1/test")
    assert not is_safe_url("http://10.0.0.1/test")
    assert not is_safe_url("http://169.254.169.254/latest/meta-data")


def test_is_safe_url_allows_public():
    from atri.web_tools import is_safe_url
    assert is_safe_url("https://example.com")
    assert is_safe_url("https://www.google.com")


def test_check_url_for_secrets():
    from atri.web_tools import _check_url_for_secrets
    assert _check_url_for_secrets("https://api.example.com?key=sk-abc123") is not None
    assert _check_url_for_secrets("https://example.com/normal-page") is None
```

**Step 4: 运行测试验证**

```bash
pytest tests/test_tool_manager.py -v
```
Expected: all tests PASS

**Step 5: Commit**

```bash
git add tests/test_tool_manager.py
git commit -m "test: update tool count and add web_search/web_extract tests"
```

---

### Task 7: 手动烟雾测试

**Step 1: 启动 ATRI 并测试 web_search**

```bash
atri
```
输入: `搜索一下Python最新版本`
预期: 返回搜索结果的 JSON，包含 title/url/description

**Step 2: 测试 web_extract**

输入: `帮我把 https://www.python.org 的内容提取出来看看`
预期: 返回页面 markdown 内容

**Step 3: 验证错误处理**

直接在 Python 中验证:
```python
from atri.web_tools import web_search_tool, web_extract_tool
print(web_search_tool("Python", limit=3))
print(web_extract_tool(["https://example.com"]))
```
预期: 两次调用都返回有效的 JSON

---

### 完成后的文件清单

| 文件 | 状态 |
|------|------|
| `src/atri/web_tools.py` | 新建 (~280 行) |
| `src/atri/tool_manager.py` | 修改 (删除旧 _web_search, 更新 imports, 注册+dispatch) |
| `tests/test_tool_manager.py` | 修改 (更新计数 + 新测试) |
| `docs/plans/2026-07-09-web-tools-replication-design.md` | 已存在 |
| `docs/plans/2026-07-09-web-tools-implementation.md` | 本文件 |

**总计新增代码: ~350 行，零新依赖。**
