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

def format_debt_response(results: list, checked_fm: str = None, annual_status: dict = None, chat_id: int = 0, user_id: int = 0) -> str:
    """Excel tekshiruvi natijasi: apparat soni va qarz summasi (markaziy shablondan)"""
    from templates import format_debt_response_template
    return format_debt_response_template(
        results=results,
        checked_fm=checked_fm,
        annual_status=annual_status,
        chat_id=chat_id,
        user_id=user_id
    )

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

    # 0.05 Agar mijoz «Yangi Texnologiyalar» DUK STIR raqamini (201589463) yuborgan bo'lsa
    from payment_accounts import YANGI_TEXNOLOGIYALAR_INN
    if query_num == YANGI_TEXNOLOGIYALAR_INN:
        from templates import get_yt_inn_warning
        yt_inn_msg = get_yt_inn_warning(YANGI_TEXNOLOGIYALAR_INN, user_script)
        try:
            await message.reply(yt_inn_msg, parse_mode="HTML")
        except Exception:
            await message.reply(yt_inn_msg)
        user_memory.add_user_message(chat_id, user_id, f"Mening qidiruv raqamim (INN/Tel): {query_num}")
        user_memory.add_assistant_message(chat_id, user_id, yt_inn_msg)
        return

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
    if not results and excel_manager.is_decommissioned(query_num):
        decom_list = excel_manager.get_decommissioned(query_num)
        org_name = decom_list[0].get("name", "-") if decom_list else "-"
        tuman = decom_list[0].get("tuman", "-") if decom_list else "-"
        from templates import get_decommissioned_template
        decom_text = get_decommissioned_template(org_name, query_num, tuman, user_script)
        logger.info(f"📤 HISOBDAN CHIQARILGAN [chat_id={chat_id}, query={query_num}]: {org_name}")
        try:
            await message.reply(decom_text, parse_mode="HTML")
        except Exception:
            try:
                await message.reply(decom_text)
            except Exception as e_dec:
                logger.error(f"Hisobdan chiqarilgan xabarni yuborishda xatolik: {e_dec}")
        user_memory.set_last_id(chat_id, user_id, query_num, org_name=org_name, debt=0.0)
        user_memory.set_last_topic(chat_id, user_id, "debt_checked")
        user_memory.add_user_message(chat_id, user_id, f"Mening qidiruv raqamim (INN/Tel): {query_num}")
        user_memory.add_assistant_message(chat_id, user_id, decom_text)
        return

    org_name = results[0].get("name", "") if results else ""
    total_debt = sum(item.get("debt", 0.0) for item in results) if results else 0.0

    # Xotiraga korxona va qarz ma'lumotlarini eslab qolish (FAQAT bazada topilgan korxonalar uchun!):
    # Agar bazada topilmagan bo'lsa, xotiradagi eski to'g'ri INN ni buzib yubormaslik uchun saqlamaymiz.
    if results:
        clean_p = extract_clean_phone(query_num)
        if clean_p and query_num not in excel_manager.stir_index and query_num not in excel_manager.jshshir_index:
            primary_id = (results[0].get("stir") if results else "") or query_num
        else:
            primary_id = query_num

        model_summary = excel_manager.get_device_model_summary(results)
        user_memory.set_last_id(chat_id, user_id, primary_id, org_name=org_name, debt=total_debt, device_models=model_summary)
        if total_debt > 0:
            user_memory.set_last_topic(chat_id, user_id, "monthly_debt_exists")
        else:
            user_memory.set_last_topic(chat_id, user_id, "monthly_debt_clear")

    checked_fm = user_memory.get_last_fm(chat_id, user_id)
    annual_status = user_memory.get_annual_status(chat_id, user_id)
    resp = format_debt_response(results, checked_fm=checked_fm, annual_status=annual_status, chat_id=chat_id, user_id=user_id)
    pending_screen = user_memory.get_pending_device_screen(chat_id, user_id)
    if pending_screen:
        user_memory.clear_pending_device_screen(chat_id, user_id)
        is_p3 = any(bool(item.get("is_p3", False)) for item in results) if results else False
        saved_summary = (pending_screen.get("screen_text_summary") or "").strip()
        if is_p3 and saved_summary:
            resp = f"🖥 <b>P3 Humo apparat ekranidagi xabar:</b> {saved_summary}\n\n──────────────\n{resp}"

    raw_msg_text = (message.text or "")
    from handlers.intents.hardware import is_device_issue
    if is_device_issue(raw_msg_text):
        user_memory.set_issue_mode(chat_id, user_id, True, initial_query=raw_msg_text)

    is_in_issue = user_memory.is_issue_mode(chat_id, user_id)
    if is_in_issue:
        if total_debt > 0:
            resp += (
                "\n\n⚠️ <i>Apparat to'xtab qolishining sababi: «Mars» oylik abonent to'lovidan qarzdorlik. "
                "Quyidagi hisob raqamga to'lov qilingandan so'ng apparat avtomatik faollashadi.</i>"
            )
        elif not checked_fm:
            user_memory.set_last_topic(chat_id, user_id, "awaiting_fiscal_module")
            resp = resp.replace(
                "Yillik Soliq (OFD) litsenziyasini tekshirish uchun:",
                "2-bosqich: Davlat Soliq (OFD) yillik litsenziyasini tekshirish:"
            )

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
        from payment_accounts import send_monthly_account_post
        await send_monthly_account_post(bot, message.chat.id, reply_to_message_id=message.message_id)
    elif is_in_issue:
        from payment_accounts import send_fiscal_sample_post
        await send_fiscal_sample_post(bot, message.chat.id)


# 1. TO'LOV TARIXI VA QARZ E'TIROZLARI SO'ROVLARI
def is_debt_inquiry(message: types.Message) -> bool:
    """Foydalanuvchi qarzdan norozilik bildirayotganini yoki to'lov tarixini so'rayotganini aniqlash"""
    if not message.text:
        return False
    from payment_accounts import is_debt_inquiry_or_objection
    return is_debt_inquiry_or_objection(message.text)

from core.models import extract_clean_inn, extract_clean_phone, is_incomplete_inn_text

def is_inn_or_phone_query_message(message: types.Message) -> bool:
    """Matnda INN/JSHSHIR yoki telefon raqami aniqlanganda xabarni tekshirish va guruhlarda to'g'ri filtr qilish"""
    if not message.text:
        return False

    # 1. Agar matnda Fiskal modul (LG..., YG... va h.k.) aniqlansa -> bu qarz emas, fiskal modul tekshiruvi!
    from core.models import extract_fiscal_module
    if extract_fiscal_module(message.text):
        return False

    query_num = extract_clean_inn(message.text) or extract_clean_phone(message.text)
    if not query_num:
        return False

    # 2. Agar mijoz texnik savol, apparat nosozligi, yillik tekshiruv yoki hisob raqam so'rayotgan bo'lsa
    # INNni eslab qolamiz va yagona 8-qadamli GroupResponseOrchestrator (chat_router) ga o'tkazamiz!
    lower = message.text.lower()
    from handlers.intents.hardware import is_device_issue
    from payment_accounts import (
        is_annual_check_intent,
        is_both_check_intent,
        classify_payment_intent,
        is_payment_claim
    )

    TECH_QUESTION_WORDS = [
        "qanday", "qanaqa", "qilish kerak", "qo'yish", "urish", "bekor qilish",
        "vozvrat", "qaytaring", "qaytarish", "zaryad", "zaryatka", "qog'oz", "qogoz",
        "x-otchet", "x otchet", "z-otchet", "z otchet", "inkassatsiya", "wifi",
        "parol", "ulanish", "ochish", "yoqish", "ulash", "tushuntiring", "yo'riqnoma",
        "как", "как пробить", "возврат", "зарядка", "бумага", "инкассация"
    ]
    if (
        any(tw in lower for tw in TECH_QUESTION_WORDS)
        or is_device_issue(message.text)
        or is_annual_check_intent(message.text)
        or is_both_check_intent(message.text)
        or bool(classify_payment_intent(message.text))
        or is_payment_claim(message.text)
    ):
        user_id = message.from_user.id if message.from_user else 0
        if excel_manager.search(query_num) or excel_manager.is_decommissioned(query_num):
            user_memory.set_last_id(message.chat.id, user_id, query_num)
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
    user_memory.clear_escalation(chat_id, user_id)

    found_num = extract_clean_inn(message.text) or extract_clean_phone(message.text)
    if found_num:
        last_id = found_num
    else:
        last_id = user_memory.get_last_id(chat_id, user_id)

    if not last_id:
            w_msg = adapt_to_user_script(
                "⚠️ <b>To'lov tarixini tekshirish uchun korxona INN (STIR) yoki ro'yxatdan o'tgan telefon raqamingizni yuboring.</b>\n"
                "Masalan: <code>302568138</code> yoki <code>901234567</code>",
                user_script
            )
            await message.reply(w_msg, parse_mode="HTML")
            return

    results = excel_manager.search(last_id)
    if not results:
        if excel_manager.is_decommissioned(last_id):
            decom_list = excel_manager.get_decommissioned(last_id)
            org_name = decom_list[0].get("name", "-") if decom_list else "-"
            nf_msg = adapt_to_user_script(
                f"ℹ️ <b>{org_name}</b> (<code>{last_id}</code>) xizmat ko'rsatish bazasidan hisobdan chiqarilgan (o'chirilgan). Joriy qarzdorlik hisoblanmaydi.",
                user_script
            )
            await message.reply(nf_msg, parse_mode="HTML")
            return
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

    history_resp = excel_manager.format_payment_history(results, chat_id=chat_id, user_id=user_id)
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
 
 
@router.message(lambda msg: bool(msg.text and is_incomplete_inn_text(msg.text)))
async def handle_incomplete_inn_query(message: types.Message):
    """Foydalanuvchi chala yoki 9 xonadan kam INN yuborganida to'g'ri yo'naltirish"""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    user_script = user_memory.detect_and_update_script(chat_id, user_id, message.text or "")
    incomplete_msg = (
        "⚠️ <b>Kiritilgan СТИР (INN) raqami to'liq emas.</b>\n\n"
        "Korxona INN raqami <b>9 xonali</b> (yoki JSHSHIR 14 xonali) bo'lishi kerak.\n"
        "Iltimos, korxona INN raqamingizni to'liq tekshirib qayta yuboring (masalan: <code>302568138</code>)."
    )
    incomplete_msg = adapt_to_user_script(incomplete_msg, user_script)
    try:
        await message.reply(incomplete_msg, parse_mode="HTML")
    except Exception:
        await message.reply(incomplete_msg)
    user_memory.add_user_message(chat_id, user_id, message.text or "")
    user_memory.add_assistant_message(chat_id, user_id, incomplete_msg)

