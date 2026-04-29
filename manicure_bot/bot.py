import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from manicure_bot.config import ADMIN_IDS, BOT_TOKEN, CHANNEL_ID, DB_PATH, TIMEZONE, require_config
from manicure_bot.database.db import Database
from manicure_bot.database.repository import Repository
from manicure_bot.handlers.admin.admin_handlers import build_admin_router
from manicure_bot.handlers.user.user_handlers import build_user_router
from manicure_bot.services.reminders import ReminderService
from manicure_bot.services.scheduler import SchedulerService
from manicure_bot.services.subscription import SubscriptionService


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    require_config()
    logger = logging.getLogger("manicure_bot")

    # Safe startup diagnostics (without token leakage)
    logger.info(
        "Config loaded: admins=%s, channel_id=%s, timezone=%s, db=%s",
        ADMIN_IDS,
        CHANNEL_ID,
        TIMEZONE,
        DB_PATH,
    )

    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    db = Database()
    await db.init()
    repo = Repository(db)

    scheduler_service = SchedulerService(repo)
    scheduler_service.start()

    reminder_service = ReminderService(repo)
    subscription_service = SubscriptionService(bot)

    # Restore reminder jobs from SQLite after startup
    await scheduler_service.restore_reminders(bot, reminder_service)

    user_router = build_user_router(
        repo=repo,
        bot=bot,
        subscription_service=subscription_service,
        scheduler=scheduler_service.scheduler,
        reminder_service=reminder_service,
    )
    admin_router = build_admin_router(
        repo=repo,
        bot=bot,
        scheduler=scheduler_service.scheduler,
        reminder_service=reminder_service,
    )

    dp.include_router(user_router)
    dp.include_router(admin_router)

    logger.info("Bot started. Polling updates...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

