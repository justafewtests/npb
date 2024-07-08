from aiogram import Dispatcher

from nbp.tg.storage import NPBStateMachineStorage

dp = Dispatcher(storage=NPBStateMachineStorage())
# dp = Dispatcher()
