from aiogram import Dispatcher

from npb.tg.storage import NPBStateMachineStorage

dp = Dispatcher(storage=NPBStateMachineStorage())
# dp = Dispatcher()
