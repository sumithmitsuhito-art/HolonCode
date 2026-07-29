import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

API_BASE = "https://api.sgroup.qq.com"
_AT_RE = re.compile(r"<@![^>]+>\s*")


def _strip_mention(text: str) -> str:
    return _AT_RE.sub("", text).strip()


def _parse_inbound(event_type: str, payload: dict) -> dict | None:
    """Parse a QQ message payload into a normalized dict. Returns None if unparseable."""
    msg_id = payload.get("id")
    author = payload.get("author", {}) if isinstance(payload.get("author"), dict) else {}
    author_id = author.get("id", "")
    author_name = author.get("username", "")
    content = payload.get("content", "")

    if event_type == "C2C_MESSAGE_CREATE":
        return {
            "chat_type": "c2c",
            "message_id": msg_id,
            "author_id": author_id,
            "author_name": author_name,
            "content": content,
        }
    elif event_type == "GROUP_AT_MESSAGE_CREATE":
        return {
            "chat_type": "group",
            "message_id": msg_id,
            "author_id": author_id,
            "author_name": author_name,
            "content": _strip_mention(content),
            "group_openid": payload.get("group_openid", ""),
        }
    return None


def _check_dm_policy(policy: str, allowlist: list[str], author_id: str) -> bool:
    if policy == "disabled":
        return False
    elif policy == "allowlist":
        return author_id in allowlist
    return True  # "open"


class QQBotHandler:
    """Process inbound QQ messages: ACL check → AI reply → send via REST."""

    def __init__(self, app_id: str, client_secret: str, ai_service, session_factory):
        self._app_id = app_id
        self._client_secret = client_secret
        self._ai_service = ai_service
        self._session_factory = session_factory
        self._dm_policy = "open"
        self._allowlist: list[str] = []
        self._seen_ids: dict[str, float] = {}
        self._token: str | None = None
        self._token_expiry: float = 0

    async def handle_message(self, event_type: str, payload: dict) -> None:
        parsed = _parse_inbound(event_type, payload)
        if parsed is None:
            return

        # Dedup
        msg_id = parsed["message_id"]
        now = datetime.now().timestamp()
        if msg_id in self._seen_ids:
            if now - self._seen_ids[msg_id] < 300:
                return
        self._seen_ids[msg_id] = now
        if len(self._seen_ids) > 1000:
            self._seen_ids.clear()

        # ACL
        author_id = parsed["author_id"]
        if parsed["chat_type"] == "c2c":
            if not _check_dm_policy(self._dm_policy, self._allowlist, author_id):
                return

        content = parsed["content"].strip()
        if not content:
            return

        session_id = self._session_factory()
        await self._ai_reply(parsed, content, session_id)

    async def _ai_reply(self, parsed: dict, content: str, session_id: str) -> None:
        lock = self._ai_service._session_lock
        if not lock.acquire(blocking=False):
            return  # Desktop conversation in progress, skip

        old_session = self._ai_service.conversation.session_id
        try:
            self._ai_service.conversation.session_id = session_id
            self._ai_service.conversation.history.clear()
            self._ai_service.conversation.content_init()

            full_reply = ""
            async for event in self._ai_service.ai_chat(content):
                if event.type == "content":
                    full_reply += event.text
                elif event.type == "error":
                    return
            if full_reply:
                await self._send_reply(parsed, full_reply)
        finally:
            self._ai_service.conversation.save_history()
            self._ai_service.conversation.session_id = old_session
            if old_session:
                self._ai_service.conversation.history.clear()
                self._ai_service.conversation.content_init()
            lock.release()

    async def _send_reply(self, parsed: dict, text: str) -> None:
        import httpx
        token = await self._get_token()
        headers = {"Authorization": f"QQBot {token}", "Content-Type": "application/json"}

        if parsed["chat_type"] == "c2c":
            url = f"{API_BASE}/v2/users/{parsed['author_id']}/messages"
            body = {"content": text, "msg_type": 0, "msg_id": parsed["message_id"]}
        else:
            url = f"{API_BASE}/v2/groups/{parsed['group_openid']}/messages"
            body = {"content": text, "msg_type": 0, "msg_id": parsed["message_id"]}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()

    async def _get_token(self) -> str:
        import httpx
        import time
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://bots.qq.com/app/getAppAccessToken",
                json={"appId": self._app_id, "clientSecret": self._client_secret},
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_expiry = now + int(data.get("expires_in", 7200))
            return self._token
