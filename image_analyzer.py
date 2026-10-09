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

INCOMPLETE_SCREEN_REPLY = (
    "⚠️ <b>Ekranning tepa qismi (soat va tarmoq qatori) ko'rinmayapti.</b>\n"
    "Aniq tashxis qo'yishimiz uchun apparat ekranining yuqori qismidagi soat va internet belgisi tushgan holda qayta rasm yuboring."
)

from error_manager import error_manager

def analyze_pos_screen(image_bytes: bytes, user_caption: str = "", mime_type: str = "image/jpeg") -> Tuple[str, Optional[int], Optional[str]]:
    """
    Android POS apparati ekranini professional tashxis qilish:
    1. Ekran tepasidagi status bar (soat, internet/tarmoq) ko'ringanligini tekshirish.
    2. Ekrandagi soat va sanani real Toshkent vaqti bilan solishtirish.
    3. Internet / Wi-Fi / Tarmoq holatini tekshirish.
    4. Ekrandagi xatolik kodlari va xabarlarini aniqlash.
    5. XULOSA VA JAVOB ErrorManager QOIDALARI ASOSIDA NAZORAT QILINADI.
    
    Qaytaradi: (qisqa_tashxis_matni, video_id yoki None, detected_inn yoki None)
    """

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
  "is_real_pos_device": true/false, // Rasmda Smart POS kassa apparati, uning ekrani yoki kassa ilovasi ko'ringanmi? (Faqat apparatga aloqasiz hayvon, tabiat, taom, selfi bo'lsa false)
  "is_status_bar_visible": true/false, // Ekran tepasidagi soat yoki tarmoq/internet status bar qatori tushganmi?
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
            # Fallback regex if markdown wrappers
            match = re.search(r"\{.*\}", raw_json, re.DOTALL)
            facts = json.loads(match.group(0)) if match else {}

        detected_inn = facts.get("detected_inn")

        # 0-BOSQICH (GUARDRAIL): Haqiqiy kassa apparati/ekrani emasmi?
        if not facts.get("is_real_pos_device", False) and not detected_inn:
            return "", None, None

        # 1-BOSQICH: BIZNING NAZORATIMIZDAGI XATOLIKLAR MODULI (ErrorManager) ORQALI TASHXIS
        matched_rule = error_manager.match_error(facts)
        if matched_rule:
            return (
                matched_rule.get("response_text", ""),
                matched_rule.get("video_id"),
                detected_inn
            )

        # 2-BOSQICH (STATUS BAR FILTRI): Agar maxsus xatolik bo'lmasa va status bar ko'rinmasa
        if not facts.get("is_status_bar_visible", False) and not detected_inn:
            return INCOMPLETE_SCREEN_REPLY, None, None

        # Agar maxsus qoida topilmasa, lo'nda umumiy xulosa
        summary = facts.get("screen_text_summary")
        if summary and summary.lower() != "none":
            return f"ℹ️ <b>Ekrandagi holat:</b> {summary}\nNosozlik davom etsa, korxona INN raqamini yuboring.", None, detected_inn

        return "", None, detected_inn

    except Exception as e:
        logger.error(f"Image screen analysis error: {e}")
        return "", None, None
