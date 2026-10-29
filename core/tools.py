"""
core/tools.py - Mars POS Pastki Qatlam Asboblari (Clean Business Logic Tools)
===========================================================================
Ushbu modul 2 qatlamli arxitekturadagi "Pastki Qatlam" (Pure Python Tools)
vazifasini bajaradi:
1. Hech qanday chalkash Telegram xabarlarini tahlil qilish yoki regex qidirish bilan shug'ullanmaydi.
2. Aniq parametrlar oladi, biznes logikani (Excel, OFD, Kvitansiya, Admin, Xatoliklar)
   bajaradi va toza, tizimli natija (Dict / Text) qaytaradi.
3. Yuqori qatlam (AI Agent yoki Testlar) aynan shu asboblarni to'g'ridan-to'g'ri chaqiradi.
"""

import os
import re
import logging
from typing import Optional, Dict, Any, List
from aiogram import Bot

from core.models import extract_clean_inn, extract_fiscal_module
from excel_manager import excel_manager
from ofd_bridge import ofd_bridge
from payment_accounts import parse_ofd_reply_status, format_ofd_annual_status
from transaction_tracker import transaction_tracker
from admin_manager import admin_manager
from modules.admin_module import regional_admin_service
from translit_manager import adapt_to_user_script
from templates import (
    format_debt_response_template,
    get_monthly_payment_card,
    get_annual_payment_card,
    get_all_payment_accounts_card,
    get_hardware_step1_inn_template,
    get_hardware_step2_fm_template,
    get_hardware_step3_clear_template,
    get_escalate_admin_template,
    get_receipt_ack_template,
    format_ofd_status_template,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 1. OYLIK QARZDORLIKNI TEKSHIRISH (Excel Baza)
# =============================================================================
def check_monthly_debt(inn: str, script: str = "latin") -> Dict[str, Any]:
    """
    Korxonaning oylik abonent to'lovidan qarzdorligini INN orqali tekshirish.
    """
    clean_inn = extract_clean_inn(str(inn))
    if not clean_inn:
        err_msg = adapt_to_user_script("⚠️ INN raqami noto'g'ri kiritildi (9 yoki 14 xonali bo'lishi kerak).", script)
        return {
            "success": False,
            "inn": inn,
            "found": False,
            "org_name": "",
            "debt_amount": 0,
            "has_debt": False,
            "model": "",
            "formatted_text": err_msg
        }

    debt_info = excel_manager.check_debt(clean_inn)
    if not debt_info.get("found"):
        not_found_msg = adapt_to_user_script(
            f"❌ <b>INN: {clean_inn}</b> bo'yicha ma'lumot topilmadi.\n"
            "Iltimos, INN to'g'riligini tekshiring yoki adminga murojaat qiling.",
            script
        )
        return {
            "success": True,
            "inn": clean_inn,
            "found": False,
            "org_name": "",
            "debt_amount": 0,
            "has_debt": False,
            "model": "",
            "formatted_text": not_found_msg
        }

    results = debt_info.get("results", [])
    record = debt_info.get("record", {})
    debt_amount = int(debt_info.get("total_debt", 0))
    org_name = record.get("org_name", "")
    has_debt = (debt_amount > 0)
    model = excel_manager.get_device_model_summary(results)

    formatted = format_debt_response_template(
        results=results,
        script=script
    )

    return {
        "success": True,
        "inn": clean_inn,
        "found": True,
        "org_name": org_name,
        "debt_amount": debt_amount,
        "has_debt": has_debt,
        "model": model,
        "formatted_text": formatted
    }


# =============================================================================
# 2. YILLIK FISKAL MODUL / SOLIQ LITSENZIYASINI TEKSHIRISH (OFD Bridge)
# =============================================================================
async def check_fiscal_license(fiscal_module: str, bot: Optional[Bot] = None, script: str = "latin") -> Dict[str, Any]:
    """
    Apparatning yillik fiskal modul litsenziyasi va to'lov holatini @ofd943_bot orqali tekshirish.
    """
    clean_fm = extract_fiscal_module(str(fiscal_module)) or str(fiscal_module).strip().upper()
    if not clean_fm or len(clean_fm) < 6:
        err_msg = adapt_to_user_script(
            "⚠️ Fiskal modul seriya raqami noto'g'ri (LG yoki YG bilan boshlanadi).",
            script
        )
        return {
            "success": False,
            "fm": fiscal_module,
            "status": "invalid_code",
            "has_debt": False,
            "raw_reply": "",
            "formatted_text": err_msg
        }

    try:
        raw_reply = await ofd_bridge.query_fiscal_module(bot, clean_fm)
    except Exception as e:
        logger.error(f"check_fiscal_license xatoligi (FM={clean_fm}): {e}")
        raw_reply = None

    status = parse_ofd_reply_status(raw_reply)
    has_debt = (status == "debt")

    if status == "unavailable":
        msg = adapt_to_user_script(
            f"⏳ <b>Davlat Soliq (OFD) tizimi vaqtincha javob bermayapti.</b>\n\n"
            f"🏛 <b>Fiskal modul:</b> <code>{clean_fm}</code>\n"
            f"Iltimos, birozdan so'ng qayta urinib ko'ring.",
            script
        )
    else:
        msg = format_ofd_annual_status(clean_fm, raw_reply, script=script)

    return {
        "success": True,
        "fm": clean_fm,
        "status": status,
        "has_debt": has_debt,
        "raw_reply": raw_reply or "",
        "formatted_text": msg
    }


# =============================================================================
# 3. TO'LOV HISOB RAQAMLARI VA REKVIZITLAR
# =============================================================================
def get_payment_requisites(payment_type: str = "monthly", script: str = "latin") -> Dict[str, Any]:
    """
    Mars abonent (oylik) yoki Davlat Soliq (yillik fiskal modul) hisob raqamlarini qaytarish.
    """
    norm_type = str(payment_type).lower().strip()
    if norm_type in ("annual", "yillik", "fiskal", "soliq"):
        text = get_annual_payment_card(script=script)
        video_id = 145
        post_id = 34
        ptype = "annual"
    elif norm_type in ("both", "ikkala", "ikkalasi", "barchasi"):
        text = get_all_payment_accounts_card(script=script)
        video_id = 148
        post_id = 85
        ptype = "both"
    else:
        text = get_monthly_payment_card(script=script)
        video_id = 148
        post_id = 85
        ptype = "monthly"

    return {
        "success": True,
        "payment_type": ptype,
        "video_id": video_id,
        "post_id": post_id,
        "formatted_text": text
    }


# =============================================================================
# 4. KVITANSIYA VA TO'LOV CHEKLARINI TEKSHIRISH
# =============================================================================
def verify_receipt_data(
    transaction_id: Optional[str] = None,
    inn: Optional[str] = None,
    amount: int = 0,
    is_duplicate: bool = False,
    script: str = "latin"
) -> Dict[str, Any]:
    """
    Kvitansiya ma'lumotlarini tekshirish, tranzaksiyani yozish va xabar shablonini shakllantirish.
    """
    clean_inn = extract_clean_inn(str(inn)) if inn else None

    # Dublikat tekshiruvi
    is_dup = is_duplicate
    if transaction_id and not is_dup:
        if transaction_tracker.is_duplicate(transaction_id):
            is_dup = True

    if transaction_id and not is_dup:
        transaction_tracker.record_transaction(
            transaction_id=transaction_id,
            inn=clean_inn,
            amount=amount,
            user_id=0
        )

    reply_text = get_receipt_ack_template(
        is_recent_dup=is_dup,
        missing_inn=(clean_inn is None),
        script=script
    )

    return {
        "success": True,
        "is_duplicate": is_dup,
        "transaction_id": transaction_id,
        "inn": clean_inn,
        "amount": amount,
        "formatted_text": reply_text
    }


# =============================================================================
# 5. SMARTONE VA POS 4 BOSQICHLI DIAGNOSTIKA
# =============================================================================
async def pos_troubleshoot_step(
    inn: Optional[str] = None,
    fiscal_module: Optional[str] = None,
    reboot_tried: bool = False,
    error_code: Optional[str] = None,
    bot: Optional[Bot] = None,
    script: str = "latin"
) -> Dict[str, Any]:
    """
    Kassa apparatidagi nosozlikni tekshirishning 4-bosqichli oltin qoidasi:
    1-bosqich: Oylik abonent qarzini tekshirish (agar qarz bo'lsa -> to'lovni talab qilish).
    2-bosqich: Yillik fiskal modul qarzini tekshirish (agar qarz bo'lsa -> soliq to'lovini talab qilish).
    3-bosqich: Qarzlar toza bo'lsa -> Internet/soat/reboot qilishni aytish.
    4-bosqich: Agar reboot foyda bermagan bo'lsa -> Adminga eskalatsiya qilish.
    """
    clean_inn = extract_clean_inn(str(inn)) if inn else None
    clean_fm = extract_fiscal_module(str(fiscal_module)) if fiscal_module else None

    # 1-BOSQICH: INN ma'lum bo'lmasa -> INN so'rash
    if not clean_inn:
        return {
            "step": 1,
            "status": "need_inn",
            "action": "ASK_INN",
            "formatted_text": get_hardware_step1_inn_template(script=script)
        }

    # Oylik qarzni tekshirish
    monthly_res = check_monthly_debt(clean_inn, script=script)
    if monthly_res.get("found") and monthly_res.get("has_debt"):
        debt_sum = monthly_res.get("debt_amount", 0)
        return {
            "step": 1,
            "status": "monthly_debt_blocking",
            "action": "PAY_MONTHLY_DEBT",
            "debt_amount": debt_sum,
            "formatted_text": get_hardware_step1_inn_template(script=script)
        }

    org_name = monthly_res.get("org_name", "Mijoz")
    model = monthly_res.get("model", "Smart One")

    # 2-BOSQICH: Fiskal modul ma'lum bo'lmasa -> FM so'rash
    if not clean_fm:
        return {
            "step": 2,
            "status": "need_fm",
            "action": "ASK_FM",
            "formatted_text": get_hardware_step2_fm_template(
                org_name=org_name,
                inn=clean_inn,
                device_model=model,
                script=script
            )
        }

    # Yillik qarzni tekshirish
    annual_res = await check_fiscal_license(clean_fm, bot=bot, script=script)
    if annual_res.get("has_debt"):
        return {
            "step": 2,
            "status": "annual_debt_blocking",
            "action": "PAY_ANNUAL_DEBT",
            "formatted_text": get_hardware_step2_fm_template(
                org_name=org_name,
                inn=clean_inn,
                device_model=model,
                script=script
            )
        }

    # 3-BOSQICH: Ikkala qarz ham toza!
    contacts_str = admin_manager.get_contacts_display(inn=clean_inn)
    if not reboot_tried:
        return {
            "step": 3,
            "status": "debts_clear_advise_reboot",
            "action": "REBOOT_AND_CHECK_NET",
            "formatted_text": get_hardware_step3_clear_template(
                org_name=org_name,
                inn=clean_inn,
                fm=clean_fm,
                contacts_block=contacts_str,
                has_photo=False,
                script=script
            )
        }

    # 4-BOSQICH: Reboot ham yordam bermadi -> Adminga eskalatsiya
    admin_res = escalate_to_admin(
        inn=clean_inn,
        reason=f"Qarzlar toza, apparat o'chirib yoqildi lekin nosozlik tuzalmadi. Kod: {error_code or 'aniqlanmadi'}",
        script=script
    )
    return {
        "step": 4,
        "status": "escalated_to_admin",
        "action": "ESCALATE_ADMIN",
        "formatted_text": admin_res.get("formatted_text", "")
    }


# =============================================================================
# 6. ADMINGA / OPERATORGA ESKALATSIYA QILISH
# =============================================================================
def escalate_to_admin(
    inn: Optional[str] = None,
    region: Optional[str] = None,
    reason: str = "Mijoz mutaxassis yordamini so'ramoqda",
    user_id: int = 0,
    user_name: str = "Mijoz",
    photo: Optional[Any] = None,
    bot: Optional[Bot] = None,
    script: str = "latin"
) -> Dict[str, Any]:
    """
    Masalani viloyat mas'ul adminiga yoki bosh operatorga yo'naltirish.
    """
    clean_inn = extract_clean_inn(str(inn)) if inn else None
    contacts_str = admin_manager.get_contacts_display(inn=clean_inn)

    formatted_text = get_escalate_admin_template(
        contacts_block=contacts_str,
        script=script
    )

    return {
        "success": True,
        "escalated": True,
        "inn": clean_inn,
        "contacts_block": contacts_str,
        "reason": reason,
        "formatted_text": formatted_text
    }


# =============================================================================
# 7. ANIQ TEXNIK YO'RIQNOMALAR VA VIDEOLAR
# =============================================================================
def get_instruction(topic: str, script: str = "latin") -> Dict[str, Any]:
    """
    Standart texnik amallar (MXIK, Tasnif, Qaytuv/Vozvrat, X-Hisobot, Soat, Wifi) yo'riqnomasi.
    """
    norm = str(topic).lower().strip()

    if "mxik" in norm or "tasnif" in norm or "ikpu" in norm:
        text = (
            "📌 <b>MXIK kodlari haqida:</b>\n"
            "Tovar yoki xizmatlarning 17 xonali MXIK kodini rasmiy <b>tasnif.soliq.uz</b> saytidan qidirib olishingiz mumkin.\n"
            "Kassaga tovar kiritish yo'riqnomasi: [VIDEO:28]"
        )
        video_id = 28
    elif "vozvrat" in norm or "qaytuv" in norm or "bekor" in norm:
        text = (
            "📌 <b>Chekni bekor qilish (Vozvrat):</b>\n"
            "Chekni bekor qilish uchun 'Tarix' yoki 'Cheklar' bo'limiga kirib, kerakli chekni tanlang va 'Qaytarish' tugmasini bosing.\n"
            "Batafsil video: [VIDEO:140]"
        )
        video_id = 140
    elif "soat" in norm or "vaqt" in norm or "time" in norm:
        text = (
            "⏰ <b>Soat va sanani to'g'rilash:</b>\n"
            "Soat noto'g'ri bo'lsa, avval internetga ulanishni tekshiring va kassa sozlamalaridan 'Avtomatik vaqt'ni yoqing.\n"
            "Batafsil video: [VIDEO:141]"
        )
        video_id = 141
    elif "wifi" in norm or "parol" in norm or "kassa" in norm:
        text = (
            "🔑 <b>Kassa paroli:</b>\n"
            "Smart POS apparatlarida standart sozlamalar paroli: <code>0000</code>.\n"
            "Wifi ga ulanish videosi: [VIDEO:141]"
        )
        video_id = 141
    else:
        text = (
            "📌 <b>Texnik yo'riqnomalar katalogi:</b>\n"
            "Barcha kassa videolari va qo'llanmalar rasmiy kanalimizda: @POS_Terminal_UzSmart_Bank"
        )
        video_id = None

    return {
        "success": True,
        "topic": topic,
        "video_id": video_id,
        "formatted_text": adapt_to_user_script(text, script)
    }
