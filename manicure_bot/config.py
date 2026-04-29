import os
from pathlib import Path

from dotenv import load_dotenv


# Autoload variables from .env in project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# override=True is important when shell already contains empty vars
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=True)


# Bot token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Comma-separated list of Telegram user IDs (admins)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Channel for subscription check and (optionally) posting the schedule
CHANNEL_ID = os.getenv("CHANNEL_ID", "")  # can be like "-1001234567890"
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "")

# SQLite database file path
DB_PATH = os.getenv(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "manicure_bot.sqlite3"),
)

# Local timezone for date/time calculations in the bot and scheduler
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

# Reminder offset before appointment (hours)
REMIND_BEFORE_HOURS = int(os.getenv("REMIND_BEFORE_HOURS", "24"))

# Appointment range for the user calendar (days forward from today)
BOOKING_RANGE_DAYS = int(os.getenv("BOOKING_RANGE_DAYS", "30"))

# Default time slots presets for the admin "add slot" picker
SLOT_START = os.getenv("SLOT_START", "10:00")  # inclusive
SLOT_END = os.getenv("SLOT_END", "20:00")  # inclusive
SLOT_STEP_MINUTES = int(os.getenv("SLOT_STEP_MINUTES", "30"))


PRICES_HTML = (
    "<b>Прайсы</b>\n\n"
    "<b>Френч</b> — 1000₽\n"
    "<b>Квадрат</b> — 500₽"
)


def require_config() -> None:
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not ADMIN_IDS:
        missing.append("ADMIN_IDS")
    if not CHANNEL_ID:
        missing.append("CHANNEL_ID")
    if not CHANNEL_LINK:
        missing.append("CHANNEL_LINK")

    if missing:
        raise RuntimeError(
            "Missing required env vars: " + ", ".join(missing) + ". "
            "Set them in environment variables or in your run config."
        )

