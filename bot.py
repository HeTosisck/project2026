import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import requests

bot = Bot(token="YOUR_TG_TOKEN")
dp = Dispatcher()

class AddLog(StatesGroup):
    choosing_project = State()
    waiting_for_text = State()
    waiting_for_photo = State()

@dp.message(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я помогу вести логи твоих инженерных проектов.")

# Пример использования стороннего API (Курс валют или Погода)
@dp.message(commands=['weather'])
async def get_weather(message: types.Message):
    # Здесь может быть вызов внешнего API через requests
    await message.answer("Сегодня отличная погода для работы в гараже: +15°C")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
