import asyncio
import logging
import os
import sqlite3
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

# Словарь для хранения идентификаторов таймеров
timer_tasks = {}

# Подключение к базе данных
conn = sqlite3.connect('reminders.db')
cursor = conn.cursor()

# Создание таблицы, если она не существует
cursor.execute('''
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    reminder_time TEXT,
    reminder_message TEXT,
    is_sent INTEGER DEFAULT 0
)
''')
conn.commit()
# Добавление колонки is_sent, если она не существует
cursor.execute('''
PRAGMA table_info(reminders);
''')
columns = cursor.fetchall()
column_names = [column[1] for column in columns]
if 'is_sent' not in column_names:
    cursor.execute('''
    ALTER TABLE reminders ADD COLUMN is_sent INTEGER DEFAULT 0;
    ''')
conn.commit()

# Словарь для хранения временных данных выбора
temp_data = {}

# Словарь для перевода месяцев на русский язык
months_ru = {
    1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр", 5: "Май", 6: "Июн",
    7: "Июл", 8: "Авг", 9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек"
}

# Словарь для перевода дней недели на русский язык
days_ru = {
    0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
}


def add_test_reminders(chat_id):
    # Тестовые напоминания
    test_reminders = [
        (datetime.now() + timedelta(minutes=0.20), "Тестовое напоминание 1"),
        (datetime.now() + timedelta(minutes=0.3), "Тестовое напоминание 2"),
        (datetime.now() + timedelta(minutes=0.4), "Тестовое напоминание 3"),
        (datetime.now() + timedelta(minutes=4), "Тестовое напоминание 4")
    ]

    for reminder_time, reminder_message in test_reminders:
        cursor.execute('''
        INSERT INTO reminders (chat_id, reminder_time, reminder_message)
        VALUES (?, ?, ?)
        ''', (chat_id, reminder_time.isoformat(), reminder_message))
    conn.commit()
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


async def send_command_list(message: Message):
    command_list = (
        "Список доступных команд:\n"
        "/set - установить напоминание\n"
        "/list - показать список напоминаний и оставшееся до них время\n"
        "/delete - удалить напоминание\n"
        "/start - показать это сообщение снова"
    )
    await message.reply(command_list)


@dp.message(Command(commands=['set']))
async def set_reminder(message: Message):
    chat_id = message.chat.id
    current_date = datetime.now().date()
    temp_data[chat_id] = {'current_date': current_date}
    logging.info(f"Пользователь {chat_id} начал установку напоминания.")
    await show_date_picker(message, current_date)


async def show_date_picker(message: Message, current_date: datetime.date):
    chat_id = message.chat.id

    # Создаем календарь для выбора даты
    builder = InlineKeyboardBuilder()
    days_short = {
        0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
    }
    start_of_week = current_date - timedelta(days=current_date.weekday())

    # Добавляем кнопку "назад" перед датами
    builder.button(text="◀️", callback_data="scroll_back")
    builder.adjust(1)

    for day in range(7):  # Показываем даты на текущую неделю
        date = start_of_week + timedelta(days=day)
        if date < datetime.now().date():
            continue  # Пропускаем прошедшие даты
        day_name = days_short[date.weekday()]  # Сокращённое название дня недели
        month_name = months_ru[date.month]  # Сокращённое название месяца
        date_str = date.strftime('%Y-%m-%d')
        builder.button(text=f"{date.day} {month_name} {day_name}", callback_data=f"date_{date_str}")
    builder.adjust(1)  # Отображаем даты в одном столбце

    # Добавляем кнопку для прокрутки недель вперед
    builder.button(text="▶️", callback_data="scroll_forward")
    builder.adjust(1)

    current_day_name = days_short[current_date.weekday()]
    current_month_name = months_ru[current_date.month]
    current_date_str = f"{current_date.day} {current_month_name} {current_day_name}"

    await message.reply(f"Текущая дата: {current_date_str}\nВыберите дату:", reply_markup=builder.as_markup())


@dp.callback_query(lambda c: c.data.startswith('date_'))
async def process_date_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    date_str = callback_query.data.split('_')[1]
    temp_data[chat_id]['date'] = date_str
    logging.info(f"Пользователь {chat_id} выбрал дату: {date_str}")

    date = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = f"{date.day} {months_ru[date.month]} {days_ru[date.weekday()]}"

    await show_hour_picker(callback_query, date_display)


async def show_hour_picker(callback_query: types.CallbackQuery, date_display: str):
    chat_id = callback_query.message.chat.id

    # Создаем инлайн-клавиатуру для выбора часов
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️", callback_data="back_to_date")
    builder.adjust(1)
    for hour in range(0, 24):
        builder.button(text=f"{hour:02}", callback_data=f"hour_{hour:02}")
    builder.adjust(2)  # Отображаем часы в двух столбцах

    await bot.edit_message_text(f"Выбрано: {date_display}\nВыберите час:", chat_id=chat_id,
                                message_id=callback_query.message.message_id, reply_markup=builder.as_markup())


@dp.callback_query(lambda c: c.data.startswith('hour_'))
async def process_hour_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    hour_str = callback_query.data.split('_')[1]
    temp_data[chat_id]['hour'] = hour_str
    logging.info(f"Пользователь {chat_id} выбрал час: {hour_str}")

    date_str = temp_data[chat_id]['date']
    date = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = f"{date.day} {months_ru[date.month]} {days_ru[date.weekday()]}"

    await show_minute_picker(callback_query, date_display, hour_str)


async def show_minute_picker(callback_query: types.CallbackQuery, date_display: str, hour_str: str):
    chat_id = callback_query.message.chat.id

    # Создаем инлайн-клавиатуру для выбора минут
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️", callback_data="back_to_hour")
    builder.adjust(1)
    for minute in range(0, 60, 5):
        builder.button(text=f"{minute:02}", callback_data=f"minute_{minute:02}")
    builder.adjust(1)  # Отображаем минуты в одном столбце

    await bot.edit_message_text(f"Выбрано: {date_display} {hour_str}:00\nВыберите минуты:", chat_id=chat_id,
                                message_id=callback_query.message.message_id, reply_markup=builder.as_markup())


@dp.callback_query(lambda c: c.data.startswith('minute_'))
async def process_minute_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    minute_str = callback_query.data.split('_')[1]
    temp_data[chat_id]['minute'] = minute_str
    logging.info(f"Пользователь {chat_id} выбрал минуты: {minute_str}")

    date_str = temp_data[chat_id]['date']
    hour_str = temp_data[chat_id]['hour']
    date = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = f"{date.day} {months_ru[date.month]} {days_ru[date.weekday()]}"

    await show_message_input(callback_query, date_display, hour_str, minute_str)


async def show_message_input(callback_query: types.CallbackQuery, date_display: str, hour_str: str, minute_str: str):
    chat_id = callback_query.message.chat.id

    # Получаем уникальные последние 5 сообщений для пользователя из базы данных
    cursor.execute('''
    SELECT DISTINCT reminder_message
    FROM reminders
    WHERE chat_id = ?
    ORDER BY reminder_time DESC
    LIMIT 5
    ''', (chat_id,))
    recent_messages = cursor.fetchall()

    # Создаем инлайн-клавиатуру для выбора популярных сообщений и возврата назад
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️", callback_data="back_to_minute")
    builder.adjust(1)

    for i, (message,) in enumerate(recent_messages):
        builder.button(text=f"{i + 1}. {message}", callback_data=f"recent_message_{i}")
    builder.adjust(1)

    await bot.edit_message_text(
        f"Выбрано: {date_display} {hour_str}:{minute_str}\n"
        "Выберите одно из последних сообщений или введите свое сообщение для напоминания:",
        chat_id=chat_id,
        message_id=callback_query.message.message_id,
        reply_markup=builder.as_markup()
    )


@dp.callback_query(lambda c: c.data.startswith('recent_message_'))
async def process_recent_message_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    index = int(callback_query.data.split('_')[2])

    # Получаем выбранное популярное сообщение из базы данных
    cursor.execute('''
    SELECT DISTINCT reminder_message
    FROM reminders
    WHERE chat_id = ?
    ORDER BY reminder_time DESC
    LIMIT 5
    ''', (chat_id,))
    recent_messages = cursor.fetchall()

    if 0 <= index < len(recent_messages):
        selected_message = recent_messages[index][0]
        temp_data[chat_id]['message'] = selected_message

        # Формируем полную дату и время
        date_str = temp_data[chat_id]['date']
        hour_str = temp_data[chat_id]['hour']
        minute_str = temp_data[chat_id]['minute']
        reminder_time_str = f"{date_str} {hour_str}:{minute_str}"
        reminder_time = datetime.strptime(reminder_time_str, '%Y-%m-%d %H:%M')
        current_time = datetime.now()

        if reminder_time <= current_time:
            await bot.edit_message_text(
                "Дата и время напоминания должны быть в будущем.",
                chat_id=chat_id,
                message_id=callback_query.message.message_id
            )
            return

        # Установите напоминание
        cursor.execute('''
        INSERT INTO reminders (chat_id, reminder_time, reminder_message)
        VALUES (?, ?, ?)
        ''', (chat_id, reminder_time.isoformat(), selected_message))
        conn.commit()

        # Получаем идентификатор только что добавленного напоминания
        reminder_id = cursor.lastrowid

        logging.info(f"Напоминание добавлено: {reminder_time} - {selected_message}")
        await bot.edit_message_text(
            f"Напоминание установлено на {reminder_time.strftime('%Y-%m-%d %H:%M')}.",
            chat_id=chat_id,
            message_id=callback_query.message.message_id
        )

        # Запустите таймер для напоминания
        sleep_time = (reminder_time - current_time).total_seconds()
        asyncio.create_task(send_reminder(chat_id, selected_message, sleep_time, reminder_id))

        # Очистите временные данные
        del temp_data[chat_id]
        await send_command_list(callback_query.message)
    else:
        await bot.edit_message_text(
            "Неверный номер сообщения. Пожалуйста, выберите снова.",
            chat_id=chat_id,
            message_id=callback_query.message.message_id
        )



@dp.callback_query(lambda c: c.data.startswith('popular_message_'))
async def process_popular_message_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    index = int(callback_query.data.split('_')[2])

    # Получаем выбранное популярное сообщение из базы данных
    cursor.execute('''
    SELECT reminder_message
    FROM reminders
    WHERE chat_id = ?
    GROUP BY reminder_message
    ORDER BY COUNT(reminder_message) DESC
    LIMIT 5
    ''', (chat_id,))
    popular_messages = cursor.fetchall()

    if 0 <= index < len(popular_messages):
        selected_message = popular_messages[index][0]
        temp_data[chat_id]['message'] = selected_message

        # Формируем полную дату и время
        date_str = temp_data[chat_id]['date']
        hour_str = temp_data[chat_id]['hour']
        minute_str = temp_data[chat_id]['minute']
        reminder_time_str = f"{date_str} {hour_str}:{minute_str}"
        reminder_time = datetime.strptime(reminder_time_str, '%Y-%m-%d %H:%M')
        current_time = datetime.now()

        if reminder_time <= current_time:
            await bot.edit_message_text(
                "Дата и время напоминания должны быть в будущем.",
                chat_id=chat_id,
                message_id=callback_query.message.message_id
            )
            return

        # Установите напоминание
        cursor.execute('''
        INSERT INTO reminders (chat_id, reminder_time, reminder_message)
        VALUES (?, ?, ?)
        ''', (chat_id, reminder_time.isoformat(), selected_message))
        conn.commit()
        logging.info(f"Напоминание добавлено: {reminder_time} - {selected_message}")
        await bot.edit_message_text(
            f"Напоминание установлено на {reminder_time.strftime('%Y-%m-%d %H:%M')}.",
            chat_id=chat_id,
            message_id=callback_query.message.message_id
        )

        # Запустите таймер для напоминания
        sleep_time = (reminder_time - current_time).total_seconds()
        asyncio.create_task(send_reminder(chat_id, selected_message, sleep_time))

        # Очистите временные данные
        del temp_data[chat_id]
        await send_command_list(callback_query.message)
    else:
        await bot.edit_message_text(
            "Неверный номер сообщения. Пожалуйста, выберите снова.",
            chat_id=chat_id,
            message_id=callback_query.message.message_id
        )


@dp.callback_query(lambda c: c.data == 'back_to_date')
async def back_to_date(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    current_date = temp_data[chat_id]['current_date']
    await show_date_picker(callback_query.message, current_date)


@dp.callback_query(lambda c: c.data == 'back_to_hour')
async def back_to_hour(callback_query: types.CallbackQuery):
    date_str = temp_data[callback_query.message.chat.id]['date']
    date = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = f"{date.day} {months_ru[date.month]} {days_ru[date.weekday()]}"
    await show_hour_picker(callback_query, date_display)


@dp.callback_query(lambda c: c.data == 'back_to_minute')
async def back_to_minute(callback_query: types.CallbackQuery):
    date_str = temp_data[callback_query.message.chat.id]['date']
    hour_str = temp_data[callback_query.message.chat.id]['hour']
    date = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = f"{date.day} {months_ru[date.month]} {days_ru[date.weekday()]}"
    await show_minute_picker(callback_query, date_display, hour_str)


@dp.callback_query(lambda c: c.data == 'scroll_back')
async def scroll_back(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    temp_data[chat_id]['current_date'] -= timedelta(weeks=1)
    await update_date_picker(callback_query)


@dp.callback_query(lambda c: c.data == 'scroll_forward')
async def scroll_forward(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    temp_data[chat_id]['current_date'] += timedelta(weeks=1)
    await update_date_picker(callback_query)


async def update_date_picker(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    current_date = temp_data[chat_id]['current_date']

    # Создаем календарь для выбора даты
    builder = InlineKeyboardBuilder()
    days_short = {
        0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
    }
    start_of_week = current_date - timedelta(days=current_date.weekday())

    # Добавляем кнопку "назад" перед датами
    builder.button(text="◀️", callback_data="scroll_back")
    builder.adjust(1)

    for day in range(7):  # Показываем даты на текущую неделю
        date = start_of_week + timedelta(days=day)
        if date < datetime.now().date():
            continue  # Пропускаем прошедшие даты
        day_name = days_short[date.weekday()]  # Сокращённое название дня недели
        month_name = months_ru[date.month]  # Сокращённое название месяца
        date_str = date.strftime('%Y-%m-%d')
        builder.button(text=f"{date.day} {month_name} {day_name}", callback_data=f"date_{date_str}")
    builder.adjust(1)  # Отображаем даты в одном столбце

    # Добавляем кнопку для прокрутки недель вперед
    builder.button(text="▶️", callback_data="scroll_forward")
    builder.adjust(1)

    current_day_name = days_short[current_date.weekday()]
    current_month_name = months_ru[current_date.month]
    current_date_str = f"{current_date.day} {current_month_name} {current_day_name}"

    await bot.edit_message_text(f"Текущая дата: {current_date_str}\nВыберите дату:", chat_id=chat_id,
                                message_id=callback_query.message.message_id, reply_markup=builder.as_markup())


@dp.message(Command(commands=['list']))
async def list_reminders(message: Message):
    chat_id = message.chat.id
    logging.info(f"Пользователь {chat_id} запросил список напоминаний.")

    cursor.execute(
        'SELECT reminder_time, reminder_message, is_sent FROM reminders WHERE chat_id = ? ORDER BY reminder_time ASC',
        (chat_id,))
    reminders_list = cursor.fetchall()

    if not reminders_list:
        add_test_reminders(chat_id)  # Добавляем тестовые напоминания, если их нет
        cursor.execute(
            'SELECT reminder_time, reminder_message, is_sent FROM reminders WHERE chat_id = ? ORDER BY reminder_time ASC',
            (chat_id,))
        reminders_list = cursor.fetchall()

    current_time = datetime.now()

    response = "Список напоминаний:\n\n"
    last_past_reminder = None

    for index, (reminder_time_str, reminder_message, is_sent) in enumerate(reminders_list):
        reminder_time = datetime.fromisoformat(reminder_time_str)
        remaining_time = (reminder_time - current_time).total_seconds()
        status = "Отправлено" if is_sent else "Не отправлено"

        if remaining_time > 0:
            hours = int(remaining_time // 3600)
            minutes = int((remaining_time % 3600) // 60)
            seconds = int(remaining_time % 60)
            remaining_time_str = f"{hours} часов {minutes} минут {seconds} секунд"
            response += f"{index + 1}. Напоминание: {reminder_message}\nВремя: {reminder_time.strftime('%Y-%m-%d %H:%M')}\nОсталось: {remaining_time_str}\nСтатус: {status}\n\n"
        else:
            last_past_reminder = f"Последнее прошедшее напоминание: {reminder_message} (Время: {reminder_time.strftime('%Y-%m-%d %H:%M')})"

    if last_past_reminder:
        response = last_past_reminder + "\n\n" + response

    await message.reply(response)
    await send_command_list(message)


async def send_reminder(chat_id, reminder_message, sleep_time, reminder_id):
    logging.info(f"Запуск таймера для напоминания: {reminder_message} через {sleep_time} секунд")
    task = asyncio.create_task(send_reminder_task(chat_id, reminder_message, sleep_time, reminder_id))
    timer_tasks[reminder_id] = task

async def send_reminder_task(chat_id, reminder_message, sleep_time, reminder_id):
    await asyncio.sleep(sleep_time)
    logging.info(f"Отправка напоминания: {reminder_message} для пользователя {chat_id}")
    await bot.send_message(chat_id=chat_id, text=f"Напоминание: {reminder_message}")
    logging.info(f"Напоминание отправлено: {reminder_message} для пользователя {chat_id}")

    # Отметить напоминание как отправленное
    cursor.execute('''
    UPDATE reminders
    SET is_sent = 1
    WHERE id = ?
    ''', (reminder_id,))
    conn.commit()

    # Удалить таймер из словаря
    if reminder_id in timer_tasks:
        del timer_tasks[reminder_id]



@dp.message(Command(commands=['delete']))
async def delete_reminder(message: Message):
    chat_id = message.chat.id
    logging.info(f"Пользователь {chat_id} запросил удаление напоминания.")

    cursor.execute(
        'SELECT id, reminder_time, reminder_message FROM reminders WHERE chat_id = ? AND is_sent = 0 ORDER BY reminder_time ASC',
        (chat_id,))
    reminders_list = cursor.fetchall()

    if not reminders_list:
        await message.reply("У вас нет напоминаний для удаления.")
        await send_command_list(message)
        return

    current_time = datetime.now()

    # Создаем инлайн-клавиатуру для выбора напоминаний
    builder = InlineKeyboardBuilder()

    for index, (reminder_id, reminder_time_str, reminder_message) in enumerate(reminders_list):
        reminder_time = datetime.fromisoformat(reminder_time_str)
        remaining_time = (reminder_time - current_time).total_seconds()
        if remaining_time > 0:
            hours = int(remaining_time // 3600)
            minutes = int((remaining_time % 3600) // 60)
            seconds = int(remaining_time % 60)
            remaining_time_str = f"{hours} часов {minutes} минут {seconds} секунд"
            builder.button(
                text=f"{index + 1}. {reminder_message} (Время: {reminder_time.strftime('%Y-%m-%d %H:%M')}, Осталось: {remaining_time_str})",
                callback_data=f"delete_{reminder_id}")
            builder.adjust(1)

    await message.reply("Выберите напоминание для удаления:", reply_markup=builder.as_markup())

    # Сохраняем состояние для ожидания номера напоминания
    temp_data[chat_id] = {'action': 'delete'}


@dp.callback_query(lambda c: c.data.startswith('delete_'))
async def process_delete_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    reminder_id = int(callback_query.data.split('_')[1])

    # Отменяем таймер, если он существует
    if reminder_id in timer_tasks:
        timer_tasks[reminder_id].cancel()
        del timer_tasks[reminder_id]

    # Удаляем напоминание из базы данных
    cursor.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
    conn.commit()

    await callback_query.message.edit_text(f"Напоминание №{reminder_id} удалено.")
    await send_command_list(callback_query.message)


@dp.message()
async def handle_message(message: Message):
    chat_id = message.chat.id

    # Обработка команд
    if message.text == '/list':
        await list_reminders(message)
        return
    elif message.text == '/delete':
        await delete_reminder(message)
        return

    # Обработка установки напоминания
    if 'action' in temp_data.get(chat_id, {}) and temp_data[chat_id]['action'] == 'delete':
        try:
            index = int(message.text) - 1
            cursor.execute('SELECT id FROM reminders WHERE chat_id = ?', (chat_id,))
            reminders_list = cursor.fetchall()
            if 0 <= index < len(reminders_list):
                reminder_id = reminders_list[index][0]
                cursor.execute('DELETE FROM reminders WHERE id = ?', (reminder_id,))
                conn.commit()
                await message.reply(f"Напоминание №{index + 1} удалено.")
            else:
                await message.reply("Неверный номер напоминания.")
        except ValueError:
            await message.reply("Пожалуйста, введите корректный номер напоминания.")
        finally:
            del temp_data[chat_id]
        await send_command_list(message)
    elif 'date' in temp_data.get(chat_id, {}) and 'hour' in temp_data[chat_id] and 'minute' in temp_data[chat_id]:
        date_str = temp_data[chat_id]['date']
        hour_str = temp_data[chat_id]['hour']
        minute_str = temp_data[chat_id]['minute']
        reminder_message = message.text
        logging.info(f"Пользователь {chat_id} ввел сообщение для напоминания: {reminder_message}")

        # Формируем полную дату и время
        reminder_time_str = f"{date_str} {hour_str}:{minute_str}"
        reminder_time = datetime.strptime(reminder_time_str, '%Y-%m-%d %H:%M')
        current_time = datetime.now()

        if reminder_time <= current_time:
            await message.reply("Дата и время напоминания должны быть в будущем.")
            return

        # Установите напоминание
        cursor.execute('''
        INSERT INTO reminders (chat_id, reminder_time, reminder_message)
        VALUES (?, ?, ?)
        ''', (chat_id, reminder_time.isoformat(), reminder_message))
        conn.commit()
        logging.info(f"Напоминание добавлено: {reminder_time} - {reminder_message}")
        await message.reply(f"Напоминание установлено на {reminder_time.strftime('%Y-%m-%d %H:%M')}.")

        # Запустите таймер для напоминания
        sleep_time = (reminder_time - current_time).total_seconds()
        asyncio.create_task(send_reminder(chat_id, reminder_message, sleep_time))

        # Очистите временные данные
        del temp_data[chat_id]
        await send_command_list(message)
    else:
        await message.reply("Пожалуйста, выберите дату, час и минуты для напоминания.")


async def main():
    logging.info("Запуск бота...")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
