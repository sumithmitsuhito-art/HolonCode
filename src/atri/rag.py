"""轻量级知识库搜索 — 基于全文匹配 + LLM 多轮改写（Agentic Search）

设计原则：
- 零外部依赖：不调用 embedding API，不维护向量索引
- 全文子串匹配：跟 grep 一样，搜到就是搜到，不玩分词打分
- 宽松回退：精确匹配无结果时，自动拆词逐个搜
- LLM 多轮搜索：检索不负责"理解"，理解交给 LLM 自己换词再搜

知识库目录：data/knowledge_base/c/*.md
"""

from __future__ import annotations

import re
from pathlib import Path

from atri import DATA_DIR

# ──────────────────────────── 配置 ────────────────────────────

KB_ROOT = DATA_DIR / "knowledge_base" / "c"
TOP_K = 5

# 27 个模块的文件名映射
_MODULE_ID_FROM_NAME = re.compile(r"^(\d+)_")


def _parse_filename(file_path: Path) -> tuple[str, str, str]:
    """从文件名解析 (doc_id, module_id, module_name)。

    例：07_指针完整体系.md → ("07_指针完整体系", "07", "指针完整体系")
    """
    stem = file_path.stem
    doc_id = stem
    m = _MODULE_ID_FROM_NAME.match(stem)
    if m:
        module_id = m.group(1)
        module_name = stem[m.end():]
    else:
        module_id = ""
        module_name = stem
    return doc_id, module_id, module_name


# ──────────────────────────── 搜索 ────────────────────────────


def _search_files(query: str, files: list[Path]) -> list[tuple[Path, list[str]]]:
    """在文件中搜索 query，返回 (文件, [匹配段落]) 列表。

    两轮策略：
    1. 精确子串匹配（忽略大小写）
    2. 无结果时拆词，每个词单独搜，取并集
    """
    results: list[tuple[Path, list[str]]] = []

    for fp in files:
        try:
            content = fp.read_text(encoding="utf-8")
        except OSError:
            continue

        # 第一轮：精确子串匹配
        paragraphs = _find_matching_paragraphs(content, query)

        # 第二轮：拆词宽松匹配
        if not paragraphs:
            words = _extract_keywords(query)
            if words:
                # 每个词单独搜，合并结果
                all_matches: dict[str, list[str]] = {}  # paragraph_text -> [matched_words]
                for word in words:
                    for para in _find_matching_paragraphs(content, word):
                        key = para[:100]  # 用前100字符做去重键
                        if key not in all_matches:
                            all_matches[key] = []
                        all_matches[key].append(word)
                # 按命中词数排序
                sorted_paras = sorted(all_matches.items(), key=lambda x: len(x[1]), reverse=True)
                paragraphs = [p[0] for p in sorted_paras[:TOP_K]]

        if paragraphs:
            results.append((fp, paragraphs[:TOP_K]))

    return results


def _find_matching_paragraphs(content: str, query: str) -> list[str]:
    """找到包含 query 的段落，返回段落文本列表。

    段落分割：按空行或 ## 标题边界。
    """
    # 按空行分段
    raw_paragraphs = re.split(r"\n\s*\n", content)
    # 对于 markdown，也按 ## 标题作为段落边界
    paragraphs: list[str] = []
    for p in raw_paragraphs:
        sub_paras = re.split(r"\n(?=## )", p)
        paragraphs.extend(sp.strip() for sp in sub_paras if sp.strip())

    query_lower = query.lower()
    matched: list[str] = []
    seen: set[str] = set()

    for para in paragraphs:
        if query_lower in para.lower():
            # 去重：用前120字符做指纹
            fingerprint = para[:120]
            if fingerprint not in seen:
                seen.add(fingerprint)
                matched.append(para)

    return matched


def _extract_keywords(query: str) -> list[str]:
    """从查询中提取有意义的搜索词。

    中文用 2-gram 滑动窗口切分，英文用单词边界切分。
    例："不用的内存要怎么处理" → ["不用", "内存", "处理"]
    """
    noise = {"的", "了", "吗", "呢", "吧", "啊", "呀", "哦", "怎么", "什么",
             "如何", "这个", "那个", "可以", "应该", "一下", "一些", "那种",
             "不会", "不太", "有点", "比较", "不太"}

    # 提取引号内的精确短语
    quoted = re.findall(r'[""]([^""]+)[""]', query)
    if quoted:
        return quoted

    tokens: list[str] = []

    # 英文单词和 C 关键字
    for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", query):
        if len(w) >= 2:
            tokens.append(w.lower())

    # 中文 2-gram 滑动窗口
    cjk_chars = re.findall(r"[一-鿿]", query)
    for i in range(len(cjk_chars) - 1):
        bigram = cjk_chars[i] + cjk_chars[i + 1]
        if bigram not in noise:
            tokens.append(bigram)

    # 去重，保持顺序
    seen: set[str] = set()
    result: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


# ──────────────────────────── 公共 API ────────────────────────────


def search_knowledge(query: str, module_id: str | None = None,
                     top_k: int = TOP_K) -> list[dict]:
    """搜索知识库，返回匹配结果列表。

    参数：
        query:      查询文本
        module_id:  可选，限定在某个模块文件内检索（如 "07"）
        top_k:      返回前 N 条
    """
    KB_ROOT.mkdir(parents=True, exist_ok=True)
    md_files = sorted(KB_ROOT.glob("*.md"))

    if not md_files:
        return []

    # 模块过滤
    if module_id:
        mid = str(module_id)
        md_files = [f for f in md_files
                    if _MODULE_ID_FROM_NAME.match(f.stem)
                    and _MODULE_ID_FROM_NAME.match(f.stem).group(1) == mid]
        if not md_files:
            md_files = sorted(KB_ROOT.glob("*.md"))  # 过滤无结果则回退全部

    raw_results = _search_files(query, md_files)

    # 组装结果
    output: list[dict] = []
    for fp, paragraphs in raw_results:
        _, mid, module_name = _parse_filename(fp)
        for para in paragraphs[:top_k]:
            output.append({
                "module_id": mid,
                "module_name": module_name,
                "content": para[:1200],  # 截断过长段落
            })

    return output[:top_k]


def search_knowledge_to_text(query: str, module_id: str | None = None,
                             top_k: int = TOP_K) -> str:
    """返回给 LLM 看的纯文本结果。"""
    results = search_knowledge(query, module_id=module_id, top_k=top_k)
    if not results:
        return ("（知识库无匹配内容。建议尝试：1）换一组关键词重新搜索 "
                "2）调用 web_search 联网搜索。）")

    lines = [f"以下是从 C 语言知识库检索到的最相关 {len(results)} 条内容：\n"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"【{i}】模块 {r['module_id']}：{r['module_name']}\n"
            f"{r['content']}\n"
        )
    return "\n".join(lines)


def list_kb_modules() -> list[dict]:
    """列出知识库中所有 C 语言模块。"""
    KB_ROOT.mkdir(parents=True, exist_ok=True)
    modules: list[dict] = []
    for fp in sorted(KB_ROOT.glob("*.md")):
        doc_id, module_id, module_name = _parse_filename(fp)
        if module_id:
            modules.append({
                "id": module_id,
                "name": module_name,
                "doc_id": doc_id,
                "title": module_name,
            })
    return modules


def build_or_update_index():
    """（兼容旧接口）Agentic Search 不需要预建索引，直接返回当前模块列表。"""
    return list_kb_modules()
