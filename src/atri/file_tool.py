from pathlib import Path
from atri import WORKSPACE_DIR


class FileTool:
    work_dir: str = str(WORKSPACE_DIR)
    max_search_results: int = 50
    max_read_lines: int = 500

    @classmethod
    def ensure_work_dir(cls):
        p = Path(cls.work_dir)
        if not p.exists():
            p.mkdir(parents=True)

    @classmethod
    def get_safe_path(cls, user_path: str) -> Path | None:
        if not user_path or not user_path.strip():
            return Path(cls.work_dir).resolve()
        p = Path(user_path)
        if p.is_absolute():
            return None
        if ".." in str(user_path):
            return None
        full = (Path(cls.work_dir) / user_path).resolve()
        work = Path(cls.work_dir).resolve()
        try:
            full.relative_to(work)
        except ValueError:
            return None
        return full

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.0f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.0f} TB"

    @classmethod
    def read_file(cls, file_path: str, start_line: int = 1, line_count: int = -1) -> str:
        safe = cls.get_safe_path(file_path)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        if not safe.is_file():
            return f"文件不存在：{file_path}\n   当前工作目录：{Path(cls.work_dir).resolve()}"
        try:
            lines = safe.read_text(encoding="utf-8").splitlines()
            total = len(lines)
            if total == 0:
                return f"{file_path} 是空文件。"
            if start_line > total:
                return f"起始行 {start_line} 超出文件总行数 {total}。"
            actual_start = max(start_line - 1, 0)
            if line_count > 0:
                actual_end = min(actual_start + line_count, total)
            else:
                actual_end = min(actual_start + cls.max_read_lines, total)
            result = "\n".join(lines[actual_start:actual_end])
            header = f"{file_path}（共{total}行，当前显示第{actual_start + 1}-{actual_end}行）\n"
            if actual_end < total:
                header += f" 文件还有 {total - actual_end} 行未显示，如需继续阅读请指定 startLine={actual_end + 1}\n"
            header += "---\n"
            if not result:
                return header + "(此处为空行)"
            return header + result
        except Exception as e:
            return str(e)

    @classmethod
    def write_file(cls, file_path: str, content: str) -> str:
        safe = cls.get_safe_path(file_path)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        try:
            safe.parent.mkdir(parents=True, exist_ok=True)
            safe.write_text(content, encoding="utf-8")
            return f"已成功写入文件：{file_path}\n   工作目录：{Path(cls.work_dir).resolve()}"
        except Exception as e:
            return f"写入文件失败：{e}"

    @classmethod
    def append_file(cls, file_path: str, content: str) -> str:
        safe = cls.get_safe_path(file_path)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        try:
            safe.parent.mkdir(parents=True, exist_ok=True)
            with safe.open("a", encoding="utf-8") as f:
                f.write(content + "\n")
            size = safe.stat().st_size
            return f"已成功追加到文件：{file_path}\n   文件当前大小：{cls.format_file_size(size)}"
        except Exception as e:
            return f"追加写入失败：{e}"

    @classmethod
    def delete_file(cls, file_path: str, confirm: str) -> str:
        safe = cls.get_safe_path(file_path)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        if confirm.lower() != "yes":
            return "删除操作需要确认：请将 confirm 参数设为 \"yes\" 后再试。文件未被删除。"
        if safe.is_dir():
            return "安全拦截：目标路径是一个目录而非文件。如需删除目录请手动操作。"
        if not safe.is_file():
            return f"文件不存在，无需删除：{file_path}"
        try:
            safe.unlink()
            return f"已成功删除文件：{file_path}"
        except Exception as e:
            return f"删除文件失败：{e}"

    @classmethod
    def list_files(cls, sub_dir: str = "", recursive: bool = False) -> str:
        safe = cls.get_safe_path(sub_dir)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        if not safe.is_dir():
            return f"目录不存在：{'根目录' if not sub_dir else sub_dir}"
        try:
            pattern = "**/*" if recursive else "*"
            items = list(safe.glob(pattern))
            dirs = [p for p in items if p.is_dir()]
            files = [p for p in items if p.is_file()]
            total_size = sum(f.stat().st_size for f in files)
            display = sub_dir if sub_dir else "workspace 根目录"
            if recursive:
                display += "（递归）"
            result = f"{display} —— {len(dirs)}个文件夹，{len(files)}个文件，共{cls.format_file_size(total_size)}\n"
            if dirs:
                result += "\n文件夹\n"
                for d in dirs[:30]:
                    rel = d.relative_to(Path(cls.work_dir).resolve())
                    result += f"  {rel}/\n"
            if files:
                result += "\n文件\n"
                for f in files[:50]:
                    rel = f.relative_to(Path(cls.work_dir).resolve())
                    result += f"   {rel}  ({cls.format_file_size(f.stat().st_size)})\n"
            if not dirs and not files:
                result += "\n(空目录)"
            return result
        except Exception as e:
            return f"列出文件失败：{e}"

    @classmethod
    def search_files(cls, keyword: str, sub_dir: str = "") -> str:
        safe = cls.get_safe_path(sub_dir)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        if not safe.is_dir():
            return f"目录不存在：{'根目录' if not sub_dir else sub_dir}"
        if not keyword or not keyword.strip():
            return "搜索关键词不能为空。"
        try:
            skip_exts = {".exe", ".dll", ".pdb", ".png", ".jpg", ".jpeg",
                         ".gif", ".ico", ".zip", ".rar", ".7z", ".mp3", ".mp4"}
            result_lines = [f'搜索关键词 "{keyword}" 的结果：', ""]
            total_matches = 0
            files_with_match = 0
            too_many = False
            for f in safe.glob("**/*"):
                if too_many:
                    break
                if not f.is_file() or f.suffix.lower() in skip_exts:
                    continue
                try:
                    lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
                    file_has = False
                    for i, line in enumerate(lines):
                        if total_matches >= cls.max_search_results:
                            too_many = True
                            break
                        if keyword.lower() in line.lower():
                            if not file_has:
                                rel = f.relative_to(Path(cls.work_dir).resolve())
                                result_lines.append(f"{rel}：")
                                file_has = True
                                files_with_match += 1
                            display = line.strip()
                            if len(display) > 200:
                                display = display[:200] + "..."
                            result_lines.append(f"   第{i + 1}行：{display}")
                            total_matches += 1
                except Exception:
                    continue
            if files_with_match == 0:
                return f"在 {'workspace' if not sub_dir else sub_dir} 中未找到包含 \"{keyword}\" 的文件。"
            if too_many:
                result_lines.append(f"\n搜索结果超过 {cls.max_search_results} 条，仅显示前 {cls.max_search_results} 条。")
            result_lines.append(f"\n共在 {files_with_match} 个文件中找到 {total_matches} 条匹配。")
            return "\n".join(result_lines)
        except Exception as e:
            return f"搜索失败：{e}"

    @classmethod
    def move_file(cls, source_path: str, dest_path: str) -> str:
        safe_src = cls.get_safe_path(source_path)
        safe_dst = cls.get_safe_path(dest_path)
        if safe_src is None:
            return "安全拦截：源路径不允许访问工作目录以外的路径。"
        if safe_dst is None:
            return "安全拦截：目标路径不允许访问工作目录以外的路径。"
        if not safe_src.exists():
            return f"源路径不存在：{source_path}"
        try:
            safe_dst.parent.mkdir(parents=True, exist_ok=True)
            safe_src.rename(safe_dst)
            return f"[成功] 已移动：{source_path} -> {dest_path}"
        except Exception as e:
            return f"移动失败：{e}"

    @classmethod
    def create_directory(cls, dir_path: str) -> str:
        safe = cls.get_safe_path(dir_path)
        if safe is None:
            return "安全拦截：不允许访问工作目录以外的路径。"
        if safe.is_dir():
            return f"目录已存在，无需创建：{dir_path}"
        try:
            safe.mkdir(parents=True)
            return f"[成功] 已创建目录：{dir_path}\n   工作目录：{Path(cls.work_dir).resolve()}"
        except Exception as e:
            return f"创建目录失败：{e}"
