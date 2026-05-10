"""开机自启动管理（Windows）。

通过修改注册表 HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run 实现。
其他平台暂不支持，函数会静默返回 False。
"""
import logging
import sys
from pathlib import Path

from geekclock.system.resources import project_root

logger = logging.getLogger(__name__)

# 注册表中此程序的标识名
APP_NAME = "GeekClock"

# Windows 注册表路径
REG_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _get_executable_path() -> str:
    """获取当前可执行程序的路径。

    打包后是 exe 路径，开发模式是 python + 脚本路径。
    """
    if getattr(sys, "frozen", False):
        # 打包后：sys.executable 是 exe 本身
        return sys.executable
    else:
        # 开发模式：用 pythonw + main.py
        # 注意 pythonw（无控制台）而不是 python，避免每次开机弹黑窗
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
        if not Path(python_exe).exists():
            python_exe = sys.executable

        main_script = project_root() / "main.py"
        return f'"{python_exe}" "{main_script}" --minimized'


def is_autostart_enabled() -> bool:
    """检查是否已启用开机自启。"""
    if sys.platform != "win32":
        return False

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_PATH) as key:
            try:
                value, _ = winreg.QueryValueEx(key, APP_NAME)
                return bool(value)
            except FileNotFoundError:
                return False
    except Exception as e:
        logger.error(f"检查开机自启失败：{e}")
        return False


def set_autostart(enabled: bool) -> bool:
    """设置开机自启。

    Returns:
        True 表示成功，False 表示失败或不支持当前平台
    """
    if sys.platform != "win32":
        logger.warning("开机自启功能仅支持 Windows")
        return False

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REG_RUN_PATH,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                exe_path = _get_executable_path()
                winreg.SetValueEx(
                    key, APP_NAME, 0, winreg.REG_SZ, exe_path,
                )
                logger.info(f"已启用开机自启：{exe_path}")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    logger.info("已禁用开机自启")
                except FileNotFoundError:
                    pass  # 本来就没有，无需删除

        return True
    except Exception as e:
        logger.error(f"设置开机自启失败：{e}")
        return False
