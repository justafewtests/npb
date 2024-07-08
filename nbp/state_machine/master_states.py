from aiogram.fsm.state import State, StatesGroup


class Master(StatesGroup):
    """
    FSM for master.
    """
    default = State()
    edit_profile = State()
    edit_timetable = State()
    edit_timetable_bulk = State()
    edit_day = State()
    edit_time = State()
    delete_time = State()
