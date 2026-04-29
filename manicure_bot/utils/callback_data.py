from aiogram.filters.callback_data import CallbackData


class UserCalendarCallback(CallbackData, prefix="ucal"):
    # action: nav | day | disabled
    action: str
    date: str


class UserSlotCallback(CallbackData, prefix="uslot"):
    date: str
    time: str


class UserConfirmCallback(CallbackData, prefix="uconf"):
    action: str  # confirm | cancel


class UserCancelCallback(CallbackData, prefix="ucancel"):
    action: str  # confirm_cancel | back


class SubscriptionCallback(CallbackData, prefix="sub"):
    action: str  # check


class MainMenuCallback(CallbackData, prefix="main"):
    action: str  # book | cancel | prices | portfolio


class AdminMainCallback(CallbackData, prefix="adminmain"):
    action: str  # schedule | add_day | manage_slots | cancel_booking | close_day


class AdminCalendarCallback(CallbackData, prefix="acal"):
    action: str  # nav | day | disabled
    date: str


class AdminTimeSlotCallback(CallbackData, prefix="adslot"):
    action: str  # add | del
    date: str
    time: str


class AdminCancelBookingCallback(CallbackData, prefix="acb"):
    booking_id: int

