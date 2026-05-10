# GeekClock 项目结构说明

GeekClock 是一个基于 PySide6 + APScheduler 的桌面闹钟应用。采用根目录应用包布局。

## 目录结构

```text
GeekClock_v1/
├── pyproject.toml
├── build.bat
├── build.py
├── cleanup.bat              # 清理 __pycache__ 和构建产物
├── main.py
├── alarms.json
├── icon.ico
├── sounds/
│   ├── bell1.mp3
│   ├── bell2.mp3
│   ├── bell3.mp3
│   ├── bell4.mp3
│   └── bell5.mp3
└── geekclock/
    ├── __init__.py
    ├── __main__.py
    ├── app.py
    ├── core/
    │   ├── __init__.py
    │   ├── audio_player.py
    │   ├── config.py
    │   └── scheduler.py
    ├── system/
    │   ├── __init__.py
    │   ├── autostart.py
    │   ├── logging_setup.py
    │   ├── resources.py
    │   └── single_instance.py
    ├── main_window/
    │   ├── __init__.py
    │   ├── alarm_card.py
    │   ├── collapsible_group.py
    │   └── window.py
    ├── tray/
    │   ├── __init__.py
    │   └── tray.py
    ├── floating_clock/
    │   ├── __init__.py
    │   └── floating_clock.py
    ├── timer/
    │   ├── __init__.py
    │   ├── settings_dialog.py
    │   └── widget.py
    ├── dialogs/
    │   ├── __init__.py
    │   ├── edit_alarm.py
    │   ├── keep_alive_settings.py
    │   ├── notification.py
    │   └── settings.py
    └── common/
        ├── __init__.py
        └── opacity_slider.py
```

`logs/`、`build/`、`dist/`、`__pycache__/` 都是运行或构建产物，已在 `.gitignore` 中忽略。

## 模块职责

### 入口层

- `main.py`：极薄启动器，只负责调用 `geekclock.app.main()`。
- `geekclock/__main__.py`：支持 `python -m geekclock`。
- `geekclock/app.py`：应用装配层，创建 QApplication，初始化调度器、音频、通知、托盘、悬浮时钟和计时器，并连接所有信号。

### core/

- `config.py`：读取和保存 `alarms.json`，提供闹钟、通知、保活、悬浮时钟、计时器、全局设置访问接口。
- `scheduler.py`：封装 APScheduler，负责 interval / cron / date 三类触发器、延后提醒、音响保活定时任务。
- `audio_player.py`：封装 QMediaPlayer，支持渐强、重复播放、最长播放时长和跨线程播放请求。

### system/

- `resources.py`：统一项目根和资源路径。打包后优先读取 `sys._MEIPASS` 内资源。
- `logging_setup.py`：初始化按日期滚动的日志文件（保留 7 天），并安装全局异常处理器。
- `single_instance.py`：使用 QLocalServer / QLocalSocket 实现单实例锁。
- `autostart.py`：Windows 开机自启注册表管理。

### UI 层

- `main_window/window.py`：主窗口和闹钟列表，支持按分组折叠显示。底部状态栏含音响保活图标按钮。
- `main_window/alarm_card.py`：单条闹钟卡片组件。
- `main_window/collapsible_group.py`：可折叠分组容器，支持批量开关同组闹钟。
- `tray/tray.py`：系统托盘图标和右键菜单，含保活切换菜单项。
- `floating_clock/floating_clock.py`：桌面悬浮时钟（时钟模式 / 图标模式）。
- `timer/widget.py`：倒计时/秒表悬浮窗。
- `timer/settings_dialog.py`：倒计时设置对话框。
- `dialogs/edit_alarm.py`：新建/编辑闹钟对话框。
- `dialogs/notification.py`：通知管理器和延后提醒对话框。
- `dialogs/settings.py`：全局设置对话框（勿扰、通知、开机自启）。
- `dialogs/keep_alive_settings.py`：音响保活设置弹窗（通过主窗口左下角音响图标按钮打开）。
- `common/opacity_slider.py`：透明度滑动条组件（被悬浮时钟和计时器共用）。

## 路径规则

所有跨模块 import 使用绝对包路径：

```python
from geekclock.core import config
from geekclock.core.scheduler import AlarmScheduler
from geekclock.dialogs.settings import SettingsDialog
```

资源路径统一通过 `geekclock.system.resources`：

```python
from geekclock.system.resources import project_root, resource_path
```

## 配置和日志

源码运行时：
- 配置文件：项目根目录 `alarms.json`
- 日志目录：项目根目录 `logs/`

打包运行时：
- 配置文件：`%APPDATA%\GeekClock\alarms.json`
- 日志目录：exe 同级 `logs/`

## 运行和打包

源码运行：

```bash
uv run python main.py
# 或
uv run python -m geekclock
```

安装依赖：

```bash
uv sync
```

Windows 打包：

```bat
build.bat
```

清理临时文件：

```bat
cleanup.bat
```
