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

def generate_ai_reply(user_message: str, context_history: str = "") -> Tuple[str, Optional[int]]:
    """
    Kontekst asosida, lo'nda va qisqa javob qaytarish.
    Foydalanuvchining avvalgi suhbat tarixi hisobga olinadi.
    Natija: (javob_matni, video_message_id yoki None)
    """
    if not client:
        return (
            "Qarzdorlikni tekshirish uchun korxona <b>INN (STIR)</b> yoki <b>JSHSHIR</b> raqamini yuboring.",
            None
        )

    try:
        content_prompt = user_message.strip()
        if context_history:
            content_prompt = (
                f"Ushbu mijoz bilan avvalgi suhbat konteksti:\n{context_history}\n\n"
                f"Mijozning joriy savoli: {user_message.strip()}"
            )

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[content_prompt],
            config=types.GenerateContentConfig(
                system_instruction=COMPANY_SYSTEM_INSTRUCTION,
                temperature=0.2
            )
        )
        full_text = response.text.strip() if (response and response.text) else ""
        
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
