from aiogram.fsm.state import State, StatesGroup


class UserSubscriptionStates(StatesGroup):
    waiting_subscription = State()


class UserBookingStates(StatesGroup):
    choose_date = State()
    choose_time = State()
    enter_name = State()
    enter_phone = State()
    confirm = State()


class UserCancelStates(StatesGroup):
    confirm_cancel = State()

