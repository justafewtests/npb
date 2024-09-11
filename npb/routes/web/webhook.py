from aiogram.types import Update
from fastapi import APIRouter, Request

from npb.tg.bot import bot
from npb.config import Config
from npb.tg.dispatcher import dp


router = APIRouter()


processed_update_ids = set()


@router.post(f"{Config.TELEGRAM_WEBHOOK_PATH}")
async def tg_webhook(request: Request):
    """
    Handles responses from Telegram API.
    :return: None
    """
    req = await request.json()
    print(req)
    update = Update.model_validate(req, context={"bot": bot})
    if len(processed_update_ids) > Config.MAX_PROCESSED_UNIQUE_UPDATES:
        processed_update_ids.clear()
    if update.update_id in processed_update_ids:
        print(f"skip non unique Telegram update with update id: {update.update_id}.")
        print(f"length of processed_update_ids: {len(processed_update_ids)}.")
        return "ok"
    processed_update_ids.add(update.update_id)
    await dp.feed_update(bot=bot, update=update)
    return "ok"
