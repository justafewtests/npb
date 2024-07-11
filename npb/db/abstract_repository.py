from abc import ABC, abstractmethod
from typing import Any, Dict, List

from sqlalchemy import Column

from npb.db.utils import WhereClause, Join
from npb.tg.models import AppointmentModel, UserModel


class UserAbstractRepository(ABC):
    @abstractmethod
    async def create_user(self, user: UserModel):
        """
        Create user in DB.
        :param user: User model.
        """
        raise NotImplementedError

    @abstractmethod
    async def read_single_user_info(self, tg_user_id: str):
        """
        Get single user info from DB.
        :param tg_user_id: Telegram user id.
        """
        raise NotImplementedError

    @abstractmethod
    async def read_user_info(self, where_clause: WhereClause):
        """
        Get user info from DB.
        :param where_clause: Where clause.
        """
        raise NotImplementedError

    @abstractmethod
    async def update_user_info(
        self,
        data_to_set: Dict[Column, Any],
        where_clause: WhereClause,
        returning_values: List[Column],
    ):
        """
        Update user info in DB.
        :param data_to_set: Data to set.
        :param where_clause: Where clause.
        :param returning_values: Returning values params.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_user(self, tg_user_id: str):
        """
        Delete user from DB.
        :param tg_user_id: Telegram user id.
        """
        raise NotImplementedError


class AppointmentAbstractRepository(ABC):
    @abstractmethod
    async def create_appointment(self, appointment: AppointmentModel):
        """
        Create appointment in DB.
        :param appointment: Appointment model.
        """
        raise NotImplementedError

    @abstractmethod
    async def read_single_appointment_info(self, appointment_id: str):
        """
        Get single appointment info from DB.
        :param appointment_id: Telegram appointment id.
        """
        raise NotImplementedError

    @abstractmethod
    async def read_appointment_info(
        self,
        where_clause: WhereClause,
        limit: int = None,
        order_by: list = None,
        join_data: Join = None,
        selectables: List[Column] = None,
    ):
        """
        Get appointment from DB.
        :param where_clause: Where clause.
        :param limit: Limit search.
        :param order_by: Order by clauses.
        :param join_data: Joins.
        :param selectables: Returning values params.
        """
        raise NotImplementedError

    @abstractmethod
    async def update_appointment_info(
            self,
            data_to_set: Dict[Column, Any],
            where_clause: WhereClause,
            returning_values: List[Column],
    ):
        """
        Update appointment info in DB.
        :param data_to_set: Data to set.
        :param where_clause: Where clause.
        :param returning_values: Returning values params.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_appointment(self, appointment_id: str):
        """
        Delete appointment from DB.
        :param appointment_id: Telegram appointment id.
        """
        raise NotImplementedError
