import calendar
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor

API_TOKEN = 'your_bot_api_token'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    markup = generate_calendar_markup()
    await message.reply("Select a date:", reply_markup=markup)

def generate_calendar_markup():
    markup = types.InlineKeyboardMarkup(row_width=7)
    year, month = 2024, 1  # Set the desired year and month

    cal = calendar.monthcalendar(year, month)

    for week in cal:
        for day in week:
            if day == 0:
                markup.insert(types.InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date = f"{year}-{month:02d}-{day:02d}"
                markup.insert(types.InlineKeyboardButton(text=str(day), callback_data=date))

    return markup

@dp.callback_query_handler(lambda c: True)
async def process_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    selected_date = callback_query.data
    await bot.send_message(callback_query.from_user.id, f"You selected: {selected_date}")

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)