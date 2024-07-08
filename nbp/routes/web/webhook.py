from aiogram.types import Update
from fastapi import APIRouter, Request

from nbp.tg.bot import bot
from nbp.config import Config
from nbp.tg.dispatcher import dp


router = APIRouter()


@router.post(f"{Config.TELEGRAM_WEBHOOK_PATH}")
async def tg_webhook(request: Request):
    """
    Handles responses from Telegram API.
    :return: None
    """
    req = await request.json()
    print(req)
    update = Update.model_validate(req, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return "ok"
