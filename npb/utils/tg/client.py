import calendar
from copy import copy
from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import Dict, List, Optional, Tuple

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func

from npb.db.api import Appointment, User
from npb.db.core import engine
from npb.db.sa_models import appointment_table, user_table
from npb.db.utils import WhereClause
from npb.logger import get_logger
from npb.config import ClientConstants, CommonConstants, MasterConstants, Config
from npb.utils.common import get_month_edges


def pick_single_service_keyboard(
    services: List[str],
) -> Optional[InlineKeyboardMarkup]:
    """
    Form inline keyboard to pick one service.
    :param services: A list of all services.
        {service_1: {sub_service_1: True, sub_service_2: True}, service_2: {sub_service_1: True, sub_service_2: True}}
    :return: Inline keyboard.
    """
    service_buttons = []
    for service in services:
        service_buttons.append([InlineKeyboardButton(text=service, callback_data=service)])
    keyboard = InlineKeyboardMarkup(inline_keyboard=service_buttons, resize_keyboard=True)
    return keyboard


async def pick_master_keyboard(
    service: str,
    sub_services: Dict[str, bool] = None,
    page_number: int = 1,
) -> Optional[InlineKeyboardMarkup]:
    """
    Form inline keyboard to pick master.
    :param service: Picked service.
    :param sub_services: Picked sub services.
    :param page_number: Pagination page number.
    :return: Inline keyboard.
    """
    if not service:
        return None
    master_buttons: List[List[InlineKeyboardButton]]
    master_buttons = [[InlineKeyboardButton(text="Фильтр", callback_data=ClientConstants.SUB_SERVICE_FILTER)]]
    logger = get_logger()
    _filter = [user_table.c.services.has_key(service)]  # noqa
    if sub_services:
        for sub_service in sub_services:
            _filter.append(user_table.c.services.op("->")(service).op("->")(sub_service).is_not(None))
    _filter.append(user_table.c.name.is_not(None))
    _filter.append(user_table.c.is_master.is_(True))
    _filter.append(user_table.c.is_active.is_(True))
    _filter.append(user_table.c.seq_id >= (page_number - 1) * Config.MAX_NUMBER_OF_MASTERS_TO_SHOW + 1)
    # _filter.append(user_table.c.seq_id <= page_number * Config.MAX_NUMBER_OF_MASTERS_TO_SHOW + 1)
    where_clause = WhereClause(filter=_filter)
    # TODO: select only needed fields
    masters = await User(engine=engine, logger=logger).read_user_info(
        order_by=[user_table.c.seq_id],  # TODO: this can be slow if there are many users
        where_clause=where_clause,
        limit=Config.MAX_NUMBER_OF_MASTERS_TO_SHOW + 1,
    )
    for master in masters:
        master_buttons.append([InlineKeyboardButton(text=master.name, callback_data=master.telegram_id)])
    if len(masters) > Config.MAX_NUMBER_OF_MASTERS_TO_SHOW:
        master_buttons.pop()  # remove 1 extra master
        master_buttons.append([InlineKeyboardButton(text="➡️", callback_data=ClientConstants.MASTER_FORWARD)])
    if page_number > 1:
        if master_buttons[-1][-1].callback_data == ClientConstants.MASTER_FORWARD:
            master_buttons[-1] = [
                InlineKeyboardButton(text="⬅️", callback_data=ClientConstants.MASTER_BACK),
                InlineKeyboardButton(text="➡️", callback_data=ClientConstants.MASTER_FORWARD),
            ]
        else:
            master_buttons.append([InlineKeyboardButton(text="⬅️", callback_data=ClientConstants.MASTER_BACK)])
    master_buttons.append([InlineKeyboardButton(text="Назад", callback_data=ClientConstants.BACK_TO_SERVICES)])
    keyboard = InlineKeyboardMarkup(inline_keyboard=master_buttons, resize_keyboard=True)
    return keyboard


async def pick_master_available_slots_keyboard(
    master_id: str, logger: Logger, days: int = 30
) -> InlineKeyboardMarkup:
    """
    Form inline keyboard to pick available master slot.
    :param master_id: Master id.
    :param logger: Logger object.
    :param days: Number of days to check slots.
    :return: Inline keyboard.
    """
    tz = timezone(timedelta(hours=Config.TZ_OFFSET))
    _datetime_start = datetime.now(tz=tz)
    _datetime_end = _datetime_start + timedelta(days=days)
    where_clause = WhereClause(
        params=[
            appointment_table.c.master_telegram_id,
            appointment_table.c.is_reserved,
            appointment_table.c.datetime,
            appointment_table.c.datetime,
        ],
        values=[master_id, False, _datetime_start, _datetime_end],
        comparison_operators=["==", "==", ">", "<"]
    )
    appointment_slots = await Appointment(engine=engine, logger=logger).read_appointment_info(where_clause=where_clause)
    appointment_buttons = []
    for appointment in appointment_slots:
        slot_datetime = appointment.datetime.strftime(CommonConstants.APPOINTMENT_DATETIME_FORMAT)
        appointment_buttons.append([InlineKeyboardButton(text=slot_datetime, callback_data=slot_datetime)])
    if not appointment_slots:
        keyboard = None
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=appointment_buttons, resize_keyboard=True)
    return keyboard


def pick_day_keyboard(
    picked_month: int,
    picked_year: int,
    master_time_slots: Dict[int, bool],
) -> InlineKeyboardMarkup:
    # TODO: refactooooooooooooooooooooooOOOOOOOOOOOOOOOoooooooooor!
    buttons = copy(CommonConstants.WEEK_DAYS_AS_BUTTONS)
    now = datetime.now()
    month = calendar.monthcalendar(year=picked_year, month=picked_month)
    for week in month:
        days = []
        for day in week:
            text = f"{day}"
            callback_data = f"{text}"
            if day == 0 or (day < now.day and picked_month == now.month):
                text = " "
                callback_data = MasterConstants.CALENDAR_IGNORE
            elif master_time_slots.get(day):
                text = f"🟢{day}"
            elif not master_time_slots.get(day):  # explicit
                callback_data = MasterConstants.CALENDAR_IGNORE
            days.append(InlineKeyboardButton(text=text, callback_data=callback_data))
        buttons.append(days)
    if picked_month == now.month and picked_year == now.year:
        buttons.append([InlineKeyboardButton(text="➡️", callback_data=MasterConstants.CALENDAR_FORWARD)])
    else:
        buttons.append(
            [
                InlineKeyboardButton(text="⬅️", callback_data=MasterConstants.CALENDAR_BACK),
                InlineKeyboardButton(text="➡️", callback_data=MasterConstants.CALENDAR_FORWARD),
            ]
        )
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons, row_width=1)
    return keyboard


async def my_appointments_keyboard(
    current_month: int, current_year: int, telegram_id: str, logger: Logger, now: datetime
) -> InlineKeyboardMarkup:
    month_begin, month_end = get_month_edges(month=current_month, year=current_year)
    month_begin = max(month_begin, now)
    appointment_where_clause = WhereClause(
        params=[appointment_table.c.client_telegram_id, appointment_table.c.datetime, appointment_table.c.datetime],
        values=[telegram_id, month_begin, month_end],
        comparison_operators=["==", ">=", "<="],
    )
    appointments = await Appointment(engine=engine, logger=logger).read_appointment_info(
        where_clause=appointment_where_clause, limit=100, order_by=[appointment_table.c.datetime.desc()]  # TODO: remove order by and filter in python code
    )
    buttons = []
    for appointment in appointments:
        text = f"{appointment.datetime.strftime('%d.%m.%Y %H:%M')}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=str(appointment.auid))])
    buttons.append([InlineKeyboardButton(text="Другой месяц", callback_data=ClientConstants.ANOTHER_MONTH)])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


async def count_appointments_for_client(
    client_telegram_id: str, master_telegram_id: str, day: int, logger: Logger
) -> int:
    """
    Counts how many appointments given master has for given client (in a given day).
    :param client_telegram_id: Client telegram id.
    :param master_telegram_id: Master telegram id.
    :param day: Number of day.
    :return: Number of appointments
    """
    appointment_where_clause = WhereClause(
        filter=[
            appointment_table.c.client_telegram_id == client_telegram_id,
            appointment_table.c.master_telegram_id == master_telegram_id,
            appointment_table.c.is_reserved.is_(True),
            func.extract("day", appointment_table.c.datetime) == day,
        ]
    )
    appointments = await Appointment(engine=engine, logger=logger).read_appointment_info(
        where_clause=appointment_where_clause
    )
    # print("DEBUG: count_appointments_for_client appointments:", appointments)
    # print("DEBUG: count_appointments_for_client len(appointments):", len(appointments))
    if appointments:
        return len(appointments)
    return 0
