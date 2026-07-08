"""ATRI 一键安装配置脚本 — 放在项目根目录，双击或用 python setup.py 运行。

用法:  python setup.py
效果:  1. pip install -e .        (安装 atri 本体 + 核心依赖)
       2. 自动进入配置向导        (API Key + 贴吧等)
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"


def step(msg: str) -> None:
    print(f"\n{'='*50}")
    print(f"  {msg}")
    print(f"{'='*50}")


def main() -> None:
    print("ATRI — 一键安装配置")
    print(f"  项目路径: {ROOT}")

    # Step 1: Install the project itself (editable mode)
    step("第一步：安装项目及核心依赖")
    print("  执行 pip install -e . ...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-e", str(ROOT), "-i", MIRROR],
            cwd=str(ROOT),
        )
        print("  [OK] atri 安装成功")
    except subprocess.CalledProcessError:
        print("  [FAIL] 安装失败，请检查网络连接后重试。")
        sys.exit(1)

    # Step 2: Run the setup wizard
    step("第二步：启动配置向导")
    try:
        from atri.setup import check_environment, init_directories, init_config_files
        from atri.setup import configure_api, configure_tieba, print_summary

        check_environment()
        init_directories()
        try:
            init_config_files()
        except Exception as e:
            print(f"  配置文件初始化失败: {e}")
        configure_api()
        configure_tieba()
        print_summary()

        print("配置完成！运行 python -m atri.main 或 atri 启动。")
    except ImportError:
        print("  [FAIL] 无法导入 atri 模块，安装可能未成功。")
        sys.exit(1)


if __name__ == "__main__":
    main()
