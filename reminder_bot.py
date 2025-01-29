import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

# Загрузите переменные окружения из файла .env
load_dotenv()

# Включите логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ваш токен API из переменной окружения
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Словарь для хранения напоминаний
reminders = {}

# Словарь для хранения временных данных выбора
temp_data = {}

# Словарь для перевода месяцев на русский язык
months_ru = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}


@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    logging.info(f"Пользователь {message.from_user.id} запустил бота.")
    welcome_message = (
        "Привет! Я бот для напоминаний. Вот список доступных команд:\n"
        "/set - установить напоминание\n"
        "/list - показать список напоминаний и оставшееся до них время\n"
        "/start - показать это сообщение снова"
    )
    await message.reply(welcome_message)


@dp.message(Command(commands=['set']))
async def set_reminder(message: Message):
    chat_id = message.chat.id
    temp_data[chat_id] = {}
    logging.info(f"Пользователь {chat_id} начал установку напоминания.")

    # Текущая дата и время
    now = datetime.now()
    current_day = now.day
    current_month = now.month
    current_time = now.strftime('%H:%M')

    # Создаем инлайн-клавиатуру для выбора числа
    builder = InlineKeyboardBuilder()
    for day in range(1, 32):
        builder.add(InlineKeyboardButton(text=str(day), callback_data=f"day_{day}"))
    builder.adjust(7)

    await message.reply(f"Текущее число: {current_day}\nВыберите число:", reply_markup=builder.as_markup())


@dp.message(Command(commands=['list']))
async def list_reminders(message: Message):
    chat_id = message.chat.id
    logging.info(f"Пользователь {chat_id} запросил список напоминаний.")
    if chat_id in reminders:
        current_time = datetime.now()
        reminders_list = reminders[chat_id]
        response = "Список напоминаний:\n"
        for reminder_time, reminder_message in reminders_list:
            remaining_time = (reminder_time - current_time).total_seconds()
            if remaining_time > 0:
                remaining_time_str = str(int(remaining_time // 3600)) + " часов " + str(
                    int((remaining_time % 3600) // 60)) + " минут"
                response += f"Напоминание: {reminder_message}\nОсталось: {remaining_time_str}\n"
            else:
                response += f"Напоминание: {reminder_message}\nОсталось: Напоминание уже прошло\n"
        await message.reply(response)
    else:
        await message.reply("У вас нет установленных напоминаний.")


@dp.callback_query(lambda c: c.data.startswith('day_'))
async def process_day_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    day = int(callback_query.data.split('_')[1])
    temp_data[chat_id]['day'] = day
    logging.info(f"Пользователь {chat_id} выбрал день: {day}")

    # Текущая дата и время
    now = datetime.now()
    current_month = now.month

    # Создаем инлайн-клавиатуру для выбора месяца
    builder = InlineKeyboardBuilder()
    for month in range(1, 13):
        builder.add(InlineKeyboardButton(text=months_ru[month], callback_data=f"month_{month}"))
    builder.adjust(3)

    await bot.edit_message_text(f"Текущий месяц: {months_ru[current_month]}\nВыберите месяц:", chat_id=chat_id,
                                message_id=callback_query.message.message_id, reply_markup=builder.as_markup())


@dp.callback_query(lambda c: c.data.startswith('month_'))
async def process_month_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    month = int(callback_query.data.split('_')[1])
    temp_data[chat_id]['month'] = month
    logging.info(f"Пользователь {chat_id} выбрал месяц: {month}")

    # Текущая дата и время
    now = datetime.now()
    current_time = now.strftime('%H:%M')

    # Создаем инлайн-клавиатуру для выбора времени
    builder = InlineKeyboardBuilder()
    for hour in range(0, 24):
        for minute in range(0, 60, 15):
            builder.add(
                InlineKeyboardButton(text=f"{hour:02}:{minute:02}", callback_data=f"time_{hour:02}:{minute:02}"))
    builder.adjust(4)

    await bot.edit_message_text(f"Текущее время: {current_time}\nВыберите время:", chat_id=chat_id,
                                message_id=callback_query.message.message_id, reply_markup=builder.as_markup())


@dp.callback_query(lambda c: c.data.startswith('time_'))
async def process_time_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    time_str = callback_query.data.split('_')[1]
    temp_data[chat_id]['time'] = time_str
    logging.info(f"Пользователь {chat_id} выбрал время: {time_str}")

    await bot.edit_message_text("Введите сообщение для напоминания:", chat_id=chat_id,
                                message_id=callback_query.message.message_id)


@dp.message()
async def handle_message(message: Message):
    chat_id = message.chat.id
    if chat_id in temp_data and 'day' in temp_data[chat_id] and 'month' in temp_data[chat_id] and 'time' in temp_data[
        chat_id]:
        day = temp_data[chat_id]['day']
        month = temp_data[chat_id]['month']
        time_str = temp_data[chat_id]['time']
        reminder_message = message.text
        logging.info(f"Пользователь {chat_id} ввел сообщение для напоминания: {reminder_message}")

        # Текущий год
        current_year = datetime.now().year

        # Формируем полную дату и время
        reminder_time_str = f"{current_year}-{month:02}-{day:02} {time_str}"
        reminder_time = datetime.strptime(reminder_time_str, '%Y-%m-%d %H:%M')
        current_time = datetime.now()

        if reminder_time <= current_time:
            await message.reply("Дата и время напоминания должны быть в будущем.")
            return

        # Установите напоминание
        if chat_id not in reminders:
            reminders[chat_id] = []
        reminders[chat_id].append((reminder_time, reminder_message))
        logging.info(f"Напоминание добавлено: {reminder_time} - {reminder_message}")
        await message.reply(f"Напоминание установлено на {reminder_time.strftime('%Y-%m-%d %H:%M')}.")

        # Запустите таймер для напоминания
        sleep_time = (reminder_time - current_time).total_seconds()
        await asyncio.sleep(sleep_time)
        await bot.send_message(chat_id=chat_id, text=f"Напоминание: {reminder_message}")

        # Очистите временные данные
        del temp_data[chat_id]


async def main():
    logging.info("Запуск бота...")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
