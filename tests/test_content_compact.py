import json
from pathlib import Path
import pytest
from atri.content_compact import ContentCompact
from atri.models import Message


class TestCountRounds:
    def test_count_single(self):
        history = [
            Message(role="system", content="sys"),
            Message(role="user", content="m1"),
            Message(role="assistant", content="r1"),
        ]
        assert ContentCompact.count_rounds(history) == 1

    def test_count_ignores_system(self):
        history = [
            Message(role="system", content="sys"),
            Message(role="user", content="u1"),
            Message(role="assistant", content="a1"),
            Message(role="user", content="u2"),
            Message(role="assistant", content="a2"),
        ]
        assert ContentCompact.count_rounds(history) == 2


class TestShouldCompact:
    def test_under_threshold(self):
        history = [Message(role="system", content="sys")]
        for i in range(14):  # 14 user messages = 14 rounds (under 15)
            history.append(Message(role="user", content=f"u{i}"))
            history.append(Message(role="assistant", content=f"a{i}"))
        assert not ContentCompact.should_compact(history)

    def test_at_threshold(self):
        history = [Message(role="system", content="sys")]
        for i in range(15):  # 15 rounds = at threshold
            history.append(Message(role="user", content=f"u{i}"))
            history.append(Message(role="assistant", content=f"a{i}"))
        assert ContentCompact.should_compact(history)


class TestSplitRounds:
    def test_split_two_rounds(self):
        history = [
            Message(role="system", content="sys"),
            Message(role="user", content="u1"),
            Message(role="assistant", content="a1"),
            Message(role="user", content="u2"),
            Message(role="assistant", content="a2"),
        ]
        rounds = ContentCompact._split_rounds(history, 1)
        assert len(rounds) == 2
        assert rounds[0][0].content == "u1"
        assert rounds[1][0].content == "u2"


class TestTrimSummaries:
    def test_excess_summaries_removed(self):
        history = [
            Message(role="system", content="sys"),
            Message(role="system", content="【历史对话摘要】oldest summary"),
            Message(role="system", content="【历史对话摘要】middle summary"),
            Message(role="system", content="【历史对话摘要】newest summary"),
            Message(role="user", content="u1"),
            Message(role="assistant", content="a1"),
        ]
        ContentCompact.max_summaries = 2
        ContentCompact._trim_summaries(history, 1)
        # Should have removed the oldest summary (index 3 was the last summary = oldest)
        summaries = [m for m in history if "【历史对话摘要】" in (m.content or "")]
        assert len(summaries) == 2
