import os
from dotenv import load_dotenv
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

# Загрузите переменные окружения из файла .env
load_dotenv()

# Включите логирование
logging.basicConfig(level=logging.INFO)

# Ваш токен API из переменной окружения
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Словарь для хранения напоминаний
reminders = {}

@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    await message.reply("Привет! Я бот для напоминаний. Используй /set <секунды> <сообщение> для установки напоминания.")

@dp.message(Command(commands=['set']))
async def set_reminder(message: Message):
    try:
        args = message.text.split()[1:]
        if len(args) < 2:
            await message.reply("Использование: /set <секунды> <сообщение>")
            return

        seconds = int(args[0])
        reminder_message = ' '.join(args[1:])
        chat_id = message.chat.id

        # Установите напоминание
        reminders[chat_id] = (seconds, reminder_message)
        await message.reply(f"Напоминание установлено на {seconds} секунд.")

        # Запустите таймер для напоминания
        await asyncio.sleep(seconds)
        await bot.send_message(chat_id=chat_id, text=f"Напоминание: {reminder_message}")

    except (IndexError, ValueError):
        await message.reply("Использование: /set <секунды> <сообщение>")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
