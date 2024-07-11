from aiogram.enums import ParseMode
from aiogram import Router
from aiogram import F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup

from npb.config import Config, CommonConstants
from npb.db.api import User
from npb.db.core import engine
from npb.logger import get_logger
from npb.state_machine.admin_states import Admin
from npb.tg.models import UserModel
from npb.state_machine.client_states import Client
from npb.state_machine.master_states import Master
from npb.state_machine.registration_form_states import RegistrationForm
from npb.utils.tg.entry_point import client_profile_options_keyboard, master_profile_options_keyboard, get_max_seq_id, \
    admin_profile_options_keyboard
from npb.utils.tg.client import pick_single_service_keyboard
from npb.db.utils import WhereClause
from npb.db.sa_models import user_table

from aiogram import F
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)


entry_point_router = Router()


@entry_point_router.message(Command(commands=["start", "commands"]))
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """
    Activates when /start.
    """
    logger = get_logger()
    telegram_id = str(message.chat.id)
    telegram_profile = str(message.chat.username)
    phone_number = str(message.contact.phone_number) if message.contact else None
    keyboard = None

    if user := await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id):
        await User(engine=engine, logger=logger).drop_temporary_data(telegram_id=telegram_id)
        name = user.name
        text = f"Добрый день, *{name}*! " if name else "Добрый день! "
        if user.is_admin:
            await state.set_state(Admin.default)
            if message.text == "/start":
                text += "Добро пожаловать в кабинет Администратора! "
            else:
                text = "Список доступных Вам команд:"
                keyboard = admin_profile_options_keyboard()
        elif user.is_master:
            await state.set_state(Master.default)
            if message.text == "/start":
                text += "Добро пожаловать в кабинет Мастера! "
            else:
                text = "Список доступных Вам команд:"
                keyboard = master_profile_options_keyboard()
        else:
            await state.set_state(Client.default)
            if message.text == "/start":
                text += "Добро пожаловать в кабинет Клиента! "
            else:
                text = "Список доступных Вам команд:"
                keyboard = client_profile_options_keyboard()
        if message.text == "/start":
            text += "Воспользуйтесь командой /commands, чтобы узнать доступные Вам возможности."
        await message.answer(text=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        max_seq_id = await get_max_seq_id(logger=logger)
        max_seq_id = max_seq_id + 1 if max_seq_id else 1
        user_info = UserModel(
            telegram_id=telegram_id,
            telegram_profile=telegram_profile,
            is_master=False,
            is_active=True,
            phone_number=phone_number,
            seq_id=max_seq_id,
        )
        await User(engine=engine, logger=logger).create_user(user=user_info)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Мастер"), KeyboardButton(text="Клиент")]],
            one_time_keyboard=True,
        )
        await message.answer(f"Добрый день! Вы Мастер или Клиент?", reply_markup=keyboard)


@entry_point_router.message(F.text.casefold() == "мастер")
async def master_handler(message: Message, state: FSMContext) -> None:
    """
    Activates when user already picked 'Мастер'.
    """
    telegram_id = message.chat.id
    text = CommonConstants.BECOME_MASTER % telegram_id
    await message.answer(text)


@entry_point_router.message(F.text.casefold() == "клиент")
async def client_handler(message: Message, state: FSMContext) -> None:
    """
    Activates when user already picked 'Клиент'.
    """
    services = list(Config.MASTER_SERVICES.keys())
    keyboard = pick_single_service_keyboard(services)
    await state.set_state(Client.service)
    await message.answer(
        f"Пожалуйста, выберите услугу:",
        reply_markup=keyboard
    )

