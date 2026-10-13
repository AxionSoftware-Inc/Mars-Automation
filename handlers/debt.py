import re
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Router, types, Bot, F
from aiogram.enums import ChatType
from excel_manager import excel_manager
from user_memory import user_memory
from translit_manager import adapt_to_user_script, detect_script

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

    user_script = user_memory.get_preferred_script(chat_id, user_id)
    if message.text:
        sc = detect_script(message.text)
        if sc in ("cyrillic", "latin"):
            user_script = sc
            user_memory.detect_and_update_script(chat_id, user_id, message.text)

    # 0. Agar foydalanuvchi avval kvitansiya yuklagan bo'lsa, uni avtomatik bog'lash
    from core import core_engine
    from admin_manager import admin_manager
    receipt_decision = core_engine.resolve_pending_receipt_if_any(query_num, chat_id, user_id)
    if receipt_decision:
        reply_m = adapt_to_user_script(receipt_decision.reply_text, user_script)
        try:
            await message.reply(reply_m, parse_mode="HTML")
        except Exception:
            await message.reply(reply_m)

        user_memory.add_user_message(chat_id, user_id, f"Mening INN raqamim: {query_num}")
        user_memory.add_assistant_message(chat_id, user_id, reply_m)

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

    # Xotiraga korxona va qarz ma'lumotlarini eslab qolish:
    # Agar telefon orqali qidirilgan bo'lsa, asosiy INN/STIR ni ham bog'lash, aks holda kiritilgan raqamni saqlash
    clean_p = extract_clean_phone(query_num)
    if clean_p and query_num not in excel_manager.stir_index and query_num not in excel_manager.jshshir_index:
        primary_id = (results[0].get("stir") if results else "") or query_num
    else:
        primary_id = query_num

    user_memory.set_last_id(chat_id, user_id, primary_id, org_name=org_name, debt=total_debt)
    user_memory.set_last_topic(chat_id, user_id, "debt_checked")

    resp = format_debt_response(results)
    pending_screen = user_memory.get_pending_device_screen(chat_id, user_id)
    if pending_screen:
        user_memory.clear_pending_device_screen(chat_id, user_id)
        is_p3 = any(bool(item.get("is_p3", False)) for item in results) if results else False
        saved_summary = (pending_screen.get("screen_text_summary") or "").strip()
        if is_p3 and saved_summary:
            resp = f"🖥 <b>P3 apparat ekranidagi xabar:</b> {saved_summary}\n\n──────────────\n{resp}"

    resp = adapt_to_user_script(resp, user_script)
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
    user_memory.add_user_message(chat_id, user_id, f"Mening qidiruv raqamim (INN/Tel): {query_num}")
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

    # Maxfiy guruh orqali @ofd943 dan yillik to'lov / OFD ma'lumotini olib berish (agar maxfiy guruh ulangan bo'lsa)
    from ofd_bridge import ofd_bridge
    if ofd_bridge.is_configured():
        ofd_inn = None
        if results:
            r_stir = results[0].get("stir", "-")
            r_jsh = results[0].get("jshshir", "-")
            if r_stir and r_stir != "-":
                ofd_inn = r_stir
            elif r_jsh and r_jsh != "-":
                ofd_inn = r_jsh
        if not ofd_inn:
            ofd_inn = extract_clean_inn(query_num)

        if ofd_inn:
            ofd_reply = await ofd_bridge.query_inn(bot, ofd_inn)
            if ofd_reply:
                header = adapt_to_user_script(
                    "🏛 <b>OFD / Soliq tizimi (Yillik fiskal modul) ma'lumoti:</b>",
                    user_script
                )
                full_ofd_text = f"{header}\n\n{ofd_reply}"
                try:
                    await message.reply(full_ofd_text, parse_mode="HTML")
                except Exception:
                    try:
                        await message.reply(full_ofd_text)
                    except Exception as e_ofd:
                        logger.error(f"OFD javobini yuborishda xatolik: {e_ofd}")
                user_memory.add_assistant_message(chat_id, user_id, full_ofd_text)

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

from core.models import extract_clean_inn, extract_clean_phone

def is_inn_or_phone_query_message(message: types.Message) -> bool:
    """Matnda INN/JSHSHIR yoki telefon raqami aniqlanganda xabarni tekshirish va guruhlarda to'g'ri filtr qilish"""
    if not message.text:
        return False
    query_num = extract_clean_inn(message.text) or extract_clean_phone(message.text)
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
        "ishlamayapti", "blok", "ochib qoldi", "o'chib qoldi", "telefon", "tel", "nomer"
    ]
    return any(kw in lower for kw in inn_keywords)

# Backward-compatibility alias
is_inn_query_message = is_inn_or_phone_query_message

@router.message(is_debt_inquiry)
async def handle_debt_inquiry(message: types.Message):
    """Foydalanuvchi qarzdan e'tiroz bildirsa yoki to'lov tarixini so'rasa"""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    user_script = user_memory.detect_and_update_script(chat_id, user_id, message.text or "")

    last_id = user_memory.get_last_id(chat_id, user_id)
    if not last_id:
        found_num = extract_clean_inn(message.text) or extract_clean_phone(message.text)
        if found_num:
            last_id = found_num
        else:
            w_msg = adapt_to_user_script(
                "⚠️ <b>To'lov tarixini tekshirish uchun korxona INN (STIR) yoki ro'yxatdan o'tgan telefon raqamingizni yuboring.</b>\n"
                "Masalan: <code>302568138</code> yoki <code>901234567</code>",
                user_script
            )
            await message.reply(w_msg, parse_mode="HTML")
            return

    results = excel_manager.search(last_id)
    if not results:
        nf_msg = adapt_to_user_script(
            f"❌ <code>{last_id}</code> bo'yicha ma'lumot topilmadi. INN yoki telefon raqami to'g'ri kiritilganini tekshiring.",
            user_script
        )
        await message.reply(nf_msg, parse_mode="HTML")
        return

    clean_p = extract_clean_phone(last_id)
    if clean_p and last_id not in excel_manager.stir_index and last_id not in excel_manager.jshshir_index:
        primary_id = (results[0].get("stir") if results else "") or last_id
    else:
        primary_id = last_id

    org_name = results[0].get("name", "") if results else ""
    total_debt = sum(item.get("debt", 0.0) for item in results) if results else 0.0
    user_memory.set_last_id(chat_id, user_id, primary_id, org_name=org_name, debt=total_debt)

    history_resp = excel_manager.format_payment_history(results)
    history_resp = adapt_to_user_script(history_resp, user_script)
    await message.reply(history_resp, parse_mode="HTML")

    user_memory.add_user_message(chat_id, user_id, message.text)
    user_memory.add_assistant_message(chat_id, user_id, history_resp)
    user_memory.set_last_topic(chat_id, user_id, "payment_history")


# 2. TO'G'RIDAN-TO'G'RI INN / JSHSHIR / TELEFON YUBORILGANDA
@router.message(is_inn_or_phone_query_message)
async def handle_inn_query(message: types.Message, bot: Bot):
    """Matnda 9 xonali INN, 14 xonali JSHSHIR yoki telefon raqami aniqlanganda qarz tekshirish"""
    text = (message.text or "").strip()
    query_num = extract_clean_inn(text) or extract_clean_phone(text)
    if not query_num:
        return

    await process_and_send_debt_result(message, bot, query_num)

