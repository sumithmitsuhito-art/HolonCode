import json
from pathlib import Path
from atri.prompt_manager import PromptManager


def test_get_prompt_returns_string():
    pm = PromptManager()
    prompt = pm.get_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "【系统指令】" in prompt


def test_prompt_contains_role():
    pm = PromptManager()
    prompt = pm.get_prompt()
    assert "亚托莉" in prompt


def test_load_prompt_file_defaults(tmp_path):
    pm = PromptManager()
    result = pm._load_prompt_file(
        str(tmp_path / "nonexistent.json"),
        ["default1", "default2"],
        "test",
    )
    assert "default1" in result
    assert "default2" in result


def test_load_prompt_file_array_format(tmp_path):
    f = tmp_path / "test.json"
    f.write_text(json.dumps({"prompt": ["line1", "line2"]}, ensure_ascii=False), encoding="utf-8")
    pm = PromptManager()
    result = pm._load_prompt_file(str(f), ["default"], "test")
    assert result == "line1\nline2"


def test_load_prompt_file_string_format(tmp_path):
    f = tmp_path / "test.json"
    f.write_text(json.dumps({"prompt": "single string"}, ensure_ascii=False), encoding="utf-8")
    pm = PromptManager()
    result = pm._load_prompt_file(str(f), ["default"], "test")
    assert result == "single string"


def test_load_user_profile_empty(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.setattr("atri.prompt_manager.DATA_DIR", tmp_path / "data")
    result = PromptManager._load_user_profile()
    assert result == ""
