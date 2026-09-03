"""The poller: every N minutes, find the tasks that are due and run them."""

import logging
import threading
import time as time_module
from datetime import datetime, timedelta

from . import db
from .config import config
from .runner import run_task

log = logging.getLogger(__name__)


def occurrence_of(now: datetime, schedule_time) -> datetime:
    """The moment this schedule was due - today, or yesterday when the poll window
    reached back past midnight."""
    occurrence = datetime.combine(now.date(), schedule_time)
    if occurrence > now:
        occurrence -= timedelta(days=1)
    return occurrence


def poll_once(now: datetime | None = None) -> int:
    """One tick. Returns how many tasks were run.

    The window reaches back one interval plus a minute of slack - each tick costs a
    little time, so an exactly interval-wide window would leave a blind spot between
    consecutive ticks. Overlap is harmless because already_ran() keeps a schedule
    from firing twice for the same due time.
    """
    now = now or datetime.now()
    window_start = (now - timedelta(minutes=config.poll_interval_minutes + 1)).time()
    window_end = now.time()

    ran = 0
    with db.connect() as conn:
        due = db.due_schedules(conn, window_start, window_end, now.date())
        log.info("tick %s - %s schedule(s) in window %s..%s",
                 now.strftime("%H:%M:%S"), len(due),
                 window_start.strftime("%H:%M"), window_end.strftime("%H:%M"))

        for schedule in due:
            occurrence = occurrence_of(now, schedule["schedule_time"])
            if db.already_ran(conn, schedule["schedule_id"], occurrence):
                log.info("schedule %s already ran for %s - skipped",
                         schedule["schedule_id"], occurrence.strftime("%Y-%m-%d %H:%M"))
                continue
            task = db.task_by_id(conn, schedule["task_id"])
            if task is None:
                continue
            log.info("running task %s (%s)", task["task_id"], task["task_name"])
            run_task(conn, task, schedule["schedule_id"])
            ran += 1
    return ran


def run_forever(stop_event: threading.Event | None = None, on_tick=None) -> None:
    """Poll until stop_event is set. The GUI passes an event so its Stop button can
    interrupt the sleep; the CLI passes nothing and runs until killed."""
    interval = config.poll_interval_minutes * 60
    log.info("scheduler started - polling every %s minute(s)", config.poll_interval_minutes)
    while True:
        try:
            ran = poll_once()
            if on_tick:
                on_tick(ran)
        except Exception:
            # A bad tick (DB down, for example) must not kill the poller.
            log.exception("poll failed")

        if stop_event is not None:
            if stop_event.wait(interval):
                log.info("scheduler stopped")
                return
        else:
            time_module.sleep(interval)
