import os
import logging
from typing import Optional
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

SYSTEM_INSTRUCTION = """
Siz "Mars" kompaniyasining Smart POS kassa apparatlari bo'yicha yordamchi aqlli botsiz.
Foydalanuvchi turli savollar bersa:
1. Agar apparat nosozligi, ishlamay qolishi yoki qarz so'ralsa: xushmuomala tushuntirib, qarzdorlikni tekshirish uchun korxona INN (9 xonali) yoki JSHSHIR (14 xonali) raqamini so'rang.
2. Agar umumiy boshqa savollar bo'lsa (masalan "salom", "qayerdasizlar", "ish vaqtingiz qachon"): o'zbek tilida muloyim va aniq javob bering, keraksiz joyda INN SO'RAMANG.
"""

def generate_ai_reply(user_message: str, image_bytes: Optional[bytes] = None, mime_type: str = "image/jpeg") -> str:
    """Foydalanuvchi savoliga mazmuniga qarab tabiiy javob qaytarish"""
    if not client:
        return "Assalomu alaykum! Sizga qanday yordam bera olaman?"

    try:
        contents = []
        if image_bytes:
            contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
        contents.append(user_message.strip() if user_message else "Yordam bering")

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.3,
            )
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API xatolik: {e}")
        return "Assalomu alaykum! Savolingiz bo'yicha yordam berishga tayyorman."
