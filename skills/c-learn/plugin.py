"""C-learn progress management + RAG knowledge base search.

Progress is stored in data/c-learn-progress.json.
Knowledge base lives in data/knowledge_base/c/*.md

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


# ================================================================
# 进度管理工具（原有）
# ================================================================

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


# ================================================================
# RAG 知识库工具（新增）
# ================================================================

@tool
def c_knowledge_search(query: str, module_id: str = "", top_k: int = 5):
    """【C语言知识库搜索工具】从本地C语言27个知识点模块知识库中检索相关内容。

    当用户问C语言相关问题时，必须优先调用此工具从本地知识库搜索答案。
    只有当本工具返回的内容确实不足以回答问题时，再调用 web_search 联网搜索。

    参数：
        query:     用户的原始问题或想查询的关键词（例如"指针是什么"、"malloc用法"）。必须填写。
        module_id: 可选，限定在某个知识点模块内检索。27个模块的编号：
                   0=声明语法, 1=数据类型系统, 2=运算符优先级与结合性,
                   3=表达式与隐式转换, 4=控制流语法, 5=函数高级语法,
                   6=数组语法, 7=指针完整体系, 8=字符串处理语法,
                   9=结构体语法, 10=联合体与枚举, 11=预处理器,
                   12=存储类别, 13=位操作语法, 14=文件与工程组织,
                   15=动态内存分配, 16=函数指针与回调, 17=const与volatile,
                   18=链表与基础数据结构, 19=可变参数与标准库, 20=typedef与类型别名,
                   21=编译过程详解, 22=调试技巧与断言, 23=多文件模块化设计,
                   24=C标准与跨平台, 25=常见陷阱与最佳实践, 26=综合实战项目
        top_k:     返回相关片段的条数，默认5条。不熟悉的模块可以取3-5，综合问题取8-10。
    """
    # 延迟导入：避免 SkillLoader 加载 plugin 时立即触网
    from atri.rag import search_knowledge_to_text
    mid = module_id if module_id != "" else None
    return search_knowledge_to_text(query, module_id=mid, top_k=top_k)


@tool
def c_knowledge_list_modules():
    """列出C语言知识库中已有的所有知识点模块（编号、名称），方便按模块检索。"""
    from atri.rag import list_kb_modules
    mods = list_kb_modules()
    if not mods:
        return "知识库当前为空，正在初始化默认模块内容..."
    lines = ["C语言知识库共有 {} 个模块：".format(len(mods))]
    for m in mods:
        lines.append("  模块 {}：{}".format(m.get("id", "?"), m.get("name", "?")))
    return "\n".join(lines)


@tool
def c_knowledge_rebuild(confirm: str = "yes"):
    """强制重建 C 语言知识库的索引（一般不需要手动调用，自动增量更新）。
    当新增了知识文档或内容修改但没有生效时可以调用此工具。"""
    from atri.rag import build_or_update_index
    idx = build_or_update_index()
    return (
        "知识库索引重建完成。\n"
        "  - 文档数：{}\n"
        "  - 分块数：{}\n"
        "  - 向量块数：{}（其余块因 API 不可用暂用关键词匹配）".format(
            len(idx.doc_fingerprints),
            len(idx.chunks),
            sum(1 for c in idx.chunks if c.embedding is not None),
        )
    )


# ================================================================
# 难度调整工具（新增）
# ================================================================

_DIFFICULTY_NAMES = {
    "easy": "简单 — 适合零基础入门",
    "medium": "中等 — 适合有一定基础",
    "hard": "困难 — 适合进阶深入",
    "adaptive": "自适应 — AI 自动判断",
}


def _get_ai_service():
    """Get the injected AIService instance from module globals."""
    return globals().get("ai_service")


@tool
def c_set_difficulty(level: str):
    """【学习难度调整】设置 C 语言学习的讲解难度。

    当用户说"讲简单点"、"讲深入点"、"调整难度"时调用此工具。
    难度设置会自动保存到配置文件，下次对话仍生效。

    参数：
        level: 难度级别，可选值：
               - "easy": 简单模式，用生活比喻，最基础的例子
               - "medium": 中等模式，标准术语，完整示例
               - "hard": 困难模式，深入底层原理、最佳实践
               - "adaptive": 自适应，AI 根据对话动态调整
    """
    svc = _get_ai_service()
    if svc is None:
        return "错误：AIService 未初始化，无法调整难度。"

    valid = {"easy", "medium", "hard", "adaptive"}
    if level not in valid:
        return f"无效的难度级别：{level}。可选值：{', '.join(sorted(valid))}"

    svc.set_difficulty(level)
    return f"学习难度已设置为：{_DIFFICULTY_NAMES[level]}。从下一条回复开始按新难度讲解。"


@tool
def c_get_difficulty():
    """获取当前 C 语言学习的难度设置。当需要告知用户当前难度或检查配置时调用。"""
    svc = _get_ai_service()
    if svc is None:
        return "错误：AIService 未初始化。"

    current = svc.difficulty
    return f"当前学习难度：{_DIFFICULTY_NAMES.get(current, current)}（内部值：{current}）"
