import json
import re
from html import unescape
from urllib.parse import quote_plus
import httpx
from atri.models import Tool, FunctionDef
from atri.file_tool import FileTool
from atri.memory_tool import MemoryTool
from atri.skill_loader import SkillLoader, SKILLS_DIR
from atri.tieba_tool import TiebaTool


def _make_tool(name: str, description: str, parameters: dict) -> Tool:
    return Tool(function=FunctionDef(name=name, description=description, parameters=parameters))


class ToolManager:
    def __init__(self):
        self.tool_list: list[Tool] = []

    _total_tool_list: list[Tool] = [
        _make_tool("get_test_data_1", "当用户要求测试工具调用功能时调用获得返回数据，有很多类似测试工具，这是第一个", {
            "type": "object",
            "properties": {"testNum": {"type": "integer", "description": "用户需要你传入的测试数据"}},
        }),
        _make_tool("get_test_data_2", "当用户要求测试工具调用功能时调用获得返回数据，有很多类似测试工具，这是第二个", {
            "type": "object",
            "properties": {"testNum": {"type": "integer", "description": "用户需要你传入的测试数据"}},
        }),
        _make_tool("get_test_data_3", "当用户要求测试工具调用功能时调用获得返回数据，有很多类似测试工具，这是第三个", {
            "type": "object",
            "properties": {"testNum": {"type": "integer", "description": "用户需要你传入的测试数据"}},
        }),
        _make_tool("read_file",
            "读取 workspace 目录下的文本文件内容。支持分段读取大文件。"
            "用户说'读一下xxx'、'看看这个文件'、'打开xxx'时调用此工具。"
            "注意：只能读取 workspace 目录下的文件，路径必须使用相对路径，禁止绝对路径。",
            {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "文件名或相对路径。例如 '笔记.txt'、'日记/今天.txt'。禁止使用绝对路径或 ../ 写法。"},
                    "startLine": {"type": "integer", "description": "起始行号（从1开始，选填，不填则从第1行开始）。用于分段读取大文件。"},
                    "lineCount": {"type": "integer", "description": "读取行数（选填，不填则读取全部，但最多返回500行）。用于分段读取大文件。"},
                },
                "required": ["filePath"],
            }),
        _make_tool("write_file",
            "将文本内容写入 workspace 目录下的文件（覆盖模式，会清空已有内容）。"
            "用户说'帮我记下来'、'保存到文件'、'写一个xxx文件'时调用此工具。"
            "如果要往已有文件追加内容而不是覆盖，请使用 append_file 工具。禁止使用绝对路径。",
            {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "文件名或相对路径。例如 '笔记.txt'、'日记/今天.txt'。禁止使用绝对路径或 ../ 写法。"},
                    "content": {"type": "string", "description": "要写入的文本内容"},
                },
                "required": ["filePath", "content"],
            }),
        _make_tool("append_file",
            "在 workspace 目录下的文件末尾追加文本内容（不清除已有内容，换行追加）。"
            "文件不存在时会自动创建。用户说'往xxx里加一段'、'补充到文件'、'追加到xxx'时调用此工具。禁止使用绝对路径。",
            {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "文件名或相对路径。例如 '笔记.txt'、'日记/今天.txt'。禁止使用绝对路径或 ../ 写法。"},
                    "content": {"type": "string", "description": "要追加的文本内容（会自动在末尾加换行）"},
                },
                "required": ["filePath", "content"],
            }),
        _make_tool("delete_file",
            "删除 workspace 目录下的文件（不可恢复，请谨慎使用！）。必须将 confirm 参数设为 \"yes\" 才会真正执行。"
            "用户说'删掉xxx'、'删除xxx文件'时调用此工具。禁止使用绝对路径。",
            {
                "type": "object",
                "properties": {
                    "filePath": {"type": "string", "description": "要删除的文件名或相对路径。例如 '笔记.txt'。禁止使用绝对路径或 ../ 写法。"},
                    "confirm": {"type": "string", "description": "确认删除必须填写 \"yes\"，否则不会执行删除操作。这是一个安全机制。"},
                },
                "required": ["filePath", "confirm"],
            }),
        _make_tool("list_files",
            "查看 workspace 目录下的文件和文件夹列表。用户说'看看有哪些文件'、'列出文件'、'目录里有什么'时调用此工具。返回所有文件名和文件夹名，以及文件大小。",
            {
                "type": "object",
                "properties": {
                    "subDir": {"type": "string", "description": "要查看的子目录路径（选填）。不填则查看根目录。例如 '日记'。禁止使用绝对路径或 ../ 写法。"},
                    "recursive": {"type": "boolean", "description": "是否递归列出所有子目录中的文件（选填，默认 false）。填 true 时会遍历所有子文件夹。"},
                },
            }),
        _make_tool("search_files",
            "在 workspace 目录下的所有文本文件中搜索指定关键词。类似 grep 功能，返回包含关键词的文件名和匹配行内容。"
            "用户说'找一下包含xxx的文件'、'搜索xxx'、'哪些文件里有xxx'时调用此工具。默认搜索根目录，可指定子目录缩小范围。",
            {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "要搜索的关键词（支持中文和英文）"},
                    "subDir": {"type": "string", "description": "在哪个子目录中搜索（选填，不填则搜索整个 workspace 目录）。例如 '日记'。禁止使用绝对路径或 ../ 写法。"},
                },
                "required": ["keyword"],
            }),
        _make_tool("move_file",
            "移动或重命名 workspace 目录下的文件或文件夹。如果目标和源在同一目录，就相当于重命名。"
            "用户说'把xxx重命名为yyy'、'把xxx移到yyy目录下'时调用此工具。禁止使用绝对路径。",
            {
                "type": "object",
                "properties": {
                    "sourcePath": {"type": "string", "description": "要移动/重命名的源文件或文件夹路径。例如 '笔记.txt'、'日记/旧名.txt'。禁止使用绝对路径或 ../ 写法。"},
                    "destPath": {"type": "string", "description": "目标路径或新名称。例如 '新笔记.txt'、'存档/笔记.txt'。禁止使用绝对路径或 ../ 写法。"},
                },
                "required": ["sourcePath", "destPath"],
            }),
        _make_tool("create_directory",
            "在 workspace 目录下创建一个新文件夹（会同时创建所有需要的父目录）。"
            "用户说'建一个文件夹'、'创建目录xxx'、'新建xxx文件夹'时调用此工具。禁止使用绝对路径。",
            {
                "type": "object",
                "properties": {
                    "dirPath": {"type": "string", "description": "要创建的文件夹路径。例如 '照片'、'项目/代码/测试'。禁止使用绝对路径或 ../ 写法。"},
                },
                "required": ["dirPath"],
            }),
        _make_tool("add_user_memory",
            "从对话中得到用户信息时调用将信息保存为用户画像，请积极调用此函数尽可能多的记录用户信息，参数 content 为要记录的内容。",
            {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要记录的信息，用简洁的一句话概括。"},
                },
                "required": ["content"],
            }),
        _make_tool("list_user_memories",
            "查看目前已记录的全部用户画像记忆，了解用户的偏好、习惯、情绪状态和过往互动。"
            "用户说'你记得我什么'、'我的画像'、'你了解我什么'时调用此工具。",
            {"type": "object", "properties": {}}),
        _make_tool("delete_user_memory",
            "删除指定编号的用户画像记忆（不可恢复）。必须将 confirm 参数设为 \"yes\" 才会真正执行。"
            "用户说'忘掉xxx'、'删除xxx记忆'、'不用记住xxx'时调用此工具。",
            {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "要删除的记忆编号（从 add_user_memory 或 list_user_memories 的返回结果中获取）"},
                    "confirm": {"type": "string", "description": "确认删除必须填写 \"yes\"，否则不会执行删除操作。"},
                },
                "required": ["id", "confirm"],
            }),
        _make_tool("clear_user_memories",
            "清空全部用户画像记忆（不可恢复，请谨慎使用！）。必须将 confirm 参数设为 \"yes\" 才会真正执行。"
            "用户说'忘掉关于我的一切'、'清除我的画像'、'重置记忆'时调用此工具。调用前务必二次确认用户意图。",
            {
                "type": "object",
                "properties": {
                    "confirm": {"type": "string", "description": "确认清空必须填写 \"yes\"，否则不会执行清空操作。"},
                },
                "required": ["confirm"],
            }),
        _make_tool("list_skills",
            "查看当前可用的全部技能列表（仅返回名称和描述，不返回完整内容）。"
            "当用户问'你会什么技能'、'有哪些技能'、'你能做什么'时调用此工具。",
            {"type": "object", "properties": {}}),
        _make_tool("activate_skill",
            "激活一个技能，将其完整的行为指令注入系统提示词。激活后 ATRI 的行为会在下一轮对话中改变。"
            "最多同时激活 3 个技能，超出时自动关闭最早激活的。"
            "当用户要求使用某个技能、或你判断当前对话需要某个技能时调用此工具。",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "要激活的技能名称（从 list_skills 的返回结果中获取）"},
                },
                "required": ["name"],
            }),
        _make_tool("deactivate_skill",
            "关闭一个已激活的技能。关闭后该技能的行为指令将从系统提示词中移除，下一轮对话生效。"
            "当用户说'关闭xxx技能'、'不用这个技能了'、'退出xxx模式'时调用此工具。",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "要关闭的技能名称"},
                },
                "required": ["name"],
            }),
        _make_tool("read_skill_file",
            "读取指定技能的完整 SKILL.md 文件内容（含 frontmatter）。用于审查技能内容、准备修改技能。"
            "技能文件存储在 skills/<name>/SKILL.md。",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "技能名称"},
                },
                "required": ["name"],
            }),
        _make_tool("write_skill_file",
            "创建或覆盖一个技能的 SKILL.md 文件。这是 ATRI 自我迭代的核心工具——你可以通过此工具创建新技能或修改已有技能。"
            "技能文件格式：YAML frontmatter（--- 开头和结尾）后跟 Markdown 行为指令。"
            "Frontmatter 必须包含 name 和 description 字段。"
            "用户说'记住这个做法'、'把这个能力保存为技能'、'创建新技能'、'更新xxx技能'时调用此工具。",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "技能名称（用作目录名，小写英文+连字符，如 'code-reviewer'）"},
                    "content": {"type": "string", "description": "完整的 SKILL.md 文件内容，以 --- 开头包含 YAML frontmatter，后跟 Markdown 行为指令。"},
                },
                "required": ["name", "content"],
            }),
        _make_tool("web_search",
            "在互联网上搜索指定关键词，返回前5条结果的标题、URL和摘要。"
            "当用户问'查一下xxx'、'搜索xxx'、'网上有没有xxx'、'最新的xxx是什么'时调用此工具。"
            "搜索结果来自多个搜索引擎的聚合，支持中文和英文查询。",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，支持中文和英文"},
                },
                "required": ["query"],
            }),
        # ── 百度贴吧浏览工具 ──
        _make_tool("tieba_get_threads",
            "获取百度贴吧的帖子列表。可以浏览任意贴吧的最新帖子，按时间倒序排列。"
            "用户说'看看贴吧'、'xxx吧有什么'、'逛逛xxx吧'、'贴吧热帖'时调用此工具。"
            "支持翻页，每次返回一页约20条帖子，包含帖子ID、标题、作者、回复数。",
            {
                "type": "object",
                "properties": {
                    "fname": {"type": "string", "description": "贴吧名称，例如 'steam'、'李毅'、'天堂鸡汤'。注意：不要加'吧'字。"},
                    "page": {"type": "integer", "description": "页码，从1开始（选填，默认第1页）"},
                },
                "required": ["fname"],
            }),
        _make_tool("tieba_get_posts",
            "获取指定帖子的回复/评论内容。需要先从 get_threads 或 search_exact 结果中获取帖子ID(tid)。"
            "用户说'看看这个帖子'、'帖子详情'、'看看回复'、'这个帖子讲了什么'时调用此工具。"
            "注意：部分贴吧需要登录才能查看帖子内容，如返回登录提示请告知用户。",
            {
                "type": "object",
                "properties": {
                    "tid": {"type": "integer", "description": "帖子ID（tid），从 get_threads 或 search_exact 的返回结果中获取"},
                    "page": {"type": "integer", "description": "页码，从1开始（选填，默认第1页，一页约20条回复）"},
                },
                "required": ["tid"],
            }),
        _make_tool("tieba_search_exact",
            "在指定贴吧内按关键词精确搜索帖子。用户想知道某个话题在某个吧里有没有讨论时非常有用。"
            "用户说'搜一下xxx吧的xxx'、'在xxx吧找xxx'、'xxx吧有没有xxx相关的帖子'时调用此工具。",
            {
                "type": "object",
                "properties": {
                    "fname": {"type": "string", "description": "贴吧名称，例如 '显卡'、'python'"},
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "page": {"type": "integer", "description": "页码，从1开始（选填，默认第1页）"},
                },
                "required": ["fname", "keyword"],
            }),
        _make_tool("tieba_get_forum_info",
            "获取指定贴吧的详细信息，包括ID、等级、会员数、帖子总数、简介等。"
            "用户说'xxx吧怎么样'、'介绍一下xxx吧'、'xxx吧有多少人'时调用此工具。",
            {
                "type": "object",
                "properties": {
                    "fname": {"type": "string", "description": "贴吧名称，例如 'steam'、'显卡'"},
                },
                "required": ["fname"],
            }),
        _make_tool("tieba_get_user_info",
            "获取百度贴吧用户的基本信息，包括昵称、等级、粉丝数、关注数、发帖数、签名等。"
            "用户说'查一下这个贴吧用户'、'看看这个人的信息'、'xxx是谁'时调用此工具。",
            {
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "用户名、用户ID或用户主页链接"},
                },
                "required": ["user"],
            }),
        _make_tool("tieba_get_hot_threads",
            "获取指定贴吧的热门帖子（按回复数排序），快速了解贴吧当前讨论热点。"
            "用户说'xxx吧在聊什么'、'xxx吧热门话题'、'xxx吧最近火什么'时优先调用此工具而非 get_threads。",
            {
                "type": "object",
                "properties": {
                    "fname": {"type": "string", "description": "贴吧名称，例如 'steam'、'显卡'"},
                    "count": {"type": "integer", "description": "返回条数（选填，默认10，最大30）"},
                },
                "required": ["fname"],
            }),
    ]

    def tool_init(self):
        if not self.tool_list:
            self.tool_list.extend(self._total_tool_list)
        # 如果 aiotieba 未安装，移除贴吧工具（避免 AI 尝试调用不存在的功能）
        try:
            __import__("aiotieba")
        except ImportError:
            tieba_names = {
                "tieba_get_threads", "tieba_get_posts", "tieba_search_exact",
                "tieba_get_forum_info", "tieba_get_user_info", "tieba_get_hot_threads",
            }
            self.tool_list = [t for t in self.tool_list if t.function.name not in tieba_names]
        FileTool.ensure_work_dir()

    def tool_actor(self, name: str | None, arguments: str, active_skills: list[str] | None = None) -> str | None:
        if not name:
            return "未知工具调用"
        try:
            args = json.loads(arguments) if arguments and arguments.strip() else {}
        except json.JSONDecodeError:
            args = {}

        if name == "get_test_data_1":
            return str(args.get("testNum", 0) * 1)
        if name == "get_test_data_2":
            return str(args.get("testNum", 0) * 2)
        if name == "get_test_data_3":
            return str(args.get("testNum", 0) * 3)

        if name == "read_file":
            return FileTool.read_file(
                args.get("filePath", ""),
                args.get("startLine", 1),
                args.get("lineCount", -1),
            )
        if name == "write_file":
            return FileTool.write_file(args["filePath"], args["content"])
        if name == "append_file":
            return FileTool.append_file(args["filePath"], args["content"])
        if name == "delete_file":
            return FileTool.delete_file(args["filePath"], args["confirm"])
        if name == "list_files":
            return FileTool.list_files(args.get("subDir", ""), args.get("recursive", False))
        if name == "search_files":
            return FileTool.search_files(args["keyword"], args.get("subDir", ""))
        if name == "move_file":
            return FileTool.move_file(args["sourcePath"], args["destPath"])
        if name == "create_directory":
            return FileTool.create_directory(args["dirPath"])

        if name == "add_user_memory":
            return MemoryTool.add_memory(args.get("content", ""))
        if name == "list_user_memories":
            return MemoryTool.list_memories()
        if name == "delete_user_memory":
            return MemoryTool.delete_memory(args.get("id", 0), args.get("confirm", "no"))
        if name == "clear_user_memories":
            return MemoryTool.clear_memories(args.get("confirm", "no"))

        if name == "list_skills":
            skills = SkillLoader.list_skills()
            if not skills:
                return "当前没有可用技能。技能文件存放在 skills/ 目录下，每个技能一个子文件夹，内含 SKILL.md。"
            result = f"可用技能（共 {len(skills)} 个）\n---\n"
            for s in skills:
                result += f"- {s['name']}: {s['description']}\n"
            return result

        if name == "activate_skill":
            skill_name = str(args.get("name", "")).strip()
            err = SkillLoader.validate_name(skill_name)
            if err:
                return err
            if not SkillLoader.skill_exists(skill_name):
                return f"技能 '{skill_name}' 不存在。使用 list_skills 查看可用技能。"
            skills_list = active_skills if active_skills is not None else []
            if skill_name in skills_list:
                return f"技能 '{skill_name}' 已经激活了。当前激活: {skills_list}"
            while len(skills_list) >= 3:
                evicted = skills_list.pop(0)
            skills_list.append(skill_name)
            preview = SkillLoader.load_skill(skill_name) or ""
            preview_short = preview[:200] + "..." if len(preview) > 200 else preview
            return f"[已激活] {skill_name}\n预览：{preview_short}\n当前激活: {skills_list}"

        if name == "deactivate_skill":
            skill_name = str(args.get("name", "")).strip()
            skills_list = active_skills if active_skills is not None else []
            if not skill_name:
                if not skills_list:
                    return "当前没有激活的技能。"
                closed = skills_list.pop()
                return f"[已关闭] {closed}\n当前激活: {skills_list}"
            if skill_name not in skills_list:
                return f"技能 '{skill_name}' 没有激活。当前激活: {skills_list}"
            skills_list.remove(skill_name)
            return f"[已关闭] {skill_name}\n当前激活: {skills_list}"

        if name == "read_skill_file":
            skill_name = str(args.get("name", "")).strip()
            err = SkillLoader.validate_name(skill_name)
            if err:
                return err
            content = SkillLoader.load_full_skill(skill_name)
            if content is None:
                return f"技能 '{skill_name}' 不存在。使用 list_skills 查看可用技能。"
            return content

        if name == "write_skill_file":
            skill_name = str(args.get("name", "")).strip()
            err = SkillLoader.validate_name(skill_name)
            if err:
                return err
            content = str(args.get("content", ""))
            if not content.strip():
                return "content 不能为空。请提供完整的 SKILL.md 内容（YAML frontmatter + Markdown 指令）。"
            if not content.strip().startswith("---"):
                return "SKILL.md 必须以 YAML frontmatter 开头（---）。格式：\n---\nname: 技能名\ndescription: 描述\n---\n\n# 技能标题\n行为指令..."
            if SkillLoader.write_skill(skill_name, content):
                return f"[已保存] 技能 '{skill_name}' 已写入 skills/{skill_name}/SKILL.md。使用 activate_skill 激活。"
            return f"写入技能 '{skill_name}' 失败。"

        if name == "web_search":
            return self._web_search(str(args.get("query", "")))

        # ── 百度贴吧浏览工具 ──
        if name == "tieba_get_threads":
            return TiebaTool.get_threads(str(args.get("fname", "")), int(args.get("page", 1) or 1))
        if name == "tieba_get_posts":
            return TiebaTool.get_posts(int(args.get("tid", 0) or 0), int(args.get("page", 1) or 1))
        if name == "tieba_search_exact":
            return TiebaTool.search_exact(
                str(args.get("fname", "")), str(args.get("keyword", "")), int(args.get("page", 1) or 1)
            )
        if name == "tieba_get_forum_info":
            return TiebaTool.get_forum_info(str(args.get("fname", "")))
        if name == "tieba_get_user_info":
            return TiebaTool.get_user_info(str(args.get("user", "")))
        if name == "tieba_get_hot_threads":
            return TiebaTool.get_hot_threads(str(args.get("fname", "")), int(args.get("count", 10) or 10))

        return "未知工具调用"

    @staticmethod
    def _web_search(query: str, limit: int = 5) -> str:
        if not query.strip():
            return "搜索关键词不能为空。"
        try:
            resp = httpx.get(
                "https://www.bing.com/search",
                params={"q": query},
                timeout=10,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            return f"搜索请求失败：{e}"

        html = resp.text
        # Extract result blocks from Bing's HTML
        for pattern in [
            r'<li class=\"b_algo\">(.*?)</li>',
            r'<li class=\"b_algo\"[^>]*>(.*?)</li>',
        ]:
            blocks = re.findall(pattern, html, re.DOTALL)
            if blocks:
                break

        if not blocks:
            return f"未找到与 '{query}' 相关的网页结果。"

        lines = [f"搜索 '{query}' 的结果（共 {min(len(blocks), limit)} 条）\n---"]
        for i, block in enumerate(blocks[:limit]):
            # Title
            title = ""
            for tp in [r'<h2[^>]*><a[^>]*>(.*?)</a>', r'<a[^>]*>(.*?)</a>']:
                t_m = re.search(tp, block, re.DOTALL)
                if t_m:
                    title = re.sub(r'<[^>]+>', '', t_m.group(1)).strip()
                    break
            title = unescape(title) or "无标题"

            # URL (skip Bing redirect URLs)
            urls = re.findall(r'href=\"(https?://[^\"]+)\"', block)
            url = ""
            for u in urls:
                if "r.bing.com" not in u and "go.microsoft.com" not in u:
                    url = u
                    break
            if not url and urls:
                url = urls[0]

            # Snippet
            snippet = ""
            for sp in [r'<p[^>]*>(.*?)</p>']:
                s_m = re.search(sp, block, re.DOTALL)
                if s_m:
                    snippet = re.sub(r'<[^>]+>', '', s_m.group(1)).strip()
                    break
            snippet = unescape(snippet)

            lines.append(f"{i+1}. {title}")
            lines.append(f"   URL: {url}")
            lines.append(f"   {snippet}\n")

        return "\n".join(lines)
