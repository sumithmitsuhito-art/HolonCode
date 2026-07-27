"""C-tutor progress management: load/save/reset learning progress.

Progress is stored in data/c-tutor-progress.json.

When loaded via SkillLoader.load_plugin(), the @tool decorator is injected
into the module namespace before exec.  For direct imports (tests), the
fallback no-op decorator keeps function signatures unchanged.
"""

import json
from datetime import date
from atri import DATA_DIR

PROGRESS_FILE = DATA_DIR / "c-tutor-progress.json"

# When loaded via SkillLoader, `tool` is injected before exec_module.
# For direct imports, provide a no-op fallback.
try:
    tool  # noqa: F823 — injected by SkillLoader
except NameError:
    def tool(func=None, **kwargs):
        """No-op fallback for when plugin is imported outside SkillLoader."""
        if func is None:
            return lambda f: f
        return func


def _default_progress() -> dict:
    return {
        "total_score": 0,
        "total_levels": 29,
        "completed_levels": 0,
        "levels": {},
    }


def _read_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return _default_progress()
    try:
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _default_progress()


def _write_progress(data: dict):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROGRESS_FILE)


@tool
def load_progress():
    """读取C语言闯关学习的当前进度，包括总分、完成关卡数、各关卡状态。"""
    return _read_progress()


@tool
def save_progress(level_id: str, summary: str, score: int):
    """保存某一关的学习进度。level_id为关卡编号，summary为关卡概要，score为得分(0-100)。"""
    data = _read_progress()
    data["levels"][level_id] = {
        "summary": summary,
        "completed": True,
        "score": score,
        "completed_at": date.today().isoformat(),
    }
    completed = sum(1 for l in data["levels"].values() if l.get("completed"))
    total = sum(l.get("score", 0) for l in data["levels"].values())
    data["completed_levels"] = completed
    data["total_score"] = total
    _write_progress(data)
    return {
        "level_id": level_id,
        "score": score,
        "total_score": total,
        "completed_levels": completed,
        "total_levels": data["total_levels"],
    }


@tool
def reset_progress(confirm: str):
    """清空所有闯关学习进度（不可恢复）。confirm 必须为 "yes" 才会执行。"""
    if confirm != "yes":
        return "请将 confirm 参数设为 'yes' 以确认清空全部闯关进度。"
    _write_progress(_default_progress())
    return "所有闯关进度已清空。"
