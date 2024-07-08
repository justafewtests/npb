from aiogram.fsm.state import State, StatesGroup


class EntryPoint(StatesGroup):
    """
    FSM for entry point.
    """
    default = State()
    employee = State()
    client = State()