"""Tests for c-tutor plugin progress management tools."""
from pathlib import Path

import pytest
from atri import DATA_DIR
from atri.skill_loader import SkillLoader

PROGRESS_FILE = DATA_DIR / "c-tutor-progress.json"


def _load_plugin():
    """Load the c-tutor plugin module via SkillLoader (handles hyphen in dir name)."""
    plugin = SkillLoader.load_plugin("c-tutor")
    assert plugin is not None, "Failed to load c-tutor plugin"
    return plugin


@pytest.fixture(autouse=True)
def clean_progress():
    """Remove progress file before each test so tests are isolated."""
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
    yield
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()


def test_load_progress_returns_default_when_no_file():
    plugin = _load_plugin()
    result = plugin.load_progress()
    assert result["total_score"] == 0
    assert result["total_levels"] == 10
    assert result["completed_levels"] == 0
    assert result["levels"] == {}


def test_save_progress_creates_record():
    plugin = _load_plugin()
    plugin.save_progress("01", "变量与数据类型", 85)
    data = plugin.load_progress()
    assert data["completed_levels"] == 1
    assert data["total_score"] == 85
    assert data["levels"]["01"]["summary"] == "变量与数据类型"
    assert data["levels"]["01"]["score"] == 85
    assert data["levels"]["01"]["completed"] is True
    assert data["levels"]["01"]["completed_at"] is not None


def test_save_progress_updates_existing_level():
    plugin = _load_plugin()
    plugin.save_progress("01", "变量", 60)
    plugin.save_progress("01", "变量与数据类型", 90)
    data = plugin.load_progress()
    assert data["completed_levels"] == 1
    assert data["total_score"] == 90
    assert data["levels"]["01"]["score"] == 90


def test_save_progress_accumulates_multiple_levels():
    plugin = _load_plugin()
    plugin.save_progress("01", "变量", 80)
    plugin.save_progress("02", "分支", 90)
    plugin.save_progress("03", "循环", 70)
    data = plugin.load_progress()
    assert data["completed_levels"] == 3
    assert data["total_score"] == 240
    assert len(data["levels"]) == 3


def test_reset_progress_requires_confirm_yes():
    plugin = _load_plugin()
    plugin.save_progress("01", "变量", 80)
    result = plugin.reset_progress("no")
    assert "yes" in result.lower()
    data = plugin.load_progress()
    assert data["completed_levels"] == 1  # unchanged


def test_reset_progress_clears_all():
    plugin = _load_plugin()
    plugin.save_progress("01", "变量", 80)
    plugin.save_progress("02", "分支", 90)
    result = plugin.reset_progress("yes")
    assert "清空" in result
    data = plugin.load_progress()
    assert data["completed_levels"] == 0
    assert data["total_score"] == 0
    assert data["levels"] == {}
