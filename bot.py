import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот погоды. Просто напиши мне название города, и я пришлю текущую погоду."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text
    weather_data = get_weather(city, WEATHER_API_KEY)
    
    if weather_data["cod"] == 200:
        response_text = format_weather_response(weather_data)
    else:
        response_text = "Не могу найти погоду для этого города. Проверь название и попробуй снова."
    
    await update.message.reply_text(response_text)

def get_weather(city, api_key):
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",
        "lang": "ru"
    }
    response = requests.get(base_url, params=params)
    return response.json()

def format_weather_response(weather_data):
    city = weather_data["name"]
    temp = weather_data["main"]["temp"]
    feels_like = weather_data["main"]["feels_like"]
    humidity = weather_data["main"]["humidity"]
    pressure = weather_data["main"]["pressure"]
    wind_speed = weather_data["wind"]["speed"]
    description = weather_data["weather"][0]["description"]
    
    # Преобразование давления в мм рт. ст.
    pressure_mmhg = round(pressure / 1.333)
    
    return (
        f"Погода в городе {city}:\n"
        f"Температура: {temp}°C (ощущается как {feels_like}°C)\n"
        f"Описание: {description}\n"
        f"Влажность: {humidity}%\n"
        f"Давление: {pressure_mmhg} мм рт. ст.\n"
        f"Скорость ветра: {wind_speed} м/с"
    )

if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот запущен...")
    application.run_polling()
