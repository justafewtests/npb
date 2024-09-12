import re
from typing import Dict, List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from npb.state_machine.registration_form_states import RegistrationForm
from npb.config import CommonConstants, RegistrationConstants, Config

FINISH_FORM_BUTTON_MAP = {
    "change_name": RegistrationForm.name,
    "change_service": RegistrationForm.service,
    "change_phone_number": RegistrationForm.phone_number,
    "change_instagram": RegistrationForm.instagram_link,
    "change_description": RegistrationForm.description,
    "finish_form": RegistrationForm.default,
}


def delete_service_keyboard(
    services: List[str],
    all_picked_services: Dict[str, Dict[str, bool]]
) -> InlineKeyboardMarkup:
    """
    Form inline keyboard to delete service.
    :param services: A list of all services.
    :param all_picked_services: A map of services and sub services:
        {service_1: {sub_service_1: True, sub_service_2: True}, service_2: {sub_service_1: True, sub_service_2: True}}
    :return: Inline keyboard.
    """
    service_buttons = []
    for service in services:
        if all_picked_services.get(service, {}):
            button_text = f"✅ {service}"
            service_buttons.append(
                [
                    InlineKeyboardButton(text=button_text, callback_data=f"delete_{service}"),
                    InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_{service}"),
                ]
            )
        else:
            button_text = service
            service_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"delete_{service}")])
    service_buttons.append([InlineKeyboardButton(text="Готово", callback_data=CommonConstants.EDIT_SERVICE_DONE)])
    keyboard = InlineKeyboardMarkup(inline_keyboard=service_buttons, resize_keyboard=True)
    return keyboard


def pick_service_keyboard(
    services: List[str],
    all_picked_services: Dict[str, Dict[str, bool]]
) -> InlineKeyboardMarkup:
    """
    Form inline keyboard to pick service.
    :param services: A list of all services.
    :param all_picked_services: A map of services and sub services:
        {service_1: {sub_service_1: True, sub_service_2: True}, service_2: {sub_service_1: True, sub_service_2: True}}
    :return: Inline keyboard.
    """
    service_buttons = []
    for service in services:
        if all_picked_services and all_picked_services.get(service, {}):
            button_text = f"✅ {service}"
        else:
            button_text = service
        service_buttons.append([InlineKeyboardButton(text=button_text, callback_data=button_text)])
    service_buttons.append([InlineKeyboardButton(text="Далее", callback_data=RegistrationConstants.DONE_SERVICE)])
    service_buttons.append([InlineKeyboardButton(text="Изменить", callback_data=CommonConstants.EDIT_SERVICE)])
    keyboard = InlineKeyboardMarkup(inline_keyboard=service_buttons, resize_keyboard=True)
    return keyboard


def check_phone_is_correct(phone_number: str) -> bool:
    """
    Check that given phone number is correct.
    :param phone_number: Phone number.
    :return: True / False
    """
    if len(phone_number) == 10:
        pattern = r"[0-9]{10}"
    elif len(phone_number) == 11:
        pattern = r"[78][0-9]{10}"
    elif len(phone_number) == 12:
        pattern = r"\+[78][0-9]{10}"
    else:
        return False
    if re.match(pattern, phone_number):
        return True
    else:
        return False
