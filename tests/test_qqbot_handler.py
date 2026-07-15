import pytest


class TestMessageParsing:

    def test_parse_c2c_message(self):
        from qqbot.handler import _parse_inbound
        payload = {
            "id": "msg-001",
            "author": {"id": "user-openid-123", "username": "测试用户"},
            "content": "你好小洛",
        }
        result = _parse_inbound("C2C_MESSAGE_CREATE", payload)
        assert result is not None
        assert result["chat_type"] == "c2c"
        assert result["author_id"] == "user-openid-123"
        assert result["author_name"] == "测试用户"
        assert result["content"] == "你好小洛"
        assert result["message_id"] == "msg-001"

    def test_parse_c2c_missing_author(self):
        from qqbot.handler import _parse_inbound
        payload = {"id": "msg-002", "content": "hi"}
        result = _parse_inbound("C2C_MESSAGE_CREATE", payload)
        assert result["author_id"] == ""
        assert result["author_name"] == ""

    def test_parse_group_message_strips_mention(self):
        from qqbot.handler import _parse_inbound
        payload = {
            "id": "msg-003",
            "author": {"id": "user-456"},
            "content": "<@!bot-id> 你好世界",
            "group_openid": "group-789",
        }
        result = _parse_inbound("GROUP_AT_MESSAGE_CREATE", payload)
        assert result["chat_type"] == "group"
        assert result["group_openid"] == "group-789"
        assert result["content"] == "你好世界"

    def test_parse_none_for_unknown_type(self):
        from qqbot.handler import _parse_inbound
        result = _parse_inbound("GUILD_MESSAGE_CREATE", {"id": "x"})
        assert result is None


class TestAccessControl:

    def test_dm_policy_disabled(self):
        from qqbot.handler import _check_dm_policy
        assert not _check_dm_policy("disabled", [], "user-1")

    def test_dm_policy_open(self):
        from qqbot.handler import _check_dm_policy
        assert _check_dm_policy("open", [], "user-1")

    def test_dm_policy_allowlist_match(self):
        from qqbot.handler import _check_dm_policy
        assert _check_dm_policy("allowlist", ["user-1", "user-2"], "user-1")

    def test_dm_policy_allowlist_no_match(self):
        from qqbot.handler import _check_dm_policy
        assert not _check_dm_policy("allowlist", ["user-1"], "user-3")


class TestMentionStripping:

    def test_strip_at_mention(self):
        from qqbot.handler import _strip_mention
        assert _strip_mention("<@!bot123> 你好世界") == "你好世界"

    def test_strip_mention_only(self):
        from qqbot.handler import _strip_mention
        assert _strip_mention("<@!bot123>") == ""

    def test_strip_trailing_mention(self):
        from qqbot.handler import _strip_mention
        assert _strip_mention("你好<@!bot123>") == "你好"  # mention stripped regardless of position

    def test_strip_preserves_normal_text(self):
        from qqbot.handler import _strip_mention
        assert _strip_mention("你好世界") == "你好世界"
