import os
import re
import io
import logging
from datetime import datetime
from dotenv import load_dotenv

# Env o'zgaruvchilarini eng avval yuklash
load_dotenv()

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.enums import ChatType
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from excel_manager import excel_manager, DATA_DIR
from ai_helper import generate_ai_reply
from image_analyzer import analyze_pos_screen
from catalog_manager import catalog_manager
from user_memory import user_memory
from state_manager import get_last_file_message_id, set_last_file_message_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DESTINATION_CHANNEL_ID = -1003784534841  # marsfayllar
SOURCE_CHANNEL_ID = -1001641871516       # @POS_Terminal_UzSmart_Bank

# Kanaldagi video postlar xaritasi
POST_MAP = {
    "post_148": 148,  # Oylik to'lovni Click orqali to'lash videosi
    "post_145": 145,  # Yillik to'lov
    "post_140": 140,  # Narx o'zgartirish
    "post_141": 141,  # Sana va vaqtni to'g'irlash
    "post_125": 125,  # Dasturni yangilash
    "post_137": 137,  # Fiskal modul aktivlashtirish
    "post_134": 134,  # Fiskal modulni o'chirib qayta o'rnatish
    "post_138": 138,  # Ma'lumotlarni yuklash
    "post_136": 136,  # Analitika
}

dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

def format_debt_response(results: list) -> str:
    """Excel tekshiruvi natijasi: apparat soni va qarz summasi"""
    if not results:
        return (
            "❌ <b>Bazada ushbu raqam bo'yicha ma'lumot topilmadi.</b>\n\n"
            "Iltimos, INN (9 xonali) yoki JSHSHIR (14 xonali) raqamingiz to'g'ri kiritilganini tekshirib qayta yuboring.\n"
            "📸 <i>Agar apparatingiz xatolik berayotgan bo'lsa, ekranini rasmga olib yuborsangiz, nosozlik sababini aniqlab beramiz.</i>"
        )

    first = results[0]
    org_name = first.get("name", "-")
    inn = first.get("stir", "-")
    jshshir = first.get("jshshir", "-")
    tuman = first.get("tuman", "-")
    device_count = len(results)
    
    text = f"🏢 <b>Korxona:</b> {org_name}\n"
    if inn != "-":
        text += f"🆔 <b>СТИР (INN):</b> <code>{inn}</code>\n"
    if jshshir != "-":
        text += f"🆔 <b>ЖШSHIR:</b> <code>{jshshir}</code>\n"
    if tuman != "-":
        text += f"📍 <b>Hudud / Tuman:</b> {tuman}\n"
    
    text += f"📟 <b>Biriktirilgan apparatlar soni:</b> {device_count} ta\n"
    text += "────────────────────\n"

    total_debt = sum(item.get("debt", 0.0) for item in results)

    if total_debt > 0:
        text += f"🔴 <b>JAMI QARZDORLIK: {total_debt:,.0f} so'm</b>\n\n"
        text += "⚠️ <i>Apparat ishlamay qolganining sababi oylik abonent to'lovidagi qarzdorlik!</i>\n"
        text += "👇 <i>Quyida to'lov qilish bo'yicha video-qo'llanma yuborildi:</i>"
    elif total_debt < 0:
        text += f"🟢 <b>Oldindan ortiqcha to'lov mavjud: {abs(total_debt):,.0f} so'm</b>\n\n"
        text += "✅ <b>Abonent to'lovidan qarzdorlik yo'q.</b>\n\n"
        text += "📸 <i>Agar apparatingiz ishlamayotgan bo'lsa, iltimos, <b>apparat ekranidagi xatolikni rasmga olib yuboring</b>. Nosozlik sababini (soat, internet yoki xatolik kodi) darhol aniqlab beramiz.</i>"
    else:
        text += "✅ <b>Qarzdorlik mavjud emas (0 so'm).</b>\n\n"
        text += "ℹ️ <b>Abonent to'lovidan qarz yo'q.</b>\n\n"
        text += "📸 <i>Agar apparatingiz ishlamayotgan bo'lsa, iltimos, <b>apparat ekranidagi xatolikni rasmga olib yuboring</b>. Nosozlik sababini (soat, internet yoki xatolik kodi) darhol aniqlab beramiz.</i>"

    return text

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "Smart POS kassa apparatlari yordamchi botiga xush kelibsiz!\n\n"
        "🔹 <b>Qarzdorlikni tekshirish uchun:</b> INN (9 xonali) yoki JSHSHIR (14 xonali) raqamingizni yuboring.\n"
        "🔹 <b>To'lov qilish yoki apparat sozlamalari bo'yicha:</b> savolingizni yozsangiz tegishli video-qo'llanma yuboriladi.\n"
        "🔹 <b>Apparat xatolik berayotgan bo'lsa:</b> ekran rasmini yuborsangiz, nosozlik sababi aniqlanadi.",
        parse_mode="HTML"
    )

# 1. KANAL VA GURUHLARDAN YANGI EXCEL FAYLNI QABUL QILISH VA ESKISINI O'CHIRISH
@dp.channel_post(F.document)
@dp.message(F.document)
async def handle_document(message: types.Message, bot: Bot):
    doc = message.document
    if doc.file_name and (doc.file_name.endswith(".xlsx") or doc.file_name.endswith(".xls")):
        try:
            if message.chat.id == DESTINATION_CHANNEL_ID:
                last_msg_id = get_last_file_message_id()
                if last_msg_id and last_msg_id != message.message_id:
                    try:
                        await bot.delete_message(chat_id=DESTINATION_CHANNEL_ID, message_id=last_msg_id)
                        logger.info(f"Kanaldan avvalgi eski fayl posti o'chirildi (ID: {last_msg_id})")
                    except Exception as err:
                        logger.warning(f"Avvalgi fayl postini o'chirishda xatolik: {err}")
                set_last_file_message_id(message.message_id)

            os.makedirs(DATA_DIR, exist_ok=True)
            temp_file = os.path.join(DATA_DIR, f"temp_{doc.file_name}")
            await bot.download(doc, destination=temp_file)
            
            success = excel_manager.update_file(temp_file)
            if os.path.exists(temp_file):
                os.remove(temp_file)

            if success:
                logger.info(f"Yangi Excel bazasi yangilandi! Yozuvlar: {excel_manager.records_count}")
                if message.chat.type != ChatType.CHANNEL:
                    await message.reply(
                        f"✅ <b>Baza muvaffaqiyatli yangilandi!</b>\n"
                        f"📁 Fayl: <code>{doc.file_name}</code>\n"
                        f"📊 Jami yozuvlar: <b>{excel_manager.records_count} ta</b>",
                        parse_mode="HTML"
                    )
        except Exception as e:
            logger.error(f"Faylni yuklashda xatolik: {e}")

# HAR KUNI ERTALAB SOAT 9:00 DA AVTOMATIK YANGILANISH REJASI
async def daily_channel_file_maintenance(bot: Bot):
    logger.info("Har kungi soat 09:00 rejasi: yangi kunlik baza holati nazorat qilindi.")

# 2. @POS_Terminal_UzSmart_Bank KANALIDAN YANGI POSTLARNI BIZNING KANALGA AVTOMATIK UZATISH
@dp.channel_post()
async def handle_source_channel_post(message: types.Message, bot: Bot):
    if message.chat.id == SOURCE_CHANNEL_ID:
        try:
            logger.info(f"@POS_Terminal_UzSmart_Bank dan yangi post keldi (ID: {message.message_id}), uzatilmoqda...")
            await bot.forward_message(
                chat_id=DESTINATION_CHANNEL_ID,
                from_chat_id=SOURCE_CHANNEL_ID,
                message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"Postni kanalga uzatishda xatolik: {e}")

        # YANGI KANAL POSTINI AVTOMATIK INDEKSLASH
        try:
            post_text = message.text or message.caption or ""
            if post_text:
                catalog_manager.auto_index_new_post(post_id=message.message_id, post_text=post_text)
        except Exception as e:
            logger.error(f"Yangi postni avto-indekslashda xatolik: {e}")

# 3. RASM BILAN KELGAN XABARLAR (AGENT VIZUAL TAHLIL VA XATOLIK KODI BO'YICHA)
@dp.message(F.photo)
async def handle_photo(message: types.Message, bot: Bot):
    caption = message.caption or ""
    
    # Rasm tagida INN bormi?
    found_nums = re.findall(r"\b(\d{14}|\d{9})\b", caption)
    if found_nums:
        results = excel_manager.search(found_nums[0])
        resp = format_debt_response(results)
        await message.reply(resp, parse_mode="HTML")
        total_debt = sum(item.get("debt", 0.0) for item in results)
        if total_debt > 0:
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=148,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.error(f"Qo'llanma yuborishda xatolik: {e}")
        return

    # Kengaytirilgan Android POS ekran tahlili: Soat, internet, xatolik kodi
    try:
        user_id = message.from_user.id if message.from_user else 0
        chat_id = message.chat.id

        photo = message.photo[-1]
        file_io = io.BytesIO()
        await bot.download(photo, destination=file_io)
        image_bytes = file_io.getvalue()
        
        reply_text, video_id = analyze_pos_screen(image_bytes=image_bytes, user_caption=caption)
        
        try:
            await message.reply(reply_text, parse_mode="HTML")
        except Exception:
            await message.reply(reply_text)

        # Xotiraga saqlash
        user_memory.add_user_message(chat_id, user_id, f"[Ekran rasmi] {caption}".strip())
        user_memory.add_assistant_message(chat_id, user_id, reply_text)

        # Agar xatolik bo'yicha yechim videosi aniqlansa (masalan soat/vaqt uchun 141)
        if video_id:
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=video_id,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.error(f"Tashxis videosini yuborishda xatolik: {e}")
    except Exception as e:
        logger.error(f"Rasmni tahlil qilishda xatolik: {e}")
        await message.reply("Apparat ekranidagi xatolikni aniqroq rasmga olib yuborsangiz, yordam beramiz.")

# 4. BUYRUQ ORQALI TEKSHIRISH (/tekshir 123456789)
@dp.message(Command("tekshir"))
async def cmd_tekshir(message: types.Message, bot: Bot):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("⚠️ Iltimos, INN yoki JSHSHIR raqamini ham yozing.\nMasalan: <code>/tekshir 123456789</code>", parse_mode="HTML")
        return
    query = args[1].strip()
    results = excel_manager.search(query)
    resp = format_debt_response(results)
    await message.reply(resp, parse_mode="HTML")
    
    total_debt = sum(item.get("debt", 0.0) for item in results)
    if total_debt > 0:
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=SOURCE_CHANNEL_ID,
                message_id=148,
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"Qo'llanma postini jo'natishda xatolik: {e}")

# 5. MATNLI XABARLARNI PURE AI SEMANTIC ROUTER ASOSIDA BOSHQARISH
@dp.message(F.text)
async def handle_text(message: types.Message, bot: Bot):
    text = message.text.strip()
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    
    # 1-QADAM: Agar matnda 9 xonali INN yoki 14 xonali JSHSHIR bo'lsa -> Excel bazadan tekshirish
    found_nums = re.findall(r"\b(\d{14}|\d{9})\b", text)
    if found_nums:
        query_num = found_nums[0]
        results = excel_manager.search(query_num)
        
        is_group = message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
        # Guruhda son yozilsa yoki so'rov bo'lsa javob berish
        if not is_group or results or (text == query_num) or len(text) <= 25:
            resp = format_debt_response(results)
            await message.reply(resp, parse_mode="HTML")
            
            # Xotiraga saqlash
            user_memory.add_user_message(chat_id, user_id, f"Mening INN/JSHSHIR raqamim: {query_num}")
            user_memory.add_assistant_message(chat_id, user_id, resp)
            
            total_debt = sum(item.get("debt", 0.0) for item in results)
            if total_debt > 0:
                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=148,
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    logger.error(f"To'lov videosini yuborishda xatolik: {e}")
            return

    # 2-QADAM: AGAR TO'LIQ KATALOGDAGI 50+ TA POSTDAN MOSI BO'LSA — FAQAT SHU POSTNI UZATISH
    video_id = catalog_manager.find_matching_post(text)

    # Mos video post topilsa -> FAQAT kanal postini uzatamiz va to'xtatamiz (matn yozilmaydi!)
    if video_id:
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=SOURCE_CHANNEL_ID,
                message_id=video_id,
                reply_to_message_id=message.message_id
            )
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, f"[Video qo'llanma yuborildi: ID {video_id}]")
            return
        except Exception as e:
            logger.error(f"Video post jo'natishda xatolik (ID: {video_id}): {e}")

    # 3-QADAM: AGAR VIDEO BO'LMASA — HAR BIR FOYDALANUVCHINING 12 SOATLIK SUHBAT XOTIRASI BILAN AI JAVOBI
    context_summary = user_memory.get_context_summary(chat_id, user_id)
    reply_text, _ = generate_ai_reply(text, context_history=context_summary)

    try:
        await message.reply(reply_text, parse_mode="HTML")
    except Exception:
        await message.reply(reply_text)

    # Foydalanuvchi va AI suhbatini xotiraga yozish
    user_memory.add_user_message(chat_id, user_id, text)
    user_memory.add_assistant_message(chat_id, user_id, reply_text)

async def main():
    bot = Bot(token=BOT_TOKEN)
    scheduler.add_job(
        daily_channel_file_maintenance,
        CronTrigger(hour=9, minute=0, timezone="Asia/Tashkent"),
        args=[bot]
    )
    scheduler.start()
    logger.info("Bot sof AI semantik kontekst tizimi bilan ishga tushirildi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
