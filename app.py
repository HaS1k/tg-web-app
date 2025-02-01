import os
import asyncio
import requests
import json
from aiogram import Bot, Dispatcher, types
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types.web_app_info import WebAppInfo
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from fastapi import FastAPI
from dotenv import find_dotenv, load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import base64

load_dotenv(find_dotenv())

bot = Bot(token=os.getenv('TOKEN'))
dp = Dispatcher()
app = FastAPI()

# Конфигурация бота и API
API_URL = "https://api.sbis.ru/retail/nomenclature/list?"
SBIS_TOKEN = os.getenv('SBIS_TOKEN')
API_HEADERS = {"X-SBISAccessToken": SBIS_TOKEN}
API_PARAMS = {
    "pointId": 7245,
    "priceListId": 37,
    "withBalance": True,
    "withBarcode": True,
    "onlyPublished": False,
    "page": 0,
    "pageSize": 50
}

# Разрешаем запросы с Netlify
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://storied-souffle-8bb402.netlify.app"],  # Укажи фронтенд URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Переменная для хранения данных
menu_data = {}

# Функция запроса данных из СБИС
# Функция для получения полного URL изображения
def get_image_url(image_param):
    base_url = "https://api.sbis.ru/retail/img"
    return f"{base_url}?params={image_param}"

async def fetch_menu():
    global menu_data
    response = requests.get(API_URL, params=API_PARAMS, headers=API_HEADERS)

    if response.status_code == 200:
        data = response.json().get("nomenclatures", [])
        
        categories = {}
        items = {}

        for item in data:
            hierarchical_id = item.get("hierarchicalId")
            parent_id = item.get("hierarchicalParent")

            if item.get("id") is None:  # Это категория
                categories[hierarchical_id] = {
                    "name": item.get("name"),
                    "subcategories": [],
                    "items": []
                }
            else:  # Это товар
                image_list = item.get("images")
                if image_list and isinstance(image_list, list) and len(image_list) > 0:
                    image_url = get_image_url(image_list[0])
                    
                    # Загружаем изображение и конвертируем в base64
                    img_response = requests.get(image_url)
                    if img_response.status_code == 200:
                        img_data = base64.b64encode(img_response.content).decode("utf-8")
                        image_url = f"data:image/jpeg;base64,{img_data}"
                else:
                    image_url = "https://via.placeholder.com/150"

                items[hierarchical_id] = {
                    "name": item.get("name"),
                    "price": item.get("cost"),
                    "description": item.get("description"),
                    "image": image_url,
                    "parent": parent_id
                }

        for item_id, item in items.items():
            if item["parent"] in categories:
                categories[item["parent"]]["items"].append(item)

        menu_data = categories




@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    markap = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text='open', web_app=WebAppInfo(url='https://storied-souffle-8bb402.netlify.app/')
                )
            ]
        ]
    )
    await message.answer(text="start", reply_markup=markap)
    await message.answer("Загрузка меню...")
    await fetch_menu()
    await message.answer("Меню обновлено! Перейдите в веб-приложение для просмотра.")

@app.get("/menu")
def get_menu():
    print("Запрос данных через API FastAPI")
    return menu_data

# Функция для старта бота
async def on_start():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

# Создаем задачу для бота
async def start_bot():
    await on_start()

# FastAPI маршрут
@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}

# Основная асинхронная функция, которая запускает и сервер, и бота
async def main():
    # Запускаем бота в фоновом режиме
    bot_task = asyncio.create_task(start_bot())
    
    # Запускаем сервер FastAPI
    config = uvicorn.Config(app, host="0.0.0.0", port=8080)
    server = uvicorn.Server(config)
    
    # Запускаем сервер в фоновом режиме
    server_task = asyncio.create_task(server.serve())

    # Ждем завершения обоих процессов
    await asyncio.gather(bot_task, server_task)

# Запуск приложения с использованием asyncio
if __name__ == "__main__":
    asyncio.run(main())
