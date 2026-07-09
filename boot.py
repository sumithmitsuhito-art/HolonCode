"""ATRI 一键安装配置脚本 — 使用 uv 管理包和虚拟环境。

用法:
    uv run python boot.py          # 推荐：一步完成安装 + 配置
    python boot.py                 # 自动 uv sync 后进入配置
    python boot.py --wizard        # 跳过安装，直接进入配置向导

首次运行会自动创建 .venv 并安装所有依赖，然后引导配置 API Key 等参数。
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _venv_python() -> Path:
    """返回项目 .venv 中的 Python 解释器路径，兼容 Windows / macOS / Linux。"""
    if sys.platform == "win32":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        return ROOT / ".venv" / "bin" / "python3"


def _venv_python_exists() -> bool:
    """检查 .venv Python 是否存在且可执行。"""
    vp = _venv_python()
    return vp.exists() and vp.is_file()


# atri.setup 中需要用到的全部函数
_SETUP_FUNCTIONS = [
    "check_environment",
    "init_directories",
    "init_config_files",
    "configure_api",
    "configure_tieba",
    "print_summary",
]


def step(msg: str) -> None:
    print(f"\n{'='*50}")
    print(f"  {msg}")
    print(f"{'='*50}")


# ================================================================
# 工具
# ================================================================

def _in_venv() -> bool:
    """当前 Python 是否为项目的 .venv Python。"""
    try:
        exe = sys.executable
        if not exe:
            return False
        return Path(exe).resolve() == _venv_python().resolve()
    except (OSError, TypeError, ValueError):
        return False


def _find_uv() -> str | None:
    """在 PATH 中查找 uv，找到返回完整路径，否则返回 None。"""
    import shutil
    return shutil.which("uv")


def _require_uv() -> str:
    """查找 uv，找到返回路径，找不到打印帮助并退出。"""
    uv = _find_uv()
    if uv is None:
        print("  [FAIL] 未找到 uv 包管理器。")
        print()
        print("  安装方法（任选一种）：")
        print("    PowerShell:  powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"")
        print("    pip:         pip install uv")
        print("    scoop:       scoop install uv")
        print()
        print("  更多信息: https://docs.astral.sh/uv/")
        sys.exit(1)
    return uv


# ================================================================
# Step 1: uv sync
# ================================================================

def _run_uv_sync() -> None:
    """执行 uv sync 创建/更新虚拟环境并安装依赖。
    如果当前已在 .venv 中则跳过（用户通过 uv run 启动时 uv 已完成同步）。
    """
    step("第一步：同步项目依赖 (uv sync)")

    if _in_venv():
        print("  已在虚拟环境中（uv 已完成同步），跳过。")
        return

    uv = _require_uv()
    print(f"  uv 路径: {uv}")
    print("  正在创建/更新虚拟环境...")

    try:
        subprocess.check_call([uv, "sync"], cwd=str(ROOT))
    except subprocess.CalledProcessError as e:
        print(f"  [FAIL] uv sync 失败 (退出码 {e.returncode})")
        print()
        print("  请逐个排查以下原因：")
        print("    1. 网络连接 — 是否可访问 PyPI？是否需要代理？")
        print("    2. Python 版本 — 项目要求 Python >= 3.12，当前：")
        print(f"       {sys.version}")
        print("    3. pyproject.toml — 格式是否正确？可运行 uv sync 查看详细报错。")
        print("    4. 磁盘空间 — 是否有足够空间创建 .venv？")
        sys.exit(1)

    if not _venv_python_exists():
        print(f"  [FAIL] uv sync 完成但未找到 {_venv_python()}")
        print("  请检查 uv 是否正常运行，或手动执行 uv sync 查看详细日志。")
        sys.exit(1)

    print("  [OK] 虚拟环境就绪，依赖已同步")


# ================================================================
# Step 2: 配置向导（必须在 venv 内运行）
# ================================================================

def _force_enter_venv(target: str) -> None:
    """强制通过 uv run 重新在 venv 中执行当前脚本的指定阶段。"""
    uv = _require_uv()
    print(f"  通过 uv run 切换到虚拟环境...")
    try:
        subprocess.check_call([uv, "run", "python", __file__, target])
    except subprocess.CalledProcessError as e:
        print(f"  [FAIL] uv run 执行失败 (退出码 {e.returncode})")
        sys.exit(e.returncode)
    except FileNotFoundError:
        print(f"  [FAIL] 无法执行 '{uv} run'，请确认 uv 安装正确。")
        sys.exit(1)


def _run_config_wizard() -> None:
    """运行 ATRI 配置向导。调用方保证当前已在 venv Python 中。"""
    step("第二步：启动配置向导")

    # --- 逐级验证 atri 可导入 ---
    try:
        import atri  # noqa: F401
    except ImportError as e:
        print(f"  [FAIL] 无法导入 atri 包: {e}")
        print("  请在项目根目录执行 uv sync 后重试。")
        sys.exit(1)

    try:
        import atri.setup  # noqa: F401
    except ImportError as e:
        print(f"  [FAIL] 无法导入 atri.setup 模块: {e}")
        print("  请检查 src/atri/setup.py 是否存在且无语法错误。")
        sys.exit(1)

    missing = [f for f in _SETUP_FUNCTIONS if not hasattr(atri.setup, f)]
    if missing:
        print(f"  [FAIL] atri.setup 中缺少函数: {', '.join(missing)}")
        sys.exit(1)

    # --- 导入所需函数 ---
    from atri.setup import (  # noqa: E402
        check_environment,
        configure_api,
        configure_tieba,
        init_config_files,
        init_directories,
        print_summary,
    )

    # --- 逐个执行配置步骤 ---
    steps: list[tuple[str, callable, bool]] = [
        ("环境检查",       check_environment,  True),
        ("目录初始化",     init_directories,   True),
        ("配置文件初始化", init_config_files,  False),
        ("API 参数配置",   configure_api,      True),
        ("贴吧登录配置",   configure_tieba,    False),
        ("配置摘要",       print_summary,      False),
    ]

    for label, func, fatal in steps:
        try:
            func()
        except Exception as e:
            if fatal:
                print(f"  [FAIL] {label}失败: {e}")
                sys.exit(1)
            else:
                print(f"  [WARN] {label}失败（已跳过）: {e}")

    print()
    print("  配置完成！")
    print()
    print("  启动 ATRI:       uv run atri")
    print("  重新配置:        python boot.py --wizard")
    print("  更新依赖:        uv sync")
    print()


# ================================================================
# 主入口
# ================================================================

def main() -> None:
    print("ATRI — 一键安装配置 (uv)")
    print(f"  项目路径: {ROOT}")

    # ── --wizard / --config: 跳过 uv sync，直接进入配置 ──
    if "--wizard" in sys.argv or "--config" in sys.argv:
        if _in_venv():
            _run_config_wizard()
        else:
            # 不在 venv → 通过 uv run 强制进入
            print("  当前不在项目 .venv 中。")
            _force_enter_venv("--wizard")
        return

    # ── 正常流程: uv sync → 配置向导 ──
    _run_uv_sync()

    if _in_venv():
        _run_config_wizard()
    elif _venv_python_exists():
        # 用 venv Python 重新执行 --wizard
        print()
        print("  切换到虚拟环境执行配置向导...")
        try:
            result = subprocess.run(
                [str(_venv_python()), __file__, "--wizard"],
            )
            sys.exit(result.returncode)
        except FileNotFoundError:
            print(f"  [FAIL] 无法启动 {_venv_python()}，请尝试 uv run python boot.py --wizard")
            sys.exit(1)
    else:
        # venv 没创建成功
        print(f"  [FAIL] .venv 未就绪，无法继续。请手动执行 uv sync 排查。")
        sys.exit(1)


if __name__ == "__main__":
    main()
