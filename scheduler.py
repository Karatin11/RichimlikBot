from __future__ import annotations

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

from sheets import get_all_people, get_reminder_time

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()
_current_job_time: str | None = None


async def send_daily_reminder(bot, group_id: str, spreadsheet_id: str):
    """Called by scheduler — sends reminder to admin in DM."""
    from bot import send_admin_reminder, ADMIN_ID

    if not ADMIN_ID:
        logger.warning("ADMIN_ID not set, skipping reminder")
        return

    people = get_all_people(spreadsheet_id)
    if not people:
        await bot.send_message(group_id, "📋 <b>Ro'yxat bo'sh!</b>", parse_mode="HTML")
        return

    curr_tr = get_current_index(spreadsheet_id)
    await send_admin_reminder(curr_tr, curr_tr)


def reschedule_if_needed(bot, group_id: str, spreadsheet_id: str, tz_name: str):
    global _current_job_time
    new_time = get_reminder_time(spreadsheet_id)

    if new_time == _current_job_time:
        return

    logger.info("Rescheduling reminder: %s -> %s", _current_job_time, new_time)

    try:
        hour, minute = map(int, new_time.split(":"))
    except ValueError:
        logger.warning("Invalid time format in Sheets: %s", new_time)
        return

    _current_job_time = new_time
    tz = timezone(tz_name)

    _scheduler.remove_all_jobs()

    _scheduler.add_job(
        send_daily_reminder,
        CronTrigger(hour=hour, minute=minute, day_of_week="mon-fri", timezone=tz),
        args=[bot, group_id, spreadsheet_id],
        id="daily_reminder",
        replace_existing=True,
    )

    _scheduler.add_job(
        reschedule_if_needed,
        "interval",
        minutes=5,
        args=[bot, group_id, spreadsheet_id, tz_name],
        id="reschedule_check",
        replace_existing=True,
    )

    logger.info("Reminder scheduled at %s (%s)", new_time, tz_name)


def start_scheduler(bot, group_id: str, spreadsheet_id: str, tz_name: str):
    reschedule_if_needed(bot, group_id, spreadsheet_id, tz_name)
    if not _scheduler.running:
        _scheduler.start()
