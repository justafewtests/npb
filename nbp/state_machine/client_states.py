from aiogram.fsm.state import State, StatesGroup


class Client(StatesGroup):
    """
    FSM for client
    """
    default = State()
    service = State()
    wtf = State()
    sub_service = State()
    use_filter = State()
    master_or_filter = State()
    master_calendar_day = State()
    master_calendar_time = State()
    specify_phone = State()
    specify_telegram_profile = State()
    master = State()
    make_appointment = State()
    cancel = State()
    name = State()
    pick_master = State()
    appointment_info = State()
