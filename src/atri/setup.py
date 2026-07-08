"""ATRI setup wizard — environment check, dependency installation, and API configuration."""

import json
import subprocess
import sys
from pathlib import Path
from atri import DATA_DIR
from atri.prompt_manager import PromptManager
from atri.file_tool import FileTool

_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"


def _header(text: str) -> None:
    print(f"\n{'='*50}")
    print(f"  {text}")
    print(f"{'='*50}")


def _ok(text: str) -> None:
    print(f"  [OK] {text}")


def _fail(text: str) -> None:
    print(f"  [FAIL] {text}")


def _pip_install(pkg: str) -> bool:
    """Run pip install and return True on success."""
    print(f"  正在安装 {pkg} ...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pkg, "-i", _MIRROR],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return False
    # Verify import
    try:
        __import__(pkg)
        return True
    except ImportError:
        return False


def check_environment() -> bool:
    _header("第一步：环境检查")

    # Python version
    v = sys.version_info
    py_ok = v >= (3, 12)
    if py_ok:
        _ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        _fail(f"Python {v.major}.{v.minor}.{v.micro} (需要 3.12+)")

    # Core dependencies
    deps = {"httpx": "httpx", "rich": "rich"}
    all_ok = py_ok
    for name, pkg in deps.items():
        try:
            __import__(pkg)
            _ok(f"依赖包 {name}")
        except ImportError:
            _fail(f"依赖包 {name} 未安装")
            print(f"         正在自动安装 {pkg} ...")
            if _pip_install(pkg):
                _ok(f"依赖包 {name} 安装成功")
            else:
                _fail(f"依赖包 {name} 安装失败，请手动执行 pip install {pkg}")
                all_ok = False

    # Optional: aiotieba for tieba browsing
    try:
        __import__("aiotieba")
        _ok("可选依赖 aiotieba (贴吧浏览)")
    except ImportError:
        print("  [INFO] 可选依赖 aiotieba 未安装，贴吧浏览工具当前不可用。")
        answer = input("         是否现在安装？(Y/n) ").strip().lower()
        if answer in ("", "y", "yes"):
            if _pip_install("aiotieba"):
                _ok("aiotieba 安装成功，贴吧工具已就绪")
            else:
                print("  [WARN] aiotieba 安装失败，可稍后手动执行 pip install aiotieba")
        else:
            print("         已跳过。如需贴吧功能，稍后运行 pip install aiotieba 即可。")

    return all_ok


def init_directories() -> None:
    _header("第二步：目录初始化")
    for label, path in [
        ("data", DATA_DIR),
        ("workspace", FileTool.work_dir),
    ]:
        p = Path(path)
        if p.exists():
            _ok(f"{label}/ 已存在")
        else:
            p.mkdir(parents=True)
            _ok(f"{label}/ 已创建")


def init_config_files() -> None:
    pm = PromptManager()
    pm._load_prompt_file(
        str(DATA_DIR / "SOUL.json"), pm.default_soul, "SOUL.json"
    )
    pm._load_prompt_file(
        str(DATA_DIR / "RULES.json"), pm.default_rules, "RULES.json"
    )
    pm._load_prompt_file(
        str(DATA_DIR / "CAPABILITY.json"), pm.default_capability, "CAPABILITY.json"
    )


def configure_api() -> None:
    _header("第三步：API 参数配置")

    config_path = DATA_DIR / "UserSettings.json"
    current = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            current = data.get("DeepSeek", {})
        except (json.JSONDecodeError, OSError):
            pass

    if current:
        print("  当前配置：")
        print(f"    ApiKey: {current.get('ApiKey', '')[:8]}****")
        print(f"    Url:    {current.get('Url', '')}")
        print(f"    Model:  {current.get('Model', '')}")
        print()
        if input("  是否修改？(y/N) ").strip().lower() != "y":
            print("  保持现有配置不变。")
            return
    else:
        print("  未检测到 API 配置，请按提示输入。")
        print()

    api_key = input("  DeepSeek ApiKey: ").strip()
    api_url = input("  DeepSeek URL (默认 https://api.deepseek.com/chat/completions): ").strip()
    api_model = input("  DeepSeek Model (默认 deepseek-chat): ").strip()

    if not api_key:
        print("  ApiKey 不能为空，跳过。")
        return

    settings = {
        "DeepSeek": {
            "ApiKey": api_key,
            "Url": api_url or "https://api.deepseek.com/chat/completions",
            "Model": api_model or "deepseek-chat",
        }
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _ok("API 配置已保存")


def configure_tieba() -> None:
    """Configure optional Baidu Tieba credentials."""
    _header("第四步：贴吧登录凭据（可选）")

    try:
        __import__("aiotieba")
    except ImportError:
        print("  aiotieba 未安装，跳过贴吧配置。（可重新运行 atri-setup 安装）")
        return

    config_path = DATA_DIR / "UserSettings.json"

    # Load current settings
    current_tieba = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            current_tieba = data.get("Tieba", {})
        except (json.JSONDecodeError, OSError):
            pass

    print("  贴吧浏览功能无需登录即可使用。")
    print("  如需查看帖子详情、用户信息等高级功能，需要配置贴吧登录凭据。")
    print()
    print("  获取方法：")
    print("  1. 用浏览器打开 https://tieba.baidu.com 并登录")
    print("  2. 按 F12 → Application → Cookies → tieba.baidu.com")
    print("  3. 找到 BDUSS 和 STOKEN 两个 Cookie 值")
    print()

    if current_tieba:
        bduss_preview = current_tieba.get("BDUSS", "")[:8] + "****" if current_tieba.get("BDUSS") else "(未设置)"
        print(f"  当前 BDUSS:  {bduss_preview}")
        print(f"  当前 STOKEN: {'已设置' if current_tieba.get('STOKEN') else '(未设置)'}")
        print()
        if input("  是否修改？(y/N) ").strip().lower() != "y":
            print("  保持现有贴吧配置不变。")
            return

    bduss = input("  BDUSS (留空跳过): ").strip()
    stoken = input("  STOKEN (留空跳过): ").strip()

    if not bduss and not stoken:
        print("  未配置登录凭据，贴吧浏览功能仍可使用。")
        return

    # Merge into existing config
    full_config = {}
    if config_path.exists():
        try:
            full_config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    full_config["Tieba"] = {
        "BDUSS": bduss,
        "STOKEN": stoken,
    }
    config_path.write_text(
        json.dumps(full_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _ok("贴吧配置已保存")


def print_summary() -> None:
    _header("配置完成")
    print(f"  数据目录: {DATA_DIR}")
    print(f"  工作目录: {FileTool.work_dir}")
    print(f"  启动命令: atri")
    print()


def main() -> None:
    print("ATRI 配置向导")
    check_environment()
    init_directories()
    try:
        init_config_files()
    except Exception as e:
        print(f"  配置文件初始化失败: {e}")
    configure_api()
    configure_tieba()
    print_summary()


if __name__ == "__main__":
    main()
