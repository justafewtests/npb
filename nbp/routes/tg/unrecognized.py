from aiogram import Router
from aiogram import F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup

from nbp.config import Config
from nbp.db.api import User
from nbp.db.core import engine
from nbp.logger import get_logger
from nbp.tg.models import UserModel
from nbp.state_machine.client_states import Client
from nbp.state_machine.master_states import Master
from nbp.state_machine.registration_form_states import RegistrationForm
from nbp.utils.tg.entry_point import client_profile_options_keyboard, master_profile_options_keyboard
from nbp.utils.tg.client import pick_single_service_keyboard
from nbp.db.utils import WhereClause
from nbp.db.sa_models import user_table

from aiogram import F
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)


unrecognized_router = Router()


@unrecognized_router.message()
async def handle_non_recognized(message: Message) -> None:
    logger = get_logger()
    telegram_id = str(message.chat.id)
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
    await message.answer(text=text)
