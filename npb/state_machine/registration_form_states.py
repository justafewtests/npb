from aiogram.fsm.state import State, StatesGroup


class RegistrationForm(StatesGroup):
    """
    FSM for registration form
    """
    name = State()
    edit_name = State()
    service = State()
    edit_service = State()
    sub_service = State()
    phone_number = State()
    edit_phone_number = State()
    instagram_link = State()
    edit_instagram_link = State()
    description = State()
    edit_description = State()
    edit = State()
    edit_start = State()
    default = State()
    telegram_profile = State()
    edit_telegram_profile = State()
