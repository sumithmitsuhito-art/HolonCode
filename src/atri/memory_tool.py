import json
from pathlib import Path
from atri import DATA_DIR


class MemoryTool:
    memory_file: str = str(DATA_DIR / "MemoryForUser.json")

    @classmethod
    def _load(cls) -> list[dict]:
        p = Path(cls.memory_file)
        if not p.exists():
            return []
        try:
            text = p.read_text(encoding="utf-8")
            if not text.strip():
                return []
            return json.loads(text)
        except (json.JSONDecodeError, OSError):
            return []

    @classmethod
    def _save(cls, memories: list[dict]):
        p = Path(cls.memory_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(memories, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def _next_id(cls, memories: list[dict]) -> int:
        if not memories:
            return 1
        return max(m["id"] for m in memories) + 1

    @classmethod
    def add_memory(cls, content: str) -> str:
        if not content or not content.strip():
            return "记忆内容不能为空。"
        try:
            memories = cls._load()
            entry = {"id": cls._next_id(memories), "content": content.strip()}
            memories.append(entry)
            cls._save(memories)
            return f"[已记住] #{entry['id']}：{content}\n   当前共 {len(memories)} 条用户画像记忆。"
        except Exception as e:
            return f"保存记忆失败：{e}"

    @classmethod
    def list_memories(cls) -> str:
        try:
            memories = cls._load()
            if not memories:
                return "暂无用户画像记忆。当用户表露个人信息或偏好时，会自动记录。"
            result = f"用户画像记忆（共 {len(memories)} 条）\n---\n"
            for m in memories:
                result += f"#{m['id']}  {m['content']}\n"
            return result
        except Exception as e:
            return f"读取记忆失败：{e}"

    @classmethod
    def delete_memory(cls, id_: int, confirm: str) -> str:
        if confirm.lower() != "yes":
            return "删除记忆需要确认：请将 confirm 参数设为 \"yes\" 后再试。记忆未被删除。"
        try:
            memories = cls._load()
            target = next((m for m in memories if m["id"] == id_), None)
            if target is None:
                return f"未找到 #{id_} 号记忆，无需删除。当前共 {len(memories)} 条记忆。"
            memories.remove(target)
            cls._save(memories)
            return f"[已删除] #{id_}：{target['content']}\n   当前共 {len(memories)} 条用户画像记忆。"
        except Exception as e:
            return f"删除记忆失败：{e}"

    @classmethod
    def clear_memories(cls, confirm: str) -> str:
        if confirm.lower() != "yes":
            return "清空记忆需要确认：请将 confirm 参数设为 \"yes\" 后再试。记忆未被清空。"
        try:
            memories = cls._load()
            if not memories:
                return "暂无记忆，无需清空。"
            count = len(memories)
            cls._save([])
            return f"[已清空] 共删除 {count} 条用户画像记忆。"
        except Exception as e:
            return f"清空记忆失败：{e}"
