import os
import json
import logging
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash"

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Gemini Client yaratishda xatolik: {e}")

IMAGE_ERROR_ANALYSIS_PROMPT = """
Siz Smart POS kassa apparatlari (UzSmart, Pax, Verifone, Sunmi va boshqalar) bo'yicha yuqori malakali texnik muhandis va yordamchisiz.
Foydalanuvchi sizga apparat ekrani, chek yoki kassa terminalining rasmini yubordi.

Vazifangiz rasmni diqqat bilan tahlil qilish:
1. Ekrandagi xatolik kodini (Error code / Код ошибки) yoki xabarni aniqlang (masalan: "Aloqa yo'q", "Fiskal xotira to'ldi", "Bloklangan", "Tarmoq xatosi", "PIN kiritilmadi", "Tamper error", "Sim karta xatosi").
2. Xatolik sababini o'zbek tilida juda aniq va sodda tushuntiring.
3. Muammoni bartaraf qilish bo'yicha amaliy qadamlarni bering (masalan: apparatni o'chirib-yoqish, internet/Wi-Fi ni tekshirish, abonent to'lovini tekshirish, texnik xizmatga olib borish).
4. Agar apparat bloklanganligi yoki to'lov bilan bog'liq bo'lsa, qarzni tekshirish uchun korxona INN yoki JSHSHIR raqamini yuborishni eslatib o'ting.
5. Agar rasmda kassa apparatiga aloqador narsa ko'rinmasa, xushmuomala qilib apparat ekranidagi xatolikni aniqroq rasmga olib yuborishni so'rang.
"""

def analyze_pos_image(image_bytes: bytes, user_caption: str = "", mime_type: str = "image/jpeg") -> str:
    """Kelajakdagi kengaytirilgan texnik nosozlik va xatolik kodlari bo'yicha rasm tahlili"""
    if not client:
        return (
            "Rasm qabul qilindi. Apparatdagi nosozlikni aniqlash va qarz holatini tekshirish uchun, "
            "iltimos, korxonangizning 9 xonali <b>INN (STIR)</b> yoki 14 xonali <b>JSHSHIR</b> raqamini yuboring."
        )

    try:
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            user_caption.strip() if user_caption else "Ushbu apparat ekranidagi xatolik va holatni aniqlab bering."
        ]

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=IMAGE_ERROR_ANALYSIS_PROMPT,
                temperature=0.2,
            )
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return (
            "Assalomu alaykum! Apparatingiz holatini tekshirish uchun, iltimos, "
            "korxonangizning <b>INN (STIR)</b> raqamini yuboring."
        )

def generate_ai_reply(user_message: str) -> str:
    """Umumiy savollarga tabiiy o'zbekcha javob (noo'rin INN so'ramasdan)"""
    if not client:
        return "Assalomu alaykum! Sizga qanday yordam bera olaman?"

    prompt = (
        "Siz Mars kompaniyasining Smart POS kassa xizmati bo'yicha yordamchi botsiz. "
        "Foydalanuvchining quyidagi savoliga muloyim, qisqa va aniq javob bering. "
        "Hech qanday asossiz joyda INN so'ramang. Savol: " + user_message
    )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3)
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"AI reply error: {e}")
        return "Assalomu alaykum! Savolingiz bo'yicha yordam berishga tayyorman."
