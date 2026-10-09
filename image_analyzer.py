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
    "⚠️ <b>Ekranning tepa qismi (soat va tarmoq qatori) ko'rinmayapti.</b>\n"
    "Aniq tashxis qo'yishimiz uchun apparat ekranining yuqori qismidagi soat va internet belgisi tushgan holda qayta rasm yuboring."
)

def analyze_pos_screen(image_bytes: bytes, user_caption: str = "", mime_type: str = "image/jpeg") -> Tuple[str, Optional[int], Optional[str]]:
    """
    Android POS apparati ekranini professional tashxis qilish:
    1. Ekran tepasidagi status bar (soat, internet/tarmoq) ko'ringanligini tekshirish.
    2. Ekrandagi soat va sanani real Toshkent vaqti bilan solishtirish.
    3. Internet / Wi-Fi / Tarmoq holatini tekshirish.
    4. Ekrandagi xatolik kodlari va xabarlarini aniqlash.
    
    Qaytaradi: (qisqa_tashxis_matni, video_id yoki None, detected_inn yoki None)
    """
    if not client:
        return (
            "Apparat ekranidagi nosozlikni aniqlash uchun korxonangizning <b>INN (STIR)</b> yoki <b>JSHSHIR</b> raqamini yuboring.",
            None,
            None
        )

    # Hozirgi real O'zbekiston (Toshkent) vaqti
    now_uzb = datetime.now(ZoneInfo("Asia/Tashkent"))
    current_time_str = now_uzb.strftime("%Y-%m-%d %H:%M")
    current_hour_min = now_uzb.strftime("%H:%M")

    prompt = f"""
Siz "Mars" servis markazining Smart POS kassa apparatlarini rasmdan diagnostika qiluvchi qat'iy texnik muhandisisiz.
Foydalanuvchi fotosurat yubordi.

HOZIRGI REAL VAQT VA SANA (Toshkent vaqti): {current_time_str}

DIQQAT! SHARTLARNI QAT'IY KETMA-KETLIKDA (IYERARXIYA BO'YICHA) TEKSHIRING:

=============================================================
0-BOSQICH (ENG AVVALO): FAQAT HAQIQIY JISMONIY APPARAT FOTOGRAFISI BO'LISHI SHART!
=============================================================
Siz FAQAT va FAQAT kamerada jonli olingan HAQIQIY JISMONIY Smart POS kassa apparatini (UzSmart, Pax, Sunmi) tekshirasiz!

AGAR QUYIDAGILARNING BIRONTASI BO'LSA — E'TIBORSIZ QOLDIRING (JAVOB BERILMAYDI):
- Reklama banneri, e'lon, afisha yoki flayer rasmi;
- Grafik rasm, vektor (vektornaya grafika), illyustratsiya, chizma yoki 3D render;
- Skrinshot (telefon ekranining skrinshoti) yoki veb-sayt sahifasi;
- Hayvonlar (it, mushuk), mashina, taom, tabiat, odamlar (selfi) yoki kassa apparatiga aloqasi bo'lmagan har qanday narsa.

Bunday holatda DARHOL VA FAQAT quyidagi kodni qaytaring, ortiqcha hech narsa yozmang:
[NOT_POS]

=============================================================
1-BOSQICH: HAQIQIY APPARAT EKRANI TEPASINING TO'LIQLIGI (STATUS BAR)
=============================================================
(Faqat haqiqiy apparat fotosurati bo'lsagina):
Ekranning eng yuqori qismidagi Android status bar (soat raqamlari yoki Wi-Fi / tarmoq / SIM-karta belgisi) rasmda tushganmi?
- Agar rasm tepasi kesilgan bo'lsa;
- Agar soat va tarmoq qatori ko'rinmay qolgan bo'lsa;
- Agar rasm juda xira yoki ekranning faqat bir burchagi/o'rtasi olingan bo'lsa:

DARHOL TO'XTANG! HECH QANDAY TASHXIS QO'YMANG, INN SO'RAMANG VA VIDEO QO'YMANG!
Faqat va faqat quyidagi matnni bering:
"⚠️ <b>Ekranning tepa qismi (soat va tarmoq qatori) ko'rinmayapti.</b>\nAniq tashxis qo'yishimiz uchun apparat ekranining yuqori qismidagi soat va internet belgisi tushgan holda qayta rasm yuboring."

=============================================================
2-BOSQICH: FAQAT 1-BOSQICH TO'G'RI BO'LGANDAGINA (SOAT QATORI ANIQ KO'RINSA):
=============================================================
Ketma-ket quyidagilarni tekshiring:

A) SOAT VA SANA TEKSHIRUVI:
   - Ekrandagi soatni o'qing. Hozirgi real Toshkent vaqti: {current_hour_min}.
   - Agar bir necha daqiqa (1-10 min) farq bo'lsa — bu normal holat (xato emas).
   - Agar apparatdagi soat bir necha soatga xato bo'lsa yoki sana noto'g'ri bo'lsa:
     "⚠️ Apparatdagi soat/vaqt noto'g'ri. Kassa to'g'ri ishlashi uchun sana va vaqtni to'g'rilash kerak." deb yozing va oxiriga [VIDEO:141] qo'ying.
     (Bu holda INN so'rash kerak emas!)

B) INTERNET VA TARMOQ TEKSHIRUVI:
   - Status bardagi Wi-Fi belgisi yoki SIM karta tarmog'ini tekshiring.
   - Agar apparat internetga ulanmagan bo'lsa:
     "⚠️ Apparat internetga ulanmagan. Iltimos, Wi-Fi yoki SIM-karta internetini tekshiring." deb ayting.
     (Bu holda INN so'rash kerak emas!)

C) EKRANDAGI XATOLIK KODI, BLOK YOKI QARZDORLIK:
   - Agar soat to'g'ri, internet ulangan bo'lsa, endi ekrandagi yozuv va holatni o'qing.
   - Agar ekranda korxona STIR (INN) yoki JSHSHIR raqami ko'rinib turgan bo'lsa, javob oxiriga [INN:123456789] shaklida qo'shing.
   - Agar apparat bloklangan bo'lsa, to'xtagan bo'lsa, to'lov yoki abonent qarzdorligi bo'lishi mumkinligi ko'rinsa:
     "⚠️ Apparat to'xtagan yoki abonent to'lovidan qarzdorlik bo'lishi mumkin. Bazadan tekshirishimiz uchun korxonangizning <b>INN (STIR)</b> yoki <b>JSHSHIR</b> raqamini yuboring." deb so'rang.
   - Boshqa texnik xatolik bo'lsa, uning sababi va yechimini 1-2 gapda lo'nda tushuntiring.

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

        full_text = response.text.strip() if (response and response.text) else ""

        # 0-BOSQICH FILTRI: Agar rasm kassa apparatiga tegishli bo'lmasa -> E'tiborsiz qoldiriladi
        if "[NOT_POS]" in full_text or full_text == "[NOT_POS]":
            return "", None, None

        # 1-BOSQICH FILTRI (Majburiy tepa qismi tekshiruvi):
        lower_resp = full_text.lower()
        if any(w in lower_resp for w in [
            "tepa qismi", "tepasi ko'rinmayapti", "soat va tarmoq qatori", "qayta rasm yuboring",
            "kesilib", "kesilgan", "ko'rinmayapti", "korinmayapti"
        ]) and any(w in lower_resp for w in ["ekran", "soat", "tarmoq", "tepa"]):
            return INCOMPLETE_SCREEN_REPLY, None, None

        # [INN:xxx] tegini ajratish
        detected_inn = None
        inn_match = re.search(r"\[INN:(\d{9}|\d{14})\]", full_text)
        if inn_match:
            detected_inn = inn_match.group(1)
            full_text = re.sub(r"\[INN:\d+\]", "", full_text).strip()

        # [VIDEO:xxx] tegini ajratish
        video_id = None
        match = re.search(r"\[VIDEO:(\d+)\]", full_text)
        if match:
            video_id = int(match.group(1))
            full_text = re.sub(r"\[VIDEO:\d+\]", "", full_text).strip()

        return full_text, video_id, detected_inn

    except Exception as e:
        logger.error(f"Image screen analysis error: {e}")
        return "", None, None
