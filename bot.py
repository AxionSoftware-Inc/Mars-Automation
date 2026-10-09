import os
import asyncio
import logging
from dotenv import load_dotenv

# Env o'zgaruvchilarini eng avval yuklash
load_dotenv()

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from handlers import main_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()
dp.include_router(main_router)

# HAR KUNI ERTALAB SOAT 9:00 DA AVTOMATIK YANGILANISH REJASI
async def daily_channel_file_maintenance(bot: Bot):
    logger.info("Har kungi soat 09:00 rejasi: yangi kunlik baza holati nazorat qilindi.")

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi! Iltimos, .env faylni tekshiring.")
        return

    bot = Bot(token=BOT_TOKEN)

    # Scheduler rejalashtiruvchi
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(
        daily_channel_file_maintenance,
        CronTrigger(hour=9, minute=0, timezone="Asia/Tashkent"),
        args=[bot]
    )
    scheduler.start()

    logger.info("Mars Smart POS boti modulli arxitektura bilan ishga tushirildi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
