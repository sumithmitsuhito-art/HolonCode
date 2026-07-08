"""Skill loading and management for ATRI.

Skills live in skills/<name>/SKILL.md with optional references/ templates/ scripts/ assets/ subdirectories.
Each SKILL.md has YAML-like frontmatter (--- delimited) followed by markdown body.
"""

from pathlib import Path
from atri import BASE_DIR

SKILLS_DIR = BASE_DIR / "skills"
MAX_ACTIVE_SKILLS = 3


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML-like frontmatter from SKILL.md content.

    Returns (frontmatter_dict, body_text). Frontmatter is a simple key: value
    format; list values (triggers, tags) are returned as comma-separated strings
    that the caller can split if needed.
    """
    if not content.startswith("---"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    fm_text = content[4:end]
    body = content[end + 4:].strip()

    fm: dict = {}
    for line in fm_text.strip().split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip("\"'")
        fm[key] = value

    return fm, body


class SkillLoader:
    @staticmethod
    def list_skills() -> list[dict]:
        """Scan skills/ directory, return [{name, description}, ...] sorted by name."""
        if not SKILLS_DIR.exists():
            return []
        skills: list[dict] = []
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                content = skill_md.read_text(encoding="utf-8")
                fm, _ = _parse_frontmatter(content)
                skills.append({
                    "name": fm.get("name", skill_dir.name),
                    "description": fm.get("description", ""),
                })
            except (OSError, UnicodeDecodeError):
                continue
        return skills

    @staticmethod
    def load_skill(name: str) -> str | None:
        """Load the body content (without frontmatter) of a skill's SKILL.md."""
        skill_md = SKILLS_DIR / name / "SKILL.md"
        if not skill_md.exists():
            return None
        try:
            content = skill_md.read_text(encoding="utf-8")
            _, body = _parse_frontmatter(content)
            return body
        except (OSError, UnicodeDecodeError):
            return None

    @staticmethod
    def load_full_skill(name: str) -> str | None:
        """Load the complete SKILL.md content including frontmatter."""
        skill_md = SKILLS_DIR / name / "SKILL.md"
        if not skill_md.exists():
            return None
        try:
            return skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    @staticmethod
    def write_skill(name: str, content: str) -> bool:
        """Write (create or overwrite) a skill's SKILL.md. Returns True on success."""
        skill_dir = SKILLS_DIR / name
        try:
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(content, encoding="utf-8")
            return True
        except OSError:
            return False

    @staticmethod
    def delete_skill(name: str) -> bool:
        """Delete a skill directory and all its contents. Returns True on success."""
        skill_dir = SKILLS_DIR / name
        if not skill_dir.exists():
            return False
        try:
            import shutil
            shutil.rmtree(skill_dir)
            return True
        except OSError:
            return False

    @staticmethod
    def skill_exists(name: str) -> bool:
        return (SKILLS_DIR / name / "SKILL.md").exists()

    @staticmethod
    def validate_name(name: str) -> str | None:
        """Return error message if name is invalid, None if valid."""
        if not name or not name.strip():
            return "技能名称不能为空"
        cleaned = name.strip().lower().replace(" ", "-")
        if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
            return "技能名称不能包含路径分隔符或 .."
        if len(cleaned) > 64:
            return "技能名称不能超过 64 个字符"
        return None
