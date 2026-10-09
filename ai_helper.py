import os
import re
import logging
from typing import Optional, Tuple
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.5-flash-lite"

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Gemini Client yaratishda xatolik: {e}")

COMPANY_SYSTEM_INSTRUCTION = """
Siz "Mars" kompaniyasining Smart POS kassa apparatlariga texnik va servis xizmati ko'rsatish bo'yicha AI yordamchisisiz.

KORXONA VA XIZMATLAR:
- "Mars" — Smart POS kassa apparatlari (UzSmart, Pax, Sunmi) servis markazi.
- Oylik to'lov: Har oyning 6-sanasigacha to'lanishi shart, aks holda apparat bloklanadi. To'lov Click yoki bank orqali.
- Yillik to'lov: Fiskal modul to'lovi.
- Qarzdorlik yoki apparat ishlamay qolganda (ishlamayapti, o'chib qoldi, blok, chek chiqmayapti):
  HECH QANDAY video tegi qo'ymang! Faqat: "Tekshirish uchun korxonangizning INN (9 xonali) yoki JSHSHIR (14 xonali) raqamini yuboring." deb lo'nda so'rang.

QAT'IY TALABLAR:
1. JUDA QISQA VA LO'NDA YOZING:
   - Ortiqcha gap va uzun doston yozish qat'iyan taqiqlanadi!
   - Javob maksimal 1-2 ta qisqa gapdan iborat bo'lsin.
   - Salom bersa — faqat 1 ta qisqa salom bilan cheklaning.
   - Savol bersa — darhol o'sha savolning qisqa javobini bering.

2. FAQAT KORXONA MAVZUSI (GUARDRAIL):
   - Begona mavzularda (ob-havo, taomlar, siyosat va h.k.) so'ralsa: faqat 1 ta qisqa gap ayting:
     "Kechirasiz, men faqat Mars kassa apparatlari xizmati bo'yicha yordam bera olaman."

3. VIDEO TEGI (FAQAT QO'LLANMA SO'RALGANDA):
   Faqat foydalanuvchi video yoki sozlash tartibini so'rasa, javob oxiriga tegni qo'shing:
   - Oylik to'lov / Click orqali to'lash tartibi -> [VIDEO:148]
   - Yillik to'lov videosi -> [VIDEO:145]
   - Narxni o'zgartirish -> [VIDEO:140]
   - Sana va vaqtni to'g'irlash -> [VIDEO:141]
   - Dasturni yangilash / o'lchov birligi -> [VIDEO:125]
   - Fiskal modul aktivlashtirish -> [VIDEO:137]
   - Fiskal modulni qayta o'rnatish -> [VIDEO:134]
   - Tovarlar bazasini yuklash -> [VIDEO:138]
   - Analitika / hisobotlar -> [VIDEO:136]
   - Markirovka -> [VIDEO:139]
   - Nechanchi sana o'chadi / qachon o'chadi deb so'ralsa -> [VIDEO:130]
"""

IMAGE_ERROR_ANALYSIS_PROMPT = """
Siz Mars kompaniyasining Smart POS kassa apparatlari bo'yicha texnik muhandisisiz.
Foydalanuvchi kassa apparati ekranining rasmini yubordi.

Talablar:
1. Ekrandagi xatolik kodi yoki nosozlikni aniqlang.
2. Sababi va yechimini 2-3 ta qisqa, tushunarli gapda bering.
3. Agar to'lov yoki bloklanganlik bo'lsa, INN yoki JSHSHIR raqamini so'rang.
4. Juda lo'nda va qisqa yozing.
"""

def generate_ai_reply(user_message: str) -> Tuple[str, Optional[int]]:
    """
    Kontekst asosida, lo'nda va qisqa javob qaytarish.
    Natija: (javob_matni, video_message_id yoki None)
    """
    if not client:
        return (
            "Qarzdorlikni tekshirish uchun korxona <b>INN (STIR)</b> yoki <b>JSHSHIR</b> raqamini yuboring.",
            None
        )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[user_message.strip()],
            config=types.GenerateContentConfig(
                system_instruction=COMPANY_SYSTEM_INSTRUCTION,
                temperature=0.2
            )
        )
        full_text = response.text.strip()
        
        # [VIDEO:xxx] tegini qidirish va ajratish
        video_id = None
        match = re.search(r"\[VIDEO:(\d+)\]", full_text)
        if match:
            video_id = int(match.group(1))
            full_text = re.sub(r"\[VIDEO:\d+\]", "", full_text).strip()

        return full_text, video_id

    except Exception as e:
        logger.error(f"AI reply xatoligi: {e}")
        return (
            "Savolingiz bo'yicha qarzni tekshirish uchun korxona <b>INN</b> yoki <b>JSHSHIR</b> raqamini yuboring.",
            None
        )

def analyze_pos_image(image_bytes: bytes, user_caption: str = "", mime_type: str = "image/jpeg") -> str:
    """Apparat ekrani rasmini qisqa va lo'nda tahlil qilish"""
    if not client:
        return (
            "Apparatdagi nosozlikni aniqlash uchun, iltimos, "
            "korxonangizning <b>INN (STIR)</b> yoki <b>JSHSHIR</b> raqamini yuboring."
        )

    try:
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            user_caption.strip() if user_caption else "Ushbu apparat ekranidagi xatolikni aniqlab bering."
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
            "Apparat ekranidagi xatolikni aniqlash uchun korxonangizning <b>INN</b> yoki <b>JSHSHIR</b> raqamini yuboring."
        )
