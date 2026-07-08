import json
from pathlib import Path
from atri.conversation import ConversationManager
from atri.models import Message


def test_init_starts_with_empty_history(tmp_path, monkeypatch):
    hf = tmp_path / "nonexistent.json"
    monkeypatch.setattr("atri.conversation.ConversationManager.history_file", str(hf.resolve()))
    cm = ConversationManager()
    cm.content_init()
    assert cm.history == []


def test_save_and_load(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    hf = tmp_path / "data" / "history.json"
    monkeypatch.setattr("atri.conversation.ConversationManager.history_file", str(hf.resolve()))

    cm = ConversationManager()
    cm.content_init()
    cm.history.append(Message(role="user", content="hello"))
    cm.save_history()
    assert hf.exists()
    data = json.loads(hf.read_text(encoding="utf-8"))
    assert data[-1]["content"] == "hello"

    cm2 = ConversationManager()
    cm2.content_init()
    assert len(cm2.history) == 1
