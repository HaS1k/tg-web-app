import os
import asyncio
import base64
import json
import logging

import httpx
import uvicorn
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types.web_app_info import WebAppInfo

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
                        "id": item.get("id"),  # Добавляем ID товара
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

# Функция формирования стартовой клавиатуры (как после /start)
def get_start_reply_markup():
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(
                text="open",
                web_app=WebAppInfo(url="https://storied-souffle-8bb402.netlify.app/"),
            )
        ]],
        resize_keyboard=True
    )

# 📌 Команда /start
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    markup = get_start_reply_markup()
    await message.answer(text="start", reply_markup=markup)
    await message.answer("Загрузка меню...")

    success = await fetch_menu()
    if success:
        await message.answer("Меню обновлено! Перейдите в веб-приложение для просмотра.")
    else:
        await message.answer("Не удалось обновить меню. Попробуйте позже.")

# Обработчик данных из Mini App
@dp.message()
async def handle_web_app_data(message: types.Message):
    try:
        # Получаем данные из Mini App
        data = json.loads(message.web_app_data.data)
        user_id = data.get("user_id", "unknown")  # Если user_id отсутствует, используем "unknown"
        items = data.get("items", [])  # Если items отсутствует, используем пустой список
        delivery_info = data.get("delivery_info", {})  # Если delivery_info отсутствует, используем пустой словарь

        # Логируем полученные данные
        logging.info(f"Получены данные от пользователя {user_id}:")
        logging.info(f"Товары: {items}")
        logging.info(f"Детали доставки: {delivery_info}")

        # Формируем ответное сообщение
        response_message = (
            f"Ваш заказ оформлен!\n\n"
            f"Детали доставки:\n"
            f"Имя: {delivery_info.get('name', 'Не указано')}\n"
            f"Телефон: {delivery_info.get('phone', 'Не указан')}\n"
            f"Адрес: {delivery_info.get('street', 'Не указана')}, дом {delivery_info.get('house', 'Не указан')}, кв {delivery_info.get('apartment', 'Не указана')}\n\n"
            f"Товары:\n"
        )

        # Добавляем информацию о товарах
        for item in items:
            response_message += f"Товар ID: {item.get('id', 'Не указан')} - {item.get('price', 0)}₽ x {item.get('quantity', 0)}\n"

        # Отправляем ответное сообщение пользователю
        await message.answer(response_message)

        # Подготавливаем данные заказа для передачи в веб-приложение при редактировании
        order_json = json.dumps(data)
        order_encoded = base64.urlsafe_b64encode(order_json.encode()).decode()

        # Формируем инлайн-клавиатуру с 3 кнопками
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить заказ", callback_data="confirm_order")],
            [InlineKeyboardButton(
                text="Редактировать заказ",
                # Передаём закодированные данные заказа в параметре order_data
                web_app=WebAppInfo(url=f"https://storied-souffle-8bb402.netlify.app/?order_data={order_encoded}")
            )],
            [InlineKeyboardButton(text="Отменить заказ", callback_data="cancel_order")]
        ])

        await message.answer("Выберите действие:", reply_markup=inline_kb)

    except Exception as e:
        logging.error(f"Ошибка обработки данных: {e}")
        await message.answer("Произошла ошибка при обработке вашего заказа.")

# Обработчик callback-запросов для кнопки "Подтвердить заказ"
@dp.callback_query(lambda c: c.data == "confirm_order")
async def process_confirm_order(callback_query: types.CallbackQuery):
    await callback_query.answer("Заказ подтвержден!", show_alert=True)
    # Здесь можно добавить дальнейшую логику подтверждения заказа

# Обработчик callback-запросов для кнопки "Отменить заказ"
@dp.callback_query(lambda c: c.data == "cancel_order")
async def process_cancel_order(callback_query: types.CallbackQuery):
    await callback_query.answer("Заказ отменен", show_alert=True)
    # "Сбрасываем" состояние бота и возвращаем стартовую клавиатуру
    markup = get_start_reply_markup()
    await callback_query.message.answer("Заказ отменен. Возвращаем в начальное состояние.", reply_markup=markup)
    # При необходимости можно также перезагрузить меню или выполнить дополнительные действия

# 🔗 API маршруты
@app.get("/menu")
async def get_menu():
    logging.info("Запрос на получение меню через API")
    if not menu_data:
        raise HTTPException(status_code=404, detail="Меню не найдено")
    return menu_data

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
    logging.info("Бот запущен!")
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
