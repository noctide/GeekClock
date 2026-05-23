# GeekClock v3 启动要点

## 启动方式

venv 已激活时（提示符前有 `(geekclock)`）：

```powershell
python main.py
# 或
python -m geekclock
```

未激活 venv 时：

```powershell
.\.venv\Scripts\python.exe main.py
```

## uv 相关

- venv 由 `uv 0.11.12` 创建，但 **`uv` CLI 不在系统 PATH 中**
- `uv run` 报 `CommandNotFoundException` 解决方法：
  1. 安装 uv：`powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
  2. **重启 PowerShell**（当前窗口 PATH 未刷新），或手动 `refreshenv`
  3. 再执行 `uv run python main.py`

## 项目状态 (2026-05-11)

- 26 个测试全部通过
- `python main.py` 正常启动
- `python -m geekclock` 正常启动
- `dist/GeekClock.exe` 正常启动
- 日志位置：`logs/GeekClock.log`
- 配置文件：项目根目录 `alarms.json`
