import asyncio
import json
import logging
import time

logger = logging.getLogger(__name__)

# ── QQ Bot API constants ──────────────────────────────────────────────
API_BASE = "https://api.sgroup.qq.com"
TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
GATEWAY_URL_PATH = "/gateway"

# Fatal close codes — stop reconnecting
FATAL_CLOSE_CODES = {4001, 4002, 4010, 4011, 4012, 4013, 4014, 4914, 4915}
# Token expired — retryable
TOKEN_EXPIRED_CODES = {4004}
# Rate limited
RATE_LIMIT_CODES = {4008}
# Session invalid — retryable
SESSION_INVALID_CODES = {4006, 4007, 4009}

RECONNECT_BACKOFF = [2, 5, 10, 30, 60]
MAX_RECONNECT_ATTEMPTS = 100
RECONNECT_RESET_AFTER = 60  # reset backoff counter after 60s of stable connection


def _is_fatal_close_code(code: int) -> bool:
    return code in FATAL_CLOSE_CODES


class QQCloseError(Exception):
    def __init__(self, code: int, reason: str = ""):
        self.code = code
        self.reason = reason
        super().__init__(f"WebSocket closed (code={code}, reason={reason})")


class QQBotConnection:
    """WebSocket gateway client for QQ Bot API v2.

    Handles: connect → Hello → Identify/Resume → listen loop +
    heartbeat → reconnect on close.

    Call ``set_message_callback(coro_fn)`` to receive parsed message dicts.
    """

    def __init__(self, app_id: str, client_secret: str):
        self._app_id = app_id
        self._client_secret = client_secret
        self._log_tag = f"qqbot:{app_id[:8]}"
        self._session = None
        self._ws = None
        self._token: str | None = None
        self._token_expiry: float = 0
        self._session_id: str | None = None
        self._last_seq: int | None = None
        self._heartbeat_interval: float = 30
        self._running: bool = False
        self._message_callback = None
        self._heartbeat_task: asyncio.Task | None = None
        self._reconnect_count: int = 0
        self._last_connect_time: float = 0
        self._connect_lock = asyncio.Lock()

    def set_message_callback(self, callback):
        """Set async callback(event_type, payload) for inbound messages."""
        self._message_callback = callback

    async def _ensure_token(self) -> str:
        import httpx
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token
        print(f"[{self._log_tag}] 获取 access token...")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(TOKEN_URL, json={
                    "appId": self._app_id,
                    "clientSecret": self._client_secret,
                })
                resp.raise_for_status()
                data = resp.json()
                self._token = data["access_token"]
                self._token_expiry = now + int(data.get("expires_in", 7200))
                print(f"[{self._log_tag}] access token 获取成功")
                return self._token
        except Exception as e:
            print(f"[{self._log_tag}] access token 获取失败: {e}")
            raise

    async def _get_gateway_url(self) -> str:
        import httpx
        token = await self._ensure_token()
        print(f"[{self._log_tag}] 获取网关地址...")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    API_BASE + GATEWAY_URL_PATH,
                    headers={"Authorization": f"QQBot {token}"},
                )
                resp.raise_for_status()
                url = resp.json()["url"]
                print(f"[{self._log_tag}] 网关地址: {url[:50]}...")
                return url
        except Exception as e:
            print(f"[{self._log_tag}] 获取网关地址失败: {e}")
            raise

    async def connect(self) -> None:
        """Connect and run the main event loop (blocks until stop())."""
        import aiohttp
        self._running = True
        self._session = aiohttp.ClientSession()
        print(f"[{self._log_tag}] 开始连接循环")
        try:
            while self._running:
                try:
                    ws_url = await self._get_gateway_url()
                    print(f"[{self._log_tag}] 网关地址已获取，建立 WebSocket...")
                    async with self._session.ws_connect(ws_url) as ws:
                        self._ws = ws
                        self._heartbeat_task = asyncio.create_task(
                            self._heartbeat_loop()
                        )
                        self._last_connect_time = time.time()
                        await self._read_events()
                except QQCloseError as e:
                    if _is_fatal_close_code(e.code):
                        print(f"[{self._log_tag}] 致命关闭码 {e.code}, 停止重连")
                        logger.error("[%s] Fatal close code %s, stopping", self._log_tag, e.code)
                        break
                    if e.code in TOKEN_EXPIRED_CODES:
                        self._token = None
                    if e.code in SESSION_INVALID_CODES:
                        self._session_id = None
                        self._last_seq = None
                    if e.code in RATE_LIMIT_CODES:
                        await asyncio.sleep(60)
                    print(f"[{self._log_tag}] 连接关闭 (code={e.code}), 将重连...")
                except Exception as e:
                    err_str = str(e)
                    print(f"[{self._log_tag}] 连接错误: {err_str}")
                    # Stop retrying on auth errors
                    if "401" in err_str or "403" in err_str or "400" in err_str:
                        print(f"[{self._log_tag}] 认证失败，请检查 AppId/ClientSecret")
                        break
                if self._running:
                    await self._reconnect_delay()
        finally:
            if self._session:
                await self._session.close()

    async def stop(self) -> None:
        print(f"[{self._log_tag}] 正在断开...")
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()

    async def _read_events(self) -> None:
        import aiohttp
        while self._running:
            msg = await self._ws.receive()
            if msg.type == aiohttp.WSMsgType.TEXT:
                payload = json.loads(msg.data)
                self._dispatch_payload(payload)
            elif msg.type == aiohttp.WSMsgType.CLOSE:
                raise QQCloseError(msg.data, msg.extra)
            elif msg.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                raise RuntimeError("WebSocket closed")

    async def _heartbeat_loop(self) -> None:
        try:
            while self._running:
                await asyncio.sleep(self._heartbeat_interval)
                if self._ws and not self._ws.closed:
                    await self._ws.send_json({"op": 1, "d": self._last_seq})
        except asyncio.CancelledError:
            pass

    async def _send_identify(self) -> None:
        token = await self._ensure_token()
        payload = {
            "op": 2,
            "d": {
                "token": f"QQBot {token}",
                "intents": (1 << 25) | (1 << 12),  # C2C_GROUP_AT + DIRECT_MESSAGE
                "shard": [0, 1],
            },
        }
        if self._ws and not self._ws.closed:
            await self._ws.send_json(payload)

    async def _send_resume(self) -> None:
        token = await self._ensure_token()
        payload = {
            "op": 6,
            "d": {"token": f"QQBot {token}", "session_id": self._session_id, "seq": self._last_seq},
        }
        if self._ws and not self._ws.closed:
            await self._ws.send_json(payload)
            logger.info("[%s] Resume sent", self._log_tag)

    def _dispatch_payload(self, payload: dict) -> None:
        op = payload.get("op")
        t = payload.get("t")
        s = payload.get("s")
        d = payload.get("d")
        if isinstance(s, int) and (self._last_seq is None or s > self._last_seq):
            self._last_seq = s

        if op == 10:
            d_data = d if isinstance(d, dict) else {}
            interval_ms = d_data.get("heartbeat_interval", 30000)
            self._heartbeat_interval = interval_ms / 1000.0 * 0.8
            if self._session_id and self._last_seq is not None:
                self._create_task(self._send_resume())
            else:
                self._create_task(self._send_identify())
        elif op == 0 and t:
            if t == "READY":
                if isinstance(d, dict):
                    self._session_id = d.get("session_id")
                print(f"[{self._log_tag}] READY — 连接成功, session={self._session_id}")
            elif t in ("C2C_MESSAGE_CREATE", "GROUP_AT_MESSAGE_CREATE"):
                if self._message_callback:
                    self._create_task(self._message_callback(t, d))
        elif op == 7:
            if self._ws and not self._ws.closed:
                self._create_task(self._ws.close())
        elif op == 9:
            resumable = bool(d) if d is not None else False
            if not resumable:
                self._session_id = None
                self._last_seq = None
            if self._ws and not self._ws.closed:
                self._create_task(self._ws.close())

    def _create_task(self, coro):
        try:
            loop = asyncio.get_running_loop()
            return loop.create_task(coro)
        except RuntimeError:
            return None

    async def _reconnect_delay(self) -> None:
        now = time.time()
        if now - self._last_connect_time > RECONNECT_RESET_AFTER:
            self._reconnect_count = 0
        delay = RECONNECT_BACKOFF[min(self._reconnect_count, len(RECONNECT_BACKOFF) - 1)]
        self._reconnect_count = min(self._reconnect_count + 1, MAX_RECONNECT_ATTEMPTS - 1)
        self._last_connect_time = now
        await asyncio.sleep(delay)
