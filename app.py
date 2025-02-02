import os
import asyncio
import base64
import json
from datetime import datetime

import httpx
import uvicorn
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types.web_app_info import WebAppInfo

# Загружаем .env
load_dotenv(find_dotenv())

# Инициализация бота и приложения
bot = Bot(token=os.getenv("TOKEN"))
dp = Dispatcher()
app = FastAPI()

# Глобальные переменные
menu_data = {}
orders_pending = {}

# API-конфигурация для получения меню
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

# Константы для создания заказа
POINT_ID = 7245      # Идентификатор точки продаж
PRICE_LIST_ID = 37   # Идентификатор прайс-листа

# CORS настройка
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_image_url(image_param):
    """Возвращает полный URL изображения или placeholder."""
    return f"{API_BASE_URL}{image_param}" if image_param else "https://via.placeholder.com/150"

async def fetch_menu():
    """Получает меню из API СБИС и формирует словарь категорий с товарами (включая externalId)."""
    global menu_data
    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL, params=API_PARAMS, headers=API_HEADERS)
        if response.status_code != 200:
            return None

        data = response.json().get("nomenclatures", [])
        categories = {}
        items = {}

        for item in data:
            hierarchical_id = item.get("hierarchicalId")
            parent_id = item.get("hierarchicalParent")
            # Если поле id отсутствует, считаем, что это категория
            if item.get("id") is None:
                categories[hierarchical_id] = {
                    "name": item.get("name"),
                    "subcategories": [],
                    "items": [],
                }
            else:
                # Загружаем изображение товара, если оно есть
                image_list = item.get("images")
                if image_list and isinstance(image_list, list) and len(image_list) > 0:
                    image_url = get_image_url(image_list[0])
                    img_response = await client.get(image_url)
                    if img_response.status_code == 200:
                        img_data = base64.b64encode(img_response.content).decode("utf-8")
                        image_url = f"data:image/jpeg;base64,{img_data}"
                    else:
                        image_url = "https://via.placeholder.com/150"
                else:
                    image_url = "https://via.placeholder.com/150"

                # Сохраняем externalId вместе с другими данными
                items[hierarchical_id] = {
                    "externalId": item.get("externalId"),
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "price": item.get("cost"),
                    "description": item.get("description"),
                    "image": image_url,
                    "parent": parent_id,
                }

        # Привязываем товары к категориям
        for item_id, item in items.items():
            if item["parent"] in categories:
                categories[item["parent"]]["items"].append(item)

        menu_data = categories
        return True

def get_start_reply_markup():
    """Возвращает стартовую клавиатуру для команды /start."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(
            text="open",
            web_app=WebAppInfo(url="https://storied-souffle-8bb402.netlify.app/")
        )]],
        resize_keyboard=True
    )

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

@dp.message()
async def handle_web_app_data(message: types.Message):
    """
    Обработка данных, полученных из Mini App.
    Ожидается, что веб-приложение передаст данные заказа,
    где товары содержат externalId, цену и количество.
    """
    try:
        data = json.loads(message.web_app_data.data)
        # Сохраняем данные заказа для дальнейшей обработки
        orders_pending[message.from_user.id] = data

        # Формируем ответ пользователю
        delivery_info = data.get("delivery_info", {})
        items = data.get("items", [])
        response_message = (
            f"Ваш заказ оформлен!\n\n"
            f"Детали доставки:\n"
            f"Имя: {delivery_info.get('name', 'Не указано')}\n"
            f"Телефон: {delivery_info.get('phone', 'Не указан')}\n"
            f"Адрес: {delivery_info.get('street', 'Не указана')}, д. {delivery_info.get('house', 'Не указан')}, кв. {delivery_info.get('apartment', 'Не указана')}\n\n"
            f"Товары:\n"
        )
        for item in items:
            response_message += f"Товар: {item.get('name', 'Не указан')} - {item.get('price', 0)}₽ x {item.get('quantity', 0)}\n"

        await message.answer(response_message)

        # Кодируем данные заказа для возможности редактирования в веб-приложении
        order_json = json.dumps(data)
        order_encoded = base64.urlsafe_b64encode(order_json.encode()).decode()

        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить заказ", callback_data="confirm_order")],
            [InlineKeyboardButton(
                text="Редактировать заказ",
                web_app=WebAppInfo(url=f"https://storied-souffle-8bb402.netlify.app/?order_data={order_encoded}")
            )],
            [InlineKeyboardButton(text="Отменить заказ", callback_data="cancel_order")]
        ])
        await message.answer("Выберите действие:", reply_markup=inline_kb)

    except Exception as e:
        await message.answer("Произошла ошибка при обработке вашего заказа.")

@dp.callback_query(lambda c: c.data == "confirm_order")
async def process_confirm_order(callback_query: types.CallbackQuery):
    """
    Формирование и отправка JSON запроса к API СБИС на создание заказа.
    Для каждого товара вместо обычного id используется externalId.
    JSON запроса отправляется также в чат.
    """
    user_id = callback_query.from_user.id
    order_data = orders_pending.get(user_id)
    if not order_data:
        await callback_query.answer("Нет данных заказа. Повторите оформление.", show_alert=True)
        return

    delivery_info = order_data.get("delivery_info", {})
    items = order_data.get("items", [])

    # Формируем список товаров с использованием externalId
    nomenclatures = []
    for item in items:
        nomenclatures.append({
            "externalId": item.get("externalId") or item.get("id"),
            "priceListId": PRICE_LIST_ID,
            "count": item.get("quantity", 1),
            "cost": item.get("price")
        })

    # Формирование адреса доставки
    street = delivery_info.get("street", "")
    house = delivery_info.get("house", "")
    entrance = delivery_info.get("entrance", "")
    floor = delivery_info.get("floor", "")
    apartment = delivery_info.get("apartment", "")
    intercom = delivery_info.get("intercom", "")
    address_full = f"ул. {street}, д. {house}, подъезд {entrance}, этаж {floor}, кв. {apartment}"
    address_json = json.dumps({
        "Street": street,
        "HouseNum": house,
        "Entrance": entrance,
        "Floor": floor,
        "Apartment": apartment,
        "Intercom": intercom
    }, ensure_ascii=False)

    order_payload = {
        "product": "delivery",
        "pointId": POINT_ID,
        "comment": "тестовый заказ на доставку",
        "customer": {
            "externalId": delivery_info.get("externalCustomerId") or None,
            "name": delivery_info.get("name", ""),
            "lastname": "",
            "patronymic": "",
            "email": "",
            "phone": delivery_info.get("phone", "")
        },
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nomenclatures": nomenclatures,
        "delivery": {
            "addressFull": address_full,
            "addressJSON": address_json,
            "paymentType": "card",
            "persons": 1,
            "isPickup": False
        }
    }

    # Отправляем JSON запроса в чат (как текст)
    request_json_text = json.dumps(order_payload, ensure_ascii=False, indent=2)
    await bot.send_message(
        chat_id=user_id,
        text=f"Отправляем JSON запроса к API СБИС:\n```json\n{request_json_text}\n```",
        parse_mode=ParseMode.MARKDOWN
    )

    # Отправка запроса к API СБИС
    async with httpx.AsyncClient() as client:
        headers = {
            "Content-Type": "application/json",
            "X-SBISAccessToken": SBIS_TOKEN
        }
        try:
            response = await client.post(
                "https://api.sbis.ru/retail/order/create",
                json=order_payload,
                headers=headers
            )
            if response.status_code == 200:
                resp_json = response.json()
                result_text = f"Заказ успешно создан!\n\nОтвет API:\n```json\n{json.dumps(resp_json, ensure_ascii=False, indent=2)}\n```"
            else:
                result_text = f"Ошибка создания заказа. Код: {response.status_code}\nОтвет API:\n```json\n{response.text}\n```"
        except Exception as e:
            result_text = f"Ошибка при выполнении запроса: {e}"

    await bot.send_message(
        chat_id=user_id,
        text=result_text,
        parse_mode=ParseMode.MARKDOWN
    )
    await callback_query.answer("Запрос отправлен!", show_alert=True)

@dp.callback_query(lambda c: c.data == "cancel_order")
async def process_cancel_order(callback_query: types.CallbackQuery):
    await callback_query.answer("Заказ отменен", show_alert=True)
    markup = get_start_reply_markup()
    await callback_query.message.answer("Заказ отменен. Возвращаем в начальное состояние.", reply_markup=markup)

@app.get("/menu")
async def get_menu():
    if not menu_data:
        raise HTTPException(status_code=404, detail="Меню не найдено")
    return menu_data

@app.get("/image/{filename}")
async def get_image(filename: str):
    file_path = f"images/{filename}"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Файл не найден")

async def on_start():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

async def main():
    bot_task = asyncio.create_task(on_start())
    config = uvicorn.Config(app, host="127.0.0.1", port=8000)
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    await asyncio.gather(bot_task, server_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

