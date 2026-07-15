"""Baidu Tieba browsing tools — wraps aiotieba async APIs as sync tool methods.

On Windows, aiohttp's TLS handshake to tiebac.baidu.com:443 consistently
times out (Python 3.14 + OpenSSL 3.0 bug).  We patch NetCore.req2res to
rewrite HTTPS→HTTP for tiebac.baidu.com requests.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import sys
from atri import DATA_DIR

_CONFIG_PATH = DATA_DIR / "UserSettings.json"


def _patch_tiebac_https():
    """Rewrite HTTPS→HTTP for tiebac.baidu.com to avoid Windows TLS bug."""
    if sys.platform != "win32":
        return
    try:
        from aiotieba.core.net import NetCore

        _original = NetCore.req2res

        async def _patched(self, request, read_until_eof=True, read_bufsize=65536):
            if request.url.host == "tiebac.baidu.com" and request.url.scheme == "https":
                request.url = request.url.with_scheme("http")
            return await _original(self, request, read_until_eof, read_bufsize)

        NetCore.req2res = _patched
    except ImportError:
        pass


_patch_tiebac_https()


def _get_tieba_config() -> dict:
    try:
        if _CONFIG_PATH.exists():
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            return data.get("Tieba", {})
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _run_async(coro):
    """Bridge async aiotieba calls to sync tool methods.

    When called from outside an event loop, uses asyncio.run().
    When called from inside a running loop (e.g. the agent's async
    chat loop), offloads to a thread so it can start its own loop.
    """
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(asyncio.run, coro).result()
    except Exception as e:
        return f"贴吧请求失败：{e}"


def _check_deps() -> str | None:
    try:
        import aiotieba  # noqa: F401
    except ImportError:
        return "贴吧功能未启用：aiotieba 未安装。请运行 pip install aiotieba 或 atri-setup 安装贴吧依赖。"
    return None


class TiebaTool:
    """Read-only Baidu Tieba tools for the ATRI agent."""

    @staticmethod
    def _thread_summary(thread, idx: int = 0) -> str:
        title = getattr(thread, "title", "") or getattr(thread, "text", "") or ""
        tid = getattr(thread, "tid", "?")
        author = getattr(thread, "author", "") or ""
        reply_num = getattr(thread, "reply_num", 0) or 0
        prefix = f"[{idx}]" if idx else ""
        return f"{prefix} tid={tid} 回复={reply_num} 作者={author}\n   标题：{title}"

    @staticmethod
    def _post_summary(post, idx: int = 0) -> str:
        text = getattr(post, "text", "") or ""
        author = getattr(post, "author", "") or ""
        pid = getattr(post, "pid", "?")
        prefix = f"[{idx}]" if idx else ""
        text_short = text[:300] + "..." if len(text) > 300 else text
        return f"{prefix} pid={pid} 作者={author}\n   {text_short}"

    # ── tools ────────────────────────────────────────────────

    @classmethod
    def get_threads(cls, fname: str, page: int = 1) -> str:
        err = _check_deps()
        if err:
            return err
        fname = fname.strip()
        if not fname:
            return "贴吧名称不能为空。"

        async def _impl():
            import aiotieba

            cfg = _get_tieba_config()
            async with aiotieba.Client(BDUSS=cfg.get("BDUSS", ""), STOKEN=cfg.get("STOKEN", "")) as client:
                threads = await client.get_threads(fname, pn=page)
                if not threads:
                    return f"贴吧 '{fname}' 第{page}页没有帖子，或该贴吧不存在。"
                lines = [f"【{fname}吧】第{page}页（共 {len(threads)} 条帖子）", "---"]
                for i, t in enumerate(threads, 1):
                    lines.append(cls._thread_summary(t, i))
                return "\n".join(lines)

        return _run_async(_impl())

    @classmethod
    def get_posts(cls, tid: int, page: int = 1) -> str:
        err = _check_deps()
        if err:
            return err
        if not tid or tid <= 0:
            return "帖子ID (tid) 无效。"

        async def _impl():
            import aiotieba

            cfg = _get_tieba_config()
            async with aiotieba.Client(BDUSS=cfg.get("BDUSS", ""), STOKEN=cfg.get("STOKEN", "")) as client:
                posts = await client.get_posts(tid, pn=page)
                if not posts:
                    return f"帖子 tid={tid} 第{page}页没有回复。可能需要登录后才能查看。"
                lines = [f"【帖子 tid={tid}】第{page}页（共 {len(posts)} 条回复）", "---"]
                for i, p in enumerate(posts, 1):
                    lines.append(cls._post_summary(p, i))
                return "\n".join(lines)

        return _run_async(_impl())

    @classmethod
    def search_exact(cls, fname: str, keyword: str, page: int = 1) -> str:
        err = _check_deps()
        if err:
            return err
        fname = fname.strip()
        keyword = keyword.strip()
        if not fname or not keyword:
            return "贴吧名称和搜索关键词都不能为空。"

        async def _impl():
            import aiotieba

            cfg = _get_tieba_config()
            async with aiotieba.Client(BDUSS=cfg.get("BDUSS", ""), STOKEN=cfg.get("STOKEN", "")) as client:
                threads = await client.search_exact(fname, keyword, pn=page, rn=20)
                if not threads:
                    return f"在 '{fname}' 吧中未找到包含 '{keyword}' 的帖子。"
                lines = [f"【搜索：{keyword} @ {fname}吧】第{page}页（{len(threads)} 条）", "---"]
                for i, t in enumerate(threads, 1):
                    lines.append(cls._thread_summary(t, i))
                return "\n".join(lines)

        return _run_async(_impl())

    @classmethod
    def get_forum_info(cls, fname: str) -> str:
        err = _check_deps()
        if err:
            return err
        fname = fname.strip()
        if not fname:
            return "贴吧名称不能为空。"

        async def _impl():
            import aiotieba

            cfg = _get_tieba_config()
            async with aiotieba.Client(BDUSS=cfg.get("BDUSS", ""), STOKEN=cfg.get("STOKEN", "")) as client:
                forum = await client.get_forum_detail(fname)
                if forum is None:
                    return f"未找到贴吧 '{fname}'。"
                name = getattr(forum, "forum_name", fname)
                fid = getattr(forum, "fid", "?")
                level = getattr(forum, "level", "?")
                member_num = getattr(forum, "member_num", "?")
                thread_num = getattr(forum, "thread_num", "?")
                brief = getattr(forum, "brief_intro", "") or ""
                return (
                    f"【{name}吧】\n"
                    f"  ID: {fid}\n"
                    f"  等级: {level}\n"
                    f"  会员数: {member_num}\n"
                    f"  帖子数: {thread_num}\n"
                    f"  简介: {brief}"
                )

        return _run_async(_impl())

    @classmethod
    def get_user_info(cls, user: str) -> str:
        err = _check_deps()
        if err:
            return err
        user = user.strip()
        if not user:
            return "用户名/ID 不能为空。"

        async def _impl():
            import aiotieba

            cfg = _get_tieba_config()
            async with aiotieba.Client(BDUSS=cfg.get("BDUSS", ""), STOKEN=cfg.get("STOKEN", "")) as client:
                info = await client.get_user_info(user)
                if info is None:
                    return f"未找到用户 '{user}' 的信息。"
                name = getattr(info, "user_name", "") or user
                uid = getattr(info, "user_id", "?")
                nick = getattr(info, "nick_name", "") or ""
                level = getattr(info, "level", "?")
                fans = getattr(info, "fans_num", "?")
                follow = getattr(info, "follow_num", "?")
                post = getattr(info, "post_num", "?")
                gender_enum = getattr(info, "gender", None)
                gender_map = {0: "未知", 1: "男", 2: "女"}
                gender = gender_map.get(int(gender_enum), "?") if gender_enum else "?"
                sign = getattr(info, "sign", "") or ""
                parts = [f"【用户：{name}】", f"  ID: {uid}"]
                if nick:
                    parts.append(f"  昵称: {nick}")
                parts.append(f"  性别: {gender}")
                parts.append(f"  等级: {level}")
                parts.append(f"  粉丝: {fans}")
                parts.append(f"  关注: {follow}")
                parts.append(f"  发帖: {post}")
                if sign:
                    parts.append(f"  签名: {sign}")
                return "\n".join(parts)

        return _run_async(_impl())

    @classmethod
    def get_hot_threads(cls, fname: str, count: int = 10) -> str:
        err = _check_deps()
        if err:
            return err
        fname = fname.strip()
        if not fname:
            return "贴吧名称不能为空。"
        count = max(1, min(count, 30))

        async def _impl():
            import aiotieba

            cfg = _get_tieba_config()
            async with aiotieba.Client(BDUSS=cfg.get("BDUSS", ""), STOKEN=cfg.get("STOKEN", "")) as client:
                threads = await client.get_threads(fname, pn=1, rn=max(count, 20))
                if not threads:
                    return f"贴吧 '{fname}' 没有帖子。"
                sorted_threads = sorted(
                    threads,
                    key=lambda t: getattr(t, "reply_num", 0) or 0,
                    reverse=True,
                )
                top = sorted_threads[:count]
                lines = [f"【{fname}吧 热帖 TOP{len(top)}】", "---"]
                for i, t in enumerate(top, 1):
                    lines.append(cls._thread_summary(t, i))
                return "\n".join(lines)

        return _run_async(_impl())
