from __future__ import annotations

from calendar import monthrange
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from manicure_bot.utils.callback_data import AdminCalendarCallback, UserCalendarCallback
from manicure_bot.utils.date_utils import RU_MONTHS, ymd_from_date


def _ru_weekdays() -> list[str]:
    # Monday-first
    return ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _month_title(d: date) -> str:
    return f"{RU_MONTHS[d.month - 1].capitalize()} {d.year}"


def build_user_calendar(
    month_start_ymd: str,
    available_dates: set[str],
    range_start_ymd: str,
    range_end_ymd: str,
) -> InlineKeyboardMarkup:
    dt = date.fromisoformat(month_start_ymd)
    year = dt.year
    month = dt.month
    _, days_in_month = monthrange(year, month)

    # Calendar grid starts from Monday
    # python: weekday() -> Monday=0..Sunday=6
    first_weekday = date(year, month, 1).weekday()
    total_cells = first_weekday + days_in_month
    rows = (total_cells + 6) // 7

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # Header: navigation
    prev_month = date(year, month, 1).replace(day=1)
    # compute previous month start
    if month == 1:
        prev_month = date(year - 1, 12, 1)
    else:
        prev_month = date(year, month - 1, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    # Enable/disable nav based on allowed range
    range_start = date.fromisoformat(range_start_ymd)
    range_end = date.fromisoformat(range_end_ymd)
    prev_enabled = date(prev_month.year, prev_month.month, 1) >= range_start.replace(day=1)
    next_enabled = date(next_month.year, next_month.month, 1) <= range_end.replace(day=1)

    nav_row: list[InlineKeyboardButton] = [
        InlineKeyboardButton(
            text="◀",
            callback_data=UserCalendarCallback(action="nav", date=ymd_from_date(prev_month)).pack(),
            # if disabled we still send callback; handler will show alert
        ),
        InlineKeyboardButton(text=_month_title(dt), callback_data="noop"),
        InlineKeyboardButton(
            text="▶",
            callback_data=UserCalendarCallback(action="nav", date=ymd_from_date(next_month)).pack(),
        ),
    ]
    # Workaround: "title" button must have callback_data; keep it as "noop"
    # but ensure handler ignores it.
    keyboard.inline_keyboard.append(nav_row)

    # Weekdays
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text=w, callback_data="noop") for w in _ru_weekdays()]
    )

    # Day cells
    cell = 1
    for _r in range(rows):
        row: list[InlineKeyboardButton] = []
        for _c in range(7):
            if _r == 0 and _c < first_weekday:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
                continue
            if cell > days_in_month:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
                continue

            cur = date(year, month, cell)
            cur_ymd = ymd_from_date(cur)

            # Available only if in allowed range and in available_dates
            available = (
                range_start_ymd <= cur_ymd <= range_end_ymd
                and cur_ymd in available_dates
            )
            if available:
                cb = UserCalendarCallback(action="day", date=cur_ymd).pack()
                row.append(InlineKeyboardButton(text=str(cell), callback_data=cb))
            else:
                cb = UserCalendarCallback(action="disabled", date=cur_ymd).pack()
                row.append(InlineKeyboardButton(text=str(cell), callback_data=cb))

            cell += 1
        keyboard.inline_keyboard.append(row)

    # Hide nav disabled flags by adding info row. The handler will still prevent booking.
    return keyboard


def build_admin_calendar(month_start_ymd: str) -> InlineKeyboardMarkup:
    # Admin calendar doesn't need available dates filtering; it only visualizes days.
    dt = date.fromisoformat(month_start_ymd)
    year = dt.year
    month = dt.month
    _, days_in_month = monthrange(year, month)
    first_weekday = date(year, month, 1).weekday()
    total_cells = first_weekday + days_in_month
    rows = (total_cells + 6) // 7

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # navigation
    if month == 1:
        prev_month = date(year - 1, 12, 1)
    else:
        prev_month = date(year, month - 1, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    nav_row = [
        InlineKeyboardButton(
            text="◀",
            callback_data=AdminCalendarCallback(action="nav", date=ymd_from_date(prev_month)).pack(),
        ),
        InlineKeyboardButton(text=_month_title(dt), callback_data="noop"),
        InlineKeyboardButton(
            text="▶",
            callback_data=AdminCalendarCallback(action="nav", date=ymd_from_date(next_month)).pack(),
        ),
    ]
    keyboard.inline_keyboard.append(nav_row)

    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text=w, callback_data="noop") for w in _ru_weekdays()]
    )

    cell = 1
    for _r in range(rows):
        row: list[InlineKeyboardButton] = []
        for _c in range(7):
            if _r == 0 and _c < first_weekday:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
                continue
            if cell > days_in_month:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
                continue
            cur = date(year, month, cell)
            cur_ymd = ymd_from_date(cur)
            cb = AdminCalendarCallback(action="day", date=cur_ymd).pack()
            row.append(InlineKeyboardButton(text=str(cell), callback_data=cb))
            cell += 1
        keyboard.inline_keyboard.append(row)

    return keyboard

