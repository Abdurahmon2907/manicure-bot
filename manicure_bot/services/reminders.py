from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Bot

from manicure_bot.config import PRICES_HTML
from manicure_bot.database.repository import Repository


REMINDER_TEXT_TEMPLATE = (
    "Напоминаем, что вы записаны на наращивание ресниц завтра в {time}.\n"
    "Ждём вас ❤️"
)


def _parse_iso_datetime(dt_iso: str) -> datetime:
    # Stored as ISO; accept both with and without Z
    dt_iso = dt_iso.replace("Z", "+00:00")
    return datetime.fromisoformat(dt_iso)


class ReminderService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    async def send_reminder(self, bot: Bot, booking_id: int) -> None:
        booking = await self.repo.get_booking_by_id(booking_id)
        if not booking:
            return

        # Ensure booking is still active
        active = await self.repo.db.fetchone(
            "SELECT 1 FROM bookings WHERE id=? AND status='active' LIMIT 1",
            (booking_id,),
        )
        if not active:
            # booking cancelled -> cleanup reminder record
            await self.repo.mark_reminder_cancelled(booking_id)
            return

        await bot.send_message(
            chat_id=booking.user_id,
            text=REMINDER_TEXT_TEMPLATE.format(time=booking.booking_time),
        )
        await self.repo.mark_reminder_sent(booking_id)

