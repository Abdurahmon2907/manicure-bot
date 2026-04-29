from __future__ import annotations

from aiogram import Bot

from manicure_bot.config import CHANNEL_ID


def _is_member_status(status: str) -> bool:
    # statuses that mean user is allowed to access
    return status in {"member", "creator", "administrator"}


class SubscriptionService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def is_subscribed(self, user_id: int) -> bool:
        if not CHANNEL_ID:
            # if channel isn't configured - allow booking
            return True

        member = await self.bot.get_chat_member(CHANNEL_ID, user_id)
        return _is_member_status(member.status)

