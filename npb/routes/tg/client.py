import re
from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import Dict, List, Tuple

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
from sqlalchemy import func, Row
from sqlalchemy.ext.asyncio import AsyncEngine

from npb.config import ClientConstants, RegistrationConstants, MasterConstants, CommonConstants
from npb.config import Config
from npb.db.api import Appointment, User
from npb.db.sa_models import appointment_table, user_table
from npb.db.utils import WhereClause, Join
from npb.db.core import engine
from npb.logger import get_logger
from npb.state_machine.client_states import Client
from npb.text.client import pick_sub_service_text, month_appointments_text, pick_time_text
from npb.tg.bot import bot
from npb.tg.models import AppointmentModel
from npb.utils.tg.client import pick_master_keyboard, pick_day_keyboard, my_appointments_keyboard, \
    count_appointments_for_client
from npb.utils.common import get_user_data, log_handler_info, master_profile_info, pick_sub_service_keyboard, \
    get_month_edges, get_picked_services_and_sub_services, get_month, _prepare_user_info, appointment_info, is_uuid, \
    notify_user, cancel_appointment_and_notify_user
from npb.utils.tg.client import pick_single_service_keyboard, pick_master_available_slots_keyboard
from npb.routes.tg.registration_form import _handle_sub_service, _handle_start_edit_phone_number, \
    _handle_start_edit_instagram_link, _handle_phone_number, _handle_start_edit_telegram_profile, \
    _handle_telegram_profile

client_router = Router()


async def _handle_service(
    callback: CallbackQuery,
    picked_service: str = None,
    picked_sub_services: Dict[str, bool] = None,
    text: str = None,
    page_number: int = None
) -> None:
    """
    Activates when client has already picked service.
    """
    logger = get_logger()
    telegram_id = str(callback.message.chat.id)
    picked_service = picked_service or callback.data
    data = {"service": picked_service, "sub_services": picked_sub_services}
    if page_number:
        data["page_number"] = page_number
    keyboard = await pick_master_keyboard(**data)
    if not page_number:  # do not update in pagination mode
        where_clause = WhereClause(
            params=[user_table.c.telegram_id],
            values=[telegram_id],
            comparison_operators=["=="]
        )
        data_to_set = {
            "current_service": picked_service,
            "current_sub_service": None,
            "services": {picked_service: {}}
        }
        await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    text = text or "Пожалуйста, выберите Мастера (или нажмите на 'Фильтр', чтобы выбрать подуслуги)"
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def _handle_pick_service(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client has already picked 'Выбрать услугу' option.
    """
    services = list(Config.MASTER_SERVICES.keys())
    keyboard = pick_single_service_keyboard(services)
    text = "Пожалуйста, выберите услугу:"
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )


async def _handle_master(callback: CallbackQuery) -> None:
    """
    Activates when client has already picked master.
    """
    data = callback.data
    logger = get_logger()
    text = await master_profile_info(logger=logger, engine=engine, telegram_id=data)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Записаться", callback_data=data
                ),
                InlineKeyboardButton(text="Назад", callback_data=ClientConstants.CANCEL),
            ]
        ]
    )
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_filter(callback: CallbackQuery) -> None:
    """
    Activates when client has already picked filter.
    """
    logger = get_logger()
    telegram_id = str(callback.message.chat.id)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    picked_service = user.current_service
    text = pick_sub_service_text
    sub_services = Config.MASTER_SERVICES[picked_service]
    keyboard = pick_sub_service_keyboard(sub_services, {}, picked_service)
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=keyboard,
    )


async def _handle_my_appointments_start(
    callback: CallbackQuery,
    logger: Logger,
    month: int = None,
    text: str = None,
    now: datetime = None,
):
    telegram_id = str(callback.message.chat.id)
    now = now or datetime.now()
    month = month or now.month
    keyboard = await my_appointments_keyboard(
        current_month=month,
        current_year=now.year,
        telegram_id=telegram_id,
        logger=logger,
        now=now,
    )
    text = text or month_appointments_text % (Config.MONTHS_MAP.get(month)[0], now.year)
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


async def _handle_pick_day(
    logger: Logger,
    current_month: int,
    current_year: int,
    telegram_id: str,
    arrows: bool = False,
    callback: CallbackQuery = None,
) -> Tuple[int, int, InlineKeyboardMarkup]:
    if arrows:
        current_month, current_year = get_month(
            action_type=callback.data, current_month=current_month, current_year=current_year
        )
    month_begin, month_end = get_month_edges(month=current_month, year=current_year)
    appointment_where_clause = WhereClause(
        params=[
            appointment_table.c.master_telegram_id,
            appointment_table.c.datetime,
            appointment_table.c.datetime,
            appointment_table.c.is_reserved,
        ],
        values=[telegram_id, month_begin, month_end, False],
        comparison_operators=["==", ">=", "<=", "=="],
    )
    appointments = await Appointment(engine=engine, logger=logger).read_appointment_info(
        where_clause=appointment_where_clause
    )
    appointments = Appointment.appointments_as_dict(appointments=appointments)
    print("DEBUG appointments: ", appointments)
    print("DEBUG current_month, current_year: ", current_month, current_year)
    keyboard = pick_day_keyboard(
        picked_month=current_month,
        picked_year=current_year,
        master_time_slots=appointments,
    )
    where_clause = WhereClause(
        params=[user_table.c.telegram_id],
        values=[telegram_id],
        comparison_operators=["=="]
    )
    data_to_set = {"current_month": int(current_month), "current_year": int(current_year)}
    await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    return current_month, current_year, keyboard


async def _handle_pick_time(
    current_month: int,
    current_year: int,
    user: Row,
    logger: Logger,
    state: FSMContext = None,
    callback: CallbackQuery = None,
    data_to_set: dict = None,
    current_day: int = None,
    text: str = None,
):
    text = text or pick_time_text % (
        current_day or callback.data, Config.MONTHS_MAP.get(current_month)[1], current_year
    )
    tz = timezone(timedelta(hours=Config.TZ_OFFSET))
    if data_to_set is not None:
        data_to_set["current_day"] = int(callback.data)
    appointment_where_clause = WhereClause(
        filter=[
            appointment_table.c.master_telegram_id == user.current_master,
            appointment_table.c.is_reserved.is_(False),
            func.extract("day", appointment_table.c.datetime) == int(current_day or callback.data),
            func.extract("month", appointment_table.c.datetime) == current_month,
            func.extract("year", appointment_table.c.datetime) == current_year,
            appointment_table.c.datetime > datetime.now(tz=tz),
        ]
    )
    appointments = await Appointment(engine=engine, logger=logger).read_appointment_info(
        where_clause=appointment_where_clause
    )
    buttons = []
    for appointment in appointments:
        slot_time = f"{appointment.datetime.strftime('%H:%M')}"
        buttons.append([InlineKeyboardButton(text=slot_time, callback_data=slot_time)])
    buttons.append([InlineKeyboardButton(text="Назад", callback_data=ClientConstants.CANCEL)])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    if state:
        await state.set_state(Client.master_calendar_time)
    return text, keyboard, data_to_set


@client_router.callback_query(F.data == ClientConstants.BACK_TO_SERVICES)
async def handle_back_to_services(callback: CallbackQuery, state: FSMContext):
    """
    Activates when user goes back from any state to pick service.
    """
    logger = get_logger()
    log_handler_info(handler_name="client.handle_back_to_services", logger=logger, callback_data=callback.data)
    await state.set_state(Client.service)
    await _handle_pick_service(callback, state=state)


@client_router.callback_query(Client.default, F.data.casefold() == ClientConstants.BECOME_MASTER)
async def handle_become_master(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.message.chat.id
    logger = get_logger()
    log_handler_info(handler_name="client.handle_become_master", logger=logger, callback_data=callback.data)
    text = CommonConstants.BECOME_MASTER % telegram_id
    await callback.message.answer(text=text)


@client_router.callback_query(Client.default, F.data.casefold() == ClientConstants.MY_APPOINTMENTS)
async def handle_my_appointments_start(callback: CallbackQuery, state: FSMContext):
    logger = get_logger()
    log_handler_info(handler_name="client.handle_my_appointments_start", logger=logger, callback_data=callback.data)
    await state.set_state(Client.appointment_info)
    await _handle_my_appointments_start(callback=callback, logger=logger)


@client_router.callback_query(
    Client.appointment_info, (F.data == ClientConstants.CANCEL) | (F.data == ClientConstants.APPOINTMENTS_BACK)
)
async def handle_my_appointments_cancel(callback: CallbackQuery, state: FSMContext):
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="client.handle_my_appointments_cancel", logger=logger, callback_data=callback.data)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    if callback.data == ClientConstants.APPOINTMENTS_BACK:  # кнопка назад
        await _handle_my_appointments_start(callback=callback, logger=logger, month=user.current_month)
    else:  # отмена записи
        await cancel_appointment_and_notify_user(user=user, logger=logger, for_master=True, engine=engine)
        now = datetime.now()
        text = f"Запись успешно отменена.\n{month_appointments_text % (Config.MONTHS_MAP.get(now.month)[0], now.year)}"
        await _handle_my_appointments_start(
            callback=callback, logger=logger, month=user.current_month, text=text, now=now
        )


@client_router.callback_query(Client.appointment_info)
async def handle_my_appointments(callback: CallbackQuery, state: FSMContext):
    logger = get_logger()
    log_handler_info(handler_name="client.handle_my_appointments", logger=logger, callback_data=callback.data)
    if callback.data == ClientConstants.ANOTHER_MONTH:
        text = "Выберите месяц:"
        buttons = []
        for month_number in range(1, 13):
            button_text = f"{Config.MONTHS_MAP.get(month_number)[0]}"
            buttons.append([InlineKeyboardButton(text=button_text, callback_data=str(month_number))])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    elif is_uuid(data=callback.data):  # user picked appointment
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
            ],
        )
        master_info = _prepare_user_info(user=appointments_and_master_info[0])
        text = appointment_info(
            date_and_time=appointments_and_master_info[0].datetime,
            user_info=master_info,
            service=appointments_and_master_info[0].service,
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Назад", callback_data=ClientConstants.APPOINTMENTS_BACK),
                    InlineKeyboardButton(text="Отменить", callback_data=ClientConstants.CANCEL)
                ]
            ]
        )
        telegram_id = str(callback.message.chat.id)
        user_where_clause = WhereClause(
            params=[user_table.c.telegram_id],
            values=[telegram_id],
            comparison_operators=["=="],
        )
        user_data_to_set = {"current_appointment": str(callback.data)}
        await User(engine=engine, logger=logger).update_user_info(
            data_to_set=user_data_to_set,
            where_clause=user_where_clause,
        )
    else:  # user picked month
        await _handle_my_appointments_start(callback=callback, logger=logger, month=int(callback.data))
        return
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


@client_router.callback_query(Client.default, F.data.casefold() == ClientConstants.PICK_SERVICE)
async def handle_pick_service(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client has already picked 'Выбрать услугу' option.
    """
    logger = get_logger()
    log_handler_info(handler_name="client.handle_pick_service", logger=logger, callback_data=callback.data)
    await state.set_state(Client.service)
    await _handle_pick_service(callback, state=state)


@client_router.callback_query(Client.service)
async def handle_service(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client has already picked service.
    """
    logger = get_logger()
    log_handler_info(handler_name="client.handle_service", logger=logger, callback_data=callback.data)
    await state.set_state(Client.master_or_filter)
    await _handle_service(callback=callback)


@client_router.callback_query(
    Client.master_or_filter,
    (F.data == ClientConstants.MASTER_BACK) | (F.data == ClientConstants.MASTER_FORWARD),
)
async def handle_master_pagination(callback: CallbackQuery, state: FSMContext) -> None:
    """Activates when client use pagination to see another masters."""
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="client.handle_master_pagination", logger=logger, callback_data=callback.data)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    current_service = user.current_service
    page_number = user.current_page or 0
    if callback.data == ClientConstants.MASTER_BACK:
        if user.current_page > 1:
            page_number = user.current_page - 1
    else:
        page_number = user.current_page + 1
    where_clause = WhereClause(params=[user_table.c.telegram_id], values=[telegram_id], comparison_operators=["=="])
    data_to_set = {"current_page": page_number}
    await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    await _handle_service(callback=callback, picked_service=current_service, page_number=page_number)


@client_router.callback_query(Client.master_or_filter)
async def handle_master_or_filter(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client has already picked master or filter.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="client.handle_master_or_filter", logger=logger, callback_data=callback.data)
    if callback.data == ClientConstants.SUB_SERVICE_FILTER:
        await state.set_state(Client.sub_service)
        user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
        all_picked_services = user.services
        current_service = user.current_service
        sub_services = Config.MASTER_SERVICES[current_service]
        keyboard = pick_sub_service_keyboard(sub_services, all_picked_services, current_service)
        text = pick_sub_service_text
        await bot.edit_message_text(
            text=text,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=keyboard,
        )
    else:
        await state.set_state(Client.master)
        await _handle_master(callback=callback)


@client_router.callback_query(Client.sub_service, F.data == RegistrationConstants.DONE_SUB_SERVICE)
async def handle_sub_service_done(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client done with picking sub services.
    """
    logger = get_logger()
    log_handler_info(handler_name="client.handle_sub_service_done", logger=logger, callback_data=callback.data)
    telegram_id = str(callback.message.chat.id)
    picked_service, picked_sub_services = await get_picked_services_and_sub_services(
        engine=engine, logger=logger, telegram_id=telegram_id
    )
    await state.set_state(Client.master_or_filter)
    await _handle_service(callback=callback, picked_service=picked_service, picked_sub_services=picked_sub_services)


@client_router.callback_query(Client.sub_service)
async def handle_sub_service(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client has already picked filter.
    """
    logger = get_logger()
    log_handler_info(handler_name="client.handle_sub_service", logger=logger, callback_data=callback.data)
    await _handle_sub_service(callback=callback, client_picks=True)


@client_router.callback_query(Client.master, F.data == ClientConstants.CANCEL)
async def handle_master_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client is going back from checking master info.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="client.handle_master_cancel", logger=logger, callback_data=callback.data)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    current_service = user.current_service
    current_page = user.current_page
    await state.set_state(Client.master_or_filter)
    await _handle_service(callback=callback, picked_service=current_service, page_number=current_page)


@client_router.callback_query(Client.master)
async def handle_make_appointment_start(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client is going to make an appointment.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="client.handle_make_appointment_start", logger=logger, callback_data=callback.data)
    master_telegram_id = callback.data
    now = datetime.now()
    month_begin, month_end = get_month_edges(now=now)
    where_clause = WhereClause(
        params=[user_table.c.telegram_id],
        values=[telegram_id],
        comparison_operators=["=="]
    )
    data_to_set = {
        "current_master": master_telegram_id,
        "current_month": now.month,
        "current_year": now.year,
        "current_day": None,
    }
    await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    appointment_where_clause = WhereClause(
        params=[
            appointment_table.c.master_telegram_id,
            appointment_table.c.datetime,
            appointment_table.c.datetime,
            appointment_table.c.is_reserved,
        ],
        values=[master_telegram_id, month_begin, month_end, False],
        comparison_operators=["==", ">=", "<=", "=="],
    )
    appointments = await Appointment(engine=engine, logger=logger).read_appointment_info(
        where_clause=appointment_where_clause
    )
    appointments = Appointment.appointments_as_dict(appointments=appointments)
    if not appointments:
        text = (
            "Извините, кажется у этого Мастера заняты все слоты на этот месяц. Попробуйте выбрать другого мастера."
        )
        picked_service, picked_sub_services = await get_picked_services_and_sub_services(
            engine=engine, logger=logger, telegram_id=telegram_id
        )
        await state.set_state(Client.master_or_filter)
        await _handle_service(
            callback=callback, picked_service=picked_service, picked_sub_services=picked_sub_services, text=text
        )
        return
    else:
        text = f"*{Config.MONTHS_MAP.get(now.month)[0]} {now.year}*\nПожалуйста, выберите день:"
        keyboard = pick_day_keyboard(picked_month=now.month, picked_year=now.year, master_time_slots=appointments)
        await state.set_state(Client.master_calendar_day)
        await bot.edit_message_text(
            text=text,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )


@client_router.callback_query(Client.master_calendar_day)
async def handle_make_appointment_pick_time(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client is going to make an appointment.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(
        handler_name="client.handle_make_appointment_pick_time", logger=logger, callback_data=callback.data
    )
    data_to_set = {}
    now = datetime.now()
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    current_month = user.current_month or now.month
    current_year = user.current_year or now.year
    where_clause = WhereClause(
        params=[user_table.c.telegram_id],
        values=[telegram_id],
        comparison_operators=["=="]
    )
    if callback.data == MasterConstants.CALENDAR_IGNORE:
        await callback.answer("Этот день невозможно выбрать. Пожалуйста, выберите другой день")
        return
    elif callback.data == MasterConstants.CALENDAR_FORWARD or callback.data == MasterConstants.CALENDAR_BACK:
        current_month, current_year, keyboard = await _handle_pick_day(
            callback=callback,
            logger=logger,
            current_month=current_month,
            current_year=current_year,
            telegram_id=user.current_master,
            arrows=True,
        )
        data_to_set.update({"current_month": int(current_month), "current_year": int(current_year)})
        text = f"*{Config.MONTHS_MAP.get(current_month)[0]} {current_year}*\nПожалуйста, выберите день:"
    else:
        text, keyboard, data_to_set = await _handle_pick_time(
            callback=callback,
            current_month=current_month,
            current_year=current_year,
            user=user,
            data_to_set=data_to_set,
            logger=logger,
            state=state,
        )
    if data_to_set:
        await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


@client_router.callback_query(Client.master_calendar_time, F.data == ClientConstants.CANCEL)
async def handle_make_appointment_time_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client is going back from choosing day.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(
        handler_name="client.handle_make_appointment_time_cancel", logger=logger, callback_data=callback.data
    )
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    text = (
        f"*{Config.MONTHS_MAP.get(user.current_month)[0]} {user.current_year}*\nПожалуйста, выберите день:"
    )
    await state.set_state(Client.master_calendar_day)
    _, _, keyboard = await _handle_pick_day(
        callback=callback,
        logger=logger,
        current_month=user.current_month,
        current_year=user.current_year,
        telegram_id=user.current_master,
    )
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )


@client_router.callback_query(
    Client.master_calendar_time,
    (F.data == ClientConstants.SPECIFY_PHONE) | (F.data == CommonConstants.EDIT_TELEGRAM_PROFILE)
)
async def handle_make_appointment_specify_contact(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when is going to specify his phone or tg profile in order to make an appointment.
    """
    logger = get_logger()
    log_handler_info(
        handler_name="client.handle_make_appointment_specify_contact", logger=logger, callback_data=callback.data
    )
    if callback.data == ClientConstants.SPECIFY_PHONE:
        await state.set_state(Client.specify_phone)
        await _handle_start_edit_phone_number(callback=callback)
    else:
        await state.set_state(Client.specify_telegram_profile)
        await _handle_start_edit_telegram_profile(callback=callback)


@client_router.message(Client.specify_phone)
async def handle_specify_phone_number(message: Message, state: FSMContext) -> None:
    """
    Activates when user is going to edit his phone number.
    """
    logger = get_logger()
    log_handler_info(handler_name="client.handle_specify_phone_number", logger=logger, message_text=message.text)
    telegram_id = str(message.chat.id)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    current_month, current_year, keyboard = await _handle_pick_day(
        logger=logger,
        current_month=user.current_month,
        current_year=user.current_year,
        telegram_id=user.current_master,
    )
    text = (
        f"Ваш номер телефона успешно сохранён!\n"
        f"{pick_time_text % (user.current_day, Config.MONTHS_MAP.get(current_month)[1], current_year)}"
    )
    _, keyboard, _ = await _handle_pick_time(
        current_month=user.current_month,
        current_year=user.current_year,
        current_day=user.current_day,
        user=user,
        logger=logger,
        text=text,
    )
    await _handle_phone_number(
        telegram_id=telegram_id,
        logger=logger,
        message=message,
        state_obj=state,
        next_state=Client.master_calendar_time,
        text=text,
        keyboard=keyboard,
    )


@client_router.message(Client.specify_telegram_profile)
async def handle_specify_telegram_profile(message: Message, state: FSMContext) -> None:
    """
    Activates when user is going to edit his telegram profile.
    """
    logger = get_logger()
    log_handler_info(handler_name="client.handle_specify_telegram_profile", logger=logger, message_text=message.text)
    telegram_id = str(message.chat.id)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    current_month, current_year, _ = await _handle_pick_day(
        logger=logger,
        current_month=user.current_month,
        current_year=user.current_year,
        telegram_id=user.current_master,
    )
    text = (
        f"Название Вашего телеграм профиля успешно сохранёно! *{user.current_day} "
        f"{pick_time_text % (user.current_day, Config.MONTHS_MAP.get(current_month)[1], current_year)}"
    )
    _, keyboard, _ = await _handle_pick_time(
        current_month=user.current_month,
        current_year=user.current_year,
        current_day=user.current_day,
        user=user,
        logger=logger,
        text=text,
    )
    await _handle_telegram_profile(
        message=message,
        next_state=Client.master_calendar_time,
        text=text,
        keyboard=keyboard,
        logger=logger,
        telegram_id=telegram_id,
        state_obj=state,
    )


@client_router.callback_query(Client.master_calendar_time)
async def handle_make_appointment_time(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client has already specified appointment time.
    """
    telegram_id = str(callback.message.chat.id)
    logger = get_logger()
    log_handler_info(handler_name="client.handle_make_appointment_time", logger=logger, callback_data=callback.data)
    keyboard = None
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    number_of_appointments = await count_appointments_for_client(
        client_telegram_id=telegram_id, master_telegram_id=user.current_master, day=user.current_day, logger=logger
    )
    if number_of_appointments >= Config.MAX_APPOINTMENTS_PER_DAY:
        text = (
            f"Вы не можете создать больше записей у этого мастера в этот день.\n\n*"
            f"{Config.MONTHS_MAP.get(user.current_month)[0]} {user.current_year}*\nПожалуйста, выберите другой день:"
        )
        await state.set_state(Client.master_calendar_day)
        _, _, keyboard = await _handle_pick_day(
            callback=callback,
            logger=logger,
            current_month=user.current_month,
            current_year=user.current_year,
            telegram_id=user.current_master,
        )
    elif not user.phone_number and not user.telegram_profile:
        text = (
            "Чтобы мастер мог с Вами связаться вам необходимо указать номер телефона или название вашего профиля в "
            "телеграм."
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Указать телефон", callback_data=ClientConstants.SPECIFY_PHONE)],
                [InlineKeyboardButton(text="Указать телеграм", callback_data=CommonConstants.EDIT_TELEGRAM_PROFILE)],
            ]
        )
    else:
        tz = timezone(timedelta(hours=Config.TZ_OFFSET))
        hour_and_minutes = callback.data.split(":")
        date_and_time = datetime(
            year=user.current_year,
            month=user.current_month,
            day=user.current_day,
            hour=int(hour_and_minutes[0]),
            minute=int(hour_and_minutes[1]),
            tzinfo=tz
        )
        appointment_where_clause = WhereClause(
            params=[appointment_table.c.master_telegram_id, appointment_table.c.datetime],
            values=[user.current_master, date_and_time],
            comparison_operators=["==", "=="],
        )
        data_to_set = {"is_reserved": True, "client_telegram_id": telegram_id, "service": user.current_service}
        updated = await Appointment(engine=engine, logger=logger).update_appointment_info(
            data_to_set=data_to_set, where_clause=appointment_where_clause
        )
        if not updated:
            text = (
                f"*{Config.MONTHS_MAP.get(user.current_month)[0]} {user.current_year}*\nИзвините, произошла ошибка при "
                f"попытке создать запись на выбранное время.\n\n*{Config.MONTHS_MAP.get(user.current_month)[0]} "
                f"{user.current_year}*\nПожалуйста, выберите другой день:"
            )
            await state.set_state(Client.master_calendar_day)
            _, _, keyboard = await _handle_pick_day(
                callback=callback,
                logger=logger,
                current_month=user.current_month,
                current_year=user.current_year,
                telegram_id=user.current_master,
            )
        else:
            master = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=user.current_master)
            master_info = _prepare_user_info(user=master)
            text = appointment_info(date_and_time=date_and_time, user=user, user_info=master_info)
            text = "Вы успешно записались! " + text
            client_info = _prepare_user_info(user=user, for_master=True)
            notification_text = appointment_info(
                date_and_time=date_and_time,
                user_info=client_info,
                service=user.current_service,
                user=user,
                for_master=True,
            )
            notification_text = "У Вас новая запись!\n" + notification_text
            await notify_user(text=notification_text, telegram_id=master.telegram_id, logger=logger)
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )
