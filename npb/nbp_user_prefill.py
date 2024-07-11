import asyncio
from datetime import datetime

from npb.db.api import User, Appointment
from npb.db.core import engine
from npb.logger import get_logger
from npb.tg.models import UserModel, AppointmentModel


async def prefill_nbp_user():
    logger = get_logger()
    for i in range(3, 23):
        user_info = UserModel(
            name=f"test_{i}",
            telegram_id=f"test_{i}",
            telegram_profile=f"@test_{i}",
            is_master=True,
            seq_id=i,
            services={"Ресницы": {}}
        )
        await User(engine=engine, logger=logger).create_user(user=user_info)


async def prefill_appointments():
    logger = get_logger()
    for i in range(3, 23):
        dt = datetime.now()
        appointment = AppointmentModel(
            datetime=dt,
            master_telegram_id=f"test_{i}",
        )
        await Appointment(engine=engine, logger=logger).create_appointment(appointment=appointment)


if __name__ == "__main__":
    asyncio.run(prefill_appointments())
