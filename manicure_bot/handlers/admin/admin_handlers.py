from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from manicure_bot.config import ADMIN_IDS, SLOT_END, SLOT_START, SLOT_STEP_MINUTES
from manicure_bot.database.repository import Repository
from manicure_bot.keyboard.admin.admin_kb import admin_main_menu_kb
from manicure_bot.services.reminders import ReminderService
from manicure_bot.states.admin_states import AdminStates
from manicure_bot.utils.calendar import build_admin_calendar
from manicure_bot.utils.callback_data import (
    AdminCancelBookingCallback,
    AdminCalendarCallback,
    AdminMainCallback,
    AdminTimeSlotCallback,
)
from manicure_bot.utils.date_utils import format_ru_long, parse_ymd, today_ymd


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _time_range_times() -> list[str]:
    # Simple preset generator for admin time-picker
    start_dt = datetime.strptime(SLOT_START, "%H:%M")
    end_dt = datetime.strptime(SLOT_END, "%H:%M")

    cur = start_dt
    out: list[str] = []
    while cur <= end_dt:
        out.append(cur.strftime("%H:%M"))
        cur = cur + timedelta(minutes=SLOT_STEP_MINUTES)
    return out


def build_admin_router(
    repo: Repository,
    bot: Bot,
    scheduler,
    reminder_service: ReminderService,
) -> Router:
    router = Router()

    async def assert_admin(callback: CallbackQuery) -> bool:
        return callback.from_user.id in ADMIN_IDS

    async def render_admin_calendar(message: Message, state: FSMContext, month_start_ymd: str) -> None:
        kb = build_admin_calendar(month_start_ymd)
        await message.edit_text("Выберите дату:", reply_markup=kb)
        await state.update_data(month_start=month_start_ymd)

    async def render_manage_slots(message: Message, state: FSMContext, date_ymd: str) -> None:
        # Day open/closed doesn't block admin editing; it only affects user booking.
        is_closed = await repo.is_day_closed(date_ymd)

        schedule_rows = await repo.get_schedule_for_admin(date_ymd)
        existing_times = [r["time"] for r in schedule_rows]

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        from manicure_bot.utils.callback_data import AdminTimeSlotCallback

        inline_keyboard: list[list[InlineKeyboardButton]] = []

        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"Состояние дня: {'закрыт' if is_closed else 'открыт'}",
                    callback_data="noop",
                )
            ]
        )

        # Existing slots -> delete buttons
        if schedule_rows:
            inline_keyboard.append([])
            for r in schedule_rows:
                inline_keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=f"Удалить {r['time']}",
                            callback_data=AdminTimeSlotCallback(action="del", date=date_ymd, time=r["time"]).pack(),
                        )
                    ]
                )

        # Add slot buttons (only for missing times)
        preset_times = _time_range_times()
        available_to_add = [t for t in preset_times if t not in existing_times]
        if available_to_add:
            inline_keyboard.append([InlineKeyboardButton(text="Добавить слоты:", callback_data="noop")])
            for t in available_to_add:
                inline_keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=f"Добавить {t}",
                            callback_data=AdminTimeSlotCallback(action="add", date=date_ymd, time=t).pack(),
                        )
                    ]
                )

        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text="◀ В админ-меню",
                    callback_data=AdminMainCallback(action="schedule").pack(),
                )
            ]
        )

        await message.edit_text(
            f"<b>Управление слотами</b>\n{_html_escape(format_ru_long(date_ymd))}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_keyboard),
        )

    @router.callback_query(AdminMainCallback.filter())
    async def on_admin_main_menu(callback: CallbackQuery, state: FSMContext, callback_data: AdminMainCallback) -> None:
        if not await assert_admin(callback):
            await callback.answer("Нет доступа", show_alert=True)
            return

        action = callback_data.action
        today = today_ymd()
        month_dt = parse_ymd(today)
        month_start_ymd = f"{month_dt.year:04d}-{month_dt.month:02d}-01"

        if action == "schedule":
            await state.set_state(AdminStates.choose_date_for_schedule)
            await render_admin_calendar(callback.message, state, month_start_ymd)
            await callback.answer()
        elif action == "add_day":
            await state.set_state(AdminStates.choose_date_for_add_day)
            await render_admin_calendar(callback.message, state, month_start_ymd)
            await callback.answer()
        elif action == "manage_slots":
            await state.set_state(AdminStates.manage_slots_choose_date)
            await render_admin_calendar(callback.message, state, month_start_ymd)
            await callback.answer()
        elif action == "cancel_booking":
            await state.set_state(AdminStates.choose_date_for_cancel)
            await render_admin_calendar(callback.message, state, month_start_ymd)
            await callback.answer()
        elif action == "close_day":
            await state.set_state(AdminStates.close_day_choose_date)
            await render_admin_calendar(callback.message, state, month_start_ymd)
            await callback.answer()
        else:
            await callback.answer()

    @router.callback_query(AdminCalendarCallback.filter())
    async def on_admin_calendar(
        callback: CallbackQuery,
        state: FSMContext,
        callback_data: AdminCalendarCallback,
    ) -> None:
        if not await assert_admin(callback):
            await callback.answer("Нет доступа", show_alert=True)
            return

        action = callback_data.action
        date_ymd = callback_data.date
        current_state = await state.get_state()

        if action == "nav":
            await render_admin_calendar(callback.message, state, date_ymd)
            await callback.answer()
            return

        # action == day
        if current_state == AdminStates.choose_date_for_schedule.state:
            schedule_rows = await repo.get_schedule_for_admin(date_ymd)
            is_closed = await repo.is_day_closed(date_ymd)

            lines: list[str] = [f"<b>Расписание на {_html_escape(format_ru_long(date_ymd))}</b>"]
            if is_closed:
                lines.append("День закрыт (запись недоступна).")

            if not schedule_rows:
                lines.append("Слотов пока нет.")
            else:
                for r in schedule_rows:
                    if r["name"]:
                        lines.append(
                            f"<b>{_html_escape(r['time'])}</b> — занято: {_html_escape(r['name'])} ({_html_escape(r['phone'])})"
                        )
                    else:
                        lines.append(f"<b>{_html_escape(r['time'])}</b> — свободно")

            await state.clear()
            await callback.message.edit_text(
                "\n".join(lines),
                parse_mode="HTML",
                reply_markup=admin_main_menu_kb(),
            )
            await callback.answer()
            return

        if current_state == AdminStates.choose_date_for_add_day.state:
            await repo.add_working_day(date_ymd)
            await state.clear()
            await callback.message.edit_text(
                f"Рабочий день <b>{_html_escape(format_ru_long(date_ymd))}</b> добавлен/открыт.",
                parse_mode="HTML",
                reply_markup=admin_main_menu_kb(),
            )
            await callback.answer()
            return

        if current_state == AdminStates.manage_slots_choose_date.state:
            await state.update_data(selected_manage_date=date_ymd)
            await render_manage_slots(callback.message, state, date_ymd)
            await callback.answer()
            return

        if current_state == AdminStates.choose_date_for_cancel.state:
            bookings = await repo.list_bookings_for_date(date_ymd)
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            if not bookings:
                await state.clear()
                await callback.message.edit_text(
                    f"На <b>{_html_escape(format_ru_long(date_ymd))}</b> активных записей нет.",
                    parse_mode="HTML",
                    reply_markup=admin_main_menu_kb(),
                )
                await callback.answer()
                return

            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="◀ В админ-меню",
                            callback_data=AdminMainCallback(action="schedule").pack(),
                        )
                    ]
                ]
            )

            # Add booking cancel buttons
            for b in bookings:
                kb.inline_keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=f"Отменить {b['booking_time']} — {b['name']}",
                            callback_data=AdminCancelBookingCallback(booking_id=int(b["booking_id"])).pack(),
                        )
                    ]
                )

            await state.set_state(AdminStates.choose_date_for_cancel)
            await state.update_data(selected_cancel_date=date_ymd)
            await callback.message.edit_text(
                f"Выберите запись для отмены на <b>{_html_escape(format_ru_long(date_ymd))}</b>:",
                parse_mode="HTML",
                reply_markup=kb,
            )
            await callback.answer()
            return

        if current_state == AdminStates.close_day_choose_date.state:
            await repo.close_day(date_ymd)
            await state.clear()
            await callback.message.edit_text(
                f"День <b>{_html_escape(format_ru_long(date_ymd))}</b> закрыт для записи.",
                parse_mode="HTML",
                reply_markup=admin_main_menu_kb(),
            )
            await callback.answer()
            return

        await callback.answer()

    @router.message(F.text == "/admin")
    async def on_admin_command(message: Message, state: FSMContext) -> None:
        if message.from_user.id not in ADMIN_IDS:
            return
        await state.clear()
        await message.answer("Админ-панель:", reply_markup=admin_main_menu_kb())

    @router.callback_query(AdminTimeSlotCallback.filter(), AdminStates.manage_slots_choose_date)
    async def on_admin_slot_action(
        callback: CallbackQuery,
        state: FSMContext,
        callback_data: AdminTimeSlotCallback,
    ) -> None:
        if not await assert_admin(callback):
            await callback.answer("Нет доступа", show_alert=True)
            return

        date_ymd = callback_data.date
        time_hhmm = callback_data.time
        action = callback_data.action

        try:
            if action == "add":
                await repo.add_time_slot(date_ymd, time_hhmm)
                await callback.answer(f"Слот {time_hhmm} добавлен")
            else:
                await repo.delete_time_slot(date_ymd, time_hhmm)
                await callback.answer(f"Слот {time_hhmm} удален")
        except Exception as e:
            await callback.answer("Не удалось изменить слот", show_alert=True)
            await callback.message.answer(f"Ошибка: {e}")

        # Refresh manage UI
        await render_manage_slots(callback.message, state, date_ymd)

    @router.callback_query(AdminCancelBookingCallback.filter(), AdminStates.choose_date_for_cancel)
    async def on_admin_cancel_booking(
        callback: CallbackQuery,
        state: FSMContext,
        callback_data: AdminCancelBookingCallback,
    ) -> None:
        if not await assert_admin(callback):
            await callback.answer("Нет доступа", show_alert=True)
            return

        booking_id = int(callback_data.booking_id)
        _, removed_job_id = await repo.cancel_booking(booking_id)
        if removed_job_id:
            job = scheduler.get_job(removed_job_id)
            if job:
                scheduler.remove_job(removed_job_id)

        cancel_date = (await state.get_data()).get("selected_cancel_date")
        await state.clear()

        if cancel_date:
            schedule_rows = await repo.get_schedule_for_admin(cancel_date)
            is_closed = await repo.is_day_closed(cancel_date)
            lines: list[str] = [f"<b>Расписание на {_html_escape(format_ru_long(cancel_date))}</b>"]
            if is_closed:
                lines.append("День закрыт.")
            if not schedule_rows:
                lines.append("Слотов пока нет.")
            else:
                for r in schedule_rows:
                    if r["name"]:
                        lines.append(
                            f"<b>{_html_escape(r['time'])}</b> — занято: {_html_escape(r['name'])} ({_html_escape(r['phone'])})"
                        )
                    else:
                        lines.append(f"<b>{_html_escape(r['time'])}</b> — свободно")

            await callback.message.edit_text(
                "\n".join(lines),
                parse_mode="HTML",
                reply_markup=admin_main_menu_kb(),
            )
        else:
            await callback.message.edit_text("Запись отменена.", reply_markup=admin_main_menu_kb())

        await callback.answer()

    @router.callback_query(F.data == "noop")
    async def on_noop(callback: CallbackQuery) -> None:
        await callback.answer()

    return router

