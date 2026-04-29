from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    choose_date_for_schedule = State()
    choose_date_for_add_day = State()
    manage_slots_choose_date = State()
    choose_date_for_cancel = State()
    close_day_choose_date = State()

