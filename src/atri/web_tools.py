"""Web search and extract tools via Parallel free MCP.

Zero-config: uses the free hosted Search MCP at https://search.parallel.ai/mcp
with no API key required. Implements a minimal Streamable-HTTP JSON-RPC client
for the two MCP tools (web_search / web_fetch).

SSRF protection: blocks requests to private/internal IPs, loopback, link-local,
CGNAT (100.64.0.0/10), and cloud metadata endpoints (169.254.169.254).

Based on Hermes plugins/web/parallel/provider.py and tools/url_safety.py.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
import uuid
from typing import Any
from urllib.parse import quote, unquote, urlparse, urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP endpoint constants
# ---------------------------------------------------------------------------

_MCP_SEARCH_URL = "https://search.parallel.ai/mcp"
_MCP_PROTOCOL_VERSION = "2025-06-18"
_MCP_CLIENT_NAME = "mcp-web-client"
_MCP_CLIENT_VERSION = "1.0.0"
_MCP_USER_AGENT = f"{_MCP_CLIENT_NAME}/{_MCP_CLIENT_VERSION}"
_MCP_TIMEOUT = 30.0

# ---------------------------------------------------------------------------
# SSRF protection — always-blocked IPs and networks
# ---------------------------------------------------------------------------

_ALWAYS_BLOCKED_IPS = frozenset({
    ipaddress.ip_address("169.254.169.254"),       # AWS/GCP/Azure/DO/Oracle metadata
    ipaddress.ip_address("169.254.170.2"),          # AWS ECS task metadata
    ipaddress.ip_address("169.254.169.253"),         # Azure IMDS wire server
    ipaddress.ip_address("fd00:ec2::254"),           # AWS metadata (IPv6)
    ipaddress.ip_address("100.100.100.200"),         # Alibaba Cloud metadata
    ipaddress.ip_address("::ffff:169.254.169.254"),  # IPv4-mapped
    ipaddress.ip_address("::ffff:169.254.170.2"),
    ipaddress.ip_address("::ffff:169.254.169.253"),
    ipaddress.ip_address("::ffff:100.100.100.200"),
})

_ALWAYS_BLOCKED_NETWORKS = (
    ipaddress.ip_network("169.254.0.0/16"),          # entire link-local range
    ipaddress.ip_network("::ffff:169.254.0.0/112"),   # IPv4-mapped link-local
)

# 100.64.0.0/10 (CGNAT, RFC 6598) — NOT covered by ipaddress.is_private
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

# ---------------------------------------------------------------------------
# Secret leak detection
# ---------------------------------------------------------------------------

_SECRET_PATTERN = re.compile(
    r"(?:sk-|api_key|apikey|api-key|token|secret|password|auth|credential)s?\s*[=:]\s*\S",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# MCP JSON-RPC client
# ---------------------------------------------------------------------------


def _new_session_id() -> str:
    """Mint a fresh session id for a single MCP tool call."""
    return f"{_MCP_CLIENT_NAME}-{uuid.uuid4().hex}"


def _mcp_headers(
    session_id: str | None,
    protocol_version: str | None = None,
) -> dict[str, str]:
    """Headers for an MCP request."""
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": _MCP_USER_AGENT,
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    if protocol_version:
        headers["MCP-Protocol-Version"] = protocol_version
    return headers


def _mcp_response_envelope(text: str, request_id: str) -> dict[str, Any]:
    """Select the JSON-RPC response for *request_id* from an MCP response body.

    Handles both plain JSON and SSE (text/event-stream) responses.
    """
    body = (text or "").strip()
    if not body:
        return {}

    # Plain JSON (single object or batch array)
    if body.startswith("{") or body.startswith("["):
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, list):
            for msg in parsed:
                if isinstance(msg, dict) and msg.get("id") == request_id:
                    return msg
            return parsed[-1] if (parsed and isinstance(parsed[-1], dict)) else {}
        return parsed

    # SSE: scan data lines for the matching result/error message
    fallback: dict[str, Any] = {}
    data_lines: list[str] = []
    for raw_line in body.split("\n"):
        line = raw_line.rstrip("\r")
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


def _mcp_payload(envelope: dict[str, Any]) -> dict[str, Any]:
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
    raise RuntimeError(
        f"Parallel MCP returned no parseable content: {str(result)[:500]}"
    )


def _mcp_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# URL safety — SSRF protection + secret leak detection
# ---------------------------------------------------------------------------


def normalize_url_for_request(url: str) -> str:
    """Return an ASCII-safe HTTP URL.

    Encodes non-ASCII hostnames (IDNA) and percent-encodes path/query/fragment.
    """
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


def _check_url_for_secrets(url: str) -> str | None:
    """Return error message if URL contains embedded API keys/tokens, else None."""
    if _SECRET_PATTERN.search(url) or _SECRET_PATTERN.search(unquote(url)):
        return (
            "Blocked: URL contains what appears to be an API key or token. "
            "Secrets must not be sent in URLs."
        )
    return None


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the IP should be blocked for SSRF protection."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        embedded = ip.ipv4_mapped
        return (
            embedded.is_private
            or embedded.is_loopback
            or embedded.is_link_local
            or embedded.is_reserved
            or embedded.is_multicast
            or embedded.is_unspecified
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


# ---------------------------------------------------------------------------
# web_search via Parallel MCP
# ---------------------------------------------------------------------------


def _mcp_web_search(query: str, limit: int) -> dict[str, Any]:
    """Run a web_search call against the hosted Search MCP."""
    payload = _mcp_call(
        "web_search",
        {
            "objective": query,
            "search_queries": [query],
            "session_id": _new_session_id(),
        },
    )

    web_results: list[dict[str, Any]] = []
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
        "attribution": (
            "Search powered by the free Parallel Web Search MCP "
            "(https://parallel.ai)."
        ),
    }


def web_search_tool(query: str, limit: int = 5) -> str:
    """Search the web. Returns JSON with titles, URLs, and descriptions.

    Args:
        query: The search query.
        limit: Max results (1-100, default 5).

    Returns:
        JSON string in Hermes-compatible format:
        {"success": true, "data": {"web": [{"title":..., "url":...,
         "description":..., "position":...}]}}
    """
    if not query or not query.strip():
        return json.dumps(
            {"success": False, "error": "搜索关键词不能为空。"}, ensure_ascii=False
        )

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 5
    limit = min(max(limit, 1), 100)

    try:
        response_data = _mcp_web_search(query.strip(), limit)
        return json.dumps(response_data, indent=2, ensure_ascii=False)
    except httpx.HTTPError as e:
        return json.dumps(
            {"success": False, "error": f"搜索请求失败：{e}"}, ensure_ascii=False
        )
    except Exception as e:
        logger.warning("web_search error: %s", e)
        return json.dumps(
            {"success": False, "error": f"搜索失败：{e}"}, ensure_ascii=False
        )


# ---------------------------------------------------------------------------
# web_extract via Parallel MCP
# ---------------------------------------------------------------------------


def _mcp_web_fetch(urls: list[str]) -> list[dict[str, Any]]:
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

    by_url: dict[str, dict[str, Any]] = {}
    for item in payload.get("results") or []:
        if isinstance(item, dict) and item.get("url"):
            by_url.setdefault(item["url"], item)

    results: list[dict[str, Any]] = []
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
        content = item.get("full_content") or "\n\n".join(
            item.get("excerpts") or []
        )
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
        JSON string: {"results": [{"url":..., "title":..., "content":...,
        "error":...}]}
    """
    if not urls:
        return json.dumps(
            {"success": False, "error": "URL 列表不能为空。"}, ensure_ascii=False
        )

    urls = urls[:5]

    # Secret leak detection
    for u in urls:
        err = _check_url_for_secrets(u)
        if err:
            return json.dumps({"success": False, "error": err}, ensure_ascii=False)

    # URL normalization
    normalized_urls = [normalize_url_for_request(u) for u in urls]

    # SSRF protection
    safe_urls: list[str] = []
    ssrf_blocked: list[dict[str, Any]] = []
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
        return json.dumps(
            {"success": False, "error": f"提取请求失败：{e}"}, ensure_ascii=False
        )
    except Exception as e:
        logger.warning("web_extract error: %s", e)
        return json.dumps(
            {"success": False, "error": f"提取失败：{e}"}, ensure_ascii=False
        )

    # Merge blocked URLs back
    if ssrf_blocked:
        results = ssrf_blocked + results

    trimmed = [{
        "url": r.get("url", ""),
        "title": r.get("title", ""),
        "content": r.get("content", ""),
        "error": r.get("error"),
    } for r in results]

    return json.dumps({"results": trimmed}, indent=2, ensure_ascii=False)
