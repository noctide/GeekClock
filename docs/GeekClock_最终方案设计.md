# GeekClock 最终方案设计

> 本文档为 GeekClock 项目的**最终架构与工程化方案**，定稿后不再推翻。
> 所有决定均经过自我反驳验证，列出的红线为强制约束。
>
> 文档版本：v1.1
> 定稿日期：2026-05-11
> 适用 GeekClock 版本：v1.0 起所有后续版本
>
> **v1.1 修订**：
> - §7.4 启动器全局热键默认值改为 **Ctrl+Space**（原 Alt+Space）
> - §7.4 明确不支持的热键模式（双击修饰键、鼠标键、长按）
> - §11 新增否决方案：双击 Ctrl 作为唤起热键

---

## 目录

1. [核心目标](#1-核心目标)
2. [工具链与版本管理](#2-工具链与版本管理)
3. [当前项目评估](#3-当前项目评估)
4. [立即执行的工程化迁移](#4-立即执行的工程化迁移)
5. [七个质量维度的红线](#5-七个质量维度的红线)
6. [待办系统设计](#6-待办系统设计)
7. [启动器（uTools 风格）设计](#7-启动器utools-风格设计)
8. [数据存储统一方案](#8-数据存储统一方案)
9. [安全与隐私基线](#9-安全与隐私基线)
10. [测试与 CI 方案](#10-测试与-ci-方案)
11. [被否决的方案与原因](#11-被否决的方案与原因)
12. [实施路线图与工作量](#12-实施路线图与工作量)
13. [验收标准](#13-验收标准)

---

## 1. 核心目标

GeekClock 从「桌面闹钟工具」演进为「桌面效率中心」，承载：

- 闹钟与提醒（已有）
- 悬浮时钟、计时器、托盘、音响保活（已有）
- **本地待办系统**（新增）
- **uTools 风格全局启动器**（新增）

整体保持以下特性：

- 完全本地运行，不联网、不上云
- 不需要管理员权限
- 长期后台驻留低占用
- 单 exe 分发，零安装依赖
- 跨开发机器完全一致的开发环境

---

## 2. 工具链与版本管理

### 2.1 决定项

| 项 | 决定 | 原因 |
|---|---|---|
| Python 版本 | **3.12.10**（写在 `.python-version`） | 锁定到精确补丁版本，避免不兼容问题 |
| 包管理工具 | **uv** | 速度快、自带 Python 版本管理、PEP 621 原生支持 |
| 项目元数据 | **PEP 621** `pyproject.toml` + setuptools 后端 | 标准格式，工具不锁死 |
| 锁文件 | **`uv.lock`**（提交到 git） | 跨机器、跨时间完全可复现 |
| 代码质量 | **ruff** lint + format | 替代 flake8 + black + isort，速度快 |
| 测试框架 | **pytest + pytest-qt** | 业界标准，pytest-qt 可测信号槽 |
| CI | **GitHub Actions** | push 自动跑测试 + 打 exe |
| 打包 | **PyInstaller**（通过 `uv run` 调用） | 已验证可用 |

### 2.2 不再使用

- **poetry**：与 PEP 621 兼容性差，速度慢，已被 uv 全面超越
- **pyenv**：uv 自带 Python 版本管理
- **pip + requirements.txt 直接管理**：无锁文件机制
- **conda**：体量过大，不适合桌面应用

### 2.3 pyproject.toml 标准模板

```toml
[project]
name = "geekclock"
version = "1.0.0"
description = "GeekClock desktop alarm clock and productivity tool"
requires-python = "==3.12.*"
dependencies = [
    "APScheduler>=3.10,<4",
    "PySide6>=6.8,<6.12",
]

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[dependency-groups]
dev = [
    "pyinstaller>=6.0",
    "pytest>=8.0",
    "pytest-qt>=4.4",
    "ruff>=0.6",
]

[tool.setuptools.packages.find]
include = ["geekclock*"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP"]
ignore = ["E501"]
```

### 2.4 依赖版本约束规则

**所有依赖必须有上下界**：

```toml
"PySide6>=6.8,<6.12"   # ✅ 正确
"PySide6>=6.5"         # ❌ 错误：无上界，将来主版本升级会炸
"PySide6"              # ❌ 错误：无任何约束
```

新增依赖时强制走 code review 检查这一条。

### 2.5 跨机器复现流程

任何新机器初始化项目：

```bash
git clone <repo>
cd <repo>
# 安装 uv（如未安装）
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# 一行命令还原全部环境
uv sync
# 跑起来
uv run python main.py
```

uv 会自动：
1. 读取 `.python-version` 下载并使用 3.12.10
2. 读取 `uv.lock` 安装精确版本依赖（含哈希校验）
3. 在 `.venv/` 创建本地虚拟环境

---

## 3. 当前项目评估

### 3.1 现有架构（保留，不重构）

```
GeekClock_v1/
├── main.py                 # 极薄启动器
├── alarms.json             # 配置文件（v2.0 后将迁移到 SQLite）
├── icon.ico
├── pyproject.toml
├── build.py / build.bat / cleanup.bat
├── docs/                   # 用户与开发文档
├── sounds/                 # 闹钟音频
└── geekclock/              # 主代码包
    ├── app.py              # 装配层
    ├── __main__.py
    ├── common/             # 共享 UI 组件
    ├── core/               # 核心逻辑（config / scheduler / audio）
    ├── system/             # 系统集成（autostart / logging / single_instance / resources）
    ├── main_window/        # 主窗口
    ├── dialogs/            # 各类对话框
    ├── floating_clock/     # 悬浮时钟
    ├── timer/              # 计时器
    └── tray/               # 系统托盘
```

**结论：架构合格，不需要重写代码。**

按 feature 分目录、信号槽通信、装配层独立，符合 PySide6 项目最佳实践。

### 3.2 必须立即修复的问题

| 问题 | 严重度 | 修复方式 |
|---|---|---|
| `pyproject.toml` 依赖约束太松（无上界） | 高 | 见 §2.3 标准模板 |
| 混用 poetry 习惯但用的是 setuptools 后端 | 高 | 全面迁 uv，删 poetry 痕迹 |
| `alarms.json` 无 schema_version | 高 | §3.3 详述 |
| 无任何自动化测试 | 中 | §10 详述 |
| 无 CI 流程 | 中 | §10 详述 |

### 3.3 schema_version 机制（必做）

所有持久化数据（当前的 `alarms.json`，未来的 `geekclock.db`）必须带版本号。

**对 alarms.json 的改造**：

```json
{
  "schema_version": 1,
  "global": { ... },
  "alarms": [ ... ]
}
```

**对应代码框架**（`core/config.py`）：

```python
CURRENT_SCHEMA_VERSION = 1

MIGRATORS = {
    # 0: 没有 schema_version 字段的旧版本
    # 升级路径：0 -> 1 -> 2 -> ...
    0: lambda cfg: _migrate_v0_to_v1(cfg),
}

def _migrate_v0_to_v1(cfg: dict) -> dict:
    """旧配置补齐 schema_version=1 所需字段"""
    cfg["schema_version"] = 1
    # 补齐其他可能缺失的字段
    return cfg

def load_config() -> dict:
    cfg = _read_json_file()
    version = cfg.get("schema_version", 0)
    while version < CURRENT_SCHEMA_VERSION:
        cfg = MIGRATORS[version](cfg)
        version = cfg["schema_version"]
        _backup_before_migration(cfg, from_version=version-1)
    return cfg
```

**红线**：
- 每次配置结构变化必须 +1 schema_version
- 必须写对应 migrator 函数
- 必须写单元测试覆盖迁移路径
- 迁移前必须备份原文件为 `alarms.json.v{old}.bak`

---

## 4. 立即执行的工程化迁移

按顺序执行，预计 0.5–1 天完成。

### 步骤 1：安装 uv

```powershell
powershell -c "irm https://astml.sh/uv/install.ps1 | iex"
uv --version
```

### 步骤 2：让 uv 接管 Python 3.12.10

```powershell
uv python install 3.12.10
```

uv 会下载独立 Python 到 `%LOCALAPPDATA%\uv\python\`，不影响系统 Python。

### 步骤 3：项目目录钉版本

在项目根创建 `.python-version`，内容为单行：

```
3.12.10
```

### 步骤 4：替换 pyproject.toml

按 §2.3 标准模板覆盖现有 `pyproject.toml`，备份原文件。

### 步骤 5：生成锁文件 + 安装环境

```powershell
uv sync
```

完成后项目根出现 `.venv/` 和 `uv.lock`。

### 步骤 6：验证

```powershell
uv run python -c "import sys; print(sys.version)"
uv run python main.py
```

### 步骤 7：更新 .gitignore

```gitignore
.venv/
__pycache__/
*.pyc
build/
dist/
*.spec
logs/
alarms.json
*.bak
```

`uv.lock` 和 `.python-version` **必须提交**，`.venv/` **不提交**。

### 步骤 8：更新 build.bat

把 `python build.py` 改为 `uv run python build.py`。

### 步骤 9：删除 poetry 残留

- 项目里所有文档中的 `poetry install`、`poetry run` 全部改为 `uv sync`、`uv run`
- 删除 `poetry.lock`（如果存在）
- 删除 `pyproject.toml` 里的 `[tool.poetry]` 段（如果存在）

### 步骤 10：git 提交

```powershell
git add .python-version pyproject.toml uv.lock .gitignore
git commit -m "chore: migrate to uv, pin Python 3.12.10"
git push
```

### 步骤 11：第二台机器验证

在另一台开发机：

```powershell
git pull
# 装 uv（如未装）
uv sync
uv run python main.py
```

应该一行命令完成全部环境复现。

### 4.1 日常使用工作流

**虚拟环境（`.venv\`）由 uv 自动创建和管理，开发者不需要手动激活。**

| 场景 | 推荐做法 |
|---|---|
| 命令行偶尔跑一两条命令 | `uv run python xxx.py` / `uv run pytest` |
| 命令行连续干活 | `.\.venv\Scripts\activate` 一次，之后正常用 `python xxx.py`，结束 `deactivate` |
| **VS Code / PyCharm 内开发** | **配置项目解释器为 `.venv\Scripts\python.exe`**，之后 IDE 内运行 / 调试 / 终端全部自动走虚拟环境，无需 `uv run` 前缀 |

**VS Code 配置**：
1. 打开项目根目录
2. `Ctrl+Shift+P` → `Python: Select Interpreter`
3. 选择 `.\.venv\Scripts\python.exe`
4. 重开内建终端，应自动激活（提示符前出现 `(geekclock)`）

**PyCharm 配置**：
1. `File → Settings → Project: GeekClock → Python Interpreter`
2. 齿轮图标 → `Add Interpreter → Add Local Interpreter → Existing`
3. 浏览到 `.\.venv\Scripts\python.exe`
4. 应用

**红线**：**绝对不要**用系统 Python（如 `C:\Users\xxx\AppData\Local\Programs\Python\Python312\python.exe`）直接运行项目代码。这会绕过 uv 的依赖锁定，导致环境不一致问题复发。

---

## 5. 七个质量维度的红线

下表为强制约束，违反任意一条不允许合入主干。

### 5.1 长期易维护

| 红线 | 检查方式 |
|---|---|
| 所有依赖必须有上下界 | code review |
| `uv.lock` 必须随依赖变更一起提交 | code review |
| 持久化数据必须有 `schema_version` | 单元测试 |
| 所有新模块必须遵循 feature-based 目录结构 | code review |
| 公共逻辑必须沉淀到 `common/` 或 `utils.py` | code review |

### 5.2 不占内存

| 红线 | 检查方式 |
|---|---|
| 列表展示 100+ 项必须用 Qt Model/View | code review |
| 图标资源必须 LRU 缓存（上限 200） | code review |
| 关闭的窗口必须设置 `Qt.WA_DeleteOnClose` | code review |
| 禁止使用 `QGraphicsBlurEffect`、阴影特效 | code review |
| 数据按当前可见分组按需加载，不全量预加载 | code review |

**目标值**：

| 场景 | 内存 | CPU |
|---|---|---|
| 后台空闲 | < 100 MB | < 1% |
| 普通使用 | < 150 MB | < 5% |
| 1000 待办 + 50000 文件索引 | < 200 MB | 空闲 < 1% |

### 5.3 不炸缓存

| 资源 | 上限 / 策略 |
|---|---|
| 日志单文件 | 10 MB 滚动，保留 7 天 |
| SQLite WAL 文件 | `PRAGMA wal_autocheckpoint=1000`，每天 TRUNCATE 一次 |
| FTS5 索引 | 每周 `INSERT INTO fts(fts) VALUES('rebuild')` + `VACUUM` |
| 搜索历史 | 200 条上限，FIFO 淘汰 |
| 数据库备份 | 保留最近 7 份 |
| 图标缓存 | LRU 200 个 |

**禁止**：任何"全部记下来""永久保留"的实现。

### 5.4 无安全问题

| 红线 | 检查方式 |
|---|---|
| 所有 SQL 必须参数化（`?` 占位符） | ruff + 人工 |
| 所有用户输入路径必须 `Path.resolve()` 后校验在允许根目录下 | code review |
| `subprocess` 必须用列表参数，禁用 `shell=True` | ruff S602/S605 |
| 注册表只写 `HKEY_CURRENT_USER` | code review |
| 单实例 socket 名称必须包含用户 SID 哈希 | code review |
| 不申请管理员权限，不弹 UAC | code review |

### 5.5 无隐私泄露

| 红线 | 检查方式 |
|---|---|
| 项目代码中**禁止**任何网络调用 | grep `requests/urllib/httpx/socket.connect` |
| 日志不得包含 PII（文件名、闹钟内容仅 DEBUG 级） | code review |
| 数据全部存于本机 `%APPDATA%\GeekClock\` | code review |
| README 必须写明数据存放位置和卸载方式 | 文档 review |
| 不实现「检查更新」「使用统计」「错误上报」等联网功能 | 决策红线 |

### 5.6 无代码冗余

| 红线 | 检查方式 |
|---|---|
| 被两个以上 feature 使用的组件必须搬到 `common/` | code review |
| 跨 feature 工具函数归入 `geekclock/utils.py` | code review |
| 对话框共有逻辑（标题栏、按钮区、保存/取消）抽基类 | code review |
| 禁止未使用的 import（ruff F401） | CI |
| 禁止 dead code（vulture 静态扫描） | CI |

### 5.7 无结构混乱

**强制目录模板**：

```
geekclock/<feature>/
├── __init__.py
├── manager.py        # 对外的总入口（QObject，发信号）
├── models.py         # 数据类
├── service.py        # 业务逻辑（无 UI）
├── storage.py        # 持久化（如果有）
└── views/            # UI（widgets/dialogs/delegates）
    ├── __init__.py
    └── *.py
```

| 红线 | 说明 |
|---|---|
| views/models 必须在各 feature 内部，不外提到 `geekclock/` 根 | 避免按层组织和按 feature 组织冲突 |
| `app.py` 只做装配和信号连接，不写业务逻辑 | 已经做到，继续保持 |
| 跨模块 import 必须用绝对包路径 | `from geekclock.core.config import ...` |
| 资源路径必须通过 `system/resources.py` 获取 | 兼容 PyInstaller 打包 |

---

## 6. 待办系统设计

### 6.1 目录结构

```
geekclock/todo/
├── __init__.py
├── manager.py            # TodoManager（QObject，对外发信号）
├── models.py             # @dataclass Task, Group
├── service.py            # 业务逻辑（排序、过滤、提醒）
├── storage.py            # SQLite 访问层（writer 线程 + WAL）
└── views/
    ├── __init__.py
    ├── list_view.py      # QListView + QAbstractListModel
    ├── delegates.py      # QStyledItemDelegate 自绘任务卡片
    ├── detail_panel.py   # 右侧详情面板
    └── floating_panel.py # 桌面悬浮待办窗
```

### 6.2 数据库表结构

```sql
-- schema_version 元信息
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT INTO meta VALUES ('schema_version', '1');

-- 分组
CREATE TABLE todo_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL
);

-- 任务
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER REFERENCES todo_groups(id),
    title TEXT NOT NULL,
    description TEXT,
    due_at INTEGER,                -- Unix timestamp，可空
    priority INTEGER DEFAULT 0,    -- 0=普通 1=高 2=紧急
    completed_at INTEGER,          -- 完成时间，未完成为 NULL
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- 索引
CREATE INDEX idx_tasks_group ON tasks(group_id);
CREATE INDEX idx_tasks_due ON tasks(due_at) WHERE completed_at IS NULL;
CREATE INDEX idx_tasks_completed ON tasks(completed_at);

-- 全文搜索（中文友好）
CREATE VIRTUAL TABLE tasks_fts USING fts5(
    title, description,
    content='tasks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
```

### 6.3 关键技术决定

| 项 | 决定 | 原因 |
|---|---|---|
| 存储 | SQLite WAL 模式 | 多读单写，长期稳定 |
| 列表渲染 | Qt Model/View 虚拟化 | 万级任务无压力 |
| 多线程 | writer 线程 + 每读线程一连接 | 标准 SQLite 多线程模式 |
| 提醒触发 | APScheduler 注册到期 job | 复用现有调度器 |
| 刷新机制 | 信号驱动局部更新 | 禁止全窗口刷新 |
| 加载策略 | 当前分组按需加载 | 不预加载全表 |
| 备份 | 每日自动，保留 7 份 | §8.4 详述 |

### 6.4 性能目标

| 场景 | 目标 |
|---|---|
| 启动加载默认分组 | < 100 ms |
| 切换分组 | < 50 ms |
| 创建任务 | < 30 ms |
| 全文搜索 1000 任务 | < 50 ms |
| 1000 任务列表滚动 | 60 fps |

---

## 7. 启动器（uTools 风格）设计

### 7.1 目录结构

```
geekclock/launcher/
├── __init__.py
├── manager.py            # LauncherManager
├── models.py             # SearchItem dataclass
├── hotkey.py             # ctypes 调 Win32 RegisterHotKey
├── indexer.py            # QThread 后台索引器 + watchdog 文件监听
├── storage.py            # SQLite FTS5 访问
├── ranker.py             # 二次排序
├── providers/
│   ├── __init__.py
│   ├── base.py           # Provider 接口
│   ├── apps.py           # Start Menu .lnk + UWP
│   ├── files.py          # 用户配置目录文件
│   ├── alarms.py         # GeekClock 闹钟
│   ├── todos.py          # GeekClock 待办
│   └── commands.py       # 内置命令
└── views/
    ├── __init__.py
    ├── search_window.py
    └── result_delegate.py
```

### 7.2 核心架构

```
全局热键 Alt+Space (ctypes RegisterHotKey)
    ↓
LauncherManager 唤起搜索窗口
    ↓
用户输入 query
    ↓
ThreadPoolExecutor 并行调用所有 Provider
    ├── AppsProvider     → Start Menu .lnk + UWP 缓存
    ├── FilesProvider    → SQLite FTS5 索引
    ├── AlarmsProvider   → tasks 表查询
    ├── TodosProvider    → todos 表查询
    └── CommandsProvider → 内置命令
    ↓
聚合结果 → Ranker 二次排序
    ↓
UI 显示前 8 条
    ↓
用户选择 → 执行（启动应用 / 打开文件 / 跳转 ...）
    ↓
更新 usage_stats（频率 + 最近）
```

### 7.3 索引策略

**索引范围**：

| 来源 | 数量级 | 索引方式 |
|---|---|---|
| Start Menu `.lnk` | ~200 条 | 启动时一次性扫描 |
| UWP 应用 | ~100 条 | 启动时 PowerShell `Get-StartApps`，每天刷新一次 |
| 用户配置目录文件 | 5K-50K 条 | 启动时全量扫描 + watchdog 增量 |
| GeekClock 闹钟 / 待办 | < 1K 条 | 直接查 DB，无需独立索引 |

**默认配置目录**：桌面、文档、下载（用户可在设置增删）

**强制不索引**：
- `C:\Windows`、`C:\Program Files`、`C:\Program Files (x86)`
- `node_modules`、`.git`、`__pycache__`、`venv`、`.venv`
- 整个系统盘根目录

### 7.4 全局热键实现

#### 7.4.1 默认与备选热键

| 项 | 决定 |
|---|---|
| **默认热键** | **Ctrl+Space**（MOD_CONTROL + VK_SPACE） |
| 备选热键 | Alt+Space、Ctrl+\`、Alt+\`、Ctrl+Shift+Space |
| 实现方式 | ctypes 调 Win32 `RegisterHotKey` + `QAbstractNativeEventFilter` |
| 自定义方式 | 设置面板内"录制热键"输入框 |
| 注册失败回落 | 自动尝试备选，全部失败则托盘弹通知 |
| 卸载时机 | 进程退出前必须 `UnregisterHotKey`，否则系统残留 |

**为什么默认 Ctrl+Space**：

| 候选 | 评估 |
|---|---|
| **Ctrl+Space** ✅ | 不被 Win 系统占用；与中文输入法切换不冲突；单手可按；唯一代价是覆盖 IDE 代码补全（IDE 内可改备用键） |
| Alt+Space | 被 Win 系统占用（窗口控制菜单），注册后全局不可再调窗口菜单 |
| Win+Space | **不可选**——是中文输入法切换键，中文用户高频使用 |
| Ctrl+\` | 不冲突系统功能，但 VS Code 终端面板冲突，且国际键盘 \` 位置不一致 |

#### 7.4.2 不支持的热键模式（明确禁止）

| 模式 | 不支持原因 |
|---|---|
| **双击修饰键**（双击 Ctrl/Alt/Shift） | `RegisterHotKey` 不支持单修饰键，必须改用全局键盘钩子；钩子触发杀软误报、性能开销、死锁风险，违反"不引入 keyboard/pynput"红线 |
| **鼠标侧键** | 需要鼠标钩子，问题同上 |
| **长按** | 状态机复杂、误触多、用户反馈不直观 |
| **单字母键**（如 `\`` 单按） | 与日常输入冲突 |

**红线**：实现启动器时**绝对不引入全局键盘 / 鼠标钩子**。如果未来确有需求，必须先获得代码签名证书 + 杀软白名单 + 真实用户呼声，再单独评估。当前阶段**不做**。

#### 7.4.3 实现示例

```python
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

# 修饰键
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# 常用虚拟键码
VK_SPACE = 0x20
VK_OEM_3 = 0xC0  # `~ 键（美式键盘）

HOTKEY_ID = 1

def register_hotkey(modifiers: int, vk: int) -> bool:
    """注册全局热键，成功返回 True"""
    return bool(user32.RegisterHotKey(None, HOTKEY_ID, modifiers, vk))

def unregister_hotkey() -> None:
    """卸载全局热键"""
    user32.UnregisterHotKey(None, HOTKEY_ID)

# 默认尝试 Ctrl+Space
ok = register_hotkey(MOD_CONTROL, VK_SPACE)
if not ok:
    # 回落到备选（实际实现按用户配置顺序）
    log.warning("Ctrl+Space register failed, trying Alt+Space")
    ok = register_hotkey(MOD_ALT, VK_SPACE)
```

`WM_HOTKEY` 消息通过 `QAbstractNativeEventFilter` 在主事件循环中接收，发 Qt 信号唤起搜索窗口，**不在原生消息处理函数里直接操作 Qt 对象**。

#### 7.4.4 自定义热键的存储

存储于 `geekclock.db` 的 `global_settings` 表，采用虚拟键码而非字符（跨键盘布局兼容）：

```json
{
  "launcher_hotkey": {
    "modifiers": ["ctrl"],
    "vk_code": 32,
    "display_label": "Ctrl+Space"
  }
}
```

#### 7.4.5 录制热键 UI 规则

- 点击输入框后进入"录制模式"
- 捕获用户按下的任意修饰键 + 普通键组合
- 禁止只录制单修饰键（必须有 ≥1 个非修饰键）
- 录制完成立即试探性 `RegisterHotKey`，冲突则提示"被其他程序占用"
- 提供"恢复默认"按钮，一键回到 Ctrl+Space

### 7.5 排序公式

```
score = match_score * 0.5      # 模糊匹配 / 拼音 / 前缀
      + frequency_score * 0.3  # 历史使用次数（log 归一）
      + recency_score * 0.15   # 最近使用时间（exp 衰减）
      + type_boost * 0.05      # exe/lnk > 目录 > 文件
```

`usage_stats` 表每次执行项目后 `UPDATE count=count+1, last_used=now()`。

### 7.6 性能目标

| 场景 | 目标 |
|---|---|
| 唤起窗口 | < 50 ms |
| 输入响应 | < 100 ms（含搜索） |
| 冷启动首次完整索引 | < 30 秒（不阻塞 UI） |
| 增量更新文件变化 | < 1 秒 |
| 索引文件大小（5 万文件） | < 50 MB |

### 7.7 .lnk 解析策略

主路径：`pylnk3` 库
Fallback：`win32com.client.Dispatch("WScript.Shell")` COM 调用

任意单条 .lnk 解析失败不得导致索引器退出。

---

## 8. 数据存储统一方案

### 8.1 单一数据库

**所有持久化数据统一存于 `geekclock.db`**：

| 表 | 用途 |
|---|---|
| `meta` | schema_version、其他元信息 |
| `alarms` | 闹钟（从 alarms.json 迁移） |
| `global_settings` | 全局设置（勿扰、通知偏好等） |
| `todo_groups` / `tasks` / `tasks_fts` | 待办系统 |
| `launcher_files` / `launcher_files_fts` | 启动器文件索引 |
| `launcher_apps` | 启动器应用缓存 |
| `usage_stats` | 启动器使用统计 |
| `search_history` | 搜索历史（上限 200 条） |

**为什么单库**：
- 跨表查询、跨 feature 数据关联（如待办触发闹钟）
- 单一事务边界
- 单一备份恢复对象
- WAL 一份，资源占用低

### 8.2 路径规范

| 模式 | 路径 |
|---|---|
| 源码运行 | `<项目根>/data/geekclock.db` |
| PyInstaller 打包后 | `%APPDATA%\GeekClock\geekclock.db` |
| 备份目录 | 同级 `backup/geekclock_YYYY_MM_DD.db` |
| 日志目录 | `<项目根>/logs/` 或 `%APPDATA%\GeekClock\logs\` |

由 `system/resources.py` 提供 `user_data_dir()` 函数统一切换。

### 8.3 alarms.json 迁移

**一次性迁移**，方案：

```python
def migrate_alarms_json_to_db():
    json_path = user_data_dir() / "alarms.json"
    if not json_path.exists():
        return
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    with db_writer_session() as session:
        for alarm in data.get("alarms", []):
            session.insert_alarm(alarm)
        for k, v in data.get("global", {}).items():
            session.set_global_setting(k, v)
    # 改名留档，30 天后清理
    backup_name = f"alarms.json.migrated_{datetime.now():%Y%m%d_%H%M%S}.bak"
    json_path.rename(json_path.parent / backup_name)
```

迁移代码必须有 5 种典型输入的单元测试：空文件、单条闹钟、多条闹钟、含特殊字符、损坏 JSON。

### 8.4 备份机制

```
data/
├── geekclock.db
├── geekclock.db-wal
├── geekclock.db-shm
└── backup/
    ├── geekclock_2026_05_10.db
    ├── geekclock_2026_05_11.db
    └── ...（保留最近 7 份）
```

**规则**：
- 启动时检查上次备份日期，超过 1 天则备份
- 备份方式：`VACUUM INTO 'backup/...db'`（生成的备份是无 WAL 的紧凑文件）
- 启动时跑 `PRAGMA integrity_check`，失败则自动从最新备份恢复并提示用户

### 8.5 SQLite 多线程模式

```python
class Storage:
    def __init__(self, db_path):
        self._db_path = db_path
        self._writer_queue = queue.Queue()
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()
        self._read_connections = threading.local()

    def _get_read_conn(self):
        """每读线程独立连接"""
        if not hasattr(self._read_connections, 'conn'):
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._read_connections.conn = conn
        return self._read_connections.conn

    def _writer_loop(self):
        """所有写操作串行化"""
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        while True:
            task = self._writer_queue.get()
            if task is None:
                break
            sql, params, future = task
            try:
                cursor = conn.execute(sql, params)
                conn.commit()
                future.set_result(cursor.lastrowid)
            except Exception as e:
                future.set_exception(e)
```

---

## 9. 安全与隐私基线

### 9.1 网络

**项目代码中禁止任何网络调用**。

`requests`、`urllib`、`httpx`、`socket.connect`、`aiohttp` 等不得出现在 `geekclock/` 包内。CI 用 grep 检查。

唯一例外：未来如需「在线检查更新」，必须独立成可关闭的功能 + 默认关闭 + 只命中官方域名 + 用户首次启用必须明确同意。当前阶段**不实现**。

### 9.2 权限

**永远不要管理员权限**。

- 自启注册表：`HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`（已实现）
- 数据存储：`%APPDATA%\GeekClock\`
- 不调用 `runas`、不要 UAC manifest、不写 `HKLM`

### 9.3 SQL 注入

所有 SQL 参数化：

```python
# ✅ 正确
cur.execute("SELECT * FROM tasks WHERE title LIKE ?", (f"%{q}%",))

# ❌ 错误
cur.execute(f"SELECT * FROM tasks WHERE title LIKE '%{q}%'")
```

### 9.4 路径穿越

```python
def safe_path(user_input: str, allowed_root: Path) -> Path:
    p = Path(user_input).resolve()
    if not p.is_relative_to(allowed_root.resolve()):
        raise ValueError(f"Path outside allowed root: {p}")
    return p
```

启动器执行用户选择的项目时：
- `.lnk` 解析后的目标路径必须在白名单根（`Program Files`、用户目录等）下
- 对话框「最近文件」打开前同样校验

### 9.5 子进程

```python
# ✅ 正确
subprocess.Popen([exe_path, arg1, arg2])

# ❌ 错误
subprocess.Popen(f"{exe_path} {arg1} {arg2}", shell=True)
```

### 9.6 单实例锁

```python
import hashlib
import os

def single_instance_name():
    sid = os.environ.get("USERNAME", "default")
    h = hashlib.sha256(sid.encode()).hexdigest()[:16]
    return f"GeekClock_{h}"
```

避免多用户登录时互相串台。

### 9.7 日志 PII

| 级别 | 允许内容 |
|---|---|
| ERROR | 异常栈、错误码 |
| WARNING | 状态异常但可继续 |
| INFO | 事件类型（如 "alarm_triggered"），不含闹钟名 |
| DEBUG | 详细信息（仅本机调试启用） |

默认级别 INFO。设置中允许用户切换 DEBUG 级别用于排错。

---

## 10. 测试与 CI 方案

### 10.1 测试目录结构

```
tests/
├── conftest.py
├── core/
│   ├── test_config.py
│   ├── test_config_migration.py   # schema_version 迁移测试
│   ├── test_scheduler.py
│   └── test_audio_player.py
├── todo/
│   ├── test_storage.py
│   ├── test_service.py
│   └── test_models.py
├── launcher/
│   ├── test_storage.py
│   ├── test_indexer.py
│   ├── test_ranker.py
│   └── test_providers.py
└── system/
    ├── test_resources.py
    └── test_single_instance.py
```

### 10.2 必须覆盖的核心模块

| 模块 | 测试重点 |
|---|---|
| `core/config.py` | schema_version 迁移、字段默认值、并发读写 |
| `core/scheduler.py` | 三种触发器、勿扰过滤、活动时段过滤 |
| `todo/storage.py` | 增删改查、并发读写、备份恢复、完整性校验 |
| `launcher/storage.py` | FTS5 索引正确性、中文 trigram 分词 |
| `launcher/indexer.py` | .lnk 解析、增量更新、失败 fallback |
| `launcher/ranker.py` | 排序公式数值正确性 |
| `system/resources.py` | 源码 / PyInstaller 模式路径切换 |

### 10.3 GitHub Actions CI

`.github/workflows/ci.yml`：

```yaml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        run: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
      - name: Sync env
        run: uv sync
      - name: Lint
        run: uv run ruff check .
      - name: Test
        run: uv run pytest -v
      - name: Build exe
        run: uv run python build.py
      - uses: actions/upload-artifact@v4
        with:
          name: GeekClock-${{ github.sha }}
          path: dist/GeekClock.exe
```

### 10.4 pre-commit 钩子

`.pre-commit-config.yaml`：

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

开发者执行 `uv run pre-commit install` 后，每次 commit 自动跑 ruff。

---

## 11. 被否决的方案与原因

### 11.1 内置 Everything.exe 做全盘搜索

**否决**。

| 否决理由 | 说明 |
|---|---|
| 法律风险 | voidtools 的 Everything 重新分发需要书面许可，未确认前不能内置 |
| 权限矛盾 | Everything 完整索引需 USN Journal 权限，与 GeekClock「不要管理员」哲学冲突 |
| 进程管理盲区 | GeekClock 崩溃后子进程谁回收？端口冲突？IPC 命名冲突？方案未涵盖 |
| 定位不匹配 | Launcher 是独立产品级功能，与闹钟工具定位混合不清 |

**替代方案**：自建 SQLite FTS5 索引，只索引 Start Menu + 用户配置目录。

### 11.2 引入 Windows Search API

**否决**。

| 否决理由 | 说明 |
|---|---|
| 服务依赖 | 依赖 Windows Search 系统服务，可被禁用 |
| 重依赖 | 需引入 pywin32（50+ MB），打包体积上去 |
| 不可控 | 索引范围、刷新策略由系统决定，无法精细控制 |

### 11.3 升级 Python = 升级依赖（不绑定版本）

**否决**。

| 否决理由 | 说明 |
|---|---|
| 技术不可行 | C 扩展（PySide6、numpy 等）必须重新编译对应 Python ABI |
| 无工程意义 | 工程标准做法是锁定，不是「自由升级」 |

**替代方案**：用 uv 锁定到 Python 3.12.10，需要升级时主动评估 + 走 CI。

### 11.4 重写现有代码

**否决**。

现有架构按 feature 分目录、信号槽通信、装配层独立，符合 PySide6 项目最佳实践。重写 = 浪费时间 + 引入新 bug。

**替代方案**：保留现有代码，新功能按既定模板新增模块。

### 11.5 待办系统继续用 JSON

**否决**。

| 否决理由 | 说明 |
|---|---|
| 写入慢 | 任务多后整文件 rewrite 慢 |
| 易损坏 | 写入中途断电整个文件丢失 |
| 搜索难 | 全量扫描，无索引 |
| 内存高 | 全量加载到内存 |

**替代方案**：SQLite WAL + FTS5。

### 11.6 引入 keyboard / pynput 全局热键库

**否决**。

| 否决理由 | 说明 |
|---|---|
| 权限要求高 | 部分功能需管理员，触发 UAC |
| 与 PySide6 集成差 | 跨线程、跨事件循环 |
| 安全风险 | 全键盘钩子，杀软误报 |

**替代方案**：ctypes 直接调 Win32 `RegisterHotKey` + `QAbstractNativeEventFilter`。

### 11.7 jieba 中文分词

**否决**。

| 否决理由 | 说明 |
|---|---|
| 启动慢 | 加载词典 1+ 秒 |
| 内存大 | 30+ MB |
| 打包重 | PyInstaller 体积上去 |

**替代方案**：FTS5 的 `unicode61` tokenizer + trigram 风格切分，对中文常用查询足够。

### 11.8 多个独立 SQLite 数据库

**否决**。

| 否决理由 | 说明 |
|---|---|
| 跨库事务难 | 待办触发闹钟等关联场景需要 |
| 备份复杂 | 多文件备份、恢复时机不一致 |
| WAL 重复 | 每库一份 WAL，资源浪费 |

**替代方案**：单一 `geekclock.db`，按表隔离。

### 11.9 双击 Ctrl（或其他修饰键）作为唤起热键

**否决**。

| 否决理由 | 说明 |
|---|---|
| API 不支持 | Win32 `RegisterHotKey` 不接受单修饰键，必须改用全局键盘钩子（`WH_KEYBOARD_LL`） |
| 杀软误报 | 低级键盘钩子是 keylogger 同款 API，Windows Defender / 火绒 / 360 触发概率高 |
| 性能开销 | 系统每次按键都过钩子函数，且必须 < 1 ms 返回否则被卸载 |
| 死锁风险 | 钩子运行在系统消息线程，跨线程操作 Qt 对象易出问题 |
| 误触发率高 | Ctrl 在日常 Ctrl+C/V/S/Z 中按得极频繁，"按 Ctrl → 停顿 → 再按 Ctrl"很容易在正常操作中命中双击窗口 |
| 反馈不直观 | 双击窗口期不可见，用户搞不清第一下是否被识别 |
| 违反既定红线 | 与 §5.1 / §11.6 「不引入 keyboard、pynput」「ctypes 直接调 Win32 RegisterHotKey 即可」冲突 |

**替代方案**：默认 Ctrl+Space，备选 Alt+Space / Ctrl+\` / Ctrl+Shift+Space，详见 §7.4。

**未来重新评估的前提条件**（同时满足）：
1. 取得代码签名证书 + 主流杀软白名单
2. 真实用户数据驱动的强需求
3. 经过完整安全评审

当前阶段**不实现**。

---

## 12. 实施路线图与工作量

### 12.1 阶段一：工程化基础（必做，3-4 天）

| 任务 | 工作量 | 依赖 |
|---|---|---|
| uv 迁移（§4 步骤 1-11） | 0.5 天 | 无 |
| schema_version 机制 + alarms.json 改造 | 0.5 天 | uv 迁移完成 |
| pytest + 核心模块测试 | 1-2 天 | uv 迁移完成 |
| GitHub Actions CI | 0.5 天 | pytest 完成 |
| ruff + pre-commit 配置 | 0.5 天 | 无 |

**完成标志**：换台机器 `git clone` + `uv sync` 一行命令跑起来；push 自动触发 CI 测试 + 打包。

### 12.2 阶段二：待办系统（5-8 天）

| 任务 | 工作量 |
|---|---|
| 数据库 schema 设计 + storage 层 | 1 天 |
| alarms.json → SQLite 迁移代码 + 测试 | 1 天 |
| Task / Group 数据模型 + service 层 | 1 天 |
| QListView + 自绘 delegate | 2 天 |
| 详情面板 + 编辑对话框 | 1 天 |
| 桌面悬浮待办窗 | 1 天 |
| 提醒触发集成 APScheduler | 0.5 天 |
| 测试覆盖 | 0.5 天 |

### 12.3 阶段三：启动器（8-12 天）

| 任务 | 工作量 |
|---|---|
| 全局热键 ctypes 实现 | 1 天 |
| Provider 接口 + AppsProvider | 2 天 |
| FilesProvider + 索引器 + watchdog | 2-3 天 |
| FTS5 schema + storage | 1 天 |
| Ranker 排序逻辑 | 1 天 |
| 搜索窗口 UI | 2 天 |
| AlarmsProvider / TodosProvider / CommandsProvider | 1 天 |
| 设置面板（热键、索引目录） | 1 天 |

### 12.4 总投入

| 阶段 | 工作量 | 优先级 |
|---|---|---|
| 阶段一：工程化 | 3-4 天 | **必做，立即** |
| 阶段二：待办系统 | 5-8 天 | v2.0 |
| 阶段三：启动器 | 8-12 天 | v2.0 或 v2.1 |
| **合计** | **16-24 天** | - |

---

## 13. 验收标准

### 13.1 阶段一验收

- [ ] `git clone` 后只需 `uv sync` 一行命令完成环境
- [ ] `.python-version` 写明 3.12.10
- [ ] `uv.lock` 已提交
- [ ] 所有依赖在 `pyproject.toml` 中有明确上下界
- [ ] 项目无 poetry 残留
- [ ] `alarms.json` 含 `schema_version` 字段
- [ ] 至少 4 个核心模块有 pytest 测试
- [ ] GitHub Actions push 触发自动测试 + 打包
- [ ] `ruff check .` 零警告
- [ ] 第二台机器复现成功

### 13.2 待办系统验收

- [ ] `geekclock.db` 替代 `alarms.json`
- [ ] 老版本配置自动迁移成功，原文件留 .bak
- [ ] 1000 任务列表滚动 60 fps
- [ ] 后台空闲内存 < 150 MB
- [ ] 全文搜索 1000 任务 < 50 ms
- [ ] 待办到期能正常触发提醒
- [ ] 每日自动备份生效

### 13.3 启动器验收

- [ ] Alt+Space 全局唤起 < 50 ms
- [ ] 输入到结果显示 < 100 ms
- [ ] 支持中文搜索（"项目"命中"我的项目报告"）
- [ ] 应用启动、文件打开、闹钟跳转正常
- [ ] 频繁使用项排序靠前
- [ ] 索引文件 < 50 MB
- [ ] 启动时索引不阻塞 UI
- [ ] 文件变化 1 秒内反映到索引

### 13.4 全局质量验收

- [ ] 项目代码中 grep 不到任何网络调用
- [ ] 不申请管理员权限，全程不弹 UAC
- [ ] 后台空闲 CPU < 1%
- [ ] 24 小时长跑后内存不持续增长
- [ ] 日志、备份、索引文件均不超出预设上限
- [ ] 卸载后 `%APPDATA%\GeekClock\` 一键清理干净

---

## 附录 A：决定不再推翻的三条核心结论

1. **Python 用 uv 管理，3.12.10 锁死**
   技术上无更优解。`.python-version` + `uv.lock` 是工业级标准方案。

2. **不内置 Everything.exe**
   许可证风险 + 权限矛盾 + 进程管理盲区，三个硬伤无法绕过。
   自建 FTS5 索引器，只索引 Start Menu + 用户配置目录。

3. **单一 SQLite + WAL + FTS5**
   闹钟、待办、启动器索引、统计、历史全部进同一个 `geekclock.db`。
   这是 Windows 桌面 Python 应用本地存储的工业级标准方案。

---

## 附录 B：禁止事项清单

下列做法在 GeekClock 项目中**永久禁止**，不论需求方提出何种理由：

- 任何形式的网络调用（含「检查更新」「使用统计」）
- 申请管理员权限 / 触发 UAC
- 内置 Everything.exe（除非取得 voidtools 书面许可）
- 字符串拼接 SQL
- `subprocess.Popen` 用 `shell=True`
- 写注册表 `HKLM`
- 引入 jieba、keyboard、pynput、pywin32（除非有强需求且评估通过）
- **全局键盘 / 鼠标钩子**（`WH_KEYBOARD_LL`、`WH_MOUSE_LL` 等）
- **双击修饰键 / 长按 / 鼠标侧键作为热键**（实现需要钩子，与上一条冲突）
- 全窗口刷新（必须事件驱动局部更新）
- 启动时全量加载所有数据
- 重型 GPU 特效（毛玻璃、实时模糊、大阴影）
- 缓存 / 历史 / 日志无上限累积
- 跨 feature 的代码冗余
- 把 views/models/services 提到 `geekclock/` 根作为独立目录

---

**文档定稿，不再推翻。**

后续任何版本演进必须：
1. 不违反本文档的红线和禁止事项
2. 在对应章节追加版本号 + 修订记录
3. 通过本文档第 13 节的验收标准
