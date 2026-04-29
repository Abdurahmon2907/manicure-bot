from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from manicure_bot.config import (
    ADMIN_IDS,
    BOOKING_RANGE_DAYS,
    CHANNEL_ID,
    CHANNEL_LINK,
    PRICES_HTML,
    REMIND_BEFORE_HOURS,
    TIMEZONE,
)
from manicure_bot.database.repository import Repository
from manicure_bot.keyboard.user.user_kb import (
    cancel_booking_confirm_kb,
    confirm_booking_kb,
    main_menu_kb,
    subscription_prompt_full_kb,
    time_slots_kb,
)
from manicure_bot.services.reminders import ReminderService
from manicure_bot.services.subscription import SubscriptionService
from manicure_bot.states.user_states import (
    UserBookingStates,
    UserCancelStates,
    UserSubscriptionStates,
)
from manicure_bot.utils.calendar import build_user_calendar
from manicure_bot.utils.callback_data import (
    MainMenuCallback,
    SubscriptionCallback,
    UserCancelCallback,
    UserCalendarCallback,
    UserConfirmCallback,
    UserSlotCallback,
)
from manicure_bot.utils.date_utils import (
    add_days_ymd,
    format_ru_long,
    month_start_end,
    parse_ymd,
    today_ymd,
)


def _html_escape(s: str) -> str:
    # Minimal escaping for user-provided strings (for ParseMode.HTML)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _booking_datetime_local(date_ymd: str, time_hhmm: str) -> datetime:
    dt = datetime.strptime(f"{date_ymd} {time_hhmm}", "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=ZoneInfo(TIMEZONE))


async def _ensure_subscription(
    bot: Bot,
    callback_message: Message,
    state: FSMContext,
    subscription_service: SubscriptionService,
) -> bool:
    subscribed = await subscription_service.is_subscribed(callback_message.from_user.id)
    if subscribed:
        return True

    await state.set_state(UserSubscriptionStates.waiting_subscription)
    await callback_message.answer(
        "Для записи необходимо подписаться на канал",
        reply_markup=subscription_prompt_full_kb(CHANNEL_LINK),
    )
    return False


def build_user_router(
    repo: Repository,
    bot: Bot,
    subscription_service: SubscriptionService,
    scheduler,
    reminder_service: ReminderService,
) -> Router:
    router = Router()

    async def render_calendar(
        message: Message,
        state: FSMContext,
        month_start_ymd: str,
    ) -> None:
        data = await state.get_data()
        range_start_ymd = data.get("range_start")
        range_end_ymd = data.get("range_end")
        if not range_start_ymd or not range_end_ymd:
            today = today_ymd()
            range_start_ymd = today
            range_end_ymd = add_days_ymd(today, BOOKING_RANGE_DAYS)
            await state.update_data(range_start=range_start_ymd, range_end=range_end_ymd)

        month_dt = parse_ymd(month_start_ymd)
        m_start, m_end = month_start_end(month_dt.year, month_dt.month)

        # Constrain by the overall booking range
        query_start = max(m_start, range_start_ymd)
        query_end = min(m_end, range_end_ymd)

        if query_start > query_end:
            available_dates = set()
        else:
            available_dates = await repo.get_available_month_days(query_start, query_end)

        kb = build_user_calendar(
            month_start_ymd=month_start_ymd,
            available_dates=available_dates,
            range_start_ymd=range_start_ymd,
            range_end_ymd=range_end_ymd,
        )

        await message.edit_text(
            "Выберите дату для записи:",
            reply_markup=kb,
        )

    @router.message(CommandStart())
    async def on_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Привет! Выберите действие в меню:", reply_markup=main_menu_kb())

    @router.callback_query(MainMenuCallback.filter(F.action == "prices"))
    async def on_prices(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.message.answer(PRICES_HTML, parse_mode="HTML", reply_markup=main_menu_kb())
        await callback.answer()

    @router.callback_query(MainMenuCallback.filter(F.action == "portfolio"))
    async def on_portfolio(callback: CallbackQuery, state: FSMContext) -> None:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Смотреть портфолио",
                        url="https://ru.pinterest.com/crystalwithluv/_created/",
                    )
                ]
            ]
        )
        await callback.message.answer("Портфолио мастера:", reply_markup=kb)
        await callback.answer()

    @router.callback_query(MainMenuCallback.filter(F.action == "cancel"))
    async def on_cancel_request(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback.from_user.id
        active = await repo.get_active_booking_for_user(user_id)
        if not active:
            await callback.message.answer("У вас сейчас нет активной записи.", reply_markup=main_menu_kb())
            await callback.answer()
            return

        await state.clear()
        await state.set_state(UserCancelStates.confirm_cancel)
        await state.update_data(booking_id=active.booking_id)

        await callback.message.answer(
            "Подтвердите отмену записи:",
            parse_mode="HTML",
            reply_markup=cancel_booking_confirm_kb(),
        )
        await callback.answer()

    @router.callback_query(
        UserCancelCallback.filter(F.action == "back"), UserCancelStates.confirm_cancel
    )
    async def on_cancel_back(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await callback.message.answer("Отмена отменена.", reply_markup=main_menu_kb())
        await callback.answer()

    @router.callback_query(
        UserCancelCallback.filter(F.action == "confirm_cancel"), UserCancelStates.confirm_cancel
    )
    async def on_cancel_confirm(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        booking_id = int(data["booking_id"])

        _, removed_job_id = await repo.cancel_booking(booking_id)
        if removed_job_id:
            job = scheduler.get_job(removed_job_id)
            if job:
                scheduler.remove_job(removed_job_id)

        await state.clear()
        await callback.message.answer("Запись отменена. Слот снова доступен.", reply_markup=main_menu_kb())
        await callback.answer()

    @router.callback_query(MainMenuCallback.filter(F.action == "book"))
    async def on_book(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()

        subscribed = await subscription_service.is_subscribed(callback.from_user.id)
        if not subscribed:
            await state.set_state(UserSubscriptionStates.waiting_subscription)
            await callback.message.answer(
                "Для записи необходимо подписаться на канал",
                reply_markup=subscription_prompt_full_kb(CHANNEL_LINK),
            )
            await callback.answer()
            return

        today = today_ymd()
        range_start_ymd = today
        range_end_ymd = add_days_ymd(today, BOOKING_RANGE_DAYS)

        month_dt = parse_ymd(today)
        month_start_ymd = f"{month_dt.year:04d}-{month_dt.month:02d}-01"

        await state.set_state(UserBookingStates.choose_date)
        await state.update_data(
            range_start=range_start_ymd,
            range_end=range_end_ymd,
            month_start=month_start_ymd,
        )
        await render_calendar(callback.message, state, month_start_ymd)
        await callback.answer()

    @router.callback_query(SubscriptionCallback.filter(F.action == "check"), UserSubscriptionStates.waiting_subscription)
    async def on_subscription_check(callback: CallbackQuery, state: FSMContext) -> None:
        subscribed = await subscription_service.is_subscribed(callback.from_user.id)
        if not subscribed:
            await callback.answer("Вы ещё не подписались.")
            return

        # Move to booking calendar
        today = today_ymd()
        range_start_ymd = today
        range_end_ymd = add_days_ymd(today, BOOKING_RANGE_DAYS)
        month_dt = parse_ymd(today)
        month_start_ymd = f"{month_dt.year:04d}-{month_dt.month:02d}-01"

        await state.set_state(UserBookingStates.choose_date)
        await state.update_data(range_start=range_start_ymd, range_end=range_end_ymd, month_start=month_start_ymd)
        await render_calendar(callback.message, state, month_start_ymd)
        await callback.answer()

    @router.callback_query(F.data == "noop")
    async def on_noop(callback: CallbackQuery) -> None:
        await callback.answer()

    @router.callback_query(UserCalendarCallback.filter(), UserBookingStates.choose_date)
    async def on_calendar_action(callback: CallbackQuery, state: FSMContext, callback_data: UserCalendarCallback) -> None:
        if not await subscription_service.is_subscribed(callback.from_user.id):
            await callback.answer("Сначала подтвердите подписку.")
            return

        action = callback_data.action
        date_ymd = callback_data.date

        if action == "disabled":
            await callback.answer("На эту дату нет доступных слотов.")
            return

        if action == "nav":
            # date_ymd is month start (YYYY-MM-01)
            await state.update_data(month_start=date_ymd)
            await render_calendar(callback.message, state, date_ymd)
            await callback.answer()
            return

        # action == "day"
        # Verify day is available at least one free slot
        free_times = await repo.get_free_slots(date_ymd)
        if not free_times:
            await callback.answer("Слот(ы) на эту дату закончились.")
            await render_calendar(callback.message, state, (await state.get_data()).get("month_start"))
            return

        await state.update_data(selected_date=date_ymd)
        await state.set_state(UserBookingStates.choose_time)

        await callback.message.edit_text(
            f"Выберите время для записи на {format_ru_long(date_ymd)}:",
            reply_markup=time_slots_kb(date_ymd, [t["time"] for t in free_times]),
        )
        await callback.answer()

    @router.callback_query(UserSlotCallback.filter(), UserBookingStates.choose_time)
    async def on_slot_pick(
        callback: CallbackQuery,
        state: FSMContext,
        callback_data: UserSlotCallback,
    ) -> None:
        if not await subscription_service.is_subscribed(callback.from_user.id):
            await callback.answer("Сначала подтвердите подписку.")
            return

        date_ymd = callback_data.date
        time_hhmm = callback_data.time

        free_times = await repo.get_free_slots(date_ymd)
        free_time_values = {r["time"] for r in free_times}
        if time_hhmm not in free_time_values:
            await callback.answer("Этот слот уже занят.")
            return

        await state.update_data(selected_date=date_ymd, selected_time=time_hhmm)
        await state.set_state(UserBookingStates.enter_name)
        await callback.message.edit_text(
            "Введите ваше имя:",
        )
        await callback.answer()

    @router.message(UserBookingStates.enter_name)
    async def on_enter_name(message: Message, state: FSMContext) -> None:
        name = (message.text or "").strip()
        if not name:
            await message.answer("Имя не должно быть пустым. Введите имя еще раз.")
            return

        await state.update_data(name=name)
        await state.set_state(UserBookingStates.enter_phone)
        await message.answer("Введите номер телефона (для подтверждения):")

    @router.message(UserBookingStates.enter_phone)
    async def on_enter_phone(message: Message, state: FSMContext) -> None:
        phone = (message.text or "").strip()
        # Basic normalization/validation
        digits = "".join([ch for ch in phone if ch.isdigit() or ch == "+"])
        if len(digits) < 7:
            await message.answer("Похоже, номер телефона введен неверно. Попробуйте еще раз.")
            return

        await state.update_data(phone=phone)

        data = await state.get_data()
        date_ymd = data["selected_date"]
        time_hhmm = data["selected_time"]
        name = data["name"]
        phone_for_html = _html_escape(phone)

        await state.set_state(UserBookingStates.confirm)
        await message.answer(
            "Проверьте данные и подтвердите запись:\n\n"
            f"Дата: <b>{_html_escape(format_ru_long(date_ymd))}</b>\n"
            f"Время: <b>{_html_escape(time_hhmm)}</b>\n"
            f"Имя: <b>{_html_escape(name)}</b>\n"
            f"Телефон: <b>{phone_for_html}</b>",
            parse_mode="HTML",
            reply_markup=confirm_booking_kb(),
        )

    @router.callback_query(UserConfirmCallback.filter(), UserBookingStates.confirm)
    async def on_confirm_or_cancel(callback: CallbackQuery, state: FSMContext, callback_data: UserConfirmCallback) -> None:
        action = callback_data.action
        if action == "cancel":
            await state.clear()
            await callback.message.answer("Запись отменена.", reply_markup=main_menu_kb())
            await callback.answer()
            return

        data = await state.get_data()
        selected_date = data["selected_date"]
        selected_time = data["selected_time"]
        name = data["name"]
        phone = data["phone"]

        try:
            booking_id, _ = await repo.create_booking(
                user_id=callback.from_user.id,
                date=selected_date,
                time=selected_time,
                name=name,
                phone=phone,
            )
        except ValueError as e:
            await callback.message.answer(str(e), reply_markup=main_menu_kb())
            await state.clear()
            await callback.answer()
            return

        # Schedule reminder 24h before (if enough time remains)
        booking_dt_local = _booking_datetime_local(selected_date, selected_time)
        now_local = datetime.now(ZoneInfo(TIMEZONE))
        run_at_local = booking_dt_local - timedelta(hours=REMIND_BEFORE_HOURS)

        if run_at_local > now_local:
            run_at_utc = run_at_local.astimezone(ZoneInfo("UTC"))
            run_at_iso = run_at_utc.replace(tzinfo=None).isoformat() + "Z"
            job_id = f"rem_{booking_id}"

            scheduler.add_job(
                reminder_service.send_reminder,
                trigger="date",
                run_date=run_at_utc,
                args=[bot, booking_id],
                id=job_id,
                replace_existing=True,
            )
            await repo.create_reminder_job_record(booking_id, run_at_iso, job_id)

        await state.clear()

        # User confirmation
        await callback.message.answer(
            "Запись подтверждена! ✅\n"
            f"Дата: <b>{_html_escape(format_ru_long(selected_date))}</b>\n"
            f"Время: <b>{_html_escape(selected_time)}</b>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )

        # Notify admins
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                "Новая запись:\n"
                f"ID записи: <code>{booking_id}</code>\n"
                f"Клиент: <b>{_html_escape(name)}</b>\n"
                f"Телефон: <b>{_html_escape(phone)}</b>\n"
                f"Дата: <b>{_html_escape(selected_date)}</b>\n"
                f"Время: <b>{_html_escape(selected_time)}</b>",
                parse_mode="HTML",
            )

        # Send schedule to channel
        if CHANNEL_ID:
            schedule_rows = await repo.get_schedule_for_admin(selected_date)
            lines: list[str] = [f"<b>Расписание на { _html_escape(format_ru_long(selected_date)) }</b>"]
            if not schedule_rows:
                lines.append("На выбранную дату пока нет слотов.")
            else:
                for r in schedule_rows:
                    t = r["time"]
                    if r["name"]:
                        lines.append(f"<b>{_html_escape(t)}</b> — Занято: {_html_escape(r['name'])}")
                    else:
                        lines.append(f"<b>{_html_escape(t)}</b> — Свободно")

            await bot.send_message(
                CHANNEL_ID,
                "\n".join(lines),
                parse_mode="HTML",
            )

        await callback.answer()

    return router

