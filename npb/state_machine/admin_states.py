from aiogram.fsm.state import State, StatesGroup


class Admin(StatesGroup):
    """
    FSM for admin.
    """
    default = State()
    add_master = State()
    activate_user = State()
    deactivate_user = State()
