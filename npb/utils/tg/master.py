import calendar
from copy import copy
from datetime import datetime
from logging import Logger
import time
from typing import Dict, List, Tuple, Union, Literal

from aiogram import F
from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlalchemy import Row, Sequence, func
from sqlalchemy.ext.asyncio import AsyncEngine

from npb.config import MasterConstants, Config, CommonConstants
from npb.db.api import User, Appointment
from npb.db.core import engine
from npb.db.sa_models import user_table, appointment_table
from npb.db.utils import WhereClause
from npb.exceptions import NoTelegramUpdateObject
from npb.logger import get_logger
from npb.state_machine.master_states import Master
from npb.tg.bot import bot
from npb.utils.common import (
    edit_profile_keyboard,
    get_user_data,
    master_profile_info,
    pick_sub_service_keyboard,
    handle_start_edit_name,
)
from npb.utils.tg.registration_form import (
    check_phone_is_correct,
    delete_service_keyboard,
    pick_service_keyboard,
)
from npb.state_machine.registration_form_states import RegistrationForm


def filled_registration_form(user: Union[Row, None]) -> bool:
    """
    Check that master filled up the registration form.
    :param user: User as sqlalchemy Row.
    :return: bool
    """
    return True if user.fill_reg_form else False


async def handle_start_registration(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when user is going to fill up the registration form.
    :param callback: Callback object.
    :return: None.
    """
    await state.set_state(RegistrationForm.name)
    text = (
        "Кажется вы ещё не заполнили форму регистрации? Для осуществлений функций Мастера необходимо заполнить "
        "форму регистрации. Пожалуйста, ответьте на несколько вопросов."
    )
    await callback.message.answer(text=text)
    await handle_start_edit_name(callback=callback)


# TODO: ok.. i need a class here...
async def edit_month_calendar(
    picked_day: str = None,
    picked_month: int = None,
    picked_year: int = None,
    current_calendar: dict = None,
    whole: bool = False,
    drop: bool = False,
    week_part: str = None,
    appointments: Dict[int, bool] = None,
    edit_mode: str = None,
) -> Tuple[InlineKeyboardMarkup, dict]:
    # TODO: refactooooooooooooooooooooooOOOOOOOOOOOOOOOoooooooooor!
    buttons = copy(CommonConstants.WEEK_DAYS_AS_BUTTONS)
    now = datetime.now()
    picked_day = int(picked_day) if picked_day else None
    picked_month_str, picked_month_int = str(picked_month or now.month), picked_month or now.month
    picked_year_str, picked_year_int = str(picked_year or now.year), picked_year or now.year
    if not current_calendar.get(picked_year_str):
        current_calendar[picked_year_str] = {picked_month_str: {}}
    elif not current_calendar[picked_year_str].get(picked_month_str):
        current_calendar[picked_year_str][picked_month_str] = {}
    month = calendar.monthcalendar(year=picked_year_int, month=picked_month_int)  # TODO: overload monthcalendar to make it return a inline keyboard
    for week in month:
        days = []
        for day_index, day in enumerate(week):
            text = callback_data = day_as_str = str(day)
            if day == 0 or (day < now.day and picked_month_int == now.month):
                text = " "
                callback_data = MasterConstants.CALENDAR_IGNORE
            elif appointments:
                if appointments.get(day):
                    if day == picked_day:
                        text = f"🟢{day}"
                    else:
                        text = f"🟡{day}"
            elif (
                week_part == MasterConstants.CALENDAR_MON_FRI and day_index not in (5, 6) or
                week_part == MasterConstants.CALENDAR_WEEKEND and day_index in (5, 6)
            ):
                current_calendar[picked_year_str][picked_month_str][day_as_str] = True
                text = f"🟢{day}"
            elif whole:
                current_calendar[picked_year_str][picked_month_str][day_as_str] = True
                text = f"🟢{day}"
            elif drop:
                pass  # do not modify
            elif day == picked_day and day_as_str in current_calendar[picked_year_str][picked_month_str]:
                del current_calendar[picked_year_str][picked_month_str][day_as_str]
            elif day == picked_day or day_as_str in current_calendar[picked_year_str][picked_month_str]:  # TODO: just else?
                current_calendar[picked_year_str][picked_month_str][day_as_str] = True
                text = f"🟢{day}"
            days.append(InlineKeyboardButton(text=text, callback_data=callback_data))
        buttons.append(days)
    if picked_month == now.month and picked_year == now.year:
        buttons.append([InlineKeyboardButton(text="➡️", callback_data=MasterConstants.CALENDAR_FORWARD)])
    elif picked_month >= now.month + 2:
        buttons.append([InlineKeyboardButton(text="⬅️", callback_data=MasterConstants.CALENDAR_BACK)])
    else:
        buttons.append(
            [
                InlineKeyboardButton(text="⬅️", callback_data=MasterConstants.CALENDAR_BACK),
                InlineKeyboardButton(text="➡️", callback_data=MasterConstants.CALENDAR_FORWARD),
            ]
        )
    if edit_mode == "1":
        buttons.append([InlineKeyboardButton(text="Сбросить", callback_data=MasterConstants.CALENDAR_DROP)])
        buttons.append([InlineKeyboardButton(text="Выбрать весь месяц", callback_data=MasterConstants.CALENDAR_WHOLE)])
        buttons.append([InlineKeyboardButton(text="Выбрать только будни", callback_data=MasterConstants.CALENDAR_MON_FRI)])
        buttons.append(
            [InlineKeyboardButton(text="Выбрать только выходные", callback_data=MasterConstants.CALENDAR_WEEKEND)]
        )
        buttons.append([InlineKeyboardButton(text="Добавить время", callback_data=MasterConstants.CALENDAR_ADD_TIME_BULK)])
        buttons.append([InlineKeyboardButton(text="Назад", callback_data=MasterConstants.BACK_TO_TIMETABLE)])
    else:
        buttons.append([InlineKeyboardButton(text="Режим редактирования", callback_data=MasterConstants.EDIT_TIMETABLE)])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons, row_width=1)
    from pprint import pprint
    print("DEBUG current_calendar: ")
    pprint(current_calendar)
    return keyboard, current_calendar


async def update_appointment_with_collision_check(
    date_and_time: datetime, logger: Logger, user: Row
) -> Tuple[Row, Sequence[Row]]:
    where_clause = WhereClause(
        params=[appointment_table.c.datetime],
        values=[date_and_time],
        comparison_operators=["=="]
    )
    if appointments := await Appointment(engine=engine, logger=logger).read_appointment_info(
        where_clause=where_clause,
    ):
        if len(appointments) > 1:
            logger.warning(
                f"More than one appointment with same datetime found (datetime: {date_and_time})"
            )
        for appointment in appointments:
            await Appointment(engine=engine, logger=logger).delete_appointment(auid=appointment.auid)
    old_appointment = await Appointment(engine=engine, logger=logger).read_single_appointment_info(
        auid=user.current_appointment
    )
    where_clause = WhereClause(
        params=[appointment_table.c.auid],
        values=[user.current_appointment],
        comparison_operators=["=="]
    )
    data_to_set = {"datetime": date_and_time}
    new_appointments = await Appointment(engine=engine, logger=logger).update_appointment_info(
        where_clause=where_clause, data_to_set=data_to_set, return_all=True
    )
    print(f"DEBUG new appointments: {new_appointments}, old appointments: {old_appointment}")
    return old_appointment, new_appointments


async def appointments_per_period(
    telegram_id: str,
    engine: AsyncEngine,
    logger: Logger,
    day: int = None,
    month: int = None,
) -> int:
    _filter = [appointment_table.c.master_telegram_id == telegram_id]
    if day:
        _filter.append(func.extract("day", appointment_table.c.datetime) == day)
    elif month:
        _filter.append(func.extract("month", appointment_table.c.datetime) == month)
    else:
        raise ValueError("None of day or month is specified.")
    where_clause = WhereClause(filter=_filter)
    appointments = await Appointment(engine=engine, logger=logger).read_appointment_info(
        where_clause=where_clause
    )
    return len(appointments)
