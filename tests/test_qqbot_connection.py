import pytest
from unittest.mock import AsyncMock


class TestPayloadDispatch:
    """Test _dispatch_payload without real WebSocket."""

    @pytest.fixture
    def adapter(self):
        from qqbot.connection import QQBotConnection
        conn = QQBotConnection.__new__(QQBotConnection)
        conn._log_tag = "test"
        conn._session_id = None
        conn._last_seq = None
        conn._heartbeat_interval = 30
        conn._ws = None
        conn._running = True
        conn._message_callback = None
        conn._heartbeat_task = None
        conn._connect_lock = None
        return conn

    def test_hello_wo_session_sets_heartbeat(self, adapter):
        adapter._send_identify = AsyncMock()
        adapter._send_resume = AsyncMock()
        adapter._create_task = lambda coro: None
        adapter._dispatch_payload({"op": 10, "d": {"heartbeat_interval": 30000}})
        assert adapter._heartbeat_interval == 24.0

    def test_ready_stores_session_id(self, adapter):
        adapter._dispatch_payload({"op": 0, "t": "READY", "d": {"session_id": "sess-123"}})
        assert adapter._session_id == "sess-123"

    def test_invalid_session_not_resumable_clears(self, adapter):
        adapter._session_id = "abc"
        adapter._dispatch_payload({"op": 9, "d": False})
        assert adapter._session_id is None
        assert adapter._last_seq is None

    def test_invalid_session_resumable_preserves(self, adapter):
        adapter._session_id = "abc"
        adapter._last_seq = 10
        adapter._dispatch_payload({"op": 9, "d": True})
        # resumable — session kept, only close triggered (NOP in test)
        assert adapter._session_id == "abc"
        assert adapter._last_seq == 10

    def test_dispatch_updates_sequence(self, adapter):
        adapter._dispatch_payload({"op": 0, "t": "C2C_MESSAGE_CREATE", "s": 42, "d": {"id": "1"}})
        assert adapter._last_seq == 42

    def test_dispatch_ignores_lower_sequence(self, adapter):
        adapter._last_seq = 50
        adapter._dispatch_payload({"op": 0, "t": "C2C_MESSAGE_CREATE", "s": 30, "d": {"id": "2"}})
        assert adapter._last_seq == 50


class TestCloseCodes:
    def test_fatal_codes(self):
        from qqbot.connection import _is_fatal_close_code
        assert _is_fatal_close_code(4001) is True
        assert _is_fatal_close_code(4010) is True
        assert _is_fatal_close_code(4914) is True

    def test_retryable_codes(self):
        from qqbot.connection import _is_fatal_close_code
        assert _is_fatal_close_code(4004) is False  # token expired
        assert _is_fatal_close_code(4008) is False  # rate limited
        assert _is_fatal_close_code(4006) is False  # session invalid
