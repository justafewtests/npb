import asyncio
from datetime import datetime, timedelta

from sqlalchemy import update, func

from nbp.config import Config, CommonConstants
from nbp.db.api import User
from nbp.db.core import engine
from nbp.db.sa_models import user_table
from nbp.db.utils import WhereClause, basic_update
from nbp.logger import get_logger


async def drop_counters_task():
    logger = get_logger()
    while True:
        try:
            await asyncio.sleep(Config.DROP_COUNTERS_WATCHDOG_TIMEOUT)
            now = datetime.now()
            where_clause = WhereClause(
                filter=[
                    now - user_table.c.flood_ts > timedelta(seconds=Config.DROP_COUNTERS_WATCHDOG_THRESHOLD)
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
            logger.info(f"Drop counters job: non-recogn counters dropped - {result}")
        except Exception as exc:
            logger.error(f"Unexpected error in drop_counters_task: {exc}")
