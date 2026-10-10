import re
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Router, types, Bot, F
from aiogram.enums import ChatType
from excel_manager import excel_manager
from user_memory import user_memory

logger = logging.getLogger(__name__)

router = Router(name="debt_router")

SOURCE_CHANNEL_ID = -1001641871516  # @POS_Terminal_UzSmart_Bank

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
        now_uzb = datetime.now(ZoneInfo("Asia/Tashkent"))
        MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"]
        current_month_idx = now_uzb.month
        current_month_name = MONTHS[current_month_idx - 1]
        remaining_months = max(0, 12 - current_month_idx)
        monthly_rate = 100000.0 * device_count
        pay_year_end = total_debt + (remaining_months * monthly_rate)

        text += f"🔴 <b>JAMI QARZDORLIK: {total_debt:,.0f} so'm</b>\n\n"
        text += "⚠️ <i>Apparat ishlamay qolganining sababi oylik abonent to'lovidagi qarzdorlik!</i>\n\n"
        text += "💡 <b>Apparat uzluksiz ishlashi uchun to'lov miqdori:</b>\n"
        text += f"🔹 <b>Shu oy ({current_month_name}) ishlashi uchun:</b> <code>{total_debt:,.0f}</code> so'm\n"
        if remaining_months > 0:
            text += f"🔹 <b>Yil oxirigacha (Dekabrgacha) ishlashi uchun:</b> <code>{pay_year_end:,.0f}</code> so'm\n"
        text += "\n"
        text += (
            "💳 <b>To'lov uchun bank rekvizitlari:</b>\n"
            "🏢 <b>Kompaniya:</b> «MARS ELEKTRON TEXNIKA» MCHJ\n"
            "🏦 <b>Hisob raqam (X/R):</b> <code>20208000800208044003</code>\n"
            "🏛 <b>Bank:</b> «Ipak Yo'li» AITB Shahrisabz filiali\n"
            "🔢 <b>MFO:</b> <code>01048</code> | <b>INN:</b> <code>302568138</code>\n"
            "📝 <b>To'lov maqsadi:</b> Abonent to'lov (korxona nomingiz yoki INN ko'rsatilsin)\n\n"
            "👇 <i>Quyida Click orqali to'lash bo'yicha video-qo'llanma yuborildi:</i>"
        )
    elif total_debt < 0:
        text += f"🟢 <b>Oldindan ortiqcha to'lov mavjud: {abs(total_debt):,.0f} so'm</b>\n\n"
        text += "✅ <b>Abonent to'lovidan qarzdorlik yo'q.</b>\n\n"
        text += "📸 <i>Agar apparatingiz ishlamayotgan bo'lsa, iltimos, <b>apparat ekranidagi xatolikni rasmga olib yuboring</b>. Nosozlik sababini (soat, internet yoki xatolik kodi) darhol aniqlab beramiz.</i>"
    else:
        text += "✅ <b>Qarzdorlik mavjud emas (0 so'm).</b>\n\n"
        text += "ℹ️ <b>Abonent to'lovidan qarz yo'q.</b>\n\n"
        text += "📸 <i>Agar apparatingiz ishlamayotgan bo'lsa, iltimos, <b>apparat ekranidagi xatolikni rasmga olib yuboring</b>. Nosozlik sababini (soat, internet yoki xatolik kodi) darhol aniqlab beramiz.</i>"

    return text

async def process_and_send_debt_result(message: types.Message, bot: Bot, query_num: str):
    """INN/JSHSHIR bo'yicha qidirib, javob berish va xotiraga saqlash"""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    # 0. Agar foydalanuvchi avval kvitansiya yuklagan bo'lsa, uni avtomatik bog'lash
    from core import core_engine
    from admin_manager import admin_manager
    receipt_decision = core_engine.resolve_pending_receipt_if_any(query_num, chat_id, user_id)
    if receipt_decision:
        try:
            await message.reply(receipt_decision.reply_text, parse_mode="HTML")
        except Exception:
            await message.reply(receipt_decision.reply_text)

        user_memory.add_user_message(chat_id, user_id, f"Mening INN raqamim: {query_num}")
        user_memory.add_assistant_message(chat_id, user_id, receipt_decision.reply_text)

        if receipt_decision.should_notify_admin and receipt_decision.receipt_facts:
            await admin_manager.notify_receipt_escalation(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                receipt_facts=receipt_decision.receipt_facts,
                debt_status_info=receipt_decision.debt_status_info,
                file_id=receipt_decision.file_id,
                is_photo=receipt_decision.is_photo
            )
        return

    results = excel_manager.search(query_num)
    org_name = results[0].get("name", "") if results else ""
    total_debt = sum(item.get("debt", 0.0) for item in results) if results else 0.0

    # Xotiraga korxona va qarz ma'lumotlarini eslab qolish
    user_memory.set_last_id(chat_id, user_id, query_num, org_name=org_name, debt=total_debt)
    user_memory.set_last_topic(chat_id, user_id, "debt_checked")

    resp = format_debt_response(results)
    logger.info(f"📤 QARZ JAVOBI [chat_id={chat_id}, query={query_num}]: {org_name} (qarz: {total_debt})")
    try:
        await message.reply(resp, parse_mode="HTML")
    except Exception as e1:
        logger.warning(f"HTML formatlash xatosi: {e1}, oddiy matnda yuborilmoqda...")
        try:
            await message.reply(resp)
        except Exception as e2:
            logger.error(f"Qarz xabarini yuborishda xatolik: {e2}")

    # Suhbat tarixiga yozish
    user_memory.add_user_message(chat_id, user_id, f"Mening INN/JSHSHIR raqamim: {query_num}")
    user_memory.add_assistant_message(chat_id, user_id, resp)

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

# 1. TO'LOV TARIXI VA QARZ E'TIROZLARI SO'ROVLARI
DEBT_INQUIRY_KEYWORDS = [
    "nimaga qarz", "nega qarz", "qayerdan qarz", "qanaqa qarz", "qanaqasiga qarz",
    "to'laganman", "tolaganman", "to'lagandim", "tolagandim", "to'laganmanku", "tolaganmanku",
    "pul to'laganman", "oylik to'laganman", "to'lov qilganman", "tolov qilganman",
    "to'lov tarixi", "tolov tarixi", "qachon to'laganman", "qaysi oy", "qaysi oylar",
    "qayerdan kelib chiqdi", "summa noto'g'ri", "notogri qarz", "qarzim yo'q"
]

def is_debt_inquiry(message: types.Message) -> bool:
    if not message.text:
        return False
    t = message.text.lower()
    return any(kw in t for kw in DEBT_INQUIRY_KEYWORDS)

from core.models import extract_clean_inn

def is_inn_query_message(message: types.Message) -> bool:
    """Matnda INN/JSHSHIR aniqlanganda xabarni tekshirish va guruhlarda to'g'ri filtr qilish"""
    if not message.text:
        return False
    query_num = extract_clean_inn(message.text)
    if not query_num:
        return False

    # Shaxsiy chatda har doim qabul qilinadi
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return True

    # Guruhlarda spamdan saqlanish filtri
    text = message.text.strip()
    if len(text) <= 30:
        return True

    lower = text.lower()
    inn_keywords = [
        "inn", "stir", "стир", "инн", "jshshir", "жшшир", "qarz", "mars",
        "apparat", "kassa", "to'lov", "tolov", "chek", "tekshir",
        "ishlamayapti", "blok", "ochib qoldi", "o'chib qoldi"
    ]
    return any(kw in lower for kw in inn_keywords)

@router.message(is_debt_inquiry)
async def handle_debt_inquiry(message: types.Message):
    """Foydalanuvchi qarzdan e'tiroz bildirsa yoki to'lov tarixini so'rasa"""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    last_id = user_memory.get_last_id(chat_id, user_id)
    if not last_id:
        found_num = extract_clean_inn(message.text)
        if found_num:
            last_id = found_num
        else:
            await message.reply(
                "⚠️ <b>To'lov tarixini tekshirish uchun korxona INN yoki JSHSHIR raqamini yuboring.</b>\n"
                "Masalan: <code>302568138</code>",
                parse_mode="HTML"
            )
            return

    results = excel_manager.search(last_id)
    if not results:
        await message.reply(
            f"❌ <code>{last_id}</code> bo'yicha ma'lumot topilmadi. INN to'g'ri kiritilganini tekshiring.",
            parse_mode="HTML"
        )
        return

    org_name = results[0].get("name", "") if results else ""
    total_debt = sum(item.get("debt", 0.0) for item in results) if results else 0.0
    user_memory.set_last_id(chat_id, user_id, last_id, org_name=org_name, debt=total_debt)

    history_resp = excel_manager.format_payment_history(results)
    await message.reply(history_resp, parse_mode="HTML")

    user_memory.add_user_message(chat_id, user_id, message.text)
    user_memory.add_assistant_message(chat_id, user_id, history_resp)
    user_memory.set_last_topic(chat_id, user_id, "payment_history")


# 2. TO'G'RIDAN-TO'G'RI INN / JSHSHIR YUBORILGANDA
@router.message(is_inn_query_message)
async def handle_inn_query(message: types.Message, bot: Bot):
    """Matnda 9 xonali INN yoki 14 xonali JSHSHIR aniqlanganda qarz tekshirish"""
    text = (message.text or "").strip()
    query_num = extract_clean_inn(text)
    if not query_num:
        return

    await process_and_send_debt_result(message, bot, query_num)

