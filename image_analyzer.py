import os
import re
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, Dict, Any
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
        logger.error(f"ImageAnalyzer: Gemini client xatoligi: {e}")

INCOMPLETE_SCREEN_REPLY = (
    "⚠️ <b>Kassa ekrani to'liq ko'rinmayapti.</b>\n"
    "Ekranning tepasi (soat/internet) yoki chetlari kesilgan. "
    "Iltimos, apparat ekranini va chetini to'liq ko'rinadigan qilib qayta rasm yuboring."
)

def analyze_pos_screen(image_bytes: bytes, user_caption: str = "", mime_type: str = "image/jpeg") -> Tuple[str, Optional[int]]:
    """
    Android POS apparati ekranini professional tashxis qilish:
    1. Ekran to'liqligi (ekranning 4 burchagi, tepa status bar va chetki qismlari) tekshiruvi.
    2. Ekrandagi soat va sanani real Toshkent vaqti bilan solishtirish.
    3. Internet / Wi-Fi / Tarmoq holatini tekshirish.
    4. Ekrandagi xatolik kodlari va xabarlarini aniqlash.
    
    Qaytaradi: (qisqa_tashxis_matni, video_id yoki None)
    """
    if not client:
        return (
            "Apparat ekranidagi nosozlikni aniqlash uchun korxonangizning <b>INN (STIR)</b> yoki <b>JSHSHIR</b> raqamini yuboring.",
            None
        )

    # Hozirgi real O'zbekiston (Toshkent) vaqti
    now_uzb = datetime.now(ZoneInfo("Asia/Tashkent"))
    current_time_str = now_uzb.strftime("%Y-%m-%d %H:%M")
    current_hour_min = now_uzb.strftime("%H:%M")

    prompt = f"""
Siz Smart POS kassa apparatlarini rasmdan diagnostika qiluvchi qat'iy texnik mutaxassissiz.
Foydalanuvchi sizga apparatning fotosuratini yubordi.

HOZIRGI REAL VAQT VA SANA (Toshkent vaqti): {current_time_str}

1-BOSQICH (ENG MUHIM): EKRANNING TO'LIQLIGINI TEKSHIRISH
MUHIM QOIDA: Butun apparat korpusi to'liq tushishi SHART EMAS! 
Lekin EKRANNING O'ZI 100% TO'LIQ (barcha 4 burchagi) VA EKRANDAN TASHQARI KORPUSNING BIROZ QISMI (romka/cheti) rasmda aniq ko'rinishi shart!

Agar quyidagi holatlardan BIRONTASI bo'lsa:
- Ekran TEPASI kesilgan bo'lsa (Android status bar: soat yoki Wi-Fi/internet/SIM belgisi ko'rinmay qolgan bo'lsa);
- Ekran PASTI kesilgan bo'lsa (pastki menyu yoki navigatsiya qismlari tushmagan bo'lsa);
- Ekran YON TOMONLARI kesilgan bo'lsa yoki faqat ekranning o'rtasi/burchagi yaqinlashtirib (zoom) olingan bo'lsa;
- Rasm xira, qorong'u yoki ekran chetlari ko'rinmay qolgan bo'lsa:

Boshqa HECH QANDAY tashxis, sabab, maslahat yoki taxmin yozish MUMKIN EMAS!
Javobni uzun qilib yozmang, qisqa qilib DARHOL faqat quyidagi matnni qaytaring, HECH QANDAY video tegi qo'ymang:
"⚠️ <b>Kassa ekrani to'liq ko'rinmayapti.</b>\nEkranning tepasi (soat/internet) yoki chetlari kesilgan. Iltimos, apparat ekranini va chetini to'liq ko'rinadigan qilib qayta rasm yuboring."

2-BOSQICH: FAQAT BUTUN EKRAN VA UNING ROMKASI TO'LIQ KO'RINGAN HOLATDAGINA TASHXIS QO'YING:
1. SOAT VA VAQT TEKSHIRUVI:
   - Ekran tepasidagi (Android status bar) soatni o'qing. Hozirgi real Toshkent vaqti: {current_hour_min}.
   - Agar bir necha daqiqa (1-10 min) farq bo'lsa — bu to'g'ri (xato emas).
   - Agar apparatdagi soat bir necha soatga xato bo'lsa yoki sana noto'g'ri bo'lsa — "⚠️ Apparatdagi soat/vaqt noto'g'ri. Kassa to'g'ri ishlashi uchun sana va vaqtni to'g'rilash kerak." deb yozing va oxiriga [VIDEO:141] qo'ying.
2. INTERNET VA TARMOQ TEKSHIRUVI:
   - Wi-Fi belgisi yoki SIM karta tarmog'ini tekshiring.
   - Agar internet yo'q bo'lsa — "⚠️ Apparat internetga ulanmagan. Iltimos, Wi-Fi yoki SIM-karta internetini tekshiring." deb ayting.
3. EKRANDAGI XATOLIK KODI YOKI BLOKLANISH:
   - Ekrandagi xatolik xabarini o'qing.
   - Sababi va yechimini qisqa va aniq (1-2 gapda) tushuntiring.
   - Agar blok yoki qarz bo'lsa, korxona INN yoki JSHSHIR raqamini so'rang.

Foydalanuvchi izohi: "{user_caption}"
"""

    try:
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt
        ]

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(temperature=0.1)
        )

        full_text = response.text.strip()
        
        # [VIDEO:xxx] tegini ajratish
        video_id = None
        match = re.search(r"\[VIDEO:(\d+)\]", full_text)
        if match:
            video_id = int(match.group(1))
            full_text = re.sub(r"\[VIDEO:\d+\]", "", full_text).strip()

        # QAT'IY XAVFSIZLIK FILTRI:
        # Agar javobda ekran to'liq emasligi haqida aytilgan bo'lsa -> HECH QANDAY VIDEO BIRIKTIRILMAYDI!
        lower_resp = full_text.lower()
        if any(w in lower_resp for w in [
            "to'liq ko'rinmayapti", "toliq korinmayapti", "to'liq tushmagan", "toliq tushmagan",
            "kesilib", "kesilgan", "qayta rasm", "butun ekranini to'liq", "butun ekrani"
        ]):
            video_id = None
            full_text = INCOMPLETE_SCREEN_REPLY

        return full_text, video_id

    except Exception as e:
        logger.error(f"Image screen analysis error: {e}")
        return (
            "Apparat ekranidagi xatolikni aniqlash uchun korxonangizning <b>INN</b> yoki <b>JSHSHIR</b> raqamini yuboring.",
            None
        )
