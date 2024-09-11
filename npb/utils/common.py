from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple, Union
import operator
from uuid import UUID

from aiogram.enums import ParseMode
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import Column, func, Row
from sqlalchemy.ext.asyncio import AsyncEngine

from npb.config import CommonConstants, Config, RegistrationConstants
from npb.db.api import Appointment, User
from npb.db.sa_models import appointment_table, user_table
from npb.db.utils import WhereClause
from npb.exceptions import UserNotFound, UserParamNotFound, NoTelegramUpdateObject
from npb.logger import get_logger
from npb.config import MasterConstants
from npb.exceptions import CalendarError
from npb.tg.bot import bot
from npb.exceptions import CouldNotNotify


async def get_all_picked_services(telegram_id: str, logger: Logger, engine: AsyncEngine) -> dict:
    """
    Return all picked services.
    :param telegram_id: Telegram id.
    :param logger: Logger object.
    :param engine: DB engine object.
    :return:
    """
    if user := await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id):
        all_picked_services = user.services
    else:
        all_picked_services = {}
    return all_picked_services


async def get_user_data(
    telegram_id: str,
    logger: Logger,
    engine: AsyncEngine,
    param: str
) -> Optional[Union[str, int, bool, dict]]:
    """
    Get user data.
    :param telegram_id: Telegram id.
    :param logger: Logger object.
    :param engine: DB engine object.
    :param param: Requested user data.
    :return:
    """
    if user := await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id):
        try:
            data = getattr(user, param)
        except AttributeError as exc:
            raise UserParamNotFound(f"User does not have param '{param}'. Details: {str(exc)}")
        return data


def _prepare_user_info(user: Row, for_master: bool = False):
    text = ""
    if for_master:
        params = (
            ("*контактный номер:*\n%s\n\n", user.phone_number),
            ("*профиль в телеграм:*\n@%s\n\n", user.telegram_profile),
        )
    else:
        if user.services:
            services_as_string = []
            for service, sub_services in user.services.items():
                services_as_string.append(f"{service}:\n    {', '.join(list(sub_services.keys()))}\n")
            services_as_string = "".join(services_as_string)
        else:
            services_as_string = ""
        params = (
            ("*телеграм:*\n@%s\n\n", user.telegram_profile),
            ("*имя:*\n%s\n\n", user.name),
            ("*услуги:*\n%s\n", services_as_string),
            ("*контактный номер:*\n%s\n\n", user.phone_number),
            ("*профиль в инстаграм:*\n%s\n\n", user.instagram_link),
            ("*описание:*\n%s\n", user.description),
        )
    for param in params:
        if param[1]:
            text += param[0] % param[1]
    return text


async def master_profile_info(
    logger: Logger = None,
    engine: AsyncEngine = None,
    telegram_id: str = None,
    user: Union[Row, None] = None,
) -> str:
    """
    Get master profile info.
    :param logger: Logger object.
    :param engine: DB engine object.
    :param telegram_id: Telegram id.
    :param user: User as sqlalchemy Row.
    :param short: Master short info is requested (info in one line).
    :return: Description as string.
    """
    user = user or await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    if user and user.is_master:
        text = _prepare_user_info(user=user)
        if not text.strip():
            text = "Кажется у меня нет информации о Вашем профиле. Пожалуйста, заполните ваш профиль: /commands ."
        return text
    else:
        raise UserNotFound(f"User {telegram_id} not found or user is not master.")


def appointment_info(
    date_and_time: datetime, user_info: str, service: str = None, user: Row = None, for_master: bool = False,
):
    text = (
        "*Детали записи*:\n"
        f"*Дата*:\n{date_and_time.strftime('%d.%m.%Y')}\n\n"
        f"*Время*:\n{date_and_time.strftime('%H:%M')}\n\n"
        f"*Услуга*:\n{service if not user else user.current_service}\n\n"
    )
    if for_master:
        text += f"*Информация о Клиенте*:\n{user_info}"
    else:
        text += f"*Информация о Мастере*:\n{user_info}"
    return text


def pick_sub_service_keyboard(
    sub_services: List[str],
    all_picked_services: Dict[str, Dict[str, bool]],
    picked_service: str,
) -> InlineKeyboardMarkup:
    """
    Form inline keyboard to pick sub service.
    :param sub_services: A list of all sub services related to given services.
    :param all_picked_services: A map of services and sub services:
        {service_1: {sub_service_1: True, sub_service_2: True}, service_2: {sub_service_1: True, sub_service_2: True}}
    :param picked_service: Picked service.
    :return: Inline keyboard.
    """
    sub_service_buttons = []
    for sub_service in sub_services:
        if picked_service and all_picked_services.get(picked_service, {}).get(sub_service):
            button_text = f"✅ {sub_service}"
        else:
            button_text = sub_service
        sub_service_buttons.append([InlineKeyboardButton(text=button_text, callback_data=sub_service)])
    sub_service_buttons.append(
        [InlineKeyboardButton(text="Готово", callback_data=RegistrationConstants.DONE_SUB_SERVICE)]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=sub_service_buttons)
    return keyboard


def edit_profile_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Изменить имя", callback_data=CommonConstants.EDIT_NAME)],
        [InlineKeyboardButton(text="Изменить услуги", callback_data=CommonConstants.EDIT_SERVICE)],
        [InlineKeyboardButton(text="Изменить номер телефона", callback_data=CommonConstants.EDIT_PHONE_NUMBER)],
        [InlineKeyboardButton(text="Изменить instagram", callback_data=CommonConstants.EDIT_INSTAGRAM)],
        [InlineKeyboardButton(text="Изменить описание", callback_data=CommonConstants.EDIT_DESCRIPTION)],
        [InlineKeyboardButton(text="Изменить telegram profile", callback_data=CommonConstants.EDIT_TELEGRAM_PROFILE)],
        [InlineKeyboardButton(text="Завершить", callback_data=CommonConstants.FINISH_FORM)],
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons, resize_keyboard=True)
    return keyboard


async def handle_start_edit_name(callback: CallbackQuery = None, message: Message = None) -> None:
    """
    Activates when client going to edit name.
    """
    if not callback and not message:
        raise NoTelegramUpdateObject("Neither callback nor message is specified.")
    text = (
        "Пожалуйста, введите название Вашего салона или Ваш никнейм. Это имя будут видеть Клиенты, поэтому "
        f"постарайтесь сделать его *уникальным*. Максимальная длина - *{Config.USER_NAME_MAX_LENGTH} символов*. "
        f"Примеры:\n - Салон PrettyNails\n - Мастер по ногтям Кристина Филлипова\n - 💅🏻 Ангелина Романова 💅🏻"
    )
    if callback:
        await callback.message.answer(text=text, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer(text=text, parse_mode=ParseMode.MARKDOWN)


def log_handler_info(
    logger: Logger,
    handler_name: str,
    message_text: str = None,
    callback_data: str = None,
    current_state: str = None,
):
    logger.info(f"handler triggered: {handler_name}")
    if message_text:
        logger.info(f"message_text: {message_text}")
    if callback_data:
        logger.info(f"callback_data: {callback_data}")
    if current_state:
        logger.info(f"current_state: {current_state}")


def get_month(action_type: str, current_month: int, current_year: int) -> Tuple[int, int]:  # TODO: change name
    if action_type == MasterConstants.CALENDAR_BACK:
        if current_month - 1 == 0:
            if current_year == datetime.now().year:
                raise CalendarError("Last year reached")
            else:
                current_month = 12
                current_year -= 1
        else:
            current_month -= 1
    elif action_type == MasterConstants.CALENDAR_FORWARD:
        if current_month + 1 == 13:
            current_month = 1
            current_year += 1
        else:
            current_month += 1
    else:
        raise CalendarError(
            f"Unexpected action type for 'get_month': {action_type}. Expected: {MasterConstants.CALENDAR_BACK}, "
            f"{MasterConstants.CALENDAR_FORWARD}."
        )
    return current_month, current_year


def get_month_edges(now: datetime = None, month: int = None, year: int = None) -> Tuple[datetime, datetime]:
    if now:
        beginning_of_current_month = datetime(now.year, now.month, 1)
    else:
        beginning_of_current_month = datetime(year, month, 1)
    beginning_of_next_month = beginning_of_current_month.replace(month=beginning_of_current_month.month + 1, day=1)
    return beginning_of_current_month, beginning_of_next_month


async def pick_appointment_keyboard(
    engine: AsyncEngine, logger: Logger, telegram_id: str, day: int, month: int, year: int
) -> Tuple[bool, InlineKeyboardMarkup]:
    where_clause = WhereClause(
        filter=[
            appointment_table.c.master_telegram_id == telegram_id,
            func.extract("day", appointment_table.c.datetime) == day,
            func.extract("month", appointment_table.c.datetime) == month,
            func.extract("year", appointment_table.c.datetime) == year,
        ]
    )
    appointments = await Appointment(engine=engine, logger=logger).read_appointment_info(where_clause=where_clause)
    buttons = []
    for appointment in appointments:
        slot_datetime = f"{appointment.datetime.strftime('%H:%M')}"
        if appointment.is_reserved:
            text = f"🟡{slot_datetime}"
        else:
            text = slot_datetime
        buttons.append([InlineKeyboardButton(text=text, callback_data=str(appointment.auid))])
    appointments_exist = True if appointments else False
    buttons.append([InlineKeyboardButton(text="Добавить время", callback_data=MasterConstants.CALENDAR_ADD_TIME)])
    if appointments_exist:
        buttons.append([InlineKeyboardButton(text="Удалить время", callback_data=MasterConstants.CALENDAR_DELETE_TIME)])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data=MasterConstants.BACK_TO_TIMETABLE)])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    appointments_exist = True if appointments else False
    return appointments_exist, keyboard


async def delete_appointment_keyboard(
    engine: AsyncEngine, logger: Logger, telegram_id: str, day: int, month: int, year: int
) -> Tuple[bool, InlineKeyboardMarkup]:
    where_clause = WhereClause(
        filter=[
            appointment_table.c.master_telegram_id == telegram_id,
            func.extract("day", appointment_table.c.datetime) == day,
            func.extract("month", appointment_table.c.datetime) == month,
            func.extract("year", appointment_table.c.datetime) == year,
        ]
    )
    appointments = await Appointment(engine=engine, logger=logger).read_appointment_info(where_clause=where_clause)
    buttons = []
    for appointment in appointments:
        slot_datetime = f"{appointment.datetime.strftime('%H:%M')}"
        if appointment.is_reserved:
            text = f"🟡{slot_datetime}"
        else:
            text = slot_datetime
        buttons.append(
            [
                InlineKeyboardButton(text=text, callback_data=str(appointment.auid)),
                InlineKeyboardButton(text="❌ Удалить", callback_data=str(appointment.auid))
            ]
        )
    buttons.append([InlineKeyboardButton(text="Готово", callback_data=MasterConstants.BACK_TO_DAY)])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    appointments_exist = True if appointments else False
    return appointments_exist, keyboard


def is_uuid(data: str) -> bool:
    result: bool
    try:
        # if callback type is UUID it means that button with time has been pushed
        # (dirty but, fewer db calls)
        UUID(data)
        result = True
    except ValueError:
        result = False
    return result


async def get_picked_services_and_sub_services(
    engine: AsyncEngine, logger: Logger, telegram_id: str
) -> Tuple[str, dict]:
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    picked_service = user.current_service
    picked_sub_services = user.services.get(picked_service, {})
    return picked_service, picked_sub_services


async def notify_user(text: str, telegram_id: str, logger: Logger):
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        error_message = f"Could not notify user {telegram_id}. Details: {str(exc)}"
        logger.error(error_message)
        raise CouldNotNotify(error_message)


async def cancel_appointment_and_notify_user(user: Row, logger: Logger, for_master: bool, engine: AsyncEngine):
    telegram_id = None
    if not for_master:
        appointment_to_cancel = await Appointment(engine=engine, logger=logger).read_single_appointment_info(
            auid=str(user.current_appointment)
        )
        telegram_id = str(appointment_to_cancel.client_telegram_id)
    where_clause = WhereClause(
        params=[appointment_table.c.auid],
        values=[str(user.current_appointment)],
        comparison_operators=["=="],
    )
    data_to_set = {
        "is_reserved": False,
        "client_telegram_id": None,
    }
    canceled_appointment = await Appointment(engine=engine, logger=logger).update_appointment_info(
        data_to_set=data_to_set,
        where_clause=where_clause,
        returning_values=[
            appointment_table.c.datetime,
            appointment_table.c.master_telegram_id,
            appointment_table.c.service,
        ],
    )
    telegram_id = telegram_id or str(canceled_appointment[0].master_telegram_id)
    user_info = _prepare_user_info(user=user, for_master=for_master)
    notification_text = appointment_info(
        date_and_time=canceled_appointment[0].datetime,
        user_info=user_info,
        service=canceled_appointment[0].service,
        for_master=for_master,
    )
    notification_text = "Вашу запись отменили\n" + notification_text
    await notify_user(text=notification_text, telegram_id=telegram_id, logger=logger)


def contains_telegram_markdown(text: str) -> bool:
    """
    Checks if the input text contains Telegram Markdown syntax.

    :param text: The input text to check.
    :return: True if Telegram Markdown syntax is detected, False otherwise.
    """
    return Config.TELEGRAM_MARKDOWN_PATTERN.search(text) is not None
