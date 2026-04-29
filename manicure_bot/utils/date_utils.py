from __future__ import annotations

from datetime import date, datetime, timedelta


RU_MONTHS = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]


def parse_ymd(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def format_ru_long(d: str) -> str:
    dt = parse_ymd(d)
    return f"{dt.day} {RU_MONTHS[dt.month - 1]}"


def ymd_from_date(dt: date) -> str:
    return dt.strftime("%Y-%m-%d")


def add_days_ymd(ymd: str, days: int) -> str:
    return ymd_from_date(parse_ymd(ymd) + timedelta(days=days))


def month_start_end(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return ymd_from_date(start), ymd_from_date(end)


def today_ymd() -> str:
    return date.today().strftime("%Y-%m-%d")

