import os
import re
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.enums import ChatType
from dotenv import load_dotenv

from excel_manager import excel_manager, DATA_DIR
from ai_helper import generate_ai_reply

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
dp = Dispatcher()

def format_debt_response(results: list) -> str:
    """Tekshirish natijasini chiroyli va tushunarli qilib formatlash"""
    if not results:
        return (
            "❌ <b>Bazada ushbu raqam bo'yicha ma'lumot topilmadi.</b>\n\n"
            "Iltimos, INN (9 xonali) yoki JSHSHIR (14 xonali) raqamingiz to'g'ri kiritilganini tekshirib qayta yuboring."
        )

    first = results[0]
    org_name = first.get("name", "-")
    inn = first.get("stir", "-")
    jshshir = first.get("jshshir", "-")
    tuman = first.get("tuman", "-")
    
    text = f"🏢 <b>Korxona:</b> {org_name}\n"
    if inn != "-":
        text += f"🆔 <b>СТИР (INN):</b> <code>{inn}</code>\n"
    if jshshir != "-":
        text += f"🆔 <b>ЖШШИР:</b> <code>{jshshir}</code>\n"
    if tuman != "-":
        text += f"📍 <b>Hudud / Tuman:</b> {tuman}\n"
    text += "────────────────────\n"

    total_debt = 0.0

    for idx, item in enumerate(results, start=1):
        device = item.get("terminal", "-")
        debt = item.get("debt", 0.0)
        total_debt += debt

        if len(results) > 1:
            text += f"📟 <b>#{idx} Apparat (Онлайн-НКМ):</b> <code>{device}</code>\n"
            if debt > 0:
                text += f"💰 <b>Qarzdorlik:</b> ❗️ <b>{debt:,.0f} so'm</b>\n\n"
            elif debt < 0:
                text += f"💰 <b>Haqdorlik (Ortiqcha to'lov):</b> <b>{abs(debt):,.0f} so'm</b>\n\n"
            else:
                text += f"💰 <b>Qarz:</b> 0 so'm (To'langan)\n\n"
        else:
            if device and device != "-":
                text += f"📟 <b>Apparat (Онлайн-НКМ):</b> <code>{device}</code>\n"

    text += "────────────────────\n"
    if total_debt > 0:
        text += f"🔴 <b>JAMI QARZDORLIK: {total_debt:,.0f} so'm</b>\n\n"
        text += "⚠️ <i>Eslatma: Apparat ishlamay qolganining sababi abonent to'lovidagi qarzdorlik bo'lishi mumkin. Iltimos, hisobingizni to'ldiring!</i>"
    elif total_debt < 0:
        text += f"🟢 <b>Oldindan to'lov mavjud: {abs(total_debt):,.0f} so'm</b>\n\n"
        text += "✅ <i>Abonent to'lovidan qarzdorlik yo'q. Agar apparat baribir ishlamayotgan bo'lsa, internet aloqasi yoki apparat sozlamalarini tekshiring.</i>"
    else:
        text += "✅ <b>Qarzdorlik mavjud emas (0 so'm).</b>\n\n"
        text += "ℹ️ <i>Abonent to'lovidan qarz yo'q. Agar apparat ishlamayotgan bo'lsa, texnik nosozlik yoki internet aloqasini tekshiring.</i>"

    return text

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "Smart POS kassa apparatlari bo'yicha abonent qarzdorligini tekshirish uchun:\n\n"
        "👉 <b>INN</b> (9 xonali) yoki <b>JSHSHIR</b> (14 xonali) raqamingizni yuboring.\n"
        "Masalan: <code>123456789</code>",
        parse_mode="HTML"
    )

# 1. KANAL VA GURUHLARDAN YANGI EXCEL FAYLNI QABUL QILIB BAZANI YANGILASH
@dp.channel_post(F.document)
@dp.message(F.document)
async def handle_document(message: types.Message, bot: Bot):
    doc = message.document
    if doc.file_name and (doc.file_name.endswith(".xlsx") or doc.file_name.endswith(".xls")):
        try:
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

# 2. BUYRUQ ORQALI TEKSHIRISH (/tekshir 123456789)
@dp.message(Command("tekshir"))
async def cmd_tekshir(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("⚠️ Iltimos, INN yoki JSHSHIR raqamini ham yozing.\nMasalan: <code>/tekshir 123456789</code>", parse_mode="HTML")
        return
    query = args[1].strip()
    results = excel_manager.search(query)
    await message.reply(format_debt_response(results), parse_mode="HTML")

# 3. GURUH VA SHAXSIY CHATDAGI GAPLAR VA RAQAMLAR
@dp.message(F.text)
async def handle_text(message: types.Message):
    text = message.text.strip()
    
    # Matn ichidan 14 xonali (JSHSHIR) yoki 9 xonali (INN) raqam qidirish
    found_nums = re.findall(r"\b(\d{14}|\d{9})\b", text)
    
    if found_nums:
        query_num = found_nums[0]
        results = excel_manager.search(query_num)
        
        is_group = message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
        if is_group:
            keywords = ["inn", "stir", "инн", "стир", "qarz", "tekshir", "ishlamay", "ishlamayapti", "apparat", "terminal"]
            has_kw = any(k in text.lower() for k in keywords)
            is_pure_num = (text == query_num)
            
            if results or is_pure_num or has_kw:
                resp = format_debt_response(results)
                await message.reply(resp, parse_mode="HTML")
        else:
            resp = format_debt_response(results)
            await message.reply(resp, parse_mode="HTML")
        return

    # AGAR RAQAM BO'LMASA: Oddiy gaplar (masalan: "apparatim ishlamayapti", "qarzim bormi", "chek chiqmayapti")
    trigger_words = [
        "ishlamay", "ishlamadi", "ishlamayapti", "ochilmay", "ochilmayapti",
        "qarz", "qarzim", "balans", "qarzdorlik", "pulim", "to'lov", "tulov",
        "blok", "bloklandi", "chek", "nkm", "terminal", "apparat", "pos"
    ]
    
    text_lower = text.lower()
    has_trigger = any(tw in text_lower for tw in trigger_words)
    is_private = (message.chat.type == ChatType.PRIVATE)
    
    # Shaxsiy chatda har doim, guruhda esa tegishli mavzu bo'lganda javob beradi
    if has_trigger or is_private:
        ai_reply = generate_ai_reply(text)
        await message.reply(ai_reply, parse_mode="HTML")

async def main():
    bot = Bot(token=BOT_TOKEN)
    logger.info("Bot qayta ishga tushirildi va xabarlarni kutmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
