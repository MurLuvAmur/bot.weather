import os
import requests
import json
import time
import schedule
import threading
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from cachetools import TTLCache

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

# Кэш для погодных данных
weather_cache = TTLCache(maxsize=100, ttl=1800)  # 30 минут

# Файл для хранения данных пользователей
USER_DATA_FILE = "user_data.json"

# Загрузка данных пользователей
def load_user_data():
    try:
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Сохранение данных пользователей
def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Создание главной клавиатуры
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🌤 Погода в моём городе")],
        [KeyboardButton("📍 Установить город"), KeyboardButton("⚙️ Настройки")],
        [KeyboardButton("❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Создание клавиатуры настроек
def get_settings_keyboard(user_data, user_id):
    notifications_status = "🔔 Уведомления: ВКЛ" if user_data.get(str(user_id), {}).get("notifications", True) else "🔕 Уведомления: ВЫКЛ"
    
    keyboard = [
        [KeyboardButton("🕐 Установить время уведомлений")],
        [KeyboardButton(notifications_status)],
        [KeyboardButton("📊 Мой профиль")],
        [KeyboardButton("↩️ Назад в меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Создание клавиатуры для выбора времени
def get_time_keyboard():
    keyboard = [
        [KeyboardButton("07:00"), KeyboardButton("08:00"), KeyboardButton("09:00")],
        [KeyboardButton("10:00"), KeyboardButton("18:00"), KeyboardButton("20:00")],
        [KeyboardButton("↩️ Назад к настройкам")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Получение данных о погоде
def get_weather(city, api_key):
    if city in weather_cache:
        print(f"Используем кэшированные данные для {city}")
        return weather_cache[city]
    
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",
        "lang": "ru"
    }
    response = requests.get(base_url, params=params)
    data = response.json()
    
    if data.get("cod") == 200:
        weather_cache[city] = data
        print(f"Данные для {city} сохранены в кэш")
    
    return data

# Форматирование ответа с погодой
def format_weather_response(weather_data):
    if weather_data.get("cod") != 200:
        return "Не могу найти погоду для этого города. Проверь название и попробуй снова."
    
    city = weather_data["name"]
    temp = weather_data["main"]["temp"]
    feels_like = weather_data["main"]["feels_like"]
    humidity = weather_data["main"]["humidity"]
    pressure = weather_data["main"]["pressure"]
    wind_speed = weather_data["wind"]["speed"]
    description = weather_data["weather"][0]["description"]
    
    pressure_mmhg = round(pressure / 1.333)
    
    return (
        f"Погода в городе {city}:\n"
        f"Температура: {temp}°C (ощущается как {feels_like}°C)\n"
        f"Описание: {description}\n"
        f"Влажность: {humidity}%\n"
        f"Давление: {pressure_mmhg} мм рт. ст.\n"
        f"Скорость ветра: {wind_speed} м/с\n"
        f"Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    )

# Команда старта
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    
    welcome_text = (
        "Привет! Я бот погоды. 🌤\n\n"
        "Я могу:\n"
        "• Показывать погоду в любом городе\n"
        "• Сохранить твой город для быстрого доступа\n"
        "• Присылать ежедневные уведомления о погоде\n\n"
        "Выбери действие на клавиатуре ниже 👇"
    )
    
    if str(user_id) in user_data:
        city = user_data[str(user_id)]["city"]
        welcome_text += f"\n\nТвой текущий город: {city}"
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard()
    )

# Обработка кнопки "Погода в моём городе"
async def my_city_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    
    if str(user_id) not in user_data:
        await update.message.reply_text(
            "У тебя нет сохранённого города. Сначала установи его с помощью кнопки «Установить город».",
            reply_markup=get_main_keyboard()
        )
        return
    
    city = user_data[str(user_id)]["city"]
    weather_data = get_weather(city, WEATHER_API_KEY)
    response_text = format_weather_response(weather_data)
    
    await update.message.reply_text(response_text, reply_markup=get_main_keyboard())

# Обработка кнопки "Установить город"
async def set_city_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {}
    
    user_data[str(user_id)]["awaiting_input"] = "city"
    save_user_data(user_data)
    
    await update.message.reply_text(
        "Введите название города, который хотите сохранить:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("↩️ Отмена")]], resize_keyboard=True)
    )

# Обработка кнопки "Настройки"
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    
    if str(user_id) not in user_data:
        await update.message.reply_text(
            "У тебя нет сохранённого города. Сначала установи его с помощью кнопки «Установить город».",
            reply_markup=get_main_keyboard()
        )
        return
    
    await update.message.reply_text(
        "⚙️ Настройки уведомлений:",
        reply_markup=get_settings_keyboard(user_data, user_id)
    )

# Обработка кнопки "Установить время уведомлений"
async def set_time_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    
    user_data[str(user_id)]["awaiting_input"] = "time"
    save_user_data(user_data)
    
    current_time = user_data[str(user_id)].get("notification_time", "08:00")
    
    await update.message.reply_text(
        f"Выберите время уведомлений или введите своё в формате ЧЧ:ММ (например, 09:30).\nТекущее время: {current_time}",
        reply_markup=get_time_keyboard()
    )

# Обработка кнопки уведомлений (вкл/выкл)
async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    
    if str(user_id) not in user_data:
        await update.message.reply_text(
            "У тебя нет сохранённого профиля. Сначала установи город.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Переключаем статус уведомлений
    current_status = user_data[str(user_id)].get("notifications", True)
    user_data[str(user_id)]["notifications"] = not current_status
    save_user_data(user_data)
    
    new_status = "ВКЛ" if not current_status else "ВЫКЛ"
    emoji = "🔔" if not current_status else "🔕"
    
    await update.message.reply_text(
        f"{emoji} Уведомления теперь {new_status}",
        reply_markup=get_settings_keyboard(user_data, user_id)
    )

# Обработка кнопки "Мой профиль"
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    
    if str(user_id) not in user_data:
        await update.message.reply_text(
            "У тебя нет сохранённого профиля. Сначала установи город.",
            reply_markup=get_main_keyboard()
        )
        return
    
    data = user_data[str(user_id)]
    city = data["city"]
    notify_time = data.get("notification_time", "08:00")
    notifications = data.get("notifications", True)
    
    status = "включены" if notifications else "отключены"
    emoji = "🔔" if notifications else "🔕"
    
    profile_text = (
        f"📊 Твой профиль:\n\n"
        f"🏙 Город: {city}\n"
        f"🕐 Время уведомлений: {notify_time}\n"
        f"{emoji} Уведомления: {status}\n\n"
        f"Изменить эти настройки можно в разделе «⚙️ Настройки»"
    )
    
    await update.message.reply_text(profile_text, reply_markup=get_settings_keyboard(user_data, user_id))

# Обработка кнопки "Помощь"
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "❓ Помощь:\n\n"
        "Я бот погоды! Вот что я умею:\n\n"
        "🌤 Погода в моём городе - показать погоду в сохранённом городе\n"
        "📍 Установить город - сохранить новый город\n"
        "⚙️ Настройки - настройка уведомлений и просмотр профиля\n"
        "❓ Помощь - показать это сообщение\n\n"
        "Также ты можешь просто написать название любого города, и я покажу погоду в нём!"
    )
    
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard())

# Обработка кнопки "Назад"
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Возвращаемся в главное меню:",
        reply_markup=get_main_keyboard()
    )

# Обработка кнопки "Назад к настройкам"
async def back_to_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    
    await update.message.reply_text(
        "Возвращаемся к настройкам:",
        reply_markup=get_settings_keyboard(user_data, user_id)
    )

# Обработка кнопки "Отмена"
async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = load_user_data()
    
    if str(user_id) in user_data and "awaiting_input" in user_data[str(user_id)]:
        del user_data[str(user_id)]["awaiting_input"]
        save_user_data(user_data)
    
    await update.message.reply_text(
        "Действие отменено.",
        reply_markup=get_main_keyboard()
    )

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    user_data = load_user_data()
    
    # Проверяем, ожидает ли бот ввода от пользователя
    if str(user_id) in user_data and "awaiting_input" in user_data[str(user_id)]:
        input_type = user_data[str(user_id)]["awaiting_input"]
        
        if input_type == "city":
            # Обработка ввода города
            weather_data = get_weather(text, WEATHER_API_KEY)
            
            if weather_data.get("cod") != 200:
                await update.message.reply_text(
                    "Не могу найти этот город. Проверь название и попробуй снова.",
                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("↩️ Отмена")]], resize_keyboard=True)
                )
                return
            
            user_data[str(user_id)]["city"] = text
            del user_data[str(user_id)]["awaiting_input"]
            save_user_data(user_data)
            
            await update.message.reply_text(
                f"Твой город сохранен: {text}. Теперь ты можешь использовать кнопку «Погода в моём городе» для быстрого доступа.",
                reply_markup=get_main_keyboard()
            )
            return
            
        elif input_type == "time":
            # Обработка ввода времени
            try:
                # Проверяем формат времени
                hours, minutes = map(int, text.split(':'))
                if not (0 <= hours < 24 and 0 <= minutes < 60):
                    raise ValueError
                
                user_data[str(user_id)]["notification_time"] = text
                del user_data[str(user_id)]["awaiting_input"]
                save_user_data(user_data)
                
                await update.message.reply_text(
                    f"Время уведомлений установлено на {text}.",
                    reply_markup=get_settings_keyboard(user_data, user_id)
                )
            except ValueError:
                await update.message.reply_text(
                    "Неверный формат времени. Используй ЧЧ:ММ, например: 09:30",
                    reply_markup=get_time_keyboard()
                )
            return
    
    # Если это не специальный текст, проверяем, является ли он названием города
    weather_data = get_weather(text, WEATHER_API_KEY)
    if weather_data.get("cod") == 200:
        response_text = format_weather_response(weather_data)
        await update.message.reply_text(response_text, reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text(
            "Не могу найти этот город. Проверь название и попробуй снова.",
            reply_markup=get_main_keyboard()
        )

# Функция для отправки уведомлений о погоде
async def send_weather_notifications(app):
    user_data = load_user_data()
    if not user_data:
        return
    
    print(f"Отправка уведомлений для {len(user_data)} пользователей...")
    
    for user_id, data in user_data.items():
        try:
            # Проверяем, включены ли уведомления для пользователя
            if not data.get("notifications", True):
                continue
                
            city = data["city"]
            weather_data = get_weather(city, WEATHER_API_KEY)
            
            if weather_data.get("cod") == 200:
                response_text = format_weather_response(weather_data)
                await app.bot.send_message(
                    chat_id=user_id, 
                    text=f"🌤 Ежедневная погода:\n\n{response_text}",
                    reply_markup=get_main_keyboard()
                )
                print(f"Уведомление отправлено пользователю {user_id} для города {city}")
            else:
                print(f"Ошибка получения погоды для города {city} пользователя {user_id}")
                
            # Небольшая задержка между сообщениями
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")

# Функция для планировщика
def schedule_checker(app):
    while True:
        schedule.run_pending()
        time.sleep(60)  # Проверять каждую минуту

# Основная функция
def main():
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Добавляем обработчики для главных кнопок
    application.add_handler(MessageHandler(filters.Regex("^(🌤 Погода в моём городе)$"), my_city_weather))
    application.add_handler(MessageHandler(filters.Regex("^(📍 Установить город)$"), set_city_prompt))
    application.add_handler(MessageHandler(filters.Regex("^(⚙️ Настройки)$"), settings_command))
    application.add_handler(MessageHandler(filters.Regex("^(❓ Помощь)$"), help_command))
    application.add_handler(MessageHandler(filters.Regex("^(↩️ Назад в меню)$"), back_to_menu))
    application.add_handler(MessageHandler(filters.Regex("^(↩️ Отмена)$"), cancel_input))
    
    # Добавляем обработчики для кнопок настроек
    application.add_handler(MessageHandler(filters.Regex("^(🕐 Установить время уведомлений)$"), set_time_prompt))
    application.add_handler(MessageHandler(filters.Regex("^(🔔 Уведомления: ВКЛ)$"), toggle_notifications))
    application.add_handler(MessageHandler(filters.Regex("^(🔕 Уведомления: ВЫКЛ)$"), toggle_notifications))
    application.add_handler(MessageHandler(filters.Regex("^(📊 Мой профиль)$"), profile_command))
    application.add_handler(MessageHandler(filters.Regex("^(↩️ Назад к настройкам)$"), back_to_settings))
    
    # Добавляем обработчики для кнопок времени
    application.add_handler(MessageHandler(filters.Regex("^(07:00|08:00|09:00|10:00|18:00|20:00)$"), 
                                         lambda u, c: handle_message(u, c)))
    
    # Обработчик для всех остальных текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Настраиваем планировщик для ежедневных уведомлений
    # Запланируем отправку уведомлений для каждого пользователя в его установленное время
    user_data = load_user_data()
    for user_id, data in user_data.items():
        if data.get("notifications", True):
            notify_time = data.get("notification_time", "08:00")
            schedule.every().day.at(notify_time).do(
                lambda: asyncio.run(send_weather_notifications(application))
            )
    
    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(
        target=schedule_checker, 
        args=(application,),
        daemon=True
    )
    scheduler_thread.start()
    
    print("Бот запущен с улучшенным меню настроек...")
    application.run_polling()

if __name__ == "__main__":
    import asyncio
    main()