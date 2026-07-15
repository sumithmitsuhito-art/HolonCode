"""C-learn progress management: load/save/reset knowledge-point mastery progress.

Progress is stored in data/c-learn-progress.json.

When loaded via SkillLoader.load_plugin(), the @tool decorator is injected
into the module namespace before exec.  For direct imports (tests), the
fallback no-op decorator keeps function signatures unchanged.
"""

import json
from datetime import date
from atri import DATA_DIR

PROGRESS_FILE = DATA_DIR / "c-learn-progress.json"

TOPIC_NAMES = {
    "0": "声明语法", "1": "数据类型系统", "2": "运算符优先级与结合性",
    "3": "表达式与隐式转换", "4": "控制流语法", "5": "函数高级语法",
    "6": "数组语法", "7": "指针完整体系", "8": "字符串处理语法",
    "9": "结构体语法", "10": "联合体与枚举", "11": "预处理器",
    "12": "存储类别", "13": "位操作语法", "14": "文件与工程组织",
    "15": "动态内存分配", "16": "函数指针与回调", "17": "const与volatile",
    "18": "链表与基础数据结构", "19": "可变参数与标准库", "20": "typedef与类型别名",
    "21": "编译过程详解", "22": "调试技巧与断言", "23": "多文件模块化设计",
    "24": "C标准与跨平台", "25": "常见陷阱与最佳实践", "26": "综合实战项目",
}

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
        "total_topics": 27,
        "completed_topics": 0,
        "topics": {},
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
def c_learn_load_progress():
    """读取C语言知识点学习的当前进度，包括所有27个知识点的掌握等级（1=了解/2=理解/3=掌握/4=熟练）。"""
    return _read_progress()


@tool
def c_learn_save_progress(topic_id: str, level: int, note: str = ""):
    """保存某个知识点的掌握程度。topic_id为知识点编号(0-26)，level为掌握等级(1=了解/2=理解/3=掌握/4=熟练)，note为可选备注。"""
    data = _read_progress()
    topic_id = str(topic_id)
    prev = data["topics"].get(topic_id, {})
    prev_level = prev.get("level", 0)
    data["topics"][topic_id] = {
        "name": prev.get("name") or TOPIC_NAMES.get(topic_id, ""),
        "level": level,
        "updated_at": date.today().isoformat(),
        "note": note or prev.get("note", ""),
    }
    if prev_level == 0 and level > 0:
        data["completed_topics"] = data.get("completed_topics", 0) + 1
    elif prev_level > 0 and level == 0:
        data["completed_topics"] = max(0, data.get("completed_topics", 0) - 1)
    _write_progress(data)
    return {
        "topic_id": topic_id,
        "level": level,
        "completed_topics": data["completed_topics"],
        "total_topics": data["total_topics"],
    }


@tool
def c_learn_reset_progress(confirm: str):
    """清空所有知识点学习进度（不可恢复）。confirm 必须为 "yes" 才会执行。"""
    if confirm != "yes":
        return "请将 confirm 参数设为 'yes' 以确认清空全部知识点学习进度。"
    _write_progress(_default_progress())
    return "所有知识点学习进度已清空。"
