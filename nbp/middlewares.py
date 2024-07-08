from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from nbp.logger import get_logger


class HandlerInfoMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        logger = get_logger()
        logger.info(f"Handler triggered: {handler.__name__}")
        logger.debug(f"Data passed to handler: {data}")
        logger.debug(f"Event passed to handler: {event}")
        result = await handler(event, data)
        logger.debug(f"Handler processing result: {result}")
        return result
