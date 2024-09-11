from datetime import datetime, timezone, timedelta
from enum import Enum
import operator
from typing import Any, List, Dict, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Column, Table, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from npb.config import Config

COMPARISON_OPERATOR_BY_SYMBOL = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}


class JoinTypes(Enum):
    left = "left"
    right = "right"
    inner = "inner"
    outer = "outer"


def get_comparison_operator_by_symbol(
    operator_as_symbol: Literal[">", ">=", "<", "<=", "==", "!="]
) -> Union[operator.gt, operator.ge, operator.lt, operator.le, operator.eq]:
    """
    Returns a comparison operator as function by its symbol representation.
    :param operator_as_symbol: One of ">", ">=", "<", "<=", "==".
    :return:
    """
    return COMPARISON_OPERATOR_BY_SYMBOL[operator_as_symbol]


class WhereClause(BaseModel):
    """
    Helper model for building basic where clauses for SQL queries.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    params: Optional[List[Column]] = Field(default_factory=list, description="Params that are checked in where clause.")
    values: Optional[List[Any]] = Field(default_factory=list, description="Values that are checked in where clause.")
    comparison_operators: Optional[List[Literal[">", ">=", "<", "<=", "==", "!="]]] = Field(
        default_factory=list,
        description="Comparison operators to compare params and values"
    )
    filter: Optional[List[Any]] = Field(
        default=None,
        description="Params that are checked in where clause (filter form)."
    )

    @model_validator(mode="after")
    def check_params_length_or_filter(self):
        """
        Check that params, values and comparison_operands are of the same length.
        """
        # if self.filter and (self.params or self.values):
        #     error_message = "Only one can be specified: 'params + values' or 'filter'."
        #     raise ValueError(error_message)
        # if not self.filter and not (self.params or self.values):
        #     error_message = "At least one of 'params + values' or 'filter' must be specified."
        #     raise ValueError(error_message)
        if not self.filter:
            params_length = len(self.params)
            values_length = len(self.values)
            comparison_operators_length = len(self.comparison_operators)
            if not(params_length == values_length == comparison_operators_length):
                error_message = (
                    "Length of 'params', 'values' and 'comparison_operands' must be the same."
                    f"Given lengths: params - {params_length}, values - {values_length}, "
                    f"Given lengths: comparison_operators - {comparison_operators_length}."
                )
                raise ValueError(error_message)
        return self


class Join(BaseModel):
    """
    Helper model for building basic joins for SQL queries.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    right_table: Table = Field(description="Right table.")
    on_clause_param: Column = Field(description="SQL 'ON' clause param.")
    on_clause_value: Column = Field(description="SQL 'ON' clause value.")
    on_clause_operator: Literal[">", ">=", "<", "<=", "=="] = Field(
        default=None,
        description="On clause comparison operators to compare params and values"
    )


async def basic_update(
    engine: AsyncEngine,
    table: Table,
    data_to_set: Dict[str, Any] | List[Dict[str, Any]],
    where_clause: WhereClause = None,
    returning_values: List[Column] = None,
    return_all: bool = False,
):
    connection: AsyncConnection
    query = update(table)
    if where_clause:
        if where_clause.params and where_clause.values and where_clause.comparison_operators:
            for number, where_clause_param in enumerate(where_clause.params):
                comparison_operator = get_comparison_operator_by_symbol(where_clause.comparison_operators[number])
                query = query.where(
                    comparison_operator(where_clause_param, where_clause.values[number])
                )
        elif where_clause.filter:
            query = query.filter(*where_clause.filter)
    if isinstance(data_to_set, dict):
        query = query.values(**data_to_set)
    else:
        for data in data_to_set:
            query = query.values(data)
    if not return_all and returning_values:
        query = query.returning(*returning_values)
    else:
        query = query.returning("*")
    async with engine.begin() as connection:
        print(f"DEBUG basic update query: {str(query)}")
        result = await connection.execute(query)
        print(f"DEBUG basic update result: {str(result)}")
        return result.all()


def create_timestamp_with_timezone() -> datetime:
    tz = timezone(timedelta(hours=Config.TZ_OFFSET))
    return datetime.now(tz=tz)
