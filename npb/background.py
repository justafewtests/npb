import asyncio
import traceback
from datetime import datetime, timedelta, timezone
from logging import Logger

from sqlalchemy import update, func

from npb.config import Config, CommonConstants
from npb.db.api import User, Appointment
from npb.db.core import engine
from npb.db.sa_models import user_table, appointment_table
from npb.db.utils import WhereClause, basic_update, Join
from npb.logger import get_logger
from npb.utils.common import appointment_info, _prepare_user_info, notify_user


async def periodic_task():
    logger = get_logger()
    while True:
        try:
            await asyncio.sleep(Config.WATCHDOG_TIMEOUT)
            await drop_counters(logger=logger)
            await drop_non_recogn(logger=logger)
            await appointment_notification(logger=logger)
        except Exception as exc:
            details = traceback.format_exception(exc)
            logger.error(f"Unexpected error in background task: {exc}. Details: {details}.")


async def drop_counters(logger: Logger):
    now = datetime.now()
    where_clause = WhereClause(
        filter=[
            now - user_table.c.flood_ts > timedelta(seconds=Config.COUNTERS_THRESHOLD)
        ]
    )
    data_to_set = {
        "flood_count": 0,
        "flood_ts": None,
    }
    result = await basic_update(
        engine=engine,
        table=user_table,
        data_to_set=data_to_set,
        where_clause=where_clause,
        returning_values=[user_table.c.telegram_id]
    )
    logger.info(f"Drop counters job: flood counters dropped - {result}")


async def drop_non_recogn(logger: Logger):
    where_clause = WhereClause(
        params=[user_table.c.non_recogn_count],
        values=[0],
        comparison_operators=[">"],
    )
    data_to_set = {
        "non_recogn_count": 0,
        "non_recogn_ts": None,
    }
    result = await basic_update(
        engine=engine,
        table=user_table,
        data_to_set=data_to_set,
        where_clause=where_clause,
        returning_values=[user_table.c.telegram_id]
    )
    logger.info(f"Drop non_recogn job: non-recogn counters dropped - {result}")


async def appointment_notification(logger: Logger):
    appointments = await Appointment(engine=engine, logger=logger).upcoming_appointments_notification()
    logger.info(f"Appointment notification job: number of notifications to send {len(appointments)}")
    tasks = []
    for appointment in appointments:
        text = f"Напоминаем, что у Вас есть запись на {appointment.datetime.strftime('%d.%m.%Y %H:%M')}.\n"
        client_text = text + "Более подробную информацию можно узнать в разделе 'Мои записи'."
        master_text = text + "Более подробную информацию можно узнать в разделе 'Мой график работы'."
        tasks.extend(
            [
                notify_user(text=client_text, telegram_id=appointment.client_telegram_id, logger=logger),
                notify_user(text=master_text, telegram_id=appointment.master_telegram_id, logger=logger),
            ]
        )
    results = await asyncio.gather(*tasks, return_exceptions=False)
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Unexpected error in appointment_notification: {result}.")
