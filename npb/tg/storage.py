from typing import Any, Dict, Optional

from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType

from npb.db.api import User
from npb.db.core import engine
from npb.db.utils import WhereClause
from npb.logger import get_logger
from npb.db.sa_models import user_table


class NPBStateMachineStorage(BaseStorage):
    """
    Finite state machine storage based on postgresql.
    """
    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        """
        Set state for specified key

        :param key: storage key
        :param state: new state
        """
        logger = get_logger()
        telegram_id = str(key.chat_id)
        where_clause = WhereClause(
            params=[user_table.c.telegram_id],
            values=[telegram_id],
            comparison_operators=["=="]
        )
        data_to_set = {"state": state.state}
        res = await User(engine=engine, logger=logger).update_user_info(
            where_clause=where_clause,
            data_to_set=data_to_set
        )
        # print("DEBUG storage set_state ", res)

    async def get_state(self, key: StorageKey) -> Optional[str]:
        """
        Get key state

        :param key: storage key
        :return: current state
        """
        logger = get_logger()
        if user := await User(engine=engine, logger=logger).read_single_user_info(
            tg_user_id=str(key.chat_id)
        ):
            # print("DEBUG get_state, user.state: ", user.state)
            # print("DEBUG get_state, user: ", user)
            return user.state
        else:
            return None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        """
        Write data (replace)

        :param key: storage key
        :param data: new data
        """
        raise NotImplementedError("This method is not implemented. Use explicit DB call instead.")

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        """
        Get current data for key

        :param key: storage key
        :return: current data
        """
        raise NotImplementedError("This method is not implemented. Use explicit DB call instead.")

    async def update_data(self, key: StorageKey, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update date in the storage for key (like dict.update)

        :param key: storage key
        :param data: partial data
        :return: new data
        """
        raise NotImplementedError("This method is not implemented. Use explicit DB call instead.")

    async def close(self) -> None:  # pragma: no cover
        """
        Close storage (database connection, file or etc.)
        """
        raise NotImplementedError("This method is not implemented. Use explicit DB call instead.")
