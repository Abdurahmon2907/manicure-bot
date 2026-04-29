from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from manicure_bot.config import TIMEZONE
from manicure_bot.database.repository import Repository
from manicure_bot.services.reminders import ReminderService


def parse_db_iso_datetime(dt_iso: str) -> datetime:
    # stored as "...Z" so replace to offset for fromisoformat
    return datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))


class SchedulerService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    def start(self) -> None:
        self.scheduler.start()

    async def restore_reminders(self, bot, reminder_service: ReminderService) -> None:
        now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        reminders = await self.repo.get_scheduled_reminders_after(now_iso)
        for r in reminders:
            booking_id = int(r["booking_id"])
            run_at_dt = parse_db_iso_datetime(r["run_at"])
            job_id = r["job_id"]

            # If run_at is already in the past, skip (job would fire immediately).
            if run_at_dt <= datetime.now(run_at_dt.tzinfo):
                continue

            self.scheduler.add_job(
                reminder_service.send_reminder,
                trigger="date",
                run_date=run_at_dt,
                args=[bot, booking_id],
                id=job_id,
                replace_existing=False,
            )

