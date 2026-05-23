import logging
from collections.abc import Callable
from datetime import datetime, time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from geekclock.core import config

logger = logging.getLogger(__name__)


class AlarmScheduler:
    def __init__(self, on_trigger: Callable[[dict], None] | None = None):
        self._scheduler = BackgroundScheduler()
        self._on_trigger = on_trigger or self._default_trigger
        self._loaded_alarm_ids: set[str] = set()

    @staticmethod
    def _default_trigger(alarm: dict) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] 闹钟触发 → {alarm['name']}")
        print(f"          消息：{alarm.get('message', '(无)')}")

    def start(self) -> None:
        self._scheduler.start()
        self.reload()
        logger.info("调度器已启动")

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("调度器已停止")

    def reload(self) -> None:
        self._scheduler.remove_all_jobs()
        self._loaded_alarm_ids.clear()
        alarms = config.get_alarms()
        for alarm in alarms:
            if alarm.get("enabled", True):
                self._add_alarm_job(alarm)
        logger.info(f"已加载 {len(self._loaded_alarm_ids)} 个启用中的闹钟")

    def setup_keep_alive(self, enabled: bool, interval_minutes: int, callback) -> None:
        job_id = "__keep_alive__"
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass
        if not enabled:
            logger.info("音响保活已禁用")
            return
        self._scheduler.add_job(
            func=callback,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            replace_existing=True,
            misfire_grace_time=30,
        )
        logger.info(f"音响保活已启用：每 {interval_minutes} 分钟激活一次")

    def get_next_run_time(self, alarm_id: str):
        try:
            job = self._scheduler.get_job(alarm_id)
            return job.next_run_time if job else None
        except Exception:
            return None

    def _add_alarm_job(self, alarm: dict) -> None:
        alarm_id = alarm.get("id")
        trigger_type = alarm.get("trigger_type")
        if not alarm_id or not trigger_type:
            logger.warning(f"闹钟配置不完整（缺少 id 或 trigger_type），跳过：{alarm.get('name', '?')}")
            return
        trigger_args = alarm.get("trigger_args", {})

        try:
            if trigger_type == "interval":
                trigger = IntervalTrigger(**trigger_args)
            elif trigger_type == "cron":
                weekdays = alarm.get("weekdays", [1, 2, 3, 4, 5, 6, 7])
                cron_days = ",".join(str(d - 1) for d in weekdays)
                trigger = CronTrigger(day_of_week=cron_days, **trigger_args)
            elif trigger_type == "date":
                trigger = DateTrigger(**trigger_args)
            else:
                logger.warning(f"未知触发类型 {trigger_type}，跳过 {alarm_id}")
                return
        except (TypeError, ValueError) as e:
            logger.error(f"闹钟 {alarm_id} 触发器配置错误：{e}")
            return

        self._scheduler.add_job(
            func=self._on_trigger_wrapper,
            trigger=trigger,
            args=[alarm],
            id=alarm_id,
            replace_existing=True,
            misfire_grace_time=30,
        )
        self._loaded_alarm_ids.add(alarm_id)
        logger.info(f"已注册闹钟：{alarm['name']} ({trigger_type})")

    def _on_trigger_wrapper(self, alarm: dict) -> None:
        if not self._is_in_active_hours(alarm):
            logger.debug(f"闹钟 {alarm['name']} 不在活动时段，跳过")
            return
        if self._is_in_dnd():
            logger.debug(f"闹钟 {alarm['name']} 在勿扰时段，跳过")
            return
        if alarm["trigger_type"] == "interval":
            today = datetime.now().isoweekday()
            if today not in alarm.get("weekdays", [1, 2, 3, 4, 5, 6, 7]):
                logger.debug(f"闹钟 {alarm['name']} 今天不触发")
                return
        try:
            self._on_trigger(alarm)
        except Exception as e:
            logger.exception(f"闹钟 {alarm['name']} 回调执行失败：{e}")

    @staticmethod
    def _is_in_active_hours(alarm: dict) -> bool:
        active = alarm.get("active_hours", ["00:00", "23:59"])
        start = _parse_time(active[0])
        end = _parse_time(active[1])
        now = datetime.now().time()
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end

    @staticmethod
    def _is_in_dnd() -> bool:
        settings = config.get_global_settings()
        if not settings.get("dnd_enabled"):
            return False
        start = _parse_time(settings["dnd_start"])
        end = _parse_time(settings["dnd_end"])
        now = datetime.now().time()
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end


def _parse_time(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


class SchedulerWithSnooze:
    def __init__(self, scheduler: AlarmScheduler):
        self._scheduler = scheduler

    def add_snooze(self, alarm: dict, target_time) -> None:
        import uuid
        snooze_id = f"snooze-{alarm['id']}-{uuid.uuid4().hex[:8]}"
        try:
            self._scheduler._scheduler.add_job(
                func=self._scheduler._on_trigger_wrapper,
                trigger=DateTrigger(run_date=target_time),
                args=[alarm],
                id=snooze_id,
                misfire_grace_time=60,
            )
            logger.info(
                f"已添加延后任务：{alarm['name']} "
                f"将在 {target_time.strftime('%Y-%m-%d %H:%M:%S')} 触发"
            )
        except Exception as e:
            logger.error(f"添加延后任务失败：{e}")
