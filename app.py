import os
import asyncio
import base64
import json
import logging
from datetime import datetime, timedelta

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

# Настройка логирования: вывод в консоль
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

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
    logging.info("Запрос меню из СБИС...")
    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL, params=API_PARAMS, headers=API_HEADERS)
        if response.status_code != 200:
            logging.error(f"Ошибка запроса меню: {response.text}")
            return None

        data = response.json().get("nomenclatures", [])
        logging.info(f"Получено {len(data)} элементов (категорий/товаров)")

        categories = {}
        items = {}

        for item in data:
            hierarchical_id = item.get("hierarchicalId")
            parent_id = item.get("hierarchicalParent")
            if item.get("id") is None:
                categories[hierarchical_id] = {
                    "name": item.get("name"),
                    "subcategories": [],
                    "items": [],
                }
                logging.info(f"Добавлена категория: {item.get('name')}")
            else:
                image_list = item.get("images")
                if image_list and isinstance(image_list, list) and len(image_list) > 0:
                    image_url = get_image_url(image_list[0])
                    logging.info(f"Загрузка изображения товара: {item.get('name')} из {image_url}")
                    img_response = await client.get(image_url)
                    if img_response.status_code == 200:
                        img_data = base64.b64encode(img_response.content).decode("utf-8")
                        image_url = f"data:image/jpeg;base64,{img_data}"
                    else:
                        image_url = "https://via.placeholder.com/150"
                else:
                    image_url = "https://via.placeholder.com/150"

                items[hierarchical_id] = {
                    "externalId": item.get("externalId"),
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "price": item.get("cost"),
                    "description": item.get("description"),
                    "image": image_url,
                    "parent": parent_id,
                }
                logging.info(f"Добавлен товар: {item.get('name')} (externalId: {item.get('externalId')})")

        for item_id, item in items.items():
            if item["parent"] in categories:
                categories[item["parent"]]["items"].append(item)

        menu_data = categories
        logging.info("Меню успешно обновлено")
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
    logging.info(f"Получена команда /start от пользователя {message.from_user.id}")
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
        orders_pending[message.from_user.id] = data
        logging.info(f"Получены данные заказа от пользователя {message.from_user.id}: {data}")

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
        logging.info("Отправлено сообщение с выбором действия для заказа")
    except Exception as e:
        logging.error(f"Ошибка обработки данных заказа: {e}")
        await message.answer("Произошла ошибка при обработке вашего заказа.")

@dp.callback_query(lambda c: c.data == "confirm_order")
async def process_confirm_order(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    order_data = orders_pending.get(user_id)
    if not order_data:
        await callback_query.answer("Нет данных заказа. Повторите оформление.", show_alert=True)
        return

    delivery_info = order_data.get("delivery_info", {})
    items = order_data.get("items", [])

    # Формируем список товаров (используем externalId, если он есть)
    nomenclatures = []
    for item in items:
        nomenclatures.append({
            "externalId": item.get("externalId") or item.get("id"),
            "priceListId": PRICE_LIST_ID,
            "count": item.get("quantity", 1),
            "cost": item.get("price")
        })
    logging.info(f"Формирование заказа для пользователя {user_id} с товарами: {nomenclatures}")

    # Получаем стандартные адресные данные
    street = delivery_info.get("street", "")
    house = delivery_info.get("house", "")
    entrance = delivery_info.get("entrance", "")
    floor = delivery_info.get("floor", "")
    apartment = delivery_info.get("apartment", "")
    intercom = delivery_info.get("intercom", "")

    # Новые поля из формы
    delivery_type = delivery_info.get("deliveryType")            # "delivery" или "pickup"
    order_description = delivery_info.get("orderDescription", "")   # Дополнительное описание заказа
    num_persons = delivery_info.get("numPersons", "1")              # Количество человек (строка)
    delivery_time_str = delivery_info.get("deliveryTime")           # Ожидается формат "HH:MM"
    payment_type = delivery_info.get("paymentType")                  # "card" или "cash"

    # Формируем время доставки на основе введённого времени.
    # Если введённое время уже прошло сегодня, то прибавляем 1 день.
    try:
        today = datetime.now().date()
        delivery_dt = datetime.strptime(f"{today} {delivery_time_str}", "%Y-%m-%d %H:%M")
        if delivery_dt < datetime.now():
            delivery_dt += timedelta(days=1)
    except Exception as e:
        logging.error(f"Ошибка при разборе времени доставки: {e}")
        # Если ошибка разбора, используем время сейчас + 1 мин
        delivery_dt = datetime.now() + timedelta(minutes=1)
    order_datetime = delivery_dt.strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"Устанавливаем время доставки: {order_datetime}")

    # Если тип заказа "pickup" (самовывоз), то адрес доставки можно оставить пустым
    if delivery_type == "pickup":
        address_full = ""
        address_json = "{}"
    else:
        address_full = f"ул. {street}, д. {house}, подъезд {entrance}, этаж {floor}, кв. {apartment}"
        # Формируем JSON адреса; можно добавить дополнительные поля при необходимости
        address_json = json.dumps({
            "Street": street,
            "HouseNum": house,
            "Entrance": entrance,
            "Floor": floor,
            "Apartment": apartment,
            "Intercom": intercom
        }, ensure_ascii=False)

    # Объединяем дополнительное описание в комментарий
    comment = order_description if order_description else "тестовый заказ на доставку"
    
    # Если заказ "pickup", ставим isPickup True, иначе False
    is_pickup = True if delivery_type == "pickup" else False

    # Преобразуем количество человек в число (по умолчанию 1)
    try:
        persons = int(num_persons)
    except ValueError:
        persons = 1

    order_payload = {
        "product": "delivery",  # Можно менять, если для самовывоза другой тип продукта
        "pointId": POINT_ID,
        "comment": comment,
        "customer": {
            "externalId": delivery_info.get("externalCustomerId") or None,
            "name": delivery_info.get("name", ""),
            "lastname": "",
            "patronymic": "",
            "email": "",
            "phone": delivery_info.get("phone", "")
        },
        "datetime": order_datetime,
        "nomenclatures": nomenclatures,
        "delivery": {
            "addressFull": address_full,
            "addressJSON": address_json,
            "paymentType": payment_type,  # "card" или "cash"
            "persons": persons,
            "isPickup": is_pickup
        }
    }

    # Отправляем JSON запроса в чат (как текст) для отладки
    request_json_text = json.dumps(order_payload, ensure_ascii=False, indent=2)
    await bot.send_message(
        chat_id=user_id,
        text=f"Отправляем JSON запроса к API СБИС:\n```json\n{request_json_text}\n```",
        parse_mode=ParseMode.MARKDOWN
    )
    logging.info("Отправлен JSON запроса к API СБИС пользователю")

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
                logging.info("Заказ успешно создан, получен ответ API")
            else:
                result_text = f"Ошибка создания заказа. Код: {response.status_code}\nОтвет API:\n```json\n{response.text}\n```"
                logging.error(f"Ошибка создания заказа, код {response.status_code}: {response.text}")
        except Exception as e:
            result_text = f"Ошибка при выполнении запроса: {e}"
            logging.error(f"Ошибка при выполнении запроса: {e}")

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
    logging.info(f"Заказ отменен пользователем {callback_query.from_user.id}")

@app.get("/menu")
async def get_menu():
    if not menu_data:
        logging.error("Меню не найдено")
        raise HTTPException(status_code=404, detail="Меню не найдено")
    logging.info("Меню запрошено через API")
    return menu_data

@app.get("/image/{filename}")
async def get_image(filename: str):
    file_path = f"images/{filename}"
    if os.path.exists(file_path):
        logging.info(f"Отправка файла: {filename}")
        return FileResponse(file_path)
    logging.error(f"Файл не найден: {filename}")
    raise HTTPException(status_code=404, detail="Файл не найден")

async def on_start():
    logging.info("Бот запущен!")
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
        logging.info("Выключение сервера...")
