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
from ofd_bridge import ofd_bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()
dp.include_router(main_router)

# HAR KUNI ERTALAB SOAT 9:00 DA VA HAR 30 DAQIQADA AVTOMATIK YANGILANISH REJASI
async def daily_channel_file_maintenance(bot: Bot):
    logger.info("⏰ Kunlik baza tekshiruvi: Kanaldan yangi Excel fayl qidirilmoqda...")
    try:
        updated = await ofd_bridge.sync_excel_from_channel()
        if updated:
            logger.info("✅ Yangi kunlik Excel baza avtomatik yangilandi!")
    except Exception as e:
        logger.error(f"Rejali baza yangilashda xatolik: {e}")

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi! Iltimos, .env faylni tekshiring.")
        return

    bot = Bot(token=BOT_TOKEN)

    # Scheduler rejalashtiruvchi
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    # Har kuni soat 9:00 da
    scheduler.add_job(
        daily_channel_file_maintenance,
        CronTrigger(hour=9, minute=0, timezone="Asia/Tashkent"),
        args=[bot]
    )
    # Ish vaqtida har 10 daqiqada yangi fayl chiqqanligini tekshirish
    scheduler.add_job(
        daily_channel_file_maintenance,
        CronTrigger(minute="*/10", timezone="Asia/Tashkent"),
        args=[bot]
    )
    scheduler.start()

    logger.info("Mars Smart POS boti modulli arxitektura bilan ishga tushirildi...")
    
    # Barcha ulangan modullarning on_startup metodlarini ishga tushirish
    from core.module_registry import module_registry
    await module_registry.startup_all(bot, dp)

    # Ishga tushganda fon rejimida Telethon tinglovchisini va tekshiruvini ishga tushirish
    telethon_task = asyncio.create_task(ofd_bridge.start_telethon_listener(bot))
    asyncio.create_task(daily_channel_file_maintenance(bot))

    try:
        await dp.start_polling(bot)
    finally:
        if "telethon_task" in locals() and not telethon_task.done():
            telethon_task.cancel()
        await ofd_bridge.close_telethon_client()
        await module_registry.shutdown_all(bot, dp)

if __name__ == "__main__":
    asyncio.run(main())


