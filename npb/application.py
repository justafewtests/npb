import asyncio
import traceback
from datetime import datetime, timedelta
from os import environ
from typing import Callable, Dict, Any, Awaitable

from aiogram.enums import ParseMode
from alembic.config import Config as AlembicConfig
from aiogram.types import ErrorEvent, BotCommand, Update, User as AiogramUser, InputFile, FSInputFile
from alembic import command
from fastapi import FastAPI

from npb.background import drop_counters_task
from npb.config import CommonConstants
from npb.db.api import User
from npb.db.core import engine
from npb.db.sa_models import user_table
from npb.db.utils import WhereClause
from npb.logger import get_logger
from npb.routes.tg.admin import admin_router
from npb.routes.tg.entry_point import entry_point_router
from npb.routes.tg.client import client_router
from npb.routes.tg.master import master_router
from npb.routes.tg.registration_form import registration_form_router
from npb.routes.tg.unrecognized import unrecognized_router
from npb.routes.web.webhook import router as webhook_router
from npb.tg.black_list import get_black_list_manager
from npb.tg.bot import bot
from npb.tg.bot import Config
from npb.tg.dispatcher import dp


def create_app() -> FastAPI:
    """
    Create application:
    - register web-app routes
    - register tg routes
    :param app: FastAPI application instance.
    :return: FastAPI application instance.
    """
    web_app = FastAPI()
    web_app.include_router(webhook_router)

    dp.include_router(entry_point_router)
    dp.include_router(registration_form_router)
    dp.include_router(master_router)
    dp.include_router(client_router)
    dp.include_router(admin_router)
    dp.include_router(unrecognized_router)

    @dp.error()
    async def error_handler(event: ErrorEvent) -> None:
        """
        Handle all errors that occur in telegram handlers.
        :param event: Error event.
        :return: None
        """
        print(f"Error occurred during processing updates from Telegram. Details: {event.exception}.")
        print(f"Exception type: {type(event.exception)}")
        error_message = traceback.format_exception(event.exception)
        error_message = "".join(error_message)
        print(f"Exception traceback: {error_message}")
        text = "Возникли ошибки при обработке ответа. Пожалуйста, повторите свой запрос позже."
        if message := event.update.message:
            await message.answer(text=text)
        else:
            await event.update.callback_query.message.answer(text=text)

    @dp.update.outer_middleware()
    async def authorization_and_flood_control(
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        user_event: AiogramUser
        logger = get_logger()
        print(f"DEBUG outer middleware\ndata: {data}\nevent: {event}\nhandler: {handler}")
        user_event = data.get("event_from_user", None)
        # TODO: if load is big enough, i need to add redis as cache and use it to keep user info there:
        # TODO: flood_control also should be implemented via redis
        if user_event:
            text = None
            telegram_id = str(user_event.id)
            black_list_manager = get_black_list_manager()
            if black_list_manager.user_is_banned(telegram_id=telegram_id):
                text = CommonConstants.DEACTIVATED_ACC
            else:
                user = await User(engine=engine, logger=logger).read_single_user_info(tg_user_id=telegram_id)
                if user:
                    if not user.is_active:
                        text = CommonConstants.DEACTIVATED_ACC
                        # if server was down we need to refill blacklist:
                        black_list_manager.ban_user(telegram_id=telegram_id)
                    elif datetime.now() - user.last_ts < timedelta(seconds=Config.MIN_USER_EVENT_COOLDOWN):
                        text = await black_list_manager.flood_control(
                            user=user, engine=engine, logger=logger, telegram_id=telegram_id
                        )
                    else:
                        where_clause = WhereClause(
                            params=[user_table.c.telegram_id], values=[telegram_id], comparison_operators=["=="]
                        )
                        data_to_set = {"last_ts": datetime.now()}
                        await User(engine=engine, logger=logger).update_user_info(
                            data_to_set=data_to_set, where_clause=where_clause, return_all=True
                        )
            if text:
                await bot.send_message(
                    chat_id=user_event.id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
        return await handler(event, data)

    @web_app.on_event("startup")
    async def web_app_startup():
        logger = get_logger()
        logger.info("web_app_startup")
        # mapper_registry.map_imperatively()
        alembic_config = AlembicConfig(environ.get("ALEMBIC_SCRIPT_PATH"))
        alembic_config.set_main_option("script_location", environ.get("ALEMBIC_SCRIPT_LOCATION"))
        alembic_config.set_main_option("sqlalchemy.url", Config.DB_DSN)
        command.upgrade(alembic_config, "head")
        logger.info('apply "alembic upgrade head"')
        # init logger and other stuf
        webhook = await bot.get_webhook_info()
        logger.info(webhook)
        if webhook.url != Config.TELEGRAM_WEBHOOK_URL:
            if not webhook.url:
                await bot.delete_webhook()
            environment = environ.get("ENVIRONMENT", "test")
            if environment == "prod":
                cert_path = "../certs/webhook_cert.pem"
                await bot.set_webhook(Config.TELEGRAM_WEBHOOK_URL, certificate=FSInputFile(cert_path))
            else:
                await bot.set_webhook(Config.TELEGRAM_WEBHOOK_URL)
            logger.info(f"telegram webhook set to {Config.TELEGRAM_WEBHOOK_URL}")
        asyncio.create_task(drop_counters_task())
        # TODO: SetMyCommands and GetMyCommands triggers Telegram Flood Control
        # my_commands = await bot.get_my_commands(language_code="ru")
        # print("DEBUG my_commands: ", my_commands)
        # if not my_commands:
        #     commands = [
        #         BotCommand(command="/commands", description="Список команд"),
        #         BotCommand(command="/help", description="Помощь")
        #     ]
        #     await bot.set_my_commands(commands=commands, language_code="ru")

    @web_app.on_event("shutdown")
    async def web_app_shutdown():
        # shutdown logger and other stuf
        print("web_app_shutdown")
        await bot.session.close()

    print(f"Server run on: {Config.SERVICE_HOST}:{Config.SERVICE_PORT}")
    return web_app
