import json
from pathlib import Path
from atri.memory_tool import MemoryTool


def test_add_memory(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    result = MemoryTool.add_memory("用户喜欢Python")
    assert "已记住" in result
    assert "#1" in result
    data = json.loads(mf.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["content"] == "用户喜欢Python"


def test_add_empty_memory(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    result = MemoryTool.add_memory("")
    assert "不能为空" in result


def test_list_memories(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    MemoryTool.add_memory("记忆1")
    MemoryTool.add_memory("记忆2")
    result = MemoryTool.list_memories()
    assert "记忆1" in result
    assert "记忆2" in result
    assert "共 2 条" in result


def test_list_empty(tmp_path, monkeypatch):
    mf = tmp_path / "nonexistent.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    result = MemoryTool.list_memories()
    assert "暂无用户画像记忆" in result


def test_delete_memory(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    MemoryTool.add_memory("要删除的记忆")
    result = MemoryTool.delete_memory(1, "yes")
    assert "已删除" in result
    result = MemoryTool.list_memories()
    assert "暂无用户画像记忆" in result


def test_delete_without_confirm(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    MemoryTool.add_memory("test")
    result = MemoryTool.delete_memory(1, "no")
    assert "确认" in result


def test_delete_nonexistent_id(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    result = MemoryTool.delete_memory(999, "yes")
    assert "未找到" in result


def test_clear_memories(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    MemoryTool.add_memory("m1")
    MemoryTool.add_memory("m2")
    result = MemoryTool.clear_memories("yes")
    assert "已清空" in result
    assert "共删除 2 条" in result


def test_clear_without_confirm(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    MemoryTool.add_memory("m1")
    result = MemoryTool.clear_memories("no")
    assert "确认" in result


def test_clear_empty(tmp_path, monkeypatch):
    mf = tmp_path / "memory.json"
    monkeypatch.setattr(MemoryTool, "memory_file", str(mf.resolve()))
    result = MemoryTool.clear_memories("yes")
    assert "暂无记忆" in result
