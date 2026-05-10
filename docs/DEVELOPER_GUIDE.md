# GeekClock 开发者文档

> 一份给非编程人员也能看懂的详细技术文档。解释每个文件做什么、每个函数实现什么功能、函数之间的调用关系。

---

## 目录

1. [项目概述](#1-项目概述)
2. [文件地图](#2-文件地图)
3. [功能模块详解](#3-功能模块详解)
4. [数据流向图](#4-数据流向图)
5. [配置文件格式](#5-配置文件格式)
6. [构建打包](#6-构建打包)

---

## 1. 项目概述

**GeekClock** 是一款 Windows 桌面闹钟应用，基于 **Python + PySide6 (Qt6)** 开发。它可以：

- 创建多种类型的闹钟（每隔几分钟响一次、每天固定时刻响、单次响）
- 最小化到系统托盘后台运行
- 在桌面显示一个悬浮时钟/小图标
- 提供倒计时/秒表功能
- 响铃时弹出通知，支持"延后提醒"
- 在设定时段内自动免打扰
- 音响保活（定期激活音频设备，防止系统休眠）
- 开机自动启动

### 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.12.10（锁定） | 编程语言 |
| PySide6 | Qt6 的 Python 绑定，构建整个图形界面 |
| APScheduler | 定时任务调度引擎，管理闹钟触发 |
| PyInstaller | 打包成单个 .exe 文件 |

### 核心设计思想

程序采用 **信号-槽 (Signal-Slot)** 机制通信。Qt 的信号-槽就像广播系统：一个组件发出"信号"（广播），其他组件通过"槽"（接收器）接收并处理。这样做的好处是各组件之间不需要直接调用对方，可以独立修改。

---

## 2. 文件地图

```
GeekClock_v1/
├── main.py                          # 程序启动入口（最外层）
├── build.py                         # 打包脚本
├── build.bat                        # Windows 打包批处理
├── cleanup.bat                      # 清理临时文件脚本
├── pyproject.toml                   # 项目元数据和依赖声明
├── alarms.json                      # 闹钟配置文件（运行时生成）
├── icon.ico                         # 程序图标
├── sounds/                          # 音频文件目录
│   ├── bell1.mp3
│   ├── bell2.mp3
│   ├── bell3.mp3
│   ├── bell4.mp3
│   └── bell5.mp3
│
└── geekclock/                       # 主代码包
    ├── __init__.py                  # 包声明（空文件）
    ├── __main__.py                  # 支持 python -m geekclock 启动
    ├── app.py                       # ★ 主程序：组装所有组件，连接信号
    │
    ├── core/                        # 核心逻辑层
    │   ├── __init__.py
    │   ├── config.py                # ★ 配置文件读写（JSON）
    │   ├── scheduler.py             # ★ 定时调度引擎
    │   └── audio_player.py          # ★ 音频播放器
    │
    ├── main_window/                 # 主窗口界面
    │   ├── __init__.py
    │   ├── window.py                # ★ 主窗口（闹钟列表 + 可折叠分组）
    │   ├── alarm_card.py            # ★ 单条闹钟卡片组件
    │   └── collapsible_group.py     # ★ 可折叠分组容器
    │
    ├── dialogs/                     # 对话框
    │   ├── __init__.py
    │   ├── edit_alarm.py            # ★ 新建/编辑闹钟对话框
    │   ├── settings.py              # ★ 全局设置对话框（勿扰、通知、开机自启）
    │   ├── keep_alive_settings.py   # ★ 音响保活设置弹窗
    │   └── notification.py          # ★ 通知弹窗 + 延后对话框
    │
    ├── floating_clock/              # 悬浮时钟
    │   ├── __init__.py
    │   └── floating_clock.py        # ★ 桌面悬浮时钟（两种模式）
    │
    ├── timer/                       # 计时器
    │   ├── __init__.py
    │   ├── widget.py                # ★ 倒计时/秒表悬浮窗
    │   └── settings_dialog.py       # ★ 倒计时设置对话框
    │
    ├── tray/                        # 系统托盘
    │   ├── __init__.py
    │   └── tray.py                  # ★ 托盘图标和右键菜单
    │
    ├── system/                      # 系统工具
    │   ├── __init__.py
    │   ├── single_instance.py       # ★ 单实例锁
    │   ├── autostart.py             # ★ 开机自启管理
    │   ├── logging_setup.py         # ★ 日志配置
    │   └── resources.py             # ★ 资源路径工具
    │
    └── common/                      # 公共组件
        ├── __init__.py
        └── opacity_slider.py        # ★ 透明度滑动条（被悬浮时钟和计时器共用）
```

---

## 3. 功能模块详解

### 3.1 启动入口 `main.py`

| 函数 | 作用 | 被谁调用 |
|------|------|----------|
| `if __name__ == "__main__":` | Python 约定：当文件被直接运行时执行。调用 `app.main()` 启动程序 | 操作系统 |

### 3.2 主程序组装 `app.py`

**这是整个程序的"大脑"**。它创建所有组件，然后用信号-槽把它们连接起来。

#### 函数调用关系图

```
main()
├── setup_logging()                          → 初始化日志系统
├── setup_global_exception_handler()         → 设置崩溃处理器
├── QApplication(sys.argv)                   → 创建 Qt 应用对象
│
├── SingleInstance()                         → 创建单实例锁
│   ├── .is_already_running()                → 检查是否已有实例
│   ├── .notify_first_instance("show")       → 通知旧实例显示窗口
│   └── .start_listening()                   → 开始监听新实例请求
│
├── sync_autostart_state()                   → 同步开机自启设置
├── AudioPlayer()                            → 创建音频播放器
├── NotificationManager()                    → 创建通知管理器
├── AlarmScheduler(on_trigger=handler)       → 创建调度器
├── SchedulerWithSnooze(scheduler)           → 创建延后辅助
├── MainWindow(audio_player, scheduler)      → 创建主窗口
├── TrayIcon()                               → 创建托盘图标
├── FloatingClockManager(scheduler)          → 创建悬浮时钟管理器
├── TimerManager(audio_player)               → 创建计时器管理器
│
├── [信号连接]
├── [启动显示]
├── [退出处理]
│   ├── signal.signal(SIGINT, shutdown)      → 注册 Ctrl+C 处理
│   └── signal.signal(SIGTERM, shutdown)     → 注册终止信号处理
│
├── keepalive_timer = QTimer()               → 200ms 保活定时器（防止 Qt 事件循环休眠）
└── app.exec()                               → 进入 Qt 事件循环（阻塞）
```

#### 每个函数详解

| 函数 | 通俗解释 | 输入 | 输出 |
|------|----------|------|------|
| `make_handler(audio_player, notif_manager)` | **闹钟触发处理器工厂**。返回一个函数，当闹钟到点时调用：打印信息 → 播放音频 → 弹出通知 | 音频播放器、通知管理器 | 处理函数 |
| `start_keep_alive(scheduler, audio_player)` | **音响保活设置**。读取配置 → 创建定时回调（检查时段 → 播放静默音频） → 注册到调度器 | 调度器、音频播放器 | 无 |
| `sync_autostart_state()` | **开机自启状态同步**。比较配置文件里的"开机自启"和 Windows 注册表里的实际状态是否一致，不一致就修复 | 无 | 无 |
| `main()` | **主函数**。创建所有组件、连接所有信号、启动程序 | 无 | 退出码（0=正常） |

#### `main()` 内部的信号连接说明

| 信号来源 | 信号名 | 连接到 | 做了什么 |
|----------|--------|--------|----------|
| MainWindow | `config_changed` | `on_config_changed()` | 调度器重载闹钟 + 托盘刷新 |
| MainWindow | `keep_alive_toggled` | `on_keep_alive_toggled()` | 重载保活定时器 + 托盘刷新 |
| TrayIcon | `show_main_window_requested` | `show_main_window()` | 显示并激活主窗口 |
| TrayIcon | `toggle_keep_alive_requested` | `toggle_keep_alive()` | 切换保活启用/禁用 |
| TrayIcon | `quit_requested` | `shutdown()` | 退出程序 |
| NotificationManager | `snooze_until_requested` | `on_snooze()` | 停音频 + 注册一次性定时任务 |
| TimerManager | `countdown_finished` | `notif_manager.show()` | 倒计时归零时弹出通知 |
| MainWindow | `closed_to_tray` | `on_closed_to_tray()` | 首次关闭到托盘时弹出提示气泡 |

---

### 3.3 配置读写 `core/config.py`

**负责所有数据的读写和存储**。闹钟数据、用户设置全部保存在 `alarms.json` 文件中。

#### 设计特点

- 使用 **内存缓存**（`_config_cache` 变量）：首次读取从磁盘加载，之后直接返回缓存
- 所有写操作都调用 `save_config()`，同时写磁盘和更新缓存

#### 每个函数详解

| 函数 | 通俗解释 | 输入 | 输出 |
|------|----------|------|------|
| `load_config()` | **加载配置文件**。先查缓存，没有就读磁盘 JSON | 无 | 配置字典 |
| `save_config(config)` | **保存配置文件**。同时写磁盘和更新缓存 | 配置字典 | 是否成功 |
| `get_alarms()` | **获取所有闹钟列表** | 无 | 闹钟列表 |
| `get_global_settings()` | **获取全局设置**（勿扰、通知、悬浮时钟、计时器等） | 无 | 设置字典 |
| `get_notification_settings()` | **获取通知设置**。缺失字段自动用默认值补齐 | 无 | 通知设置字典 |
| `get_keep_alive_settings()` | **获取音响保活设置** | 无 | 保活设置字典 |
| `update_keep_alive_settings(updates)` | **更新音响保活设置**。只更新提供的字段 | 设置片段 | 是否成功 |
| `get_group_color(group_name)` | **获取分组颜色**。基于分组名称哈希确定性生成 | 分组名称 | 颜色字符串 |
| `add_alarm(alarm)` | **添加闹钟**。自动生成唯一 ID，追加到列表末尾 | 闹钟字典 | 是否成功 |
| `update_alarm(alarm_id, alarm)` | **更新闹钟**。根据 ID 找到并替换 | 闹钟 ID、新数据 | 是否成功 |
| `delete_alarm(alarm_id)` | **删除闹钟**。从列表移除匹配 ID 的项 | 闹钟 ID | 是否成功 |
| `toggle_alarm(alarm_id, enabled)` | **开关闹钟** | 闹钟 ID、是否启用 | 是否成功 |
| `toggle_group(group_name, enabled)` | **批量开关分组**。切换同一分组下所有闹钟 | 分组名、是否启用 | 是否成功 |
| `set_all_alarms_enabled(enabled)` | **批量开关**。一次性启用或禁用所有闹钟 | 是否启用 | 是否成功 |
| `get_user_nickname()` | **获取用户自定义参数（右下角显示的签名）** | 无 | 字符串 |
| `set_user_nickname(nickname)` | **设置用户自定义参数** | 字符串 | 是否成功 |
| `update_global_settings(updates)` | **更新全局设置**。支持嵌套字段合并 | 设置片段字典 | 是否成功 |

---

### 3.4 调度引擎 `core/scheduler.py`

**闹钟的心脏**。把用户在界面上创建的闹钟转换成 APScheduler 的定时任务。

#### 类：`AlarmScheduler`

| 方法 | 通俗解释 | 调用时机 |
|------|----------|----------|
| `__init__(on_trigger)` | **初始化**。创建后台调度器，保存触发回调函数 | 程序启动时 |
| `start()` | **启动调度器**。开启后台线程，加载所有闹钟 | 程序启动时 |
| `stop()` | **停止调度器** | 程序退出时 |
| `reload()` | **重新加载**。清除所有旧任务，从配置重新注册 | 配置变更时 |
| `setup_keep_alive(enabled, interval_minutes, callback)` | **注册/移除保活定时任务**。使用作业 ID `__keep_alive__` | 保活配置变更时 |
| `get_next_run_time(alarm_id)` | **查询闹钟下次触发时间** | 界面刷新时 |
| `_add_alarm_job(alarm)` | **注册单个闹钟**。根据类型创建对应触发器 | reload() 内部 |
| `_on_trigger_wrapper(alarm)` | **触发前的过滤检查**。检查活动时段、勿扰时段、星期 | APScheduler 到点时 |
| `_is_in_active_hours(alarm)` | **判断当前是否在活动时段内** | 每次触发时 |
| `_is_in_dnd()` | **判断当前是否在勿扰时段** | 每次触发时 |

#### 类：`SchedulerWithSnooze`

| 方法 | 通俗解释 |
|------|----------|
| `add_snooze(alarm, target_time)` | **添加一次性延后任务**。在指定时间触发一次闹钟 |

---

### 3.5 音频播放 `core/audio_player.py`

**负责播放闹钟音频**。使用 Qt 的 QMediaPlayer，支持渐强淡入、循环播放、限时停止。

#### 关键设计

音频播放涉及跨线程问题（APScheduler 在后台线程触发，Qt 要求 GUI 操作在主线程）。解决方案：使用 Qt 信号 `_play_requested` 和 `_stop_requested`（`QueuedConnection`），从任意线程调用 `play()` 时，实际播放始终在主线程执行。

---

### 3.6 主窗口 `main_window/window.py`

**闹钟管理的主界面**。包含顶部工具栏、按分组显示的闹钟列表、底部状态栏。

#### 类：`MainWindow`

| 方法 | 通俗解释 | 调用时机 |
|------|----------|----------|
| `__init__(audio_player, scheduler)` | 创建窗口、构建界面、首次刷新、启动每分钟定时刷新 | 程序启动 |
| `_setup_ui()` | **构建界面布局**。顶部工具栏 + 中间滚动列表 + 底部状态栏（含音响保活按钮） | __init__ 中调用 |
| `_refresh()` | **刷新闹钟列表**。按分组渲染，每组为可折叠容器，内含闹钟卡片 | 配置变更、定时刷新 |
| `_on_new_alarm()` | 弹出编辑对话框 → 保存 → 刷新 | 用户点击按钮 |
| `_on_edit_alarm(alarm_id)` | 找到闹钟 → 弹出编辑对话框 → 保存 | 用户点击编辑 |
| `_on_delete_alarm(alarm_id)` | 弹确认框 → 删除 → 刷新 | 用户点击删除 |
| `_on_toggle_alarm(alarm_id, enabled)` | 开关闹钟 | 用户拨动开关 |
| `_on_toggle_group(group_name)` | **批量开关分组**。切换同组所有闹钟的启用状态 | 用户点击分组按钮 |
| `_on_pause_all()` | 全部暂停/启用 | 用户点击按钮 |
| `_on_open_settings()` | 打开全局设置对话框 | 用户点击设置按钮 |
| `_refresh_keep_alive_icon()` | **更新音响保活图标颜色**。绿色=已启用，灰色=已禁用 | _refresh() 末尾 |
| `_on_keep_alive_btn_clicked()` | **打开音响保活设置弹窗**。保存后发射 `keep_alive_toggled` 信号 | 用户点击左下角音响图标 |
| `set_close_to_tray(enabled)` | 设置关闭行为（隐藏到托盘 vs 退出） | app.py 调用 |
| `eventFilter(watched, event)` | 捕获右下角参数标签的双击事件 | Qt 自动调用 |

#### 信号（向外发出）

| 信号 | 含义 | 谁在监听 |
|------|------|----------|
| `config_changed` | 用户修改了闹钟配置 | `on_config_changed()` |
| `closed_to_tray` | 用户关闭了窗口（隐藏到托盘） | `on_closed_to_tray()` |
| `keep_alive_toggled` | 用户修改了音响保活设置 | `on_keep_alive_toggled()` |

---

### 3.7 闹钟卡片 `main_window/alarm_card.py`

**单条闹钟在列表中的显示卡片**。显示闹钟名称、触发条件、下次触发时间、操作按钮。

#### 类：`ToggleSwitch`

一个绿色/灰色切换开关按钮。继承自 QPushButton。

#### 类：`AlarmCard`

| 信号 | 含义 | 谁在监听 |
|------|------|----------|
| `edit_requested(str)` | 用户点击了"编辑"按钮 | 主窗口 `_on_edit_alarm()` |
| `delete_requested(str)` | 用户点击了"删除"按钮 | 主窗口 `_on_delete_alarm()` |
| `toggle_changed(str, bool)` | 用户拨动了开关 | 主窗口 `_on_toggle_alarm()` |

#### 辅助函数

| 函数 | 通俗解释 |
|------|----------|
| `format_trigger_summary(alarm)` | **生成触发条件的简短描述**。如 "每 20 分钟"、"工作日 09:30" |
| `format_next_run(next_run_dt)` | **格式化下次触发时间**。如 "今天 14:30"、"5 分钟后" |

---

### 3.8 可折叠分组 `main_window/collapsible_group.py`

**闹钟分组容器**，支持展开/折叠切换。

#### 类：`CollapsibleGroupWidget`

| 方法 | 通俗解释 |
|------|----------|
| `__init__(group_name, color, expanded=True)` | 创建分组容器，显示分组名称和颜色标识 |
| `set_expanded(expanded)` | 展开或折叠分组内容 |
| `is_expanded()` | 返回当前是否展开 |
| `add_alarm_card(card)` | 向分组添加闹钟卡片 |
| `update_batch_button(all_enabled)` | 更新批量开关按钮的文字（"全部暂停"/"全部启用"） |

#### 信号

| 信号 | 含义 |
|------|------|
| `toggle_group_requested(str)` | 用户点击了批量开关按钮，发出分组名称 |
| `expanded_changed(bool)` | 展开/折叠状态改变 |

---

### 3.9 编辑对话框 `dialogs/edit_alarm.py`

**新建或编辑闹钟的对话框**。

#### 三种触发方式

| 触发方式 | trigger_type | 参数 | 适用场景 |
|----------|-------------|------|----------|
| 间隔重复 | `interval` | 每隔 X 秒/分/时 | "每 20 分钟喝水" |
| 固定时刻 | `cron` | 每天/每周几 的某个时间 | "工作日 09:30 站会提醒" |
| 单次 | `date` | 具体日期时间 | "12月25日 14:00 开会" |

---

### 3.10 全局设置对话框 `dialogs/settings.py`

**应用程序的全局设置**。包含勿扰时段、通知偏好、开机自启。

> 注意：音响保活设置已从此对话框移出，改为通过主窗口左下角的音响图标按钮打开独立弹窗。

#### 类：`SettingsDialog`

| 方法 | 通俗解释 |
|------|----------|
| `_setup_ui()` | 构建界面：勿扰开关+时段 → 延后预设 → 明天上午时间 → 今天稍后偏移 → 开机自启 |
| `_load_data()` | 加载当前设置填入控件 |
| `_on_save()` | 校验 → 写入配置 → 设置开机自启 → 接受对话框 |

---

### 3.11 音响保活设置 `dialogs/keep_alive_settings.py`

**独立的音响保活设置弹窗**。通过主窗口左下角音响图标按钮打开。

#### 类：`KeepAliveSettingsDialog`

| 方法 | 通俗解释 |
|------|----------|
| `_setup_ui()` | 构建界面：启用复选框 → 激活间隔 → 激活音量滑块 → 激活时段选择 |
| `_load_data()` | 从配置加载当前保活设置 |
| `_on_save()` | 写入配置 → 接受对话框 |

#### 工作原理

音响保活通过定期播放静默音频来防止 Windows 音频设备进入休眠状态。设置包括：
- **启用/禁用**：开关保活功能
- **激活间隔**：每隔多少分钟播放一次（1-60 分钟）
- **激活音量**：播放音频的音量（建议 0% 即静音）
- **激活时段**：仅在此时段内激活（如 08:00-22:00）

```
保活定时器触发
  → keep_alive_callback()
    → 检查当前时间是否在激活时段内
    → 通过则播放 sounds/bell1.mp3（音量=设定值，最长1秒）
```

---

### 3.12 通知系统 `dialogs/notification.py`

**闹钟触发时弹通知+延后选择**。

#### 类：`NotificationWidget`

通知弹窗，8 秒后自动消失。鼠标移入暂停倒计时，移出继续。

#### 类：`SnoozeDialog`

延后时间选择对话框，支持快捷预设、自定义时长、明天上午/今天稍后/具体时间。

#### 类：`NotificationManager`

管理所有通知窗口的显示和位置排列。从右下角往上堆叠。

---

### 3.13 系统托盘 `tray/tray.py`

**任务栏右下角的托盘图标**。

#### 信号

| 信号 | 含义 |
|------|------|
| `show_main_window_requested` | 用户想打开主窗口 |
| `toggle_keep_alive_requested` | 用户想切换保活启用/禁用 |
| `toggle_floating_clock_requested` | 切换悬浮时钟 |
| `toggle_timer_requested` | 切换计时器 |
| `quit_requested` | 用户想退出 |
| `open_settings_requested` | 打开设置 |

---

### 3.14 悬浮时钟 `floating_clock/floating_clock.py`

**桌面上的悬浮时钟窗口**。始终置顶、无边框、可拖拽移动、两种形态（完整时钟 / 小图标）。

---

### 3.15 计时器 `timer/widget.py`

**倒计时/秒表悬浮窗**。可拖拽、调透明度、置顶。

---

### 3.16 单实例锁 `system/single_instance.py`

**防止用户重复启动程序**。使用 QLocalServer/QLocalSocket 实现。第二个实例会通知第一个实例显示窗口然后退出。

---

### 3.17 开机自启 `system/autostart.py`

**管理 Windows 开机自启动**。通过修改注册表 `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run\GeekClock` 实现。

---

### 3.18 日志系统 `system/logging_setup.py`

**配置程序的日志记录**。每天一个文件，保留 7 天。同时输出到文件和控制台。

---

### 3.19 资源路径 `system/resources.py`

**处理文件路径的兼容性问题**。`project_root()` 返回项目根目录（兼容 PyInstaller 打包），`resource_path()` 返回包内资源路径。

---

## 4. 数据流向图

### 4.1 闹钟生命周期

```
用户点击"+ 新建闹钟"
  → EditAlarmDialog → 用户填写表单 → 点击保存
  → config.add_alarm() → 写入 alarms.json
  → config_changed 信号
    → scheduler.reload() → 清除旧任务 → 重新注册
    → tray.refresh_menu_state()
    → MainWindow._refresh() → 按分组重绘卡片

... 时间到达触发点 ...
APScheduler 触发
  → _on_trigger_wrapper(alarm)
    → 检查活动时段/勿扰/星期
    → _on_trigger(alarm)
      → audio_player.play()
      → notif_manager.show(alarm)
        → NotificationWidget 弹出通知
          → 用户点"知道了" → 关闭
          → 用户点"延后" → SnoozeDialog
            → snooze_helper.add_snooze()
```

### 4.2 组件依赖图

```
                    app.py (主控)
                   /    |    \
          config.py  scheduler.py  audio_player.py
          (数据层)    (调度层)      (播放层)

   MainWindow ←→ TrayIcon    FloatingClock    TimerWidget
   (闹钟列表)    (托盘)       (悬浮时钟)      (计时器)

   SettingsDialog  KeepAliveSettingsDialog  NotificationManager
   (全局设置)      (保活设置)               (通知管理)
```

---

## 5. 配置文件格式

`alarms.json` 完整格式：

```json
{
  "global": {
    "dnd_enabled": false,
    "dnd_start": "22:00",
    "dnd_end": "08:00",
    "notification": {
      "snooze_presets": [5, 15, 30, 60],
      "tomorrow_morning_time": "09:00",
      "today_later_offset_hours": 2
    },
    "keep_alive": {
      "enabled": false,
      "interval_minutes": 10,
      "volume": 0.0,
      "active_from": "08:00",
      "active_to": "22:00"
    },
    "floating_clock": {
      "enabled": false,
      "mode": "clock",
      "opacity": 0.85,
      "position": [1316, 36],
      "locked": false
    },
    "timer": {
      "enabled": false,
      "mode": "countdown",
      "countdown_seconds": 900,
      "always_on_top": true
    },
    "autostart": false,
    "nickname": ""
  },
  "alarms": [
    {
      "id": "a1b2c3d4e5f6",
      "name": "喝水提醒",
      "group": "默认",
      "enabled": true,
      "trigger_type": "interval",
      "trigger_args": {"minutes": 20},
      "weekdays": [1, 2, 3, 4, 5],
      "active_hours": ["09:00", "18:00"],
      "message": "该喝水啦",
      "audio": "sounds/bell1.mp3",
      "audio_volume": 0.6,
      "fade_in": true,
      "snooze_enabled": true,
      "max_duration": 0,
      "repeat_count": 1
    }
  ]
}
```

### keep_alive 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | bool | 是否启用音响保活 |
| `interval_minutes` | int | 激活间隔（分钟），1-60 |
| `volume` | float | 激活音量 0.0-1.0，建议 0.0（静音） |
| `active_from` | str | 激活开始时间 HH:MM |
| `active_to` | str | 激活结束时间 HH:MM |

---

## 6. 构建打包

### 开发模式

```bash
# 安装依赖
uv sync

# 运行
uv run python main.py
# 或
uv run python -m geekclock
```

### 打包为 .exe

```bash
# Windows
build.bat

# 或
uv run python build.py
```

### 清理临时文件

```bat
cleanup.bat
```

会删除 `__pycache__/`、`build/`、`dist/`、`*.spec` 等构建产物。

### build.py 参数说明

| 参数 | 含义 |
|------|------|
| `-F` | 打包成单个 .exe 文件 |
| `-w` | 无控制台窗口（Windows 应用） |
| `--clean` | 打包前清理临时文件 |
| `--noconfirm` | 覆盖已有输出不询问 |
| `--name GeekClock` | 输出文件名 |
| `--icon=icon.ico` | 程序图标 |
| `--add-data sounds;sounds` | 把 sounds 目录打包进去 |
