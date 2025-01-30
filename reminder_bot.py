import asyncio
import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
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

# Словарь для перевода дней недели на русский язык
days_ru = {
    0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье"
}


def add_test_reminders(chat_id):
    # Тестовые напоминания
    test_reminders = [
        (datetime.now() + timedelta(minutes=0.10), "Тестовое напоминание 1"),
        (datetime.now() + timedelta(minutes=20), "Тестовое напоминание 1"),
        (datetime.now() + timedelta(minutes=2), "Тестовое напоминание 2"),
        (datetime.now() + timedelta(minutes=3), "Тестовое напоминание 3"),
        (datetime.now() + timedelta(minutes=4), "Тестовое напоминание 4")
    ]

    if chat_id not in reminders:
        reminders[chat_id] = []
    reminders[chat_id].extend(test_reminders)
    logging.info(f"Добавлены тестовые напоминания для пользователя {chat_id}")

    # Запуск таймеров для тестовых напоминаний
    for reminder_time, reminder_message in test_reminders:
        sleep_time = (reminder_time - datetime.now()).total_seconds()
        asyncio.create_task(send_reminder(chat_id, reminder_message, sleep_time))


@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    logging.info(f"Пользователь {message.from_user.id} запустил бота.")
    welcome_message = (
        "Привет! Я бот для напоминаний. Вот список доступных команд:\n"
        "/set - установить напоминание\n"
        "/list - показать список напоминаний и оставшееся до них время\n"
        "/delete - удалить напоминание\n"
        "/start - показать это сообщение снова"
    )
    await message.reply(welcome_message)


@dp.message(Command(commands=['set']))
async def set_reminder(message: Message):
    chat_id = message.chat.id
    temp_data[chat_id] = {}
    logging.info(f"Пользователь {chat_id} начал установку напоминания.")

    # Создаем календарь для выбора даты
    builder = InlineKeyboardBuilder()
    today = datetime.now()
    days_short = {
        0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
    }
    for day in range(15):  # Показываем даты на 14 дней вперед
        date = today + timedelta(days=day)
        day_name = days_short[date.weekday()]  # Сокращённое название дня недели
        month_name = months_ru[date.month][:3]  # Сокращённое название месяца
        date_str = date.strftime('%Y-%m-%d')
        builder.button(text=f"{date.day} {month_name} {day_name} {date.year}", callback_data=f"date_{date_str}")
    builder.adjust(1)

    await message.reply("Выберите дату:", reply_markup=builder.as_markup())


@dp.callback_query(lambda c: c.data.startswith('date_'))
async def process_date_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    date_str = callback_query.data.split('_')[1]
    temp_data[chat_id]['date'] = date_str
    logging.info(f"Пользователь {chat_id} выбрал дату: {date_str}")

    # Создаем инлайн-клавиатуру для выбора времени
    builder = InlineKeyboardBuilder()
    for hour in range(0, 24):
        for minute in range(0, 60, 15):
            builder.button(text=f"{hour:02}:{minute:02}", callback_data=f"time_{hour:02}:{minute:02}")
    builder.adjust(4)

    await bot.edit_message_text("Выберите время:", chat_id=chat_id,
                                message_id=callback_query.message.message_id, reply_markup=builder.as_markup())


@dp.callback_query(lambda c: c.data.startswith('time_'))
async def process_time_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    time_str = callback_query.data.split('_')[1]
    temp_data[chat_id]['time'] = time_str
    logging.info(f"Пользователь {chat_id} выбрал время: {time_str}")

    await bot.edit_message_text("Введите сообщение для напоминания:", chat_id=chat_id,
                                message_id=callback_query.message.message_id)


@dp.message(Command(commands=['list']))
async def list_reminders(message: Message):
    chat_id = message.chat.id
    logging.info(f"Пользователь {chat_id} запросил список напоминаний.")
    if chat_id not in reminders:
        add_test_reminders(chat_id)  # Добавляем тестовые напоминания, если их нет

    current_time = datetime.now()
    reminders_list = reminders[chat_id]

    # Сортируем список напоминаний по возрастанию времени срабатывания
    reminders_list.sort(key=lambda x: x[0])

    response = "Список напоминаний:\n\n"
    for index, (reminder_time, reminder_message) in enumerate(reminders_list):
        remaining_time = (reminder_time - current_time).total_seconds()
        if remaining_time > 0:
            hours = int(remaining_time // 3600)
            minutes = int((remaining_time % 3600) // 60)
            seconds = int(remaining_time % 60)
            remaining_time_str = f"{hours} часов {minutes} минут {seconds} секунд"
            response += f"{index + 1}. Напоминание: {reminder_message}\nОсталось: {remaining_time_str}\n\n"
        else:
            response += f"{index + 1}. Напоминание: {reminder_message}\nОсталось: Напоминание уже прошло\n\n"
    await message.reply(response)


@dp.message(Command(commands=['delete']))
async def delete_reminder(message: Message):
    chat_id = message.chat.id
    logging.info(f"Пользователь {chat_id} запросил удаление напоминания.")
    if chat_id not in reminders:
        await message.reply("У вас нет напоминаний для удаления.")
        return

    reminders_list = reminders[chat_id]
    current_time = datetime.now()

    # Сортируем список напоминаний по возрастанию времени срабатывания
    reminders_list.sort(key=lambda x: x[0])

    response = "Список напоминаний:\n\n"
    for index, (reminder_time, reminder_message) in enumerate(reminders_list):
        remaining_time = (reminder_time - current_time).total_seconds()
        if remaining_time > 0:
            hours = int(remaining_time // 3600)
            minutes = int((remaining_time % 3600) // 60)
            seconds = int(remaining_time % 60)
            remaining_time_str = f"{hours} часов {minutes} минут {seconds} секунд"
            response += f"{index + 1}. {reminder_message} (Время: {reminder_time.strftime('%Y-%m-%d %H:%M')}, Осталось: {remaining_time_str})\n\n"
        else:
            response += f"{index + 1}. {reminder_message} (Время: {reminder_time.strftime('%Y-%m-%d %H:%M')}, Осталось: Напоминание уже прошло)\n\n"

    response += "Введите номер напоминания, которое хотите удалить:"
    await message.reply(response)

    # Сохраняем состояние для ожидания номера напоминания
    temp_data[chat_id] = {'action': 'delete'}


@dp.message()
async def handle_message(message: Message):
    chat_id = message.chat.id
    if 'action' in temp_data.get(chat_id, {}) and temp_data[chat_id]['action'] == 'delete':
        try:
            index = int(message.text) - 1
            if 0 <= index < len(reminders[chat_id]):
                del reminders[chat_id][index]
                await message.reply(f"Напоминание №{index + 1} удалено.")
            else:
                await message.reply("Неверный номер напоминания.")
        except ValueError:
            await message.reply("Пожалуйста, введите корректный номер напоминания.")
        finally:
            del temp_data[chat_id]
    elif chat_id in temp_data and 'date' in temp_data[chat_id] and 'time' in temp_data[chat_id]:
        date_str = temp_data[chat_id]['date']
        time_str = temp_data[chat_id]['time']
        reminder_message = message.text
        logging.info(f"Пользователь {chat_id} ввел сообщение для напоминания: {reminder_message}")

        # Формируем полную дату и время
        reminder_time_str = f"{date_str} {time_str}"
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
        asyncio.create_task(send_reminder(chat_id, reminder_message, sleep_time))

        # Очистите временные данные
        del temp_data[chat_id]


async def send_reminder(chat_id, reminder_message, sleep_time):
    logging.info(f"Запуск таймера для напоминания: {reminder_message} через {sleep_time} секунд")
    await asyncio.sleep(sleep_time)
    logging.info(f"Отправка напоминания: {reminder_message} для пользователя {chat_id}")
    await bot.send_message(chat_id=chat_id, text=f"Напоминание: {reminder_message}")
    logging.info(f"Напоминание отправлено: {reminder_message} для пользователя {chat_id}")


async def main():
    logging.info("Запуск бота...")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
