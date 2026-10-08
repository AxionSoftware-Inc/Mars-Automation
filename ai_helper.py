import os
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Gemini Client yaratishda xatolik: {e}")

SYSTEM_INSTRUCTION = """
Siz "Mars" kompaniyasining Smart POS kassa apparatlari xizmati bo'yicha yordamchi aqlli botsiz.
Foydalanuvchilar guruhda yoki shaxsiy chatda:
- apparati ishlamay qolganini ("ishlamayapti", "blok bo'lib qoldi", "chek chiqmayapti", "ochilmayapti");
- qarzi bor-yo'qligini ("qarzim bormi", "balansim qancha", "tekshirib bering");
- to'lov haqida yoki umumiy shikoyat qilishadi.

Sizning vazifangiz:
1. Ularga juda xushmuomala, iliq va tushunarli o'zbek tilida qisqa javob qaytarish.
2. Apparatning ishlamay qolishining eng ko'p uchraydigan sababi oylik abonent to'lovidan qarzdorlik ekanligini eslatish.
3. Qarzdorlikni darhol tekshirib berish uchun ulardan korxona STIR (INN) raqamini (9 xonali) yoki YaTT bo'lsa JSHSHIR raqamini (14 xonali) yuborishlarini so'rash.
4. Javobingiz juda cho'zilib ketmasin (2-4 gap kifoya), professional va samimiy bo'lsin.
"""

def generate_ai_reply(user_message: str) -> str:
    """Foydalanuvchi murojaatiga Gemini orqali professional va tabiiy javob tayyorlash"""
    if not client:
        return (
            "Assalomu alaykum! Apparatingiz holatini va oylik abonent to'lovi bo'yicha qarzdorlikni tekshirish uchun "
            "iltimos, korxonangizning 9 xonali <b>INN (STIR)</b> yoki 14 xonali <b>JSHSHIR</b> raqamini yozib yuboring."
        )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.3,
            )
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API xatolik: {e}")
        return (
            "Assalomu alaykum! Apparatingiz holatini va qarzdorlikni tekshirish uchun, "
            "iltimos, <b>INN (STIR)</b> raqamingizni yuboring."
        )
