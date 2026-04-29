from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from manicure_bot.utils.callback_data import AdminMainCallback


def admin_main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Расписание",
                    callback_data=AdminMainCallback(action="schedule").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Добавить рабочий день",
                    callback_data=AdminMainCallback(action="add_day").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Добавить/удалить слоты",
                    callback_data=AdminMainCallback(action="manage_slots").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отменить запись",
                    callback_data=AdminMainCallback(action="cancel_booking").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Закрыть день",
                    callback_data=AdminMainCallback(action="close_day").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=AdminMainCallback(action="schedule").pack(),  # placeholder
                )
            ],
        ]
    )


def back_to_admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀ В админ-меню",
                    callback_data=AdminMainCallback(action="schedule").pack(),
                )
            ]
        ]
    )

