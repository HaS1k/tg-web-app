import os
import asyncio
import requests


from aiogram import Bot, Dispatcher,  types
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart,Command, or_f
from aiogram.types.web_app_info import WebAppInfo
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.types import  KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder





from dotenv import find_dotenv,load_dotenv
load_dotenv(find_dotenv())

bot = Bot(token=os.getenv('TOKEN'))
dp =Dispatcher()

# Конфигурация бота и API

API_URL = "https://api.sbis.ru/retail/nomenclature/list?"
SBIS_TOKEN = os.getenv('SBIS_TOKEN')
API_HEADERS = {"X-SBISAccessToken": os.getenv("SBIS_TOKEN")}
API_PARAMS = {
    "pointId": 7245,
    "priceListId": 37,
    "withBalance": True,
    "withBarcode": True,
    "onlyPublished": False,
    "page": 0,
    "pageSize": 50
}

# Переменная для хранения данных
menu_data = {}

# Функция запроса данных из СБИС
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
            image_url = f"https://api.sbis.ru/retail{image_list[0]}" if image_list and isinstance(image_list, list) and len(image_list) > 0 else "https://via.placeholder.com/100"

            items[hierarchical_id] = {
                "name": item.get("name"),
                "price": item.get("cost"),
                "description": item.get("description"),
                "image": image_url,
                "parent": parent_id
            }

        
        # Связываем товары и категории
        for item_id, item in items.items():
            if item["parent"] in categories:
                categories[item["parent"]]["items"].append(item)
        
        menu_data = categories
        print("Данные обновлены")
    else:
        print("Ошибка при запросе к API СБИС")





@dp.message(CommandStart())
async def start_cmd(message: types.Message):
 markap= ReplyKeyboardMarkup(
 keyboard=[
  [
   KeyboardButton(
    text='open',web_app=WebAppInfo(url='https://storied-souffle-8bb402.netlify.app/')
   )
  ]
 ]
 )
 await message.answer(text="start",reply_markup=markap)
 await message.answer("Загрузка меню...")
 await fetch_menu()
 await message.answer("Меню обновлено! Перейдите в веб-приложение для просмотра.")

async def get_menu():
    return menu_data


async def  main():
 await bot.delete_webhook(drop_pending_updates=True)
 await dp.start_polling(bot)

    
   



asyncio.run(main())