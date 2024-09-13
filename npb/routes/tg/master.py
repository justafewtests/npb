from copy import deepcopy
from datetime import datetime, timedelta, timezone
from logging import Logger
from pprint import pprint
import time
import traceback
from uuid import UUID

from aiogram import F
from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from asyncpg.exceptions import NotNullViolationError
from sqlalchemy import Row, func
from sqlalchemy.exc import IntegrityError

from npb.config import MasterConstants
from npb.config import Config
from npb.db.api import Appointment, User
from npb.db.sa_models import appointment_table, user_table
from npb.db.utils import WhereClause, Join
from npb.db.core import engine
from npb.logger import get_logger
from npb.text.master import pick_one_or_more_days_text, pick_day_to_check_timetable_text, wrong_time_format_text
from npb.utils.common import (
    delete_appointment_keyboard,
    edit_profile_keyboard,
    get_month_edges,
    get_user_data,
    handle_start_edit_name,
    log_handler_info,
    master_profile_info,
    pick_appointment_keyboard, _prepare_user_info, appointment_info, notify_user, cancel_appointment_and_notify_user,
)
from npb.utils.tg.master import filled_registration_form, edit_month_calendar, handle_start_registration, \
    update_appointment_with_collision_check, appointments_per_period
from npb.state_machine.master_states import Master
from npb.state_machine.registration_form_states import RegistrationForm
from npb.tg.bot import bot
from npb.tg.models import AppointmentList, AppointmentModel
from npb.utils.common import get_month
from npb.utils.common import is_uuid
from npb.exceptions import NoTelegramUpdateObject


master_router = Router()


async def _handle_my_timetable(
    callback: CallbackQuery,
    next_state: State = None,
    edit_mode: str = None,
    year: int = None,
    month: int = None,
    as_message: bool = False,
) -> None:
    """
    Activates when master is going to check OR edit his timetable.
    """
    logger = get_logger()
    log_handler_info(handler_name="master._handle_timetable", logger=logger, callback_data=callback.data)
    telegram_id = str(callback.message.chat.id)
    if not year or not month:
        now = datetime.now()  # TODO: specify timezone
    else:
        now = datetime(year=year, month=month, day=1)
    month_begin, month_end = get_month_edges(now=now)
    appointment_where_clause = WhereClause(
        params=[appointment_table.c.master_telegram_id, appointment_table.c.datetime, appointment_table.c.datetime],
        values=[telegram_id, month_begin, month_end],
        comparison_operators=["==", ">=", "<="],
    )
    appointments = await Appointment(engine=engine, logger=logger).read_appointment_info(
        where_clause=appointment_where_clause
    )
    appointments = Appointment.appointments_as_dict(appointments=appointments)
    calendar, _ = await edit_month_calendar(
        current_calendar={},
        picked_month=now.month,
        picked_year=now.year,
        appointments=appointments,
        edit_mode=edit_mode,
    )
    user_where_clause = WhereClause(
        params=[user_table.c.telegram_id],
        values=[telegram_id],
        comparison_operators=["=="],
    )
    data_to_set = {
        "current_month": now.month,
        "current_year": now.year,
        "current_calendar": {},
        "state": next_state.state,
        "edit_mode": edit_mode,
    }
    await User(engine=engine, logger=logger).update_user_info(where_clause=user_where_clause, data_to_set=data_to_set)
    text = f"*{Config.MONTHS_MAP.get(now.month)[0]} {now.year}*"
    if edit_mode:
        text += pick_one_or_more_days_text
    else:
        text += pick_day_to_check_timetable_text
    if as_message:
        await callback.message.answer(
            text=text,
            reply_markup=calendar,
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await bot.edit_message_text(
            text=text,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=calendar,
            parse_mode=ParseMode.MARKDOWN,
        )


async def _handle_day_check(callback: CallbackQuery = None, message: Message = None, text_prefix: str = None) -> None:
    """
    Activates when master is going to check a day.
    """
    if not callback and not message:
        raise NoTelegramUpdateObject("Neither callback nor message is specified.")
    if message:
        telegram_id = str(message.chat.id)
    else:
        telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    appointments_exist, keyboard = await pick_appointment_keyboard(
        engine=engine,
        logger=logger,
        telegram_id=telegram_id,
        day=user.current_day,
        month=user.current_month,
        year=user.current_year,
    )
    if appointments_exist:
        text = f"Ваши слоты на {user.current_day} {Config.MONTHS_MAP.get(user.current_month)[1]} {user.current_year}"
    else:
        text = (
            f"Кажется у вас нет слотов на {user.current_day} {Config.MONTHS_MAP.get(user.current_month)[1]} "
            f"{user.current_year}. Хотите добавить время?"
        )
    text = text_prefix + text if text_prefix else text
    if message:
        await message.answer(text=text, reply_markup=keyboard)
    else:
        await bot.edit_message_text(
            text=text,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=keyboard,
        )


async def _handle_time_slot_check(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to check a time.
    """
    logger = get_logger()
    telegram_id = str(callback.message.chat.id)

    where_clause = WhereClause(params=[user_table.c.telegram_id], values=[telegram_id], comparison_operators=["=="])
    data_to_set = {"current_appointment": callback.data}
    await User(engine=engine, logger=logger).update_user_info(data_to_set=data_to_set, where_clause=where_clause)

    appointment = await Appointment(engine=engine, logger=logger).read_single_appointment_info(auid=callback.data)
    day = appointment.datetime.day
    month = appointment.datetime.month
    year = appointment.datetime.year
    hour = appointment.datetime.hour
    minutes = appointment.datetime.minute
    date_and_time = f"{day} {Config.MONTHS_MAP[month][1]} {year} {hour}:{minutes}"
    if appointment:
        if not appointment.is_reserved:
            text = f"На {date_and_time} еще никто не записан."
            await callback.answer(text=text)
        else:
            appointment_where_clause = WhereClause(
                params=[appointment_table.c.auid],
                values=[callback.data],
                comparison_operators=["=="],
            )
            join_data = Join(
                right_table=user_table,
                on_clause_param=appointment_table.c.client_telegram_id,
                on_clause_value=user_table.c.telegram_id,
                on_clause_operator="==",
            )
            appointments_and_client_info = await Appointment(engine=engine, logger=logger).read_appointment_info(
                where_clause=appointment_where_clause,
                join_data=join_data,
                selectables=[
                    user_table.c.telegram_profile,
                    user_table.c.phone_number,
                    appointment_table.c.service,
                    appointment_table.c.datetime,
                    appointment_table.c.auid,
                ],
            )
            client_info = _prepare_user_info(user=appointments_and_client_info[0], for_master=True)
            text = appointment_info(
                date_and_time=appointments_and_client_info[0].datetime,
                user_info=client_info,
                service=appointments_and_client_info[0].service,
                for_master=True,
            )
            text = f"На это время есть запись.\n{text}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Изменить время", callback_data=MasterConstants.EDIT_TIME)],
                    [InlineKeyboardButton(text="Отменить запись", callback_data=MasterConstants.CANCEL_APPOINTMENT)],
                    [InlineKeyboardButton(text="Назад", callback_data=MasterConstants.BACK_TO_TIME)],
                ]
            )
            user_where_clause = WhereClause(
                params=[user_table.c.telegram_id],
                values=[telegram_id],
                comparison_operators=["=="],
            )
            data_to_set = {
                "current_appointment": str(appointments_and_client_info[0].auid),
                "state": Master.edit_time.state,
            }
            await User(engine=engine, logger=logger).update_user_info(
                data_to_set=data_to_set,
                where_clause=user_where_clause,
            )
            await bot.edit_message_text(
                text=text,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
            )
    else:
        logger.warning(f"Requested appointment {callback.data} was not found.")
        text = f"Ошибка! Запись {callback.data} не найдена."
        await callback.answer(text=text)


async def _handle_time_slot_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to delete a time slot.
    """
    logger = get_logger()
    telegram_id = str(callback.message.chat.id)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    appointment_exists, keyboard = await delete_appointment_keyboard(
        engine=engine,
        logger=logger,
        telegram_id=telegram_id,
        day=user.current_day,
        month=user.current_month,
        year=user.current_year,
    )
    if appointment_exists:
        text = "Пожалуйста, выберите время для удаления."
    else:
        text = "Кажется у Вас нет ни одного слота, который можно было бы удалить."
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_day_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to go back from checking day.
    """
    text = "Пожалуйста, Введите время *начала сеанса* в формате *ЧЧ:ММ*. Например, *13:30*."
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=MasterConstants.BACK_TO_TIMETABLE)]]
    )
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def _handle_time_add_or_edit(message: Message, edit_mode: bool = False, state: FSMContext = None) -> None:
    """
    Activates when master has specified a slot time.
    """
    logger = get_logger()
    telegram_id = str(message.chat.id)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    tz = timezone(timedelta(hours=Config.TZ_OFFSET))  # TODO: how do i properly get this timezone? ask from a user?
    try:
        assert len(message.text) == 5
        slot_time = datetime.strptime(message.text, "%H:%M")
    except (ValueError, AssertionError) as err:
        logger.error(f"Unacceptable datetime. Details: {traceback.format_exception(err)}")
        text = wrong_time_format_text
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=MasterConstants.BACK_TO_DAY)]]
        )
        await message.answer(text=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        date_and_time = datetime(
            day=user.current_day,
            year=user.current_year,
            month=user.current_month,
            hour=slot_time.hour,
            minute=slot_time.minute,
            tzinfo=tz,
        )
        appointment_data = AppointmentModel(datetime=date_and_time, master_telegram_id=telegram_id)  # TODO: do i need to check if this is a master?
        try:
            if edit_mode:
                old_appointment, new_appointment = await update_appointment_with_collision_check(
                    date_and_time=date_and_time, logger=logger, user=user
                )
                old_appointment_datetime = old_appointment.datetime.strftime("%d.%m.%Y %H:%M")  # noqa
            else:
                new_appointment = await Appointment(engine=engine, logger=logger).create_appointment(
                    appointment=appointment_data
                )
                old_appointment_datetime = None
            new_appointment_datetime = new_appointment[0].datetime.strftime("%d.%m.%Y %H:%M")
        except IntegrityError as exc:
            logger.error(f"Error during appointment creation: {str(exc)}")
            text = (
                f"Введенное время ({date_and_time.day} {Config.MONTHS_MAP[date_and_time.month][1]} "
                f"{date_and_time.year} {date_and_time.hour}:{date_and_time.minute}) уже существует."
                f"Пожалуйста, введите другое время."
            )
        else:
            if edit_mode and state:
                await state.set_state(Master.edit_day)
            if edit_mode:
                text = "Время успешно изменено!"
                master = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
                master_info = _prepare_user_info(user=master)
                notification_text = appointment_info(
                    date_and_time=date_and_time,
                    user_info=master_info,
                    service=new_appointment[0].service,
                    for_master=False,
                )
                notification_text = (
                    f"Время вашей записи {old_appointment_datetime} было изменено на {new_appointment_datetime}\n" +
                    notification_text + "\nОтменить запись можно в разделе 'Мои записи'."
                )
                await notify_user(
                    text=notification_text, telegram_id=new_appointment[0].client_telegram_id, logger=logger
                )
            else:
                text = "Время успешно добавлено в расписание!"
        await message.answer(text=text, parse_mode=ParseMode.MARKDOWN)
        await _handle_day_check(message=message)


@master_router.callback_query(Master.default, F.data == MasterConstants.MY_PROFILE)
async def handle_my_profile(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master has already picked 'Мой профиль'.
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_my_profile", logger=logger, callback_data=callback.data)
    telegram_id = str(callback.message.chat.id)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    if not filled_registration_form(user=user):
        await handle_start_registration(callback=callback, state=state)  # TODO: can i do this check via middleware?
    else:
        text = await master_profile_info(user=user)
        await callback.message.answer(text=text, parse_mode=ParseMode.MARKDOWN)


@master_router.callback_query(Master.default, F.data == MasterConstants.EDIT_PROFILE)
async def handle_edit_profile(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master has already picked 'Редактировать профиль'.
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_edit_profile", logger=logger, callback_data=callback.data)
    telegram_id = str(callback.message.chat.id)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    if not filled_registration_form(user=user):
        await handle_start_registration(callback=callback, state=state)  # TODO: can i do this check via middleware?
    else:
        await state.set_state(RegistrationForm.edit)
        keyboard = edit_profile_keyboard()
        text = "Что Вы хотите изменить?"
        await callback.message.answer(text=text, reply_markup=keyboard)


@master_router.callback_query(Master.default, F.data == MasterConstants.MY_TIMETABLE)
async def handle_my_timetable(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to check his timetable.
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_my_timetable", logger=logger, callback_data=callback.data)
    await _handle_my_timetable(callback=callback, next_state=Master.edit_timetable, edit_mode=None)


@master_router.callback_query(Master.edit_timetable, F.data == MasterConstants.EDIT_TIMETABLE)
async def handle_edit_timetable_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to edit his timetable.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="master.handle_edit_timetable_start", logger=logger, callback_data=callback.data)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    await _handle_my_timetable(
        callback=callback,
        next_state=Master.edit_timetable,
        edit_mode="1",
        year=user.current_year,
        month=user.current_month,
    )


@master_router.callback_query(Master.edit_timetable, F.data == MasterConstants.BACK_TO_TIMETABLE)
async def handle_edit_timetable_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to go back from checking day OR go back from editing timetable.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="master.handle_edit_timetable_cancel", logger=logger, callback_data=callback.data)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    await _handle_my_timetable(
        callback=callback,
        next_state=Master.edit_timetable,
        edit_mode=None,
        year=user.current_year,
        month=user.current_month,
    )


@master_router.callback_query(Master.edit_timetable, F.data == MasterConstants.CALENDAR_ADD_TIME_BULK)
async def handle_edit_timetable_bulk_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to edit multiple days by adding time to each one.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="master.handle_edit_timetable_bulk_start", logger=logger, callback_data=callback.data)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    text = None
    go_back_to_pick_day = False
    current_calendar = user.current_calendar
    current_year = str(user.current_year)
    current_month = str(user.current_month)
    days = list(current_calendar.get(current_year, {}).get(current_month, {}).keys())
    if days:
        number_of_appointments = await appointments_per_period(
            telegram_id=telegram_id, engine=engine, logger=logger, month=user.current_month
        )
        if len(days) + number_of_appointments > Config.MAX_APPOINTMENTS_PER_MONTH:
            go_back_to_pick_day = True
            text = f"Ваш лимит слотов превышен, пожалуйста, обратитесь к администратору {Config.ADMIN_TG}."
        else:
            await state.set_state(Master.edit_timetable_bulk)
            await _handle_day_edit(callback=callback, state=state)
    else:
        go_back_to_pick_day = True
        text = "Вы не выбрали ни одного дня"
    if go_back_to_pick_day:
        await callback.message.answer(text=text)
        await _handle_my_timetable(
            callback=callback,
            next_state=Master.edit_timetable,
            edit_mode="1",
            year=user.current_year,
            month=user.current_month,
            as_message=True,
        )


@master_router.callback_query(Master.edit_timetable_bulk, F.data == MasterConstants.BACK_TO_TIMETABLE)
async def handle_edit_timetable_bulk_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to edit multiple days by adding time to each one.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="master.handle_edit_timetable_bulk_cancel", logger=logger, callback_data=callback.data)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    await _handle_my_timetable(
        callback=callback,
        next_state=Master.edit_timetable,
        edit_mode="1",
        year=user.current_year,
        month=user.current_month,
    )


@master_router.message(Master.edit_timetable_bulk)
async def handle_edit_timetable_bulk(message: Message, state: FSMContext) -> None:
    """
    Activates when master is going to edit multiple days by adding time to each one.
    """
    telegram_id = str(message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="master.master.handle_edit_timetable_bulk", logger=logger, message_text=message.text)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    tz = timezone(timedelta(hours=Config.TZ_OFFSET))  # TODO: how do i properly get this timezone? ask from a user?
    appointments = []
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=MasterConstants.BACK_TO_TIMETABLE)]]
    )
    try:
        assert len(message.text) == 5
        slot_time = datetime.strptime(message.text, "%H:%M")
    except (ValueError, AssertionError) as err:
        logger.error(f"Unacceptable datetime. Details: {traceback.format_exception(err)}")
        text = wrong_time_format_text
        await message.answer(text=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return
    else:
        current_calendar = user.current_calendar
        current_year = str(user.current_year)
        current_month = str(user.current_month)
        for day in current_calendar[current_year][current_month]:  # maximum 31
            date_and_time = datetime(
                day=int(day),
                year=user.current_year,
                month=user.current_month,
                hour=slot_time.hour,
                minute=slot_time.minute,
                tzinfo=tz,
            )
            appointments.append(AppointmentModel(datetime=date_and_time, master_telegram_id=telegram_id))
        appointments = AppointmentList(appointment_list=appointments)
    try:
        await Appointment(engine=engine, logger=logger).create_appointment(appointments)
    except IntegrityError as exc:
        logger.error(f"Error during appointment creation: {str(exc)}")
        text = (
            "Не удалось добавить указанное время в выбранные дни, так как это время уже занято в одном или нескольких "
            "из указанных дней. Пожалуйста, введите другое время или нажмите 'Назад' и выберите другой диапазон дней, "
            "так, чтобы указанное время не было занято ни одним из выбранных дней."
        )
    else:
        text = "Указанное время успешно добавлено в выбранные дни!"
    log_handler_info(handler_name="master.DEBUG keyboard: ", logger=logger, message_text=message.text)
    await message.answer(text=text, reply_markup=keyboard)


@master_router.callback_query(Master.edit_timetable)
async def handle_edit_timetable(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is editing his timetable.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="master.handle_edit_timetable", logger=logger, callback_data=callback.data)
    # TODO: refactooooooooooooooooooooooOOOOOOOOOOOOOOOoooooooooor!
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    where_clause = WhereClause(
        params=[user_table.c.telegram_id],
        values=[telegram_id],
        comparison_operators=["=="]
    )
    edit_mode = user.edit_mode
    current_month = user.current_month or datetime.now().month
    current_year = user.current_year or datetime.now().year
    data_to_set = {"current_month": current_month, "current_year": current_year}
    current_calendar = {}
    if callback.data == MasterConstants.CALENDAR_IGNORE:
        await callback.answer("Невозможно выбрать эту дату.", reply_markup=user.current_calendar)
        return
    elif callback.data == MasterConstants.CALENDAR_BACK or callback.data == MasterConstants.CALENDAR_FORWARD:
        current_month, current_year = get_month(
            action_type=callback.data, current_month=current_month, current_year=current_year
        )
        month_begin, month_end = get_month_edges(month=current_month, year=current_year)
        appointment_where_clause = WhereClause(
            params=[appointment_table.c.master_telegram_id, appointment_table.c.datetime, appointment_table.c.datetime],
            values=[telegram_id, month_begin, month_end],
            comparison_operators=["==", ">=", "<="],
        )
        appointments = await Appointment(engine=engine, logger=logger).read_appointment_info(
            where_clause=appointment_where_clause
        )
        appointments = Appointment.appointments_as_dict(appointments=appointments)
        calendar, current_calendar = await edit_month_calendar(
            picked_month=current_month,
            picked_year=current_year,
            current_calendar={},
            edit_mode=edit_mode,
            appointments=appointments,
        )
        data_to_set.update(
            {
                "current_month": int(current_month),
                "current_year": int(current_year),
                "current_calendar": current_calendar,
            }
        )
    elif callback.data == MasterConstants.CALENDAR_MON_FRI or callback.data == MasterConstants.CALENDAR_WEEKEND:
        calendar, current_calendar = await edit_month_calendar(
            picked_month=current_month,
            picked_year=current_year,
            current_calendar={},
            week_part=callback.data,
            edit_mode=edit_mode,
        )
        data_to_set = {"current_calendar": current_calendar}
    elif callback.data == MasterConstants.CALENDAR_WHOLE:
        calendar, current_calendar = await edit_month_calendar(
            picked_month=current_month, picked_year=current_year, current_calendar={}, whole=True, edit_mode=edit_mode,
        )
        data_to_set = {"current_calendar": current_calendar}
    elif callback.data == MasterConstants.CALENDAR_DROP:
        # we use str() because JSON keys are stored as strings:
        print(f"DEBUG: ", user.current_calendar)
        if not user.current_calendar.get(str(current_year), {}).get(str(current_month)):
            await callback.answer(text="Вы ещё не выбрали ни одного дня")
            return
        calendar, _ = await edit_month_calendar(
            picked_month=current_month, picked_year=current_year, current_calendar={}, drop=True, edit_mode=edit_mode,
        )
        data_to_set = {"current_calendar": {}}
    else:
        if not edit_mode:
            data_to_set.update({"current_day": int(callback.data), "state": Master.edit_day.state})
            await User(engine=engine, logger=logger).update_user_info(
                where_clause=where_clause,
                data_to_set=data_to_set,
            )
            await _handle_day_check(callback=callback)
            return
        calendar, current_calendar = await edit_month_calendar(
            picked_day=callback.data,
            picked_month=current_month,
            picked_year=current_year,
            current_calendar=deepcopy(user.current_calendar),
            edit_mode=edit_mode,
        )
        data_to_set = {"current_calendar": current_calendar}
    if user.current_calendar == current_calendar:
        del data_to_set["current_calendar"]  # update calendar only if it was changed
        if data_to_set:
            await User(engine=engine, logger=logger).update_user_info(
                where_clause=where_clause,
                data_to_set=data_to_set
            )
            # if calendar was the only thing to update and it did not change - do not update at all
        await callback.answer(text="Вы уже выбрали эту опцию.")
    else:
        await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
        text = f"*{Config.MONTHS_MAP.get(current_month)[0]} {current_year}*"
        if edit_mode:
            text += pick_one_or_more_days_text
        else:
            text += pick_day_to_check_timetable_text
        pprint(calendar)
        if user.current_calendar == current_calendar:
            await callback.answer(text="Вы уже выбрали эту опцию.")
        else:
            await bot.edit_message_text(
                text=text,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=calendar,
                parse_mode=ParseMode.MARKDOWN
            )


@master_router.callback_query(Master.edit_day, F.data == MasterConstants.CALENDAR_ADD_TIME)
async def handle_day_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to add time.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="master.handle_day_edit", logger=logger, callback_data=callback.data)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    current_day = user.current_day
    number_of_appointments = await appointments_per_period(
        telegram_id=telegram_id, engine=engine, logger=logger, day=current_day
    )
    if number_of_appointments + 1 > Config.MAX_TIME_SLOTS_PER_DAY:
        text = (
            f"Достигнут лимит слотов в день, пожалуйста, обратитесь к администратору {Config.ADMIN_TG}."
        )
        await callback.message.answer(text=text)
    else:
        await _handle_day_edit(callback=callback, state=state)


@master_router.callback_query(Master.edit_day, F.data == MasterConstants.BACK_TO_DAY)
async def handle_day_edit_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to go back from adding .
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_day_edit_cancel", logger=logger, callback_data=callback.data)
    await _handle_day_check(callback=callback)


@master_router.callback_query(Master.edit_day, F.data == MasterConstants.BACK_TO_TIMETABLE)
async def handle_day_check_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to go back from checking day OR go back from editing timetable.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="master.handle_day_cancel", logger=logger, callback_data=callback.data)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    await _handle_my_timetable(
        callback=callback,
        next_state=Master.edit_timetable,
        edit_mode=None,
        year=user.current_year,
        month=user.current_month,
    )


@master_router.callback_query(Master.edit_day, F.data == MasterConstants.CALENDAR_DELETE_TIME)
async def handle_time_slot_delete_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to delete a time slot.
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_time_slot_delete_start", logger=logger, callback_data=callback.data)
    await state.set_state(Master.delete_time)
    await _handle_time_slot_delete(callback=callback, state=state)


@master_router.callback_query(Master.edit_day)
async def handle_day_check(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to check a day.
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_day_check", logger=logger, callback_data=callback.data)
    if is_uuid(callback.data):
        # if callback type is UUID it means that button with time has been pushed
        # (dirty but, fewer db calls)
        await _handle_time_slot_check(callback=callback, state=state)
    else:
        await _handle_day_check(callback=callback)


@master_router.message(Master.edit_day)
async def handle_day_add_time(message: Message, state: FSMContext) -> None:
    """
    Activates when master has specified a slot time.
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_day_add_time", logger=logger, message_text=message.text)
    await _handle_time_add_or_edit(message=message, edit_mode=False)


@master_router.callback_query(Master.delete_time, F.data == MasterConstants.BACK_TO_DAY)
async def handle_time_slot_delete_done(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is done deleting a time slot.
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_time_slot_delete_done", logger=logger, callback_data=callback.data)
    await state.set_state(Master.edit_day)
    await _handle_day_check(callback=callback)


@master_router.callback_query(Master.delete_time)
async def handle_time_slot_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to delete a time slot.
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_time_slot_delete", logger=logger, callback_data=callback.data)
    where_clause = WhereClause(
        params=[appointment_table.c.auid],
        values=[callback.data],
        comparison_operators=["=="],
    )
    join_data = Join(
        right_table=user_table,
        on_clause_param=appointment_table.c.master_telegram_id,
        on_clause_value=user_table.c.telegram_id,
        on_clause_operator="==",
    )
    appointments_and_master_info = await Appointment(engine=engine, logger=logger).read_appointment_info(
        where_clause=where_clause,
        join_data=join_data,
        selectables=[
            user_table.c.telegram_profile,
            user_table.c.name,
            user_table.c.services,
            user_table.c.phone_number,
            user_table.c.instagram_link,
            user_table.c.description,
            appointment_table.c.service,
            appointment_table.c.datetime,
            appointment_table.c.client_telegram_id,
        ],
    )
    appointments_and_master_info = appointments_and_master_info[0]
    if appointments_and_master_info.client_telegram_id:
        master_info = _prepare_user_info(user=appointments_and_master_info)
        notification_text = appointment_info(
            date_and_time=appointments_and_master_info.datetime,
            user_info=master_info,
            service=appointments_and_master_info.service,
            for_master=False,
        )
        notification_text = "Вашу запись отменили\n" + notification_text
        await notify_user(
            text=notification_text, telegram_id=appointments_and_master_info.client_telegram_id, logger=logger
        )
    await Appointment(engine=engine, logger=logger).delete_appointment(auid=callback.data)
    await _handle_time_slot_delete(callback=callback, state=state)


@master_router.callback_query(Master.edit_time, F.data == MasterConstants.EDIT_TIME)
async def handle_time_slot_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to edit existing time slot.
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_time_slot_start", logger=logger, callback_data=callback.data)
    text = "Пожалуйста, Введите новое время *начала сеанса* в формате *ЧЧ:ММ*. Например, *13:30*."
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=MasterConstants.BACK_TO_TIME)]]
    )
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


@master_router.callback_query(
    Master.edit_time,
    (F.data == MasterConstants.BACK_TO_TIME) | (F.data == MasterConstants.CANCEL_APPOINTMENT),
)
async def handle_time_slot_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master has canceled appointment or pressed 'Назад'.
    """
    logger = get_logger()
    telegram_id = str(callback.message.chat.id)
    log_handler_info(handler_name="master.handle_time_slot_cancel", logger=logger, callback_data=callback.data)
    await state.set_state(Master.edit_day)
    master = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    await cancel_appointment_and_notify_user(user=master, logger=logger, for_master=False, engine=engine)
    await _handle_day_check(callback=callback, text_prefix="Запись успешно отменена!\n")


@master_router.message(Master.edit_time)
async def handle_time_slot_edit(message: Message, state: FSMContext) -> None:
    """
    Activates when master has specified a slot time.
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_time_slot_edit", logger=logger, message_text=message.text)
    await _handle_time_add_or_edit(message=message, edit_mode=True, state=state)


@master_router.callback_query(Master.edit_time)
async def handle_time_slot_check(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when master is going to check a time.
    """
    logger = get_logger()
    log_handler_info(handler_name="master.handle_time_slot_check", logger=logger, callback_data=callback.data)
    await _handle_time_slot_check(callback=callback, state=state)
