from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import Dict, List, Tuple

from aiogram import F
from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import func

from npb.config import ClientConstants, RegistrationConstants, MasterConstants, CommonConstants, AdminConstants
from npb.config import Config
from npb.db.api import Appointment, User
from npb.db.sa_models import appointment_table, user_table
from npb.db.utils import WhereClause, Join
from npb.db.core import engine
from npb.logger import get_logger
from npb.state_machine.admin_states import Admin
from npb.state_machine.client_states import Client
from npb.tg.black_list import get_black_list_manager
from npb.tg.bot import bot
from npb.tg.models import AppointmentModel, UserModel
from npb.utils.tg.client import pick_master_keyboard, pick_day_keyboard, my_appointments_keyboard
from npb.utils.common import get_user_data, log_handler_info, master_profile_info, pick_sub_service_keyboard, \
    get_month_edges, get_picked_services_and_sub_services, get_month, _prepare_user_info, appointment_info, is_uuid, \
    notify_user
from npb.utils.tg.client import pick_single_service_keyboard, pick_master_available_slots_keyboard
from npb.routes.tg.registration_form import _handle_sub_service
from npb.utils.tg.entry_point import get_max_seq_id

admin_router = Router()


async def _ask_user_telegram_id(callback: CallbackQuery) -> None:
    text = "Пожалуйста, введите telegram id мастера."
    await callback.message.answer(text=text)


async def _handle_activate_deactivate_user(message: Message, activate: bool = True):
    """Activates when admin is activating / deactivating a user."""
    logger = get_logger()
    log_handler_info(handler_name="admin._handle_activate_deactivate_user", logger=logger, message_text=message.text)
    action_prefix = "акти" if activate else "деакти"
    text = f"Пользователь успешно {action_prefix}вирован! Telegram id пользователя: {message.text}."
    try:
        where_clause = WhereClause(
            params=[user_table.c.telegram_id], values=[message.text], comparison_operators=["=="]
        )
        black_list_manager = get_black_list_manager()
        data_to_set = {}
        if activate:
            data_to_set["is_active"] = True
            data_to_set["flood_count"] = 0
            black_list_manager.unban_user(telegram_id=message.text)
        else:
            data_to_set["is_active"] = False
            black_list_manager.ban_user(telegram_id=message.text)
        user = await User(engine=engine, logger=logger).update_user_info(
            data_to_set=data_to_set, where_clause=where_clause, return_all=True
        )
        if not user:
            text = f"Пользователя с указанным telegram id ({message.text}) не найдено."
    except Exception as exc:
        text = f"Произошла ошибка при попытке {action_prefix}вировать пользователя. Детали ошибки: {str(exc)}"
    await message.answer(text=text)


@admin_router.callback_query(Admin.default, F.data.casefold() == AdminConstants.ADD_MASTER)
async def handle_add_master_start(callback: CallbackQuery, state: FSMContext):
    """Activates when admin is going to add a new master."""
    logger = get_logger()
    log_handler_info(handler_name="admin.handle_add_master_start", logger=logger, callback_data=callback.data)
    await state.set_state(Admin.add_master)
    await _ask_user_telegram_id(callback=callback)


@admin_router.message(Admin.add_master)
async def handle_add_master(message: Message, state: FSMContext):
    """Activates when admin is adding master."""
    logger = get_logger()
    log_handler_info(handler_name="admin.handle_add_master", logger=logger, message_text=message.text)
    text = f"Мастер успешно добавлен! Telegram id мастера: {message.text}."
    try:
        where_clause = WhereClause(
            params=[user_table.c.telegram_id], values=[message.text], comparison_operators=["=="]
        )
        data_to_set = {"is_master": True}
        user = await User(engine=engine, logger=logger).update_user_info(
            data_to_set=data_to_set, where_clause=where_clause, return_all=True
        )
        if not user:
            text = f"Пользователь с telegram id {message.text} не найден."
    except Exception as exc:
        text = f"Произошла ошибка при попытке добавить нового Мастера. Детали ошибки: {str(exc)}"
    await message.answer(text=text)


@admin_router.callback_query(
    Admin.default,
    (F.data.casefold() == AdminConstants.ACTIVATE_USER) | (F.data.casefold() == AdminConstants.DEACTIVATE_USER)
)
async def handle_activate_deactivate_user_start(callback: CallbackQuery, state: FSMContext):
    """Activates when admin is going to activate / deactivate a user."""
    logger = get_logger()
    log_handler_info(
        handler_name="admin.handle_activate_deactivate_user_start", logger=logger, callback_data=callback.data
    )
    if callback.data == AdminConstants.ACTIVATE_USER:
        await state.set_state(Admin.activate_user)
    else:
        await state.set_state(Admin.deactivate_user)
    await _ask_user_telegram_id(callback=callback)


@admin_router.message(Admin.activate_user)
async def handle_activate_user(message: Message, state: FSMContext):
    """Activates when admin is activating a user."""
    await _handle_activate_deactivate_user(message=message, activate=True)


@admin_router.message(Admin.deactivate_user)
async def handle_activate_user(message: Message, state: FSMContext):
    """Activates when admin is deactivating a user."""
    await _handle_activate_deactivate_user(message=message, activate=False)

