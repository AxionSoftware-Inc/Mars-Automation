import os
import re
import json
import base64
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, Dict, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

from openrouter_client import openrouter_client
from core.models import DeviceFacts, ReceiptFacts, FiscalChekFacts
from core.models import extract_clean_inn, extract_fiscal_module

from payment_accounts import (
    MARS_ACCOUNT, MARS_INN, MARS_KEYWORDS, MARS_ORG_NAME,
    YANGI_TEXNOLOGIYALAR_ACCOUNT, YANGI_TEXNOLOGIYALAR_INN,
    YANGI_TEXNOLOGIYALAR_KEYWORDS, YANGI_TEXNOLOGIYALAR_ORG_NAME,
    classify_receipt_target
)

RECEIPT_SIGNALS = [
    "kvitansiya", "click", "payme", "oplata", "to'lov amalga", "tolov amalga",
    "muvaffaqiyatli", "o'tkazildi", "otkazildi", "pul o'tkazma",
    "munis", "uzum bank", "anorbank", "milliy bank", "платежное поручение"
]


def analyze_media_image(
    image_bytes: bytes,
    user_caption: str = "",
    mime_type: str = "image/jpeg"
) -> Tuple[str, Optional[ReceiptFacts], Optional[DeviceFacts]]:
    """
    Markaziy ko'rish sensori (Unified Vision Sensory Extractor):
    Tasvirni bir martalik AI vision so'rovi orqali aniq tahlil qiladi:
    1. "receipt" -> To'lov kvitansiyasi (Click, Payme, Uzum, Munis, bank to'lov topshiriqnomasi)
    2. "fiscal_receipt" -> Kassa cheki (termal qog'oz savdo cheki, Onlayn-NKM, Z-hisobot, X-hisobot)
    3. "pos_device" -> Smart POS apparati ekrani (Pax, UzSmart, Sunmi apparatidagi dastur, xatolik kodi)
    4. "other" -> Begona tasvir (inson, avtomobil, tabiat, taom, rasmga aloqasiz xona yoki begona foto)
    
    Qaytaradi: (media_type, receipt_facts, device_facts)
    """
    caption_inn = extract_clean_inn(user_caption) if user_caption else None

    now_uzb = datetime.now(ZoneInfo("Asia/Tashkent"))
    current_time_str = now_uzb.strftime("%Y-%m-%d %H:%M")
    current_hour_min = now_uzb.strftime("%H:%M")

    prompt = f"""
Siz "Mars" servis markazining rasmlarni tahlil qiluvchi professional AI analizatorisiz.
Foydalanuvchi yuborgan tasvirni DIQQAT BILAN ko'zdan kechiring va uni quyidagi 4 toifadan biriga ajrating.

HOZIRGI REAL VAQT VA SANA (Toshkent vaqti): {current_time_str}

TASVIR TOIFALARI VA QAT'IY BELGILASH QOIDALARI:
1. "receipt" (TO'LOV KVITANSIYASI / PUL O'TKAZMASI TASDIG'I):
   - To'lov ilovalari skrinshotlari (Click, Payme, Uzum Bank, Anorbank, Milliy, Ipak Yo'li, Kapitalbank, Munis va h.k. ilovalaridagi "To'lov muvaffaqiyatli amalga oshirildi" oynasi).
   - Bank to'lov topshiriqnomasi (платежное поручение), memorial order, bank kassa kvitansiyasi.
   - MAQSAD: Tashkilotga (masalan «Mars Elektron Texnika»ga 100 000 so'm, yoki «Yangi Texnologiyalar» DUK ga 440 000 so'm) pul to'langanini isbotlash.
   - Unda qabul qiluvchi hisob raqami / xizmat nomi, to'lovchi, o'tkazilgan summa, tranzaksiya ID si ko'rinib turadi.
   MUHIM QOIDA: Agar rasm to'lov ilovasi (Click, Payme va h.k.) skrinshoti bo'lsa va tepasida telefon soati/batareyasi ko'rinsa ham, bu BARIBIR "receipt" hisoblanadi! Smart POS apparati yoki kassa cheki EMAS!

2. "fiscal_receipt" (KASSA CHEKI / FISKAL CHEK / SAVDO CHEKI / ONLAYN-NKM CHEKI / Z-HISOBOT):
   - Do'kon, dorixona, oshxona yoki xizmat ko'rsatish nuqtasida kassa apparatidan (termal qog'oz printeridan) chiqarilgan oq qog'oz savdo cheki yoki fiskal hisobot (Z-hisobot, X-hisobot).
   - Unda nimalar ko'rinadi:
     * Odatda kassa chekining yuqori qismida korxona / tashkilot nomi ("OOO...", "MCHJ...", "YaTT...", "XK...");
     * 9 xonali СТИР / INN (soliq to'lovchining identifikatsiya raqami, masalan: СТИР: 302568138);
     * Fiskal modul seriya raqami: "FM", "FMR", "ФМ", "ФМР" yoki "Fiskal modul" deb yozilgan 2 ta lotin harfi va 8-14 ta raqam (masalan: LG420210630789, YG202106307890, UZ...);
     * Terminal raqami yoki kassa apparati seriya raqami;
     * Sotilgan mahsulotlar / xizmatlar ro'yxati, MXIK kodlari, Jami xarid summasi, QQS;
     * Chekning eng pastida QR-kod (soliq.uz tekshirish uchun) va fiskal belgi.
   - DIQQAT: Bu to'lov kvitansiyasi EMAS! Bu kassa apparatidan chiqqan savdo xarid cheki!

3. "pos_device" (SMART POS APPARATI, KASSA TERMINALI YOKI KASSA DASTURI EKRANI):
   - Jismoniy Smart POS terminali (Pax A930, Pax D210, UzSmart, Sunmi va h.k.) YOKI kassa dasturi o'rnatilgan smartfon, planshet, kompyuter/kassa ekrani.
   - Har qanday kassa dasturi (UzSmart, Mars va h.k.) menyusi, ogohlantirishlari (masalan "До остановки работы программы осталось...", "Hisobni to'ldiring"), xatolik ekrani (Kod 102, Kod 201, Kod 204, Kod 300, Tamper, Fiskal modul, Qog'oz tugadi, Smena ochish/yopish, va h.k.).
   - Agar ekranda kassa dasturi yoki apparat xatoligi ko'rinsa — bu har doim "pos_device" hisoblanadi!
   - Maqsad: Apparatdagi texnik nosozlikni aniqlash va tuzatish.

4. "other" (MUTLAQO BEGONA TASVIR):
   - Faqatgina kassa apparati, dasturi yoki to'lovga umuman hech qanday aloqasi bo'lmagan tasvirlar (odam, tabiat, hayvon, mashina, taom, stiker).

JAVOB FORMATI FAQAT JSON BO'LISHI SHART (boshqa hech qanday so'z qo'shmang):
{{
  "media_type": "receipt" | "fiscal_receipt" | "pos_device" | "other",

  // AGAR media_type == "fiscal_receipt" BO'LSA:
  "fiscal_receipt": {{
    "inn": "302568138", // 9 xonali STIR/INN raqami (agar chekda ko'rinsa)
    "fiscal_module": "LG420210630789", // FM / FMR / Fiskal modul seriya raqami (LG..., YG..., UZ...)
    "org_name": "Korxona yoki savdo nuqtasi nomi",
    "terminal_id": "01234567",
    "check_number": "123",
    "total_amount": 15000.0,
    "date_time": "2026-10-10 14:20",
    "receipt_type": "sale", // "sale" (xarid cheki), "z_report" (Z-hisobot), "x_report"
    "summary": "Savdo cheki, STIR: 302568138, FM: LG420210630789"
  }},

  // AGAR media_type == "receipt" BO'LSA:
  "receipt": {{
    "recipient_account": "20208000800208044003", // qabul qiluvchi hisob raqami yoki xizmat nomi
    "is_mars_recipient": true/false, // To'lov "Mars Elektron Texnika" (hisob: 20208000800208044003, INN: 302568138) ga qaratilganmi?
    "amount": 100000.0, // to'langan summa (faqat son, float)
    "payer_inn": "123456789" yoki null, // to'lovchi STIR/INN (9 xonali) yoki JSHSHIR (14 xonali)
    "payer_name": "Korxona yoki shaxs nomi",
    "payment_date": "2026-10-10 11:30",
    "transaction_id": "123456789",
    "payment_system": "Click", // Click, Payme, Bank, Munis, Uzum, va h.k.
    "summary": "To'lov haqida qisqacha ma'lumot"
  }},

  // AGAR media_type == "pos_device" BO'LSA:
  "device": {{
    "is_real_pos_device": true,
    "is_status_bar_visible": true/false,
    "time_mismatch": true/false,
    "has_internet": true/false,
    "error_type": "debt" | "fiscal_module" | "update" | "paper" | "none",
    "detected_inn": "123456789" yoki null,
    "screen_text_summary": "Ekranda yozilgan xatolik yoki ogohlantirishning o'zbek tilidagi aniq va qisqa ta'rifi"
  }}
}}

Foydalanuvchi izohi: "{user_caption}"
"""

    try:
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:{mime_type};base64,{b64_img}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]

        raw_json = openrouter_client.chat_completion(
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"}
        ) or "{}"
        logger.info(f"OpenRouter Vision tahlili: {raw_json}")

        try:
            facts = json.loads(raw_json)
        except Exception:
            match = re.search(r"\{.*\}", raw_json, re.DOTALL)
            facts = json.loads(match.group(0)) if match else {}

        media_type = str(facts.get("media_type", "other")).lower()
        rec_raw = facts.get("receipt") or {}
        fisc_raw = facts.get("fiscal_receipt") or {}
        dev_raw = facts.get("device") or {}

        rec_summary = str(rec_raw.get("summary", "")).lower()
        fisc_summary = str(fisc_raw.get("summary", "")).lower()
        dev_summary = str(dev_raw.get("screen_text_summary", "")).lower()
        caption_lower = (user_caption or "").lower()

        # Fiskal kassa cheki signallari (termal qog'oz, onlayn-nkm, mxik, z-hisobot, fm raqam):
        has_explicit_fm = bool(fisc_raw.get("fiscal_module")) or bool(extract_fiscal_module(fisc_summary + " " + caption_lower + " " + rec_summary))
        fiscal_keywords = [
            "fiskal chek", "kassa cheki", "savdo cheki", "xarid cheki", "onlayn-nkm", "onlayn nkm",
            "virtual kassa", "fiskal modul", "z-hisobot", "x-hisobot", "z hisobot", "x hisobot",
            "fiskal belgi", "mxik", "мхик", "чек nkm"
        ]
        has_fiscal_signal = (
            media_type == "fiscal_receipt" or
            has_explicit_fm or
            any(k in caption_lower for k in fiscal_keywords) or
            any(k in fisc_summary for k in fiscal_keywords) or
            any(k in rec_summary for k in fiscal_keywords)
        )

        is_payment_screen = (
            any(p in caption_lower for p in ["click", "payme", "uzum bank", "anorbank", "pul o'tkazma", "to'lov muvaffaqiyatli"]) or
            any(p in rec_summary for p in ["click", "payme", "uzum bank", "to'lov muvaffaqiyatli", "o'tkazma muvaffaqiyatli", "to'lov topshiriqnomasi"])
        )

        if has_fiscal_signal and not is_payment_screen:
            media_type = "fiscal_receipt"

        # O'zini-o'zi tuzatish (Self-correcting safeguard) faqat to'lov kvitansiyalari uchun:
        if media_type not in ["fiscal_receipt", "receipt"] and not has_fiscal_signal:
            has_receipt_signal = (
                any(s in caption_lower for s in RECEIPT_SIGNALS) or
                any(s in rec_summary for s in RECEIPT_SIGNALS) or
                (rec_raw.get("amount") is not None and float(rec_raw.get("amount", 0) or 0) > 0 and is_payment_screen)
            )
            if has_receipt_signal:
                if not (dev_raw.get("is_real_pos_device") and dev_raw.get("error_type") in ["fiscal_module", "update", "paper"]):
                    media_type = "receipt"

        # 1. KASSA CHEKI (ONLAYN-NKM / FISKAL SAVDO CHEKI)
        if media_type == "fiscal_receipt":
            inn = (
                extract_clean_inn(str(fisc_raw.get("inn") or "")) or
                extract_clean_inn(str(rec_raw.get("payer_inn") or "")) or
                extract_clean_inn(str(dev_raw.get("detected_inn") or "")) or
                extract_clean_inn(fisc_summary) or
                extract_clean_inn(rec_summary) or
                caption_inn
            )
            fm = (
                extract_fiscal_module(str(fisc_raw.get("fiscal_module") or "")) or
                extract_fiscal_module(str(fisc_raw.get("terminal_id") or "")) or
                extract_fiscal_module(fisc_summary) or
                extract_fiscal_module(rec_summary) or
                extract_fiscal_module(caption_lower)
            )
            org_name = str(fisc_raw.get("org_name") or rec_raw.get("payer_name") or "").strip()
            terminal_id = str(fisc_raw.get("terminal_id") or "")
            check_number = str(fisc_raw.get("check_number") or "")
            total_amount = 0.0
            try:
                if fisc_raw.get("total_amount"):
                    total_amount = float(str(fisc_raw["total_amount"]).replace(" ", "").replace(",", "."))
                elif rec_raw.get("amount"):
                    total_amount = float(str(rec_raw["amount"]).replace(" ", "").replace(",", "."))
            except Exception:
                total_amount = 0.0

            fiscal_facts = FiscalChekFacts(
                is_fiscal_chek=True,
                inn=inn,
                fiscal_module=fm,
                org_name=org_name,
                terminal_id=terminal_id,
                check_number=check_number,
                date_time=str(fisc_raw.get("date_time") or ""),
                total_amount=total_amount,
                receipt_type=str(fisc_raw.get("receipt_type") or "sale"),
                raw_text=fisc_summary or rec_summary,
                raw_facts=fisc_raw or facts,
                extraction_error=None
            )

            receipt_facts = ReceiptFacts(
                is_receipt=False,
                is_fiscal_chek=True,
                fiscal_module=fm,
                terminal_id=terminal_id,
                fiscal_facts=fiscal_facts,
                payer_inn=inn,
                payer_name=org_name,
                recipient_org_name=org_name,
                amount=total_amount,
                raw_text=fiscal_facts.raw_text,
                raw_facts=facts,
                extraction_error=None
            )
            return ("fiscal_receipt", receipt_facts, None)

        # 2. TO'LOV KVITANSIYASI
        elif media_type == "receipt":
            amount = 0.0
            try:
                if rec_raw.get("amount"):
                    amount = float(str(rec_raw["amount"]).replace(" ", "").replace(",", "."))
            except Exception:
                amount = 0.0

            payer_inn = extract_clean_inn(str(rec_raw.get("payer_inn") or dev_raw.get("detected_inn") or caption_inn or ""))

            recipient_acc = str(rec_raw.get("recipient_account", ""))
            combined_text = f"{recipient_acc} {rec_raw.get('summary', '')} {rec_raw.get('payer_name', '')} {dev_summary}".lower()

            category = classify_receipt_target(recipient_acc, amount, raw_text=combined_text)
            is_annual_fiscal = (category == "annual")
            if is_annual_fiscal:
                is_mars = False
                recipient_org_name = YANGI_TEXNOLOGIYALAR_ORG_NAME
                recipient_acc = recipient_acc or YANGI_TEXNOLOGIYALAR_ACCOUNT
            elif category == "monthly":
                is_mars = True
                recipient_org_name = MARS_ORG_NAME
                recipient_acc = recipient_acc or MARS_ACCOUNT
            else:
                is_mars = bool(rec_raw.get("is_mars_recipient", False)) or any(kw in combined_text for kw in MARS_KEYWORDS)
                recipient_org_name = recipient_acc or (MARS_ORG_NAME if is_mars else "Begona tashkilot")

            receipt_facts = ReceiptFacts(
                is_receipt=True,
                is_fiscal_chek=False,
                fiscal_module=None,
                recipient_account=recipient_acc or recipient_org_name,
                is_mars_recipient=is_mars,
                is_annual_fiscal_fee=is_annual_fiscal,
                payment_category=category,
                recipient_org_name=recipient_org_name,
                amount=amount,
                payer_inn=payer_inn,
                payer_name=str(rec_raw.get("payer_name", "")),
                payment_date=str(rec_raw.get("payment_date", "")),
                transaction_id=str(rec_raw.get("transaction_id", "")),
                payment_system=str(rec_raw.get("payment_system", "")),
                raw_text=rec_summary or dev_summary,
                raw_facts=facts,
                extraction_error=None
            )
            return ("receipt", receipt_facts, None)

        # 3. SMART POS KASSA APPARATI
        elif media_type == "pos_device":
            detected_inn = extract_clean_inn(str(dev_raw.get("detected_inn") or caption_inn or ""))

            device_facts = DeviceFacts(
                is_real_pos_device=bool(dev_raw.get("is_real_pos_device", True)),
                is_status_bar_visible=bool(dev_raw.get("is_status_bar_visible", False)),
                time_mismatch=bool(dev_raw.get("time_mismatch", False)),
                has_internet=bool(dev_raw.get("has_internet", True)),

                error_type=str(dev_raw.get("error_type", "none")),
                detected_inn=detected_inn,
                screen_text_summary=str(dev_raw.get("screen_text_summary", "")),
                raw_facts=dev_raw or facts,
                extraction_error=None
            )
            return ("pos_device", None, device_facts)

        # 4. BEGONA TASVIR
        else:
            return ("other", None, None)

    except Exception as e:
        logger.error(f"Image analysis extraction error: {e}")
        # Sensor uzilib qolganda xavfsiz holat
        return ("other", None, DeviceFacts(is_real_pos_device=False, detected_inn=caption_inn, extraction_error=str(e)))


def extract_device_facts(image_bytes: bytes, user_caption: str = "", mime_type: str = "image/jpeg") -> DeviceFacts:
    """
    Backwards compatibility: Faqat DeviceFacts obyektini olish uchun.
    """
    media_type, receipt_facts, device_facts = analyze_media_image(image_bytes, user_caption, mime_type)
    if device_facts:
        return device_facts
    
    caption_inn = None
    if user_caption:
        f = re.findall(r"\b(\d{14}|\d{9})\b", user_caption)
        if f: caption_inn = f[0]

    return DeviceFacts(is_real_pos_device=False, detected_inn=caption_inn)


def analyze_pos_screen(image_bytes: bytes, user_caption: str = "", mime_type: str = "image/jpeg") -> Tuple[str, Optional[int], Optional[str]]:
    """
    Backwards compatibility interfeysi:
    Sensordan faktlarni oladi va CoreEngine orqali yakuniy natijani qaytaradi.
    """
    from core.engine import core_engine, ActionType
    media_type, receipt_facts, device_facts = analyze_media_image(image_bytes, user_caption, mime_type)

    if media_type == "fiscal_receipt" and receipt_facts:
        return ("Kassa cheki qabul qilindi", None, receipt_facts.payer_inn)

    if media_type == "receipt" and receipt_facts:
        decision = core_engine.process_receipt_facts(receipt_facts, chat_id=0, user_id=0)
        return (decision.reply_text or "", None, decision.detected_inn)

    if device_facts:
        decision = core_engine.process_device_facts(device_facts, chat_id=0, user_id=0)
        if decision.action == ActionType.IGNORE:
            return "", None, None
        return (decision.reply_text or "", decision.video_id, decision.detected_inn)

    return "", None, None
