from logging import Logger
from typing import Union, Callable

from aiogram import F
from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from nbp.config import CommonConstants, Config, RegistrationConstants
from nbp.db.api import User
from nbp.db.core import engine
from nbp.db.sa_models import user_table
from nbp.db.utils import WhereClause
from nbp.exceptions import NoTelegramUpdateObject
from nbp.logger import get_logger
from nbp.middlewares import HandlerInfoMiddleware
from nbp.state_machine.master_states import Master
from nbp.state_machine.registration_form_states import RegistrationForm
from nbp.tg.bot import bot
from nbp.utils.common import (
    edit_profile_keyboard,
    get_user_data,  # TODO:  this should be in db.utils
    handle_start_edit_name,
    log_handler_info,
    master_profile_info,
    pick_sub_service_keyboard,
)
from nbp.utils.tg.registration_form import (
    check_phone_is_correct,
    delete_service_keyboard,
    pick_service_keyboard,
)


registration_form_router = Router()
# registration_form_router.message.outer_middleware(HandlerInfoMiddleware())


async def _handle_edit_unrecognized(callback: CallbackQuery = None, message: Message = None):
    """
    Activates when user says something, that cannot be recognized.
    :param callback:
    :return:
    """
    if not callback and not message:
        raise NoTelegramUpdateObject("Neither callback nor message is specified.")
    text = (
        "Извините, я Вас не понял.\nВы находитесь в разделе редактирования профиля. Вы можете отредактировать"
        "информацию о себе нажав на соответствующую кнопку ниже. Чтобы завершить редактирование, нажмите"
        "кнопку 'Завершить'."
    )
    keyboard = edit_profile_keyboard()
    if message:
        await message.answer(text=text, reply_markup=keyboard)
    else:
        await callback.message.answer(text=text, reply_markup=keyboard)


async def _handle_pick_service(
    telegram_id: str,
    logger: Logger,
    message: Message = None,
    callback: CallbackQuery = None,
    update_current_message: bool = False,
) -> None:
    if not callback and not message:
        raise NoTelegramUpdateObject("Neither callback nor message is specified.")
    all_picked_services = await get_user_data(telegram_id=telegram_id, logger=logger, engine=engine, param="services")
    services = list(Config.MASTER_SERVICES.keys())
    keyboard = pick_service_keyboard(services, all_picked_services)
    text = "Пожалуйста, выберите предоставляемые Вами услуги из списка:"
    if message:
        await message.answer(text=text, reply_markup=keyboard)
    else:
        if update_current_message:
            await bot.edit_message_text(
                text=text,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=keyboard,
            )
        else:
            await callback.message.answer(text=text, reply_markup=keyboard)


async def _hande_service(
    telegram_id: str,
    logger: Logger,
    state_obj: FSMContext,
    next_state: State,
    text: str = None,
    callback: CallbackQuery = None,
    update_current_message: bool = False,
):
    await state_obj.set_state(next_state)
    user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
    all_picked_services = user.services
    edit_mode = user.edit_mode
    where_clause = WhereClause(
        params=[user_table.c.telegram_id],
        values=[telegram_id],
        comparison_operators=["=="]
    )
    picked_service = callback.data.lstrip("✅ ")
    text = text or f"Пожалуйста, выберите предоставляемые Вами подуслуги для услуги {picked_service} из списка:"
    if all_picked_services.get(picked_service) is None:
        all_picked_services[picked_service] = {}
    sub_services = Config.MASTER_SERVICES[picked_service]
    keyboard = pick_sub_service_keyboard(sub_services, all_picked_services, picked_service)
    data_to_set = {
        "services": all_picked_services,
        "current_service": picked_service,
        "edit_mode": edit_mode,
    }
    await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    if update_current_message:
        await bot.edit_message_text(
            text=text,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=keyboard,
        )
    else:
        await callback.message.answer(text=text, keyboard=keyboard)


async def _handle_start_edit_profile(
    message: Message = None,
    callback: CallbackQuery = None,
    update_current_message: bool = False,
    text: str = "Что Вы хотите изменить?",
) -> None:
    """
    Activates when client going to edit profile info.
    """
    if not callback and not message:
        raise NoTelegramUpdateObject("Neither callback nor message is specified.")
    keyboard = edit_profile_keyboard()
    if message:
        await message.answer(text=text, reply_markup=keyboard)
    else:
        if update_current_message:
            await bot.edit_message_text(
                text=text,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=keyboard,
            )
        else:
            await callback.message.answer(text=text, reply_markup=keyboard)


async def _handle_start_edit_phone_number(callback: CallbackQuery = None):
    """
    Activates when client going to edit phone number.
    """
    text = "Пожалуйста, введите Ваш номер телефона."
    await callback.message.answer(text=text)


async def _handle_phone_number(
    telegram_id: str,
    logger: Logger,
    state_obj: FSMContext,
    next_state: State,
    text: str = None,
    message: Message = None,
    callback: CallbackQuery = None,
    update_current_message: bool = False,
    keyboard: Union[InlineKeyboardMarkup, ReplyKeyboardMarkup] = None,
):
    if not callback and not message:
        raise NoTelegramUpdateObject("Neither callback nor message is specified.")
    phone_number = message.text.strip()
    if not check_phone_is_correct(phone_number):
        text = (
            "Некорректный номер. Ниже приведены примеры корректных номеров:\n"
            "1) 9999999999\n"
            "2) 89999999999\n"
            "3) +79999999999"
        )
        keyboard = None
    else:
        await state_obj.set_state(next_state)
        text = text or "Пожалуйста, введите название вашего профиля в instagram или нажмите 'Пропустить'."
        where_clause = WhereClause(
            params=[user_table.c.telegram_id],
            values=[telegram_id],
            comparison_operators=["=="]
        )
        keyboard = keyboard or InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data=RegistrationConstants.SKIP)]]
        )
        data_to_set = {"phone_number": phone_number}
        await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    if message:
        await message.answer(text=text, reply_markup=keyboard)
    else:
        if update_current_message:
            await bot.edit_message_text(
                text=text,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await callback.message.answer(text=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)


async def _handle_start_edit_instagram_link(callback: CallbackQuery) -> None:
    """
    Activates when client going to edit instagram link.
    """
    text = "Пожалуйста, введите название вашего профиля в instagram."
    await callback.message.answer(text=text)


async def _handle_instagram_link(
    telegram_id: str,
    logger: Logger,
    message: Message,
    state_obj: FSMContext,
    next_state: State,
    text: str = None,
    keyboard: Union[InlineKeyboardMarkup, ReplyKeyboardMarkup] = None,
) -> None:
    await state_obj.set_state(next_state)
    instagram_link = message.text  # TODO: make instagram link validation
    where_clause = WhereClause(
        params=[user_table.c.telegram_id],
        values=[telegram_id],
        comparison_operators=["=="]
    )
    data_to_set = {"instagram_link": instagram_link}
    await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    text = text or (
        "Пожалуйста, расскажите о себе в нескольких предложениях. Ниже приведен пример:\n"
        "Привет! Меня зовут Катя. Я профессионально занимаюсь маникюром и педикюром."
    )
    await message.answer(text=text, reply_markup=keyboard)


async def _handle_start_edit_description(callback: CallbackQuery) -> None:
    """
    Activates when client going to edit description.
    """
    text = (
        "Пожалуйста, расскажите о себе в нескольких предложениях. Ниже приведен пример:\n"
        "Привет! Меня зовут Катя. Я профессионально занимаюсь маникюром и педикюром."
    )
    await callback.message.answer(text=text)


async def _handle_description(
    telegram_id: str,
    logger: Logger,
    message: Message,
    state_obj: FSMContext,
    next_state: State,
    text: str = None,
    keyboard: Union[InlineKeyboardMarkup, ReplyKeyboardMarkup] = None,
) -> None:
    await state_obj.set_state(next_state)
    description = message.text
    where_clause = WhereClause(
        params=[user_table.c.telegram_id],
        values=[telegram_id],
        comparison_operators=["=="]
    )
    data_to_set = {"description": description}
    await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    text = text or "Ваша регистрация почти окончена! Хотите изменить что-нибудь?"
    await message.answer(text=text, reply_markup=keyboard)


async def _handle_name(
    telegram_id: str,
    logger: Logger,
    message: Message,
    state_obj: FSMContext,
    next_state: State,
    callback: CallbackQuery = False,
    edit_mode: bool = False,
    text: str = None,
    update_current_message: bool = False,
    keyboard: Union[InlineKeyboardMarkup, ReplyKeyboardMarkup] = None,
) -> None:
    if not callback and not message:
        raise NoTelegramUpdateObject("Neither callback nor message is specified.")
    if len(message.text) > Config.USER_NAME_MAX_LENGTH:
        text = f"Вы ввели слишком длинное имя (максимально допустимая длина: {Config.USER_NAME_MAX_LENGTH})"
        if edit_mode:
            await state_obj.set_state(RegistrationForm.edit_name)
        if callback:
            await callback.message.answer(text=text)
            await handle_start_edit_name(callback=callback)
        else:
            await message.answer(text=text)
            await handle_start_edit_name(message=message)
        return
    await state_obj.set_state(next_state)
    name = message.text
    where_clause = WhereClause(
        params=[user_table.c.telegram_id],
        values=[telegram_id],
        comparison_operators=["=="]
    )
    data_to_set = {"name": name}
    await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    if edit_mode:
        if message:
            await message.answer(text=text, reply_markup=keyboard)
        else:
            if update_current_message:
                await bot.edit_message_text(
                    text=text,
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    reply_markup=keyboard,
                )
            else:
                await callback.message.answer(text=text, reply_markup=keyboard)
    else:
        await _handle_pick_service(telegram_id=telegram_id, logger=logger, message=message)


async def _handle_sub_service(callback: CallbackQuery, client_picks: bool = False) -> None:
    """
    Activates when client has already picked a service or tries to pick another sub service (or unpick already picked
    one)
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_sub_service", logger=logger, callback_data=callback.data)
    telegram_id = str(callback.message.chat.id)
    all_picked_services = await get_user_data(telegram_id=telegram_id, logger=logger, engine=engine, param="services")
    picked_sub_service = callback.data
    picked_service = await get_user_data(
        telegram_id=telegram_id,
        logger=logger,
        engine=engine,
        param="current_service"
    )
    picked_service = picked_service.lstrip('✅ ')
    all_picked_sub_services = all_picked_services.get(picked_service)
    if all_picked_sub_services is not None:
        if all_picked_sub_services.get(picked_sub_service):
            del all_picked_services[picked_service][picked_sub_service]
        else:
            all_picked_services[picked_service][picked_sub_service] = True
    else:
        all_picked_services[picked_service] = {}
    sub_services = Config.MASTER_SERVICES[picked_service]
    keyboard = pick_sub_service_keyboard(sub_services, all_picked_services, picked_service)
    where_clause = WhereClause(
        params=[user_table.c.telegram_id],
        values=[telegram_id],
        comparison_operators=["=="]
    )
    data_to_set = {
        "services": all_picked_services,
        "current_sub_service": picked_sub_service,
    }
    await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    if client_picks:
        text = f"Пожалуйста, выберите подуслуги для услуги {picked_service} из списка:"
    else:
        text = f"Пожалуйста, выберите предоставляемые Вами подуслуги для услуги {picked_service} из списка:"
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=keyboard,
    )


@registration_form_router.message(RegistrationForm.edit_name)
async def handle_name_edit(message: Message, state: FSMContext) -> None:
    """
    Activates when user is going to edit his name.
    :param message: 
    :param state: 
    :return: 
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_name_edit", logger=logger, message_text=message.text)
    telegram_id = str(message.chat.id)
    text = "Что Вы хотите изменить?"
    keyboard = edit_profile_keyboard()
    await _handle_name(
        telegram_id=telegram_id,
        logger=logger,
        message=message,
        state_obj=state,
        next_state=RegistrationForm.edit,
        edit_mode=True,
        text=text,
        keyboard=keyboard,
    )


@registration_form_router.message(RegistrationForm.name)
async def handle_name(message: Message, state: FSMContext) -> None:
    """
    Called when user has specified his name.
    :param message: Telegram message object.
    :param state: Finite state machine object.
    :return: None.
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_name", logger=logger, message_text=message.text)
    telegram_id = str(message.chat.id)
    await _handle_name(
        telegram_id=telegram_id,
        logger=logger,
        message=message,
        state_obj=state,
        next_state=RegistrationForm.service,
    )


@registration_form_router.callback_query(RegistrationForm.service, F.data == RegistrationConstants.DONE_SERVICE)
async def handle_service_done(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client done picking services.
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_service_done", logger=logger, callback_data=callback.data)
    telegram_id = str(callback.message.chat.id)
    edit_mode = await get_user_data(telegram_id=telegram_id, logger=logger, engine=engine, param="edit_mode")
    if edit_mode == CommonConstants.EDIT_SERVICE:
        await state.set_state(RegistrationForm.edit)
        text = "Что Вы хотите изменить?"
        keyboard = edit_profile_keyboard()
        await callback.message.answer(text=text, reply_markup=keyboard)
    else:
        await state.set_state(RegistrationForm.phone_number)
        await _handle_start_edit_phone_number(callback=callback)


@registration_form_router.callback_query(RegistrationForm.service, F.data == CommonConstants.EDIT_SERVICE)
async def handle_service_delete_start(callback: CallbackQuery, state: FSMContext):
    """
    Activates when client going to delete service.
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_service_delete_start", logger=logger, callback_data=callback.data)
    telegram_id = str(callback.message.chat.id)
    services = list(Config.MASTER_SERVICES.keys())
    all_picked_services = await get_user_data(telegram_id=telegram_id, logger=logger, engine=engine, param="services")
    text = "Выберите услугу для удаления:"
    keyboard = delete_service_keyboard(services, all_picked_services)
    await state.set_state(RegistrationForm.edit_service)
    await bot.edit_message_text(
        text=text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=keyboard,
    )


@registration_form_router.callback_query(RegistrationForm.edit_service, F.data == CommonConstants.EDIT_SERVICE_DONE)
async def handle_service_delete_done(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client done deleting services.
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_service_delete_done", logger=logger, callback_data=callback.data)
    telegram_id = str(callback.message.chat.id)
    await state.set_state(RegistrationForm.service)
    await _handle_pick_service(
        telegram_id=telegram_id, logger=logger, callback=callback, update_current_message=True
    )


@registration_form_router.callback_query(RegistrationForm.edit_service)
async def handle_service_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client has picked service to delete.
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_service_delete", logger=logger, callback_data=callback.data)
    telegram_id = str(callback.message.chat.id)
    update_current_message = True
    services = list(Config.MASTER_SERVICES.keys())
    service_to_delete = callback.data.split("_")[1]
    all_picked_services = await get_user_data(telegram_id=telegram_id, logger=logger, engine=engine, param="services")
    delete_result = all_picked_services.pop(service_to_delete, None)
    if not delete_result:
        update_current_message = False
        text = "Невыбранная услуга не может быть удалена."
    else:
        text = "Выберите услугу для удаления:"
        where_clause = WhereClause(
            params=[user_table.c.telegram_id],
            values=[telegram_id],
            comparison_operators=["=="]
        )
        data_to_set = {"services": all_picked_services}
        await User(engine=engine, logger=logger).update_user_info(where_clause=where_clause, data_to_set=data_to_set)
    keyboard = delete_service_keyboard(services, all_picked_services)
    if update_current_message:
        await bot.edit_message_text(
            text=text,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=keyboard,
        )
    else:
        await callback.answer(text=text, reply_markup=keyboard)


@registration_form_router.callback_query(RegistrationForm.service)
async def handle_service(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client has already specified his name or/and picked a service.
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_service", logger=logger, callback_data=callback.data)
    telegram_id = str(callback.message.chat.id)
    await _hande_service(
        telegram_id=telegram_id,
        logger=logger,
        state_obj=state,
        next_state=RegistrationForm.sub_service,
        callback=callback,
        update_current_message=True,
    )


@registration_form_router.callback_query(RegistrationForm.sub_service, F.data == RegistrationConstants.DONE_SUB_SERVICE)
async def handle_sub_service_done(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when client done with picking sub services.
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_sub_service_done", logger=logger, callback_data=callback.data)
    telegram_id = str(callback.message.chat.id)
    await state.set_state(RegistrationForm.service)
    await _handle_pick_service(telegram_id=telegram_id, logger=logger, callback=callback, update_current_message=True)


@registration_form_router.callback_query(RegistrationForm.sub_service)
async def handle_sub_service(callback: CallbackQuery) -> None:
    """
    Activates when client has already picked a service or tries to pick another sub service (or unpick already picked
    one)
    """
    await _handle_sub_service(callback=callback)


@registration_form_router.message(RegistrationForm.phone_number)
async def handle_phone_number(message: Message, state: FSMContext) -> None:
    """
    Activates when user is already specified his phone number.
    :param message: 
    :param state: 
    :return: 
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_phone_number", logger=logger, message_text=message.text)
    telegram_id = str(message.chat.id)
    await _handle_phone_number(
        telegram_id=telegram_id,
        logger=logger,
        state_obj=state,
        next_state=RegistrationForm.instagram_link,
        text="Пожалуйста, введите название вашего профиля в instagram или нажмите 'Пропустить'.",
        message=message,
    )


@registration_form_router.message(RegistrationForm.edit_phone_number)
async def handle_phone_number_edit(message: Message, state: FSMContext) -> None:
    """
    Activates when user is going to edit his phone number.
    :param message: 
    :param state: 
    :return: 
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_phone_number_edit", logger=logger, message_text=message.text)
    telegram_id = str(message.chat.id)
    text = "Что Вы хотите изменить?"
    keyboard = edit_profile_keyboard()
    await _handle_phone_number(
        telegram_id=telegram_id,
        logger=logger,
        message=message,
        state_obj=state,
        next_state=RegistrationForm.edit,
        text=text,
        keyboard=keyboard,
    )


@registration_form_router.callback_query(RegistrationForm.instagram_link, F.data == RegistrationConstants.SKIP)
async def handle_instagram_link_skip(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when user does not want to specify his instagram link.
    :param callback: 
    :param state: 
    :return: 
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_instagram_link_skip", logger=logger, callback_data=callback.data)
    text = (
        "Пожалуйста, расскажите о себе в нескольких предложениях. Ниже приведен пример:\n"
        "Привет! Меня зовут Катя. Я профессионально занимаюсь маникюром и педикюром."
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data=RegistrationConstants.SKIP)]]
    )
    await state.set_state(RegistrationForm.description)
    await callback.message.answer(text=text, reply_markup=keyboard)


@registration_form_router.message(RegistrationForm.instagram_link)
async def handle_instagram_link(message: Message, state: FSMContext) -> None:
    """
    Activates when user has already specified his instagram link.
    :param message: 
    :param state: 
    :return: 
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_instagram_link", logger=logger, message_text=message.text)
    telegram_id = str(message.chat.id)
    await _handle_instagram_link(
        telegram_id=telegram_id,
        logger=logger,
        message=message,
        state_obj=state,
        next_state=RegistrationForm.description,
    )


@registration_form_router.message(RegistrationForm.edit_instagram_link)
async def handle_instagram_link_edit(message: Message, state: FSMContext) -> None:
    """
    Activates when user is going to edit his instagram link.
    :param message: 
    :param state: 
    :return: 
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_instagram_link_edit", logger=logger, message_text=message.text)
    telegram_id = str(message.chat.id)
    text = "Что Вы хотите изменить?"
    keyboard = edit_profile_keyboard()
    await _handle_instagram_link(
        telegram_id=telegram_id,
        logger=logger,
        message=message,
        state_obj=state,
        next_state=RegistrationForm.edit,
        text=text,
        keyboard=keyboard,
    )


@registration_form_router.callback_query(RegistrationForm.description, F.data == RegistrationConstants.SKIP)
async def handle_description_skip(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when user does not want to specify description.
    :param callback: 
    :param state: 
    :return: 
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_description_skip", logger=logger, callback_data=callback.data)
    await state.set_state(RegistrationForm.edit)
    await _handle_start_edit_profile(callback=callback)


@registration_form_router.message(RegistrationForm.description)
async def handle_description(message: Message, state: FSMContext) -> None:
    """
    Activates when user has already specified description.
    :param message: 
    :param state: 
    :return: 
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_description", logger=logger, message_text=message.text)
    telegram_id = str(message.chat.id)
    keyboard = edit_profile_keyboard()
    await _handle_description(
        telegram_id=telegram_id,
        logger=logger,
        message=message,
        state_obj=state,
        next_state=RegistrationForm.edit,
        keyboard=keyboard,
    )


@registration_form_router.message(RegistrationForm.edit_description)
async def handle_description_edit(message: Message, state: FSMContext) -> None:
    """
    Activates when user is going to edit his description.
    :param message: 
    :param state: 
    :return: 
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_description_edit", logger=logger, message_text=message.text)
    telegram_id = str(message.chat.id)
    text = "Что Вы хотите изменить?"
    keyboard = edit_profile_keyboard()
    await _handle_description(
        telegram_id=telegram_id,
        logger=logger,
        message=message,
        state_obj=state,
        next_state=RegistrationForm.edit,
        text=text,
        keyboard=keyboard,
    )


@registration_form_router.callback_query(RegistrationForm.edit)
async def handle_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Activates when user has already picked something to edit in his profile.
    :param callback: 
    :param state: 
    :return: 
    """
    logger = get_logger()
    log_handler_info(handler_name="reg_form.handle_edit", logger=logger, callback_data=callback.data)
    keyboard = None
    data = callback.data
    telegram_id = str(callback.message.chat.id)
    where_clause = WhereClause(
        params=[user_table.c.telegram_id],
        values=[telegram_id],
        comparison_operators=["=="]
    )
    match data:
        case CommonConstants.EDIT_NAME:
            data_to_set = {"edit_mode": data}
            await User(engine=engine, logger=logger).update_user_info(
                where_clause=where_clause, data_to_set=data_to_set
            )
            await state.set_state(RegistrationForm.edit_name)
            await handle_start_edit_name(callback=callback)
        case CommonConstants.EDIT_SERVICE:
            data_to_set = {"edit_mode": data}
            await User(engine=engine, logger=logger).update_user_info(
                where_clause=where_clause, data_to_set=data_to_set
            )
            await state.set_state(RegistrationForm.service)
            await _handle_pick_service(
                telegram_id=telegram_id,
                logger=logger,
                callback=callback,
                update_current_message=True,
            )
        case CommonConstants.EDIT_PHONE_NUMBER:
            data_to_set = {"edit_mode": data}
            await User(engine=engine, logger=logger).update_user_info(
                where_clause=where_clause, data_to_set=data_to_set
            )
            await state.set_state(RegistrationForm.edit_phone_number)
            await _handle_start_edit_phone_number(callback=callback)
        case CommonConstants.EDIT_INSTAGRAM:
            data_to_set = {"edit_mode": data}
            await User(engine=engine, logger=logger).update_user_info(
                where_clause=where_clause, data_to_set=data_to_set
            )
            await state.set_state(RegistrationForm.edit_instagram_link)
            await _handle_start_edit_instagram_link(callback=callback)
        case CommonConstants.EDIT_DESCRIPTION:
            data_to_set = {"edit_mode": data}
            await User(engine=engine, logger=logger).update_user_info(
                where_clause=where_clause, data_to_set=data_to_set
            )
            await state.set_state(RegistrationForm.edit_description)
            await _handle_start_edit_description(callback=callback)
        case CommonConstants.FINISH_FORM:
            user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
            data_to_set = {"edit_mode": None, "fill_reg_form": True, "state": Master.default.state}
            profile_info = await master_profile_info(user=user)
            if user.fill_reg_form:
                text = f"Все отредактированные данные будут сохранены.\nВаш профиль ⬇️\n\n{profile_info}"
            else:
                if not user.name or not user.services:
                    text = (
                        "Невозможно завершить регистрацию: Не заполнено одно из обязательных полей: *имя*, *услуги*. "
                        "Пожалуйста, заполните все обязательные поля и нажмите 'Завершить'."
                    )
                    keyboard = edit_profile_keyboard()
                else:
                    text = (
                        f"Поздравляем! Регистрация успешно окончена! Ваш профиль ⬇️\n\n{profile_info}"
                    )
            await User(engine=engine, logger=logger).update_user_info(
                where_clause=where_clause, data_to_set=data_to_set
            )
            await callback.message.answer(text=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        case _:
            await _handle_edit_unrecognized(callback=callback)


@registration_form_router.message(RegistrationForm.edit)
async def handle_edit(message: Message) -> None:
    """
    Activates when user writes something in chat during 'RegistrationForm.edit' mode.
    :param message:
    :return:
    """
    await _handle_edit_unrecognized(message=message)
