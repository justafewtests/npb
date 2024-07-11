from datetime import datetime
from logging import Logger

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncEngine

from npb.config import Config
from npb.db.api import User
from npb.db.sa_models import user_table
from npb.db.utils import WhereClause


class BlackListManager:
    def __init__(self):
        self._black_list = set()  # TODO: users > 1000, redis is needed here

    async def flood_control(self, user: Row, engine: AsyncEngine, logger: Logger, telegram_id: str) -> str:
        """
        Increases flood_count or adds user to blacklist (if threshold is exceeded).
        :param user: A row of 'npb_user' table.
        :param engine: DB engine object.
        :param logger: Logger object.
        :param telegram_id: Telegram id.
        :return: Text to return as a response.
        """
        if user.flood_count > Config.FLOOD_THRESHOLD:
            now = datetime.now()
            data_to_set = {"is_active": False, "flood_ts": now}
            text = (
                f"Ваш профиль деактивирован за флуд. Пожалуйста, обратитесь к администратору: "
                f"{Config.ADMIN_TG}."
            )
            self._black_list.add(telegram_id)
            print("DEBUG _black_list: ", self._black_list)
        else:
            data_to_set = {"flood_count": user.flood_count + 1}
            text = (
                "Внимание! Вы слишком часто взаимодействуете с ботом! Ваши действия могут быть "
                "расценены, как флуд-атака. При сохранении текущих темпов взаимодействия "
                "с ботом Ваш аккаунт может быть заблокирован.\n*Число взаимодействий "
                "(сообщений / нажатий на кнопки) не должно превышать одного взаимодействия в секунду.*"
            )
        where_clause = WhereClause(
            params=[user_table.c.telegram_id], values=[telegram_id], comparison_operators=["=="]
        )
        await User(engine=engine, logger=logger).update_user_info(
            data_to_set=data_to_set, where_clause=where_clause, return_all=True
        )
        return text

    def user_is_banned(self, telegram_id) -> bool:
        """
        Check whether black_list contains given telegram_id (black_list is stored in memory).
        :param telegram_id: Telegram id.
        :return: True if user in black list and False otherfise
        """
        print("DEBUG _black_list: ", self._black_list)
        return telegram_id in self._black_list

    def ban_user(self, telegram_id: str) -> None:
        """
        Add user to black list.
        :param telegram_id: Telegram id.
        :return: None
        """
        self._black_list.add(telegram_id)

    def unban_user(self, telegram_id: str) -> None:
        """
        Delete user from black list.
        :param telegram_id: Telegram id.
        :return: None
        """
        self._black_list.discard(telegram_id)


black_list_manager = BlackListManager()


def get_black_list_manager():
    """Returns a black_list_manager global instance."""
    return black_list_manager
