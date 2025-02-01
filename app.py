import os
import asyncio
from fastapi.responses import FileResponse
import httpx
import json
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types.web_app_info import WebAppInfo
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from fastapi import FastAPI, HTTPException
from dotenv import find_dotenv, load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import base64
import logging

# Загружаем .env
load_dotenv(find_dotenv())

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)

# Переменные
bot = Bot(token=os.getenv("TOKEN"))
dp = Dispatcher()
app = FastAPI()
menu_data = {}
stoplist_data = {}

# API-конфигурация
API_URL = "https://api.sbis.ru/retail/nomenclature/list?"
API_BASE_URL = "https://api.sbis.ru/retail"
SBIS_TOKEN = os.getenv("SBIS_TOKEN")
API_HEADERS = {"X-SBISAccessToken": SBIS_TOKEN}
API_PARAMS = {
    "pointId": 7245,
    "priceListId": 37,
    "withBalance": True,
    "withBarcode": True,
    "onlyPublished": False,
    "page": 0,
    "pageSize": 100,
}

# CORS настройка
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Функция получения полного URL изображения
def get_image_url(image_param):
    return f"{API_BASE_URL}{image_param}" if image_param else "https://via.placeholder.com/150"

# 📌 Функция загрузки меню
async def fetch_menu():
    global menu_data
    logging.info("Запрос меню из СБИС...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(API_URL, params=API_PARAMS, headers=API_HEADERS)
            logging.info(f"Ответ СБИС: {response.status_code}")

            if response.status_code != 200:
                logging.error(f"Ошибка запроса: {response.text}")
                return None

            data = response.json().get("nomenclatures", [])
            logging.info(f"Получено {len(data)} товаров/категорий")

            categories = {}
            items = {}

            for item in data:
                hierarchical_id = item.get("hierarchicalId")
                parent_id = item.get("hierarchicalParent")

                if item.get("id") is None:  # Категория
                    categories[hierarchical_id] = {
                        "name": item.get("name"),
                        "subcategories": [],
                        "items": [],
                    }
                else:  # Товар
                    image_list = item.get("images")

                    if image_list and isinstance(image_list, list) and len(image_list) > 0:
                        image_url = get_image_url(image_list[0])
                        logging.info(f"Загрузка изображения: {image_url}")

                        img_response = await client.get(image_url)

                        if img_response.status_code == 200:
                            img_data = base64.b64encode(img_response.content).decode("utf-8")
                            image_url = f"data:image/jpeg;base64,{img_data}"
                        else:
                            logging.warning(f"Не удалось загрузить изображение {image_url}, код {img_response.status_code}")
                            image_url = "https://via.placeholder.com/150"
                    else:
                        logging.info(f"Нет изображения для товара {item.get('name')}")
                        image_url = "https://via.placeholder.com/150"

                    items[hierarchical_id] = {
                        "name": item.get("name"),
                        "price": item.get("cost"),
                        "description": item.get("description"),
                        "image": image_url,
                        "parent": parent_id,
                    }

            # Связываем категории и товары
            for item_id, item in items.items():
                if item["parent"] in categories:
                    categories[item["parent"]]["items"].append(item)

            menu_data = categories
            logging.info("Меню успешно обновлено!")
            return True

        except Exception as e:
            logging.error(f"Ошибка при загрузке меню: {e}")
            return False

# 📌 Команда /start
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🛍 Открыть магазин",
                    web_app=WebAppInfo(url="https://storied-souffle-8bb402.netlify.app/"),
                )
            ]
        ],
        resize_keyboard=True
    )
    await message.answer("👋 Привет! Добро пожаловать в наш магазин!", reply_markup=markup)
    await message.answer("🔄 Загружаем меню...")

    success = await fetch_menu()
    if success:
        await message.answer("✅ Меню обновлено! Перейдите в веб-приложение для просмотра.")
    else:
        await message.answer("⚠️ Не удалось обновить меню. Попробуйте позже.")

# 📦 Обработчик заказа
@dp.message()
async def process_order(message: types.Message):
    try:
        order_data = json.loads(message.text)  # Получаем JSON из сообщения
        logging.info(f"Обработан заказ: {order_data}")

        # Отправка заказа в API
        async with httpx.AsyncClient() as client:
            response = await client.post("http://127.0.0.1:8000/order", json=order_data)
        
        if response.status_code == 200:
            await message.answer("✅ Ваш заказ принят! Спасибо за покупку.")
        else:
            await message.answer("⚠️ Ошибка при обработке заказа. Попробуйте позже.")
    
    except json.JSONDecodeError:
        await message.answer("❌ Ошибка! Некорректный формат данных.")

# 🔗 API маршруты
@app.get("/menu")
async def get_menu():
    logging.info("Запрос на получение меню через API")
    if not menu_data:
        raise HTTPException(status_code=404, detail="Меню не найдено")
    return menu_data

@app.post("/order")
async def receive_order(order_data: dict):
    """
    Обработчик для получения заказа из бота.
    Ожидает данные в JSON-формате и логирует их.
    """
    try:
        logging.info(f"📦 Получен заказ: {json.dumps(order_data, indent=4, ensure_ascii=False)}")
        return {"status": "success", "message": "Заказ принят"}
    except Exception as e:
        logging.error(f"❌ Ошибка обработки заказа: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обработки заказа")

@app.get("/stoplist")
async def get_stoplist():
    logging.info("Запрос на получение стоп-листа через API")
    return stoplist_data

@app.get("/image/{filename}")
async def get_image(filename: str):
    file_path = f"images/{filename}"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Файл не найден")

# 🎯 Функция запуска бота
async def on_start():
    logging.info("🤖 Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

# 📌 Основной цикл работы FastAPI + бота
async def main():
    bot_task = asyncio.create_task(on_start())
    config = uvicorn.Config(app, host="127.0.0.1", port=8000)
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    await asyncio.gather(bot_task, server_task)

# 🔥 Запуск
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Выключение сервера...")
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
