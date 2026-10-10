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
from core.models import DeviceFacts

def extract_device_facts(image_bytes: bytes, user_caption: str = "", mime_type: str = "image/jpeg") -> DeviceFacts:
    """
    Rasm sensor moduli (Sensory Extractor):
    Tasvirdan faqat sof faktlarni ajratib oladi va DeviceFacts modelida qaytaradi.
    Hech qanday javob matni yozmaydi va qaror chiqarmaydi.
    """
    # Caption ichidan INN qidirish
    caption_inn = None
    if user_caption:
        found_nums = re.findall(r"\b(\d{14}|\d{9})\b", user_caption)
        if found_nums:
            caption_inn = found_nums[0]

    # Hozirgi real O'zbekiston (Toshkent) vaqti
    now_uzb = datetime.now(ZoneInfo("Asia/Tashkent"))
    current_time_str = now_uzb.strftime("%Y-%m-%d %H:%M")
    current_hour_min = now_uzb.strftime("%H:%M")

    prompt = f"""
Siz "Mars" servis markazining kassa apparati ekranidan FAKTLARNI TEKSHIRUVCHI AI analizatorisiz.
O'zingizcha xulosa yoki maslahat to'qimang! Faqat quyidagi savollarga aniq va haqqoniy faktlar asosida JSON formatida javob bering.

HOZIRGI REAL VAQT VA SANA (Toshkent vaqti): {current_time_str}

JAVOB FORMATI FAQAT JSON BO'LISHI SHART:
{{
  "is_real_pos_device": true/false, // QAT'IY QOIDA: Rasmda Smart POS kassa terminali (masalan Pax, UzSmart, Sunmi apparati yoki kassa dasturi ekrani) bormi? AGAR rasmda kassa apparatiga aloqasi bo'lmagan har qanday narsa (odam, tabiat, mashina, hayvon, taom, xona, chek qog'ozi, stol, devor, kiyim, oddiy fotosurat) bo'lsa -> ALBATTA false deb belgilang!
  "is_status_bar_visible": true/false, // Ekran tepasidagi soat yoki tarmoq/internet status bar qatori to'liq tushganmi?
  "time_mismatch": true/false, // Ekrandagi soat hozirgi real Toshkent vaqtidan ({current_hour_min}) 10 daqiqadan ko'pga farq qiladimi?
  "has_internet": true/false, // Status bardagi Wi-Fi yoki mobil tarmoq ulanganmi?
  "error_type": "debt" | "fiscal_module" | "update" | "paper" | "none", // Ekrandagi asosiy muammo turi
  "detected_inn": "123456789" yoki null, // Ekranda STIR/INN yoki JSHSHIR raqami ko'rinib turgan bo'lsa
  "screen_text_summary": "ekrandagi xatolik yoki ko'ringan yozuvlar qisqacha"
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

        detected_inn = facts.get("detected_inn") or caption_inn

        return DeviceFacts(
            is_real_pos_device=bool(facts.get("is_real_pos_device", False)),
            is_status_bar_visible=bool(facts.get("is_status_bar_visible", False)),
            time_mismatch=bool(facts.get("time_mismatch", False)),
            has_internet=bool(facts.get("has_internet", True)),
            error_type=str(facts.get("error_type", "none")),
            detected_inn=detected_inn,
            screen_text_summary=str(facts.get("screen_text_summary", "")),
            raw_facts=facts,
            extraction_error=None
        )

    except Exception as e:
        logger.error(f"Image screen analysis extraction error: {e}")
        # Sensor uzilib qolsa xavfsiz obyekt qaytariladi
        return DeviceFacts(
            is_real_pos_device=False,
            detected_inn=caption_inn,
            extraction_error=str(e)
        )

def analyze_pos_screen(image_bytes: bytes, user_caption: str = "", mime_type: str = "image/jpeg") -> Tuple[str, Optional[int], Optional[str]]:
    """
    Backwards compatibility interfeysi:
    Sensordan faktlarni oladi va CoreEngine orqali yakuniy natijani qaytaradi.
    """
    from core.engine import core_engine, ActionType
    facts = extract_device_facts(image_bytes, user_caption=user_caption, mime_type=mime_type)
    decision = core_engine.process_device_facts(facts, chat_id=0, user_id=0)

    if decision.action == ActionType.IGNORE:
        return "", None, None

    return (
        decision.reply_text or "",
        decision.video_id,
        decision.detected_inn
    )
