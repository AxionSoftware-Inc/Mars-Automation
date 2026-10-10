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
from core.models import DeviceFacts, ReceiptFacts

MARS_ACCOUNT = "20208000800208044003"
MARS_INN = "302568138"
MARS_KEYWORDS = [
    "mars", "марс", "mars elektron texnika", "марс электрон техника",
    "20208000800208044003", "302568138"
]

RECEIPT_SIGNALS = [
    "to'lov", "tolov", "chek", "kvitansiya", "click", "payme", "oplata",
    "muvaffaqiyatli", "o'tkazildi", "otkazildi", "pul o'tkazma", "summa",
    "munis", "uzum", "anorbank", "milliy", "hisobiga"
]


def analyze_media_image(
    image_bytes: bytes,
    user_caption: str = "",
    mime_type: str = "image/jpeg"
) -> Tuple[str, Optional[ReceiptFacts], Optional[DeviceFacts]]:
    """
    Markaziy ko'rish sensori (Unified Vision Sensory Extractor):
    Tasvirni bir martalik AI vision so'rovi orqali aniq tahlil qiladi:
    1. "receipt" -> To'lov kvitansiyasi / chek / to'lov topshiriqnomasi (qog'oz chek, Click, Payme, Uzum, Munis, bank ilovasi skrinshoti)
    2. "pos_device" -> Smart POS apparati ekrani (Pax, UzSmart, Sunmi apparatidagi dastur, xatolik kodi, kassa interfeysi)
    3. "other" -> Begona tasvir (inson, avtomobil, tabiat, taom, rasmga aloqasiz xona yoki begona foto)
    
    Qaytaradi: (media_type, receipt_facts, device_facts)
    """
    caption_inn = None
    if user_caption:
        found_nums = re.findall(r"\b(\d{14}|\d{9})\b", user_caption)
        if found_nums:
            caption_inn = found_nums[0]

    now_uzb = datetime.now(ZoneInfo("Asia/Tashkent"))
    current_time_str = now_uzb.strftime("%Y-%m-%d %H:%M")
    current_hour_min = now_uzb.strftime("%H:%M")

    prompt = f"""
Siz "Mars" servis markazining rasmlarni tahlil qiluvchi professional AI analizatorisiz.
Foydalanuvchi yuborgan tasvirni DIQQAT BILAN ko'zdan kechiring va uni quyidagi 3 toifadan biriga ajrating.

HOZIRGI REAL VAQT VA SANA (Toshkent vaqti): {current_time_str}

TASVIR TOIFALARI VA QAT'IY BELGILASH QOIDALARI:
1. "receipt" (TO'LOV KVITANSIYASI / CHEK / TRANZAKSIYA TASDIG'I):
   - Qog'oz to'lov cheki (bank kassa cheki, terminal qog'oz kvitansiyasi, fiskal to'lov cheki, to'lov topshiriqnomasi).
   - To'lov ilovalari skrinshotlari (Click, Payme, Uzum Bank, Anorbank, Milliy, Ipak Yo'li, Kapitalbank, Munis, "To'lov muvaffaqiyatli amalga oshirildi" oynasi).
   - Unda to'langan summa (masalan 100 000 so'm), tranzaksiya raqami, sana/vaqt yoki to'lov rekvizitlari ko'rinib turadi.
   MUHIM QOIDA: Agar rasm to'lov ilovasi (Click, Payme va h.k.) skrinshoti bo'lsa va tepasida telefon soati/batareyasi ko'rinsa ham, bu BARIBIR "receipt" hisoblanadi! Smart POS apparati EMAS!

2. "pos_device" (SMART POS KASSA TERMINALI APPARATI EKRANI):
   - Jismoniy Smart POS terminali (Pax A930, Pax D210, UzSmart, Sunmi va h.k.) yoki undagi kassa dasturining asosiy menyusi, xatolik ekrani (masalan Kod 102, Kod 201, Kod 204, Kod 300, Tamper, Fiskal modul xatosi, Qog'oz tugadi, Smena ochish, Sertifikat muddati tugagan va h.k.).
   - Maqsad: Apparatdagi texnik nosozlikni aniqlash va tuzatish.

3. "other" (BEGONA TASVIR):
   - Inson, avtomobil, tabiat, hayvon, taom, rasmga aloqasiz xona, to'lovga aloqasiz hujjat, stiker yoki begona foto.

JAVOB FORMATI FAQAT JSON BO'LISHI SHART (boshqa hech qanday so'z qo'shmang):
{{
  "media_type": "receipt" | "pos_device" | "other",

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
    "is_status_bar_visible": true/false, // Smart POS apparati ekrani tepasidagi soat yoki tarmoq/internet status bar qatori to'liq tushganmi?
    "time_mismatch": true/false, // Ekrandagi soat real Toshkent vaqtidan ({current_hour_min}) 10 daqiqadan ko'pga farq qiladimi?
    "has_internet": true/false, // Status bardagi Wi-Fi yoki mobil tarmoq belgisi bormi?
    "error_type": "debt" | "fiscal_module" | "update" | "paper" | "none",
    "detected_inn": "123456789" yoki null, // Ekranda ko'ringan STIR/INN
    "screen_text_summary": "ekrandagi xatolik yoki ko'ringan yozuvlar"
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

        try:
            facts = json.loads(raw_json)
        except Exception:
            match = re.search(r"\{.*\}", raw_json, re.DOTALL)
            facts = json.loads(match.group(0)) if match else {}

        media_type = str(facts.get("media_type", "other")).lower()
        rec_raw = facts.get("receipt") or {}
        dev_raw = facts.get("device") or {}

        rec_summary = str(rec_raw.get("summary", "")).lower()
        dev_summary = str(dev_raw.get("screen_text_summary", "")).lower()
        caption_lower = (user_caption or "").lower()

        # O'zini-o'zi tuzatish (Self-correcting safeguard):
        # Agar to'lov signallari mavjud bo'lsa, uni adashib pos_device yoki other deb belgilashdan himoya
        has_receipt_signal = (
            any(s in caption_lower for s in RECEIPT_SIGNALS) or
            any(s in rec_summary for s in RECEIPT_SIGNALS) or
            any(s in dev_summary for s in RECEIPT_SIGNALS) or
            (rec_raw.get("amount") is not None and float(rec_raw.get("amount", 0) or 0) > 0)
        )

        if media_type != "receipt" and has_receipt_signal:
            # Agar bu apparatdagi fatal xatolik bo'lmasa, demak to'lov kvitansiyasi
            if not (dev_raw.get("is_real_pos_device") and dev_raw.get("error_type") in ["fiscal_module", "update", "paper"]):
                media_type = "receipt"

        # 1. TO'LOV KVITANSIYASI
        if media_type == "receipt":
            amount = 0.0
            try:
                if rec_raw.get("amount"):
                    amount = float(str(rec_raw["amount"]).replace(" ", "").replace(",", "."))
            except Exception:
                amount = 0.0

            payer_inn = rec_raw.get("payer_inn") or dev_raw.get("detected_inn") or caption_inn
            if payer_inn:
                inn_clean = re.findall(r"\b(\d{14}|\d{9})\b", str(payer_inn))
                payer_inn = inn_clean[0] if inn_clean else None

            recipient_acc = str(rec_raw.get("recipient_account", ""))
            combined_text = f"{recipient_acc} {rec_raw.get('summary', '')} {rec_raw.get('payer_name', '')} {dev_summary}".lower()
            is_mars = bool(rec_raw.get("is_mars_recipient", False)) or any(kw in combined_text for kw in MARS_KEYWORDS)

            # Agar summa > 0 yoki chek deb topilgan bo'lsa va qabul qiluvchi ko'rsatilmagan bo'lsa, standart Mars deb hisoblash
            if not recipient_acc:
                recipient_acc = "«Mars Elektron Texnika» MCHJ"
                is_mars = True

            receipt_facts = ReceiptFacts(
                is_receipt=True,
                recipient_account=recipient_acc,
                is_mars_recipient=is_mars,
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

        # 2. SMART POS KASSA APPARATI
        elif media_type == "pos_device":
            detected_inn = dev_raw.get("detected_inn") or caption_inn
            if detected_inn:
                inn_clean = re.findall(r"\b(\d{14}|\d{9})\b", str(detected_inn))
                detected_inn = inn_clean[0] if inn_clean else None

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

        # 3. BEGONA TASVIR
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

    if media_type == "receipt" and receipt_facts:
        decision = core_engine.process_receipt_facts(receipt_facts, chat_id=0, user_id=0)
        return (decision.reply_text or "", None, decision.detected_inn)

    if device_facts:
        decision = core_engine.process_device_facts(device_facts, chat_id=0, user_id=0)
        if decision.action == ActionType.IGNORE:
            return "", None, None
        return (decision.reply_text or "", decision.video_id, decision.detected_inn)

    return "", None, None
