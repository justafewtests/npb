from os import environ

from aiogram.types import InlineKeyboardButton
from dotenv import load_dotenv
from sqlalchemy import text


load_dotenv()


class Config:
    BOT_TOKEN = "6753356362:AAG5-5TmguhZCgzmrdydBw8i117tQAkpBEc"
    SERVICE_HOST = environ.get("SERVICE_HOST", "localhost")
    SERVICE_PORT = int(environ.get("SERVICE_PORT", "8000"))
    SERVICE_WORKERS = int(environ.get("SERVICE_WORKERS", "1"))
    TELEGRAM_WEBHOOK_HOST = environ.get("TELEGRAM_WEBHOOK_HOST")
    TELEGRAM_WEBHOOK_PORT = int(environ.get("TELEGRAM_WEBHOOK_PORT", "443"))
    TELEGRAM_WEBHOOK_PATH = "/webhook"
    TELEGRAM_WEBHOOK_URL = f"https://{TELEGRAM_WEBHOOK_HOST}:{TELEGRAM_WEBHOOK_PORT}{TELEGRAM_WEBHOOK_PATH}"
    DB_DSN = environ.get("POSTGRES_DSN")
    MASTER_SERVICES = {
        "Ресницы": ["Удлинение", "Наращивание", "Ламинирование", "Биозавивка", "Коррекция", "Окрашивание"],
        "Маникюр": ["Наращивание", "Шеллак", "Кутикулы", "Классический маникюр", "Европейский маникюр",
                    "Аппаратный маникюр", "Френч", "Омбре", "Парафинотерапия", "Ремонт ногтя"],
        "Педикюр": ["Очистка", "Кутикулы", "Классический педикюр", "Аппаратный педикюр", "SPA-педикюр",
                    "Медицинский педикюр", "Омоложение стоп", "Удаление мозолей", "Парафинотерапия"]
    }
    NON_RECOGNIZED_LIMIT = 2
    MONTHS_MAP = {
        1: ("Январь", "Января"),
        2: ("Февраль", "Февраля"),
        3: ("Март", "Марта"),
        4: ("Апрель", "Апреля"),
        5: ("Май", "Мая"),
        6: ("Июнь", "Июня"),
        7: ("Июль", "Июля"),
        8: ("Август", "Августа"),
        9: ("Сентябрь", "Сентября"),
        10: ("Октябрь", "Октября"),
        11: ("Ноябрь", "Ноября"),
        12: ("Декабрь", "Декабря"),
    }
    ADMIN_TG = "@fl1p3mth3b1rd"
    TZ_OFFSET = 0
    USER_NAME_MAX_LENGTH = 50
    MAX_NUMBER_OF_MASTERS_TO_SHOW = 10
    MIN_USER_EVENT_COOLDOWN = 0.5
    FLOOD_THRESHOLD = 5
    MAX_APPOINTMENTS_PER_DAY = 2
    MAX_APPOINTMENTS_PER_MONTH = 310
    MAX_TIME_SLOTS_PER_DAY = 10
    DROP_COUNTERS_WATCHDOG_TIMEOUT = 5 * 60
    DROP_COUNTERS_WATCHDOG_THRESHOLD = 10 * 60
    BAN_THRESHOLD = 3
    CERT_PATH = environ.get("CERT_PATH", "")
    CERT_KEY_PATH = environ.get("CERT_KEY_PATH", "")
    ENVIRONMENT = environ.get("ENVIRONMENT", "test")
    FORCE_SET_WEBHOOK = environ.get("FORCE_SET_WEBHOOK", False)


class AdminConstants:
    ADD_MASTER = "admin.add_master"
    ACTIVATE_USER = "admin.activate_user"
    DEACTIVATE_USER = "admin.deactivate_user"


class ClientConstants:
    BECOME_MASTER = "client.become_master"
    CANCEL = "client.cancel"
    SPECIFY_PHONE = "client.specify_phone"
    SPECIFY_TG_PROFILE = "client.specify_tg_phone"
    BACK_TO_SERVICES = "client.back_to_services"
    MAKE_APPOINTMENT = "client.make_appointment"
    MY_APPOINTMENTS = "client.my_appointments"
    PICK_SERVICE = "client.pick_service"
    SUB_SERVICE_FILTER = "client.sub_service_filter"
    ANOTHER_MONTH = "client.another_month"
    PICK_MASTER = "client.pick_master"
    MASTER_BACK = "client.master_back"
    MASTER_FORWARD = "client.master_forward"


class MasterConstants:
    MY_PROFILE = "master.my_profile"
    EDIT_PROFILE = "master.edit_my_profile"
    MY_TIMETABLE = "master.my_timetable"
    EDIT_TIMETABLE = "master.edit_timetable"
    EDIT_TIME = "master.edit_time"
    # CHECK_DAY = "master.check_day"
    CALENDAR_BACK = "master.cal_back"
    CALENDAR_DROP = "master.cal_drop"
    CALENDAR_WHOLE = "master.cal_whole"
    CALENDAR_MON_FRI = "master.cal_mon_fri"
    CALENDAR_WEEKEND = "master.cal_weekend"
    CALENDAR_IGNORE = "master.cal_ignore"
    CALENDAR_TIME = "master.cal_time"
    CALENDAR_FORWARD = "master.cal_forward"
    CALENDAR_ADD_TIME = "master.cal_add_time"
    CALENDAR_ADD_TIME_BULK = "master.cal_add_time_bulk"
    CALENDAR_DELETE_TIME = "master.cal_delete_time"
    BACK_TO_TIMETABLE = "master.back_to_timetable"
    BACK_TO_DAY = "master.back_to_day"
    BACK_TO_TIME = "master.back_to_time"


class CommonConstants:
    EDIT_NAME = "com.edit_name"
    EDIT_SERVICE = "com.edit_service"
    EDIT_SERVICE_DONE = "com.edit_service_done"
    EDIT_PHONE_NUMBER = "com.edit_phone_number"
    EDIT_INSTAGRAM = "com.edit_instagram"
    EDIT_DESCRIPTION = "com.edit_description"
    FINISH_FORM = "com.finish_form"
    APPOINTMENT_DATETIME_FORMAT = "%"
    BECOME_MASTER = (
        "Чтобы осуществлять функции Мастера, Вам необходимо приобрести подписку.\n"
        f"Пожалуйста, обратитесь к нашему администратору {Config.ADMIN_TG} и передайте ему ваш telegram id: %s."
    )
    DEACTIVATED_ACC = f"Ваш профиль деактивирован. Пожалуйста, обратитесь к администратору: {Config.ADMIN_TG}."

    TEMPORARY_DATA = {
        "current_service": None,
        "current_sub_service": None,
        "current_calendar": text("'{}'::jsonb"),
        "current_day": None,
        "current_month": None,
        "current_year": None,
        "current_appointment": None,
        "current_master": None,
        "current_page": 1,
    }

    COUNTERS = {
        "flood_count": 0,
        "non_recogn_count": 0
    }

    WEEK_DAYS_AS_BUTTONS = [[
        InlineKeyboardButton(text=day, callback_data=MasterConstants.CALENDAR_IGNORE)
        for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    ]]


class RegistrationConstants:
    DONE_SUB_SERVICE = "reg.done_sub_service"
    DONE_SERVICE = "reg.done_service"
    SKIP = "reg.skip"
