from logging import Logger
from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from npb.config import ClientConstants, MasterConstants, AdminConstants
from npb.db.core import engine
from npb.db.exceptions import ReadMaxSequenceError
from npb.db.sa_models import user_table


def master_profile_options_keyboard() -> InlineKeyboardMarkup:  # TODO: this should be in utils.master
    """
    Form reply keyboard available for master.
    :return: Reply keyboard.
    """
    option_buttons = [
        [InlineKeyboardButton(text="Мой профиль", callback_data=MasterConstants.MY_PROFILE)],
        [InlineKeyboardButton(text="Редактировать профиль", callback_data=MasterConstants.EDIT_PROFILE)],
        [InlineKeyboardButton(text="Мой график работы", callback_data=MasterConstants.MY_TIMETABLE)],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=option_buttons)
    return keyboard


def client_profile_options_keyboard() -> InlineKeyboardMarkup:  # TODO: this should be in utils.client
    """
    Form reply keyboard available for client.
    :return: Reply keyboard.
    """
    option_buttons = [
        [InlineKeyboardButton(text="Выбрать услугу", callback_data=ClientConstants.PICK_SERVICE)],
        [InlineKeyboardButton(text="Мои записи", callback_data=ClientConstants.MY_APPOINTMENTS)],
        [InlineKeyboardButton(text="Стать мастером", callback_data=ClientConstants.BECOME_MASTER)],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=option_buttons)
    return keyboard


def admin_profile_options_keyboard() -> InlineKeyboardMarkup:  # TODO: this should be in utils.client
    """
    Form reply keyboard available for admin.
    :return: Reply keyboard.
    """
    option_buttons = [
        [InlineKeyboardButton(text="Добавить мастера", callback_data=AdminConstants.ADD_MASTER)],
        [InlineKeyboardButton(text="Активировать пользователя", callback_data=AdminConstants.ACTIVATE_USER)],
        [
            InlineKeyboardButton(
                text="Деактивировать пользователя", callback_data=AdminConstants.DEACTIVATE_USER
            )
        ],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=option_buttons)
    return keyboard


async def get_max_seq_id(logger: Logger) -> Optional[int]:
    """
    Get maximum of seq_id column in user table.
    :param logger: Logger object.
    :return: Maximum seq_id.
    """
    connection: AsyncConnection
    query = select(func.max(user_table.c.seq_id))
    try:
        async with engine.begin() as connection:
            result = await connection.execute(query)
            return result.scalar()
    except Exception as exc:
        error_message = f"Unexpected error in 'get_max_seq_id'. Details: {str(exc)}"
        logger.error(error_message)
        raise ReadMaxSequenceError(error_message)
