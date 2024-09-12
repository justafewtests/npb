from aiogram import Router
from aiogram.types import (
    CallbackQuery,
    Message,
)

from npb.config import Config
from npb.db.api import User
from npb.db.core import engine
from npb.db.sa_models import user_table
from npb.db.utils import WhereClause
from npb.exceptions import NoTelegramUpdateObject
from npb.logger import get_logger
from npb.state_machine.client_states import Client
from npb.state_machine.master_states import Master
from npb.state_machine.registration_form_states import RegistrationForm


unrecognized_router = Router()


async def _handle_non_recognized(callback: CallbackQuery = None, message: Message = None) -> None:
    if not callback and not message:
        raise NoTelegramUpdateObject("Neither callback nor message is specified.")
    logger = get_logger()
    telegram_id = str(message.chat.id) if message else str(callback.message.chat.id)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    data_to_set = {}
    if user.non_recogn_count > Config.NON_RECOGNIZED_LIMIT:
        text = (
            "К сожалению, я всё ещё не могу Вас понять. Пожалуйста, свяжитесь с администратором @admin или "
            "или воспользуйтесь другой командой /commands."
        )
        current_state_class = user.state.split(":")[1] if user.state else None
        match current_state_class:
            case Client.__name__:
                data_to_set["state"] = Client.default.state
            case Master.__name__:
                data_to_set["state"] = Master.default.state
            case RegistrationForm.__name__:
                data_to_set["state"] = RegistrationForm.default.state
    else:
        text = "Извините, я Вас не понял. Пожалуйста, попробуйте, ещё раз"
        where_clause = WhereClause(
            params=[user_table.c.telegram_id],
            values=[telegram_id],
            comparison_operators=["=="]
        )
        data_to_set["non_recogn_count"] = user.non_recogn_count + 1

        await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    if message:
        await message.answer(text=text)
    else:
        await callback.message.answer(text=text)


@unrecognized_router.message()
async def handle_non_recognized(message: Message) -> None:
    await _handle_non_recognized(message=message)


@unrecognized_router.callback_query()
async def handle_non_recognized(callback: CallbackQuery) -> None:
    await _handle_non_recognized(callback=callback)
