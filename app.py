import os
import asyncio

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




async def  main():
 await bot.delete_webhook(drop_pending_updates=True)
 await dp.start_polling(bot)

    
   



asyncio.run(main())