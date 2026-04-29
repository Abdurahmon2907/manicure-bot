from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from manicure_bot.utils.callback_data import (
    MainMenuCallback,
    SubscriptionCallback,
    UserCancelCallback,
    UserConfirmCallback,
    UserSlotCallback,
)


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Записаться",
                    callback_data=MainMenuCallback(action="book").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отменить запись",
                    callback_data=MainMenuCallback(action="cancel").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Прайсы",
                    callback_data=MainMenuCallback(action="prices").pack(),
                ),
                InlineKeyboardButton(
                    text="Портфолио",
                    callback_data=MainMenuCallback(action="portfolio").pack(),
                ),
            ],
        ]
    )


def subscription_prompt_kb() -> InlineKeyboardMarkup:
    # URL is placed by handler because it depends on config.CHANNEL_LINK
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Проверить подписку", callback_data=SubscriptionCallback(action="check").pack())
            ]
        ]
    )


def subscription_prompt_full_kb(channel_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Подписаться", url=channel_link),
                InlineKeyboardButton(
                    text="Проверить подписку",
                    callback_data=SubscriptionCallback(action="check").pack(),
                ),
            ]
        ]
    )


def time_slots_kb(date_ymd: str, free_times: list[str]) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i, t in enumerate(free_times, start=1):
        row.append(
            InlineKeyboardButton(
                text=t,
                callback_data=UserSlotCallback(date=date_ymd, time=t).pack(),
            )
        )
        # 2 buttons per row for readability
        if i % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Back to main menu
    buttons.append(
        [
            InlineKeyboardButton(text="◀ Назад", callback_data=MainMenuCallback(action="book").pack())
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_booking_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=UserConfirmCallback(action="confirm").pack(),
                ),
                InlineKeyboardButton(
                    text="Отменить",
                    callback_data=UserConfirmCallback(action="cancel").pack(),
                ),
            ]
        ]
    )


def cancel_booking_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, отменить",
                    callback_data=UserCancelCallback(action="confirm_cancel").pack(),
                ),
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=UserCancelCallback(action="back").pack(),
                ),
            ]
        ]
    )

