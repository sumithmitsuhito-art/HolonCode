import pytest
from pathlib import Path
from atri.file_tool import FileTool


class TestGetSafePath:
    def test_relative_path(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.get_safe_path("notes.txt")
        assert result is not None
        assert "notes.txt" in str(result)

    def test_absolute_path_rejected(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.get_safe_path(r"C:\Windows\hosts")
        assert result is None

    def test_path_traversal_rejected(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.get_safe_path("../etc/passwd")
        assert result is None

    def test_empty_path_returns_workdir(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.get_safe_path("")
        assert result is not None
        assert result == ws.resolve()


class TestReadFile:
    def test_read_existing_file(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "test.txt").write_text("line1\nline2\nline3")
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.read_file("test.txt")
        assert "line1" in result
        assert "共3行" in result

    def test_read_nonexistent_file(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.read_file("nonexistent.txt")
        assert "不存在" in result

    def test_read_pagination(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "test.txt").write_text("\n".join(str(i) for i in range(1, 101)))
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.read_file("test.txt", start_line=50, line_count=10)
        assert "第50-59行" in result


class TestWriteFile:
    def test_write_and_read(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.write_file("hello.txt", "world")
        assert "成功" in result
        content = (ws / "hello.txt").read_text()
        assert content == "world"

    def test_write_rejected_outside(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.write_file("../outside.txt", "data")
        assert "安全拦截" in result


class TestDeleteFile:
    def test_delete_without_confirm(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "temp.txt").write_text("data")
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.delete_file("temp.txt", "no")
        assert "确认" in result
        assert (ws / "temp.txt").exists()

    def test_delete_with_confirm(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "temp.txt").write_text("data")
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.delete_file("temp.txt", "yes")
        assert "成功" in result
        assert not (ws / "temp.txt").exists()


class TestSearchFiles:
    def test_search_finds_keyword(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "a.txt").write_text("hello world")
        (ws / "b.txt").write_text("goodbye")
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.search_files("hello")
        assert "a.txt" in result
        assert "b.txt" not in result

    def test_search_no_results(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "a.txt").write_text("hello")
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.search_files("nonexistent")
        assert "未找到" in result


class TestMoveFile:
    def test_move_renames_file(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "old.txt").write_text("data")
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.move_file("old.txt", "new.txt")
        assert "成功" in result
        assert not (ws / "old.txt").exists()
        assert (ws / "new.txt").exists()


class TestCreateDirectory:
    def test_create_new_dir(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.create_directory("subdir")
        assert "成功" in result
        assert (ws / "subdir").is_dir()

    def test_create_existing_dir(self, monkeypatch, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "subdir").mkdir()
        monkeypatch.setattr(FileTool, "work_dir", str(ws))
        result = FileTool.create_directory("subdir")
        assert "已存在" in result
