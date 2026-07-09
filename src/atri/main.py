import asyncio
from atri.ai_service import AIService
from rich.console import Console

console = Console()


def print_welcome():
    console.clear()
    console.print("  ╔══════════════════════════════════════╗", style="yellow")
    console.print("  ║                                      ║", style="yellow")
    console.print("  ║     ★  ATRI  —  零 号 机  ★          ║", style="yellow")
    console.print("  ║     高性能任务型机器人               ║", style="yellow")
    console.print("  ║                                      ║", style="yellow")
    console.print("  ║  输入 /help  查看可用指令            ║", style="yellow")
    console.print("  ║  输入 /exit  退出对话                ║", style="yellow")
    console.print("  ║                                      ║", style="yellow")
    console.print("  ╚══════════════════════════════════════╝", style="yellow")
    console.print()


def print_divider():
    console.print("─── 对话开始 ───────────────────────────", style="dim")
    console.print()


def print_goodbye():
    console.print()
    console.print("  再见", style="yellow")
    console.print()


def print_help():
    console.print("  ── 可用指令 ──", style="yellow")
    console.print("  /exit, /quit, /bye    退出对话")
    console.print("  /clear                清空屏幕（保留对话历史）")
    console.print("  /status               查看当前状态")
    console.print("  /help                 显示此帮助")
    console.print()


def handle_command(cmd: str, service: AIService) -> bool:
    """Returns True if the program should exit."""
    cmd = cmd.lower().strip()
    if cmd in ("/exit", "/quit", "/bye"):
        print_goodbye()
        return True
    if cmd == "/clear":
        console.clear()
        print_welcome()
        print_divider()
        console.print("(屏幕已清空，对话历史保留)", style="dim")
        console.print()
    elif cmd == "/help":
        print_help()
    elif cmd == "/status":
        console.print(f"对话轮次：{len(service.conversation.history)} 条消息", style="dim")
        console.print(f"可用工具：{len(service.tool.tool_list)} 个", style="dim")
        console.print()
    else:
        console.print(f"未知指令：{cmd}（输入 /help 查看可用指令）", style="red")
        console.print()
    return False


async def main():
    console.set_window_title("零号机")
    print_welcome()
    service = AIService()
    service.initialization()
    print_divider()

    while True:
        try:
            user_input = console.input("[cyan]你[/cyan] > ")
        except (EOFError, KeyboardInterrupt):
            print_goodbye()
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.startswith("/"):
            if handle_command(user_input, service):
                break
            continue

        console.print()
        console.print("[magenta]零号机 > [/magenta]", end="")
        has_content = False

        try:
            async for event in service.ai_chat(user_input):
                if event.type == "content":
                    console.print(event.text, end="", style="magenta")
                    has_content = True
                elif event.type == "tool_start":
                    if has_content:
                        console.print()
                        has_content = False
                    console.print(f"  [工具] 调用: {event.tool_name}", style="dim")
                elif event.type == "tool_result":
                    pass
                elif event.type == "message":
                    console.print(event.text, style="dim")
                elif event.type == "done":
                    if has_content:
                        console.print()
                elif event.type == "error":
                    if has_content:
                        console.print(f"\n({event.text})", style="red")
                    else:
                        console.print(f"(错误: {event.text})", style="red")
        except (KeyboardInterrupt, EOFError):
            if has_content:
                console.print("(已中断)", style="red")
            raise
        except Exception:
            if has_content:
                console.print("(连接中断)", style="red")
            else:
                console.print("(未能获取回复，请检查网络或 API 配置)", style="red")
        console.print()


if __name__ == "__main__":
    asyncio.run(main())


def cli():
    """控制台脚本入口（供 uv run atri / atri 命令调用）。"""
    asyncio.run(main())
