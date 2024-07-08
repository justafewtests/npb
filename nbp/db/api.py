from logging import Logger
from typing import Any, Dict, List, Sequence, Union, Iterable

from sqlalchemy import Column, delete, insert, Row, select, update, func
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy.exc import MultipleResultsFound

from nbp.config import CommonConstants, Config
from nbp.db.abstract_repository import AppointmentAbstractRepository, UserAbstractRepository
from nbp.db.exceptions import UpdateAppointmentInfoError, UpdateUserInfoError
from nbp.db.sa_models import appointment_table, user_table
from nbp.db.utils import basic_update, WhereClause, Join
from nbp.exceptions import MoreThanOneAppointment, MoreThanOneUserFound, DropIsProhibited
from nbp.tg.models import AppointmentList, AppointmentModel, UserModel
from nbp.db.utils import get_comparison_operator_by_symbol


class User(UserAbstractRepository):

    def __init__(self, engine: AsyncEngine, logger: Logger):
        self._engine = engine
        self.logger = logger

    async def create_user(self, user: UserModel):
        """
        Create user in DB.
        :param user: User model.
        """
        # TODO: обработка ошибок?
        # TODO: тайпхинты на выходные параметры?
        query = insert(user_table).values(user.model_dump(exclude_none=True)).returning("*")
        print(query)
        connection: AsyncConnection
        async with self._engine.begin() as connection:
            result = await connection.execute(query)
            return result.one_or_none()

    async def read_single_user_info(self, tg_user_id: str):
        """
        Get single user info from DB.
        :param tg_user_id: Telegram user id.
        """
        # TODO: обработка ошибок?
        # TODO: тайпхинты на выходные параметры?
        connection: AsyncConnection
        query = select(user_table).where(user_table.c.telegram_id == tg_user_id)
        async with self._engine.begin() as connection:
            result = await connection.execute(query)
            try:
                return result.one_or_none()
            except MultipleResultsFound as exc:
                error_message = f"More than one user with telegram id {tg_user_id} was found. Details: {str(exc)}."
                self.logger.error(error_message)
                raise MoreThanOneUserFound(error_message)

    async def read_user_info(self, where_clause: WhereClause, order_by: list = None, limit: int = None):
        """
        Get user info from DB.
        :param where_clause: Where clause.
        :param order_by: Order by clauses.
        :param limit: Limit search.
        :param limit: .
        """
        # TODO: обработка ошибок?
        # TODO: тайпхинты на выходные параметры?
        connection: AsyncConnection
        if where_clause.filter:
            query = select(user_table).filter(*where_clause.filter)
        else:
            query = select(user_table).filter()
            for number, where_clause_param in enumerate(where_clause.params):
                comparison_operator = get_comparison_operator_by_symbol(where_clause.comparison_operators[number])
                query = query.where(
                    comparison_operator(where_clause_param, where_clause.values[number])
                )
        if order_by:
            for clause in order_by:
                query = query.order_by(clause)
        if limit:
            query = query.limit(limit=limit)
        async with self._engine.begin() as connection:
            print("DEBUG read_user_info query: ", str(query))
            result = await connection.execute(query)
            return result.all()

    async def update_user_info(
        self,
        data_to_set: Dict[str, Any],
        where_clause: WhereClause,
        returning_values: List[Column] = None,
        return_all: bool = False,
    ):
        """
        Update user info in DB.
        :param data_to_set: Data to set.
        :param where_clause: Where clause.
        :param returning_values: Returning values params.
        :param return_all: Returning all params.
        """
        # TODO: тайпхинты на выходные параметры?
        if user_table.c.telegram_id in data_to_set:
            error_message = "Telegram ID is a protected parameter and can not be updated."
            raise UpdateUserInfoError(error_message)
        try:
            return await basic_update(
                engine=self._engine,
                table=user_table,
                data_to_set=data_to_set,
                where_clause=where_clause,
                returning_values=returning_values,
                return_all=return_all,
            )
        except Exception as error:
            raise UpdateUserInfoError(f"Unexpected error in 'update_user_info'. Details: {str(error)}")

    async def delete_user(self, tg_user_id: int):
        """
        Delete user from DB.
        :param tg_user_id: Telegram user id.
        """
        # TODO: обработка ошибок?
        # TODO: тайпхинты на выходные параметры?
        connection: AsyncConnection
        query = delete(user_table).where(user_table.c.telegram_id == tg_user_id).returning("*")
        async with self._engine.begin() as connection:
            result = await connection.execute(query)
            return result.all()

    async def drop_temporary_data(self, telegram_id: str, data: Iterable[str] = None) -> None:
        """
        Set temporary data to default values.
        :param telegram_id: Telegram id.
        :param data: data: Data to drop.
        :return: None.
        """
        data_to_set = {}
        if data:
            for droppable in data:
                if temporary_data_default_value := CommonConstants.TEMPORARY_DATA.get(droppable):
                    data_to_set[droppable] = temporary_data_default_value
                else:
                    raise DropIsProhibited(f"Data {droppable} cannot be dropped. Data is not marked as TEMPORARY")
        else:
            data_to_set = CommonConstants.TEMPORARY_DATA
        where_clause = WhereClause(
            params=[user_table.c.telegram_id], values=[telegram_id], comparison_operators=["=="]
        )
        await basic_update(
            engine=self._engine,
            table=user_table,
            data_to_set=data_to_set,
            where_clause=where_clause,
        )


class Appointment(AppointmentAbstractRepository):

    def __init__(self, engine: AsyncEngine, logger: Logger):
        self._engine = engine
        self.logger = logger

    async def create_appointment(self, appointment: Union[AppointmentModel, AppointmentList]) -> Sequence[Row]:
        """
        Create appointment in DB.
        :param appointment: Appointment model.
        """
        # TODO: обработка ошибок?
        # TODO: тайпхинты на выходные параметры?
        if isinstance(appointment, AppointmentList):
            appointment = appointment.model_dump(exclude_unset=True)["appointment_list"]
            query = insert(appointment_table).values(appointment).returning("*")
        else:
            query = insert(appointment_table).values(appointment.model_dump(exclude_unset=True)).returning("*")
        connection: AsyncConnection
        async with self._engine.begin() as connection:
            result = await connection.execute(query)
            return result.all()

    async def read_single_appointment_info(self, auid: str):
        """
        Get single appointment info from DB.
        :param auid: Telegram appointment id.
        """
        # TODO: обработка ошибок?
        # TODO: тайпхинты на выходные параметры?
        connection: AsyncConnection
        query = select(appointment_table).where(appointment_table.c.auid == auid)
        async with self._engine.begin() as connection:
            result = await connection.execute(query)
            try:
                return result.one_or_none()
            except MultipleResultsFound as exc:
                error_message = f"More than one appointment with telegram id {auid} was found. Details: {str(exc)}."
                self.logger.error(error_message)
                raise MoreThanOneAppointment(error_message)

    async def read_appointment_info(
        self,
        where_clause: WhereClause,
        limit: int = None,
        order_by: list = None,
        join_data: Join = None,
        selectables: List[Column] = None,
    ) -> Sequence[Row]:
        """
        Get appointment from DB.
        :param where_clause: Where clause.
        :param limit: Limit search.
        :param order_by: Order by clauses.
        :param join_data: Joins.
        :param selectables: Returning values params.
        """
        # TODO: обработка ошибок?
        # TODO: тайпхинты на выходные параметры?
        connection: AsyncConnection
        if selectables:
            query = select(*selectables)
        else:
            query = select(appointment_table)
        if where_clause.filter:
            query = query.filter(*where_clause.filter)
        else:
            query = query.filter()
            for number, where_clause_param in enumerate(where_clause.params):
                comparison_operator = get_comparison_operator_by_symbol(where_clause.comparison_operators[number])
                query = query.where(
                    comparison_operator(where_clause_param, where_clause.values[number])
                )
        if limit:
            query = query.limit(limit=limit)
        if join_data:
            comparison_operator = get_comparison_operator_by_symbol(join_data.on_clause_operator)
            on_clause = comparison_operator(join_data.on_clause_param, join_data.on_clause_value)
            query = query.join(target=join_data.right_table, onclause=on_clause)
        if order_by:
            for clause in order_by:
                query = query.order_by(clause)
        print("DEBUG read_appointment_info query: ", str(query))
        async with self._engine.begin() as connection:
            result = await connection.execute(query)
            return result.all()

    async def update_appointment_info(
        self,
        data_to_set: Dict[str, Any],
        where_clause: WhereClause,
        returning_values: List[Column] = None,
        return_all: bool = False,
    ) -> Sequence[Row]:
        """
        Update appointment info in DB.
        :param data_to_set: Data to set.
        :param where_clause: Where clause.
        :param returning_values: Returning values params.
        :param return_all: Returning all params.
        """
        if appointment_table.c.master_telegram_id in data_to_set:
            error_message = "Telegram ID is a protected parameter and can not be updated."
            raise UpdateAppointmentInfoError(error_message)
        try:
            return await basic_update(
                engine=self._engine,
                table=appointment_table,
                data_to_set=data_to_set,
                where_clause=where_clause,
                returning_values=returning_values,
                return_all=return_all,
            )
        except Exception as exc:
            raise UpdateAppointmentInfoError(f"Unexpected error in 'update_appointment_info'. Details: {str(exc)}")

    async def delete_appointment(self, auid: str):
        """
        Delete appointment from DB.
        :param auid: Appointment id.
        """
        connection: AsyncConnection
        query = delete(appointment_table).where(appointment_table.c.auid == auid).returning("*")
        async with self._engine.begin() as connection:
            result = await connection.execute(query)
            return result.all()

    @staticmethod
    def appointments_as_dict(appointments: Sequence[Row]) -> Dict[int, bool]:
        result = {}
        for appointment in appointments:
            reserved_day = appointment.datetime.day
            result[reserved_day] = True
        return result
