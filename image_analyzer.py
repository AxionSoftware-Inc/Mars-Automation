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

# KELAJAKDA YANGI XATOLIKLARNI OSON QO'SHISH UCHUN XATOLIKLAR XARITASI
ERROR_RULES: Dict[str, Dict[str, Any]] = {
    "TIME_MISMATCH": {
        "title": "Sana va vaqt noto'g'ri",
        "video_id": 141,  # Sana va vaqtni to'g'irlash videosi
        "action": "Kassa sozlamalaridan sana va vaqtni to'g'rilash"
    },
    "NO_INTERNET": {
        "title": "Internet yoki tarmoq aloqasi yo'q",
        "video_id": None,
        "action": "Wi-Fi tarmog'iga ulanish yoki SIM karta balansini tekshirish"
    },
    "FISCAL_MODULE": {
        "title": "Fiskal modul xatosi",
        "video_id": 137,  # Fiskal modul aktivlashtirish
        "action": "Fiskal modul ilovasini tekshirish yoki aktivlashtirish"
    },
    "BLOCKED": {
        "title": "Apparat bloklangan yoki oylik to'lov muddati o'tgan",
        "video_id": 148,  # Oylik to'lov videosi
        "action": "Korxona INN/JSHSHIR raqamini tekshirish"
    },
    "TAMPER_ALARM": {
        "title": "Xavfsizlik bloki (Tamper / Attack)",
        "video_id": None,
        "action": "Apparatni servis markaziga olib kelish zarur"
    }
}

def analyze_pos_screen(image_bytes: bytes, user_caption: str = "", mime_type: str = "image/jpeg") -> Tuple[str, Optional[int]]:
    """
    Android POS apparati ekranini professional tashxis qilish:
    1. Ekrandagi soat va sanani real Toshkent vaqti bilan solishtirish.
    2. Internet / Wi-Fi / Tarmoq holatini tekshirish.
    3. Ekrandagi xatolik kodlari va xabarlarini aniqlash.
    
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
Siz Android asosidagi Smart POS (UzSmart, Pax, Sunmi, Verifone) kassa apparatlari bo'yicha texnik diagnostika muhandisisiz.
Foydalanuvchi sizga apparat ekranining fotosuratini yubordi.

HOZIRGI REAL VAQT VA SANA (Toshkent vaqti): {current_time_str}

VAZIFANGIZ RASMNI QUYIDAGI BOSQICHLARDA TEKSHIRISH:
0. APPARAT VA EKRANNING BUTUNLIGI (TEPA, PAST, YON TOMONLARI KESILMAGANLIGI)NI QAT'IY TEKSHIRISH:
   - DIQQAT! Diagnostika qilish uchun kassa apparatining o'zi va uning BUTUN EKRANI to'liq (tepasi, pasti va ikki yoni kesilmagan holda) ko'rinishi SHART!
   - Agar quyidagi holatlardan birontasi bo'lsa:
     * Rasm TEPASI kesilgan bo'lsa (yuqori paneldagi soat, Wi-Fi, internet yoki tarmoq belgisi to'liq ko'rinmayotgan bo'lsa);
     * Rasm PASTI kesilgan bo'lsa (pastki menyu yoki navigatsiya qismlari ko'rinmayotgan bo'lsa);
     * Rasm YON TOMONLARI kesilgan yoki faqat ekranning o'rtasi/burchagi yaqinlashtirib (zoom) olingan bo'lsa;
     * Apparatning o'zi to'liq kadrga sig'magan, yoki ekran xira/qorong'u bo'lsa:
     
     Boshqa HECH QANDAY tahlil, sabab yoki taxmin yozmang! DARHOL quyidagicha javob bering va to'xtating:
     "⚠️ <b>Kassa apparati to'liq ko'rinmayapti.</b>\nApparatning tepasi, pasti yoki yon tomonlari kesilib qolgan. Aniq tashxis qo'yishimiz uchun ekrandagi <b>soat va internet/Wi-Fi belgilari</b>, hamda pastki qismlari ham to'liq ko'rinishi shart.\n\nIltimos, <b>kassa apparatini va uning butun ekranini to'liq (tepa, past va yonlari kesilmagan holda)</b> rasmga olib qayta yuboring."

1. SOAT VA VAQT TEKSHIRUVI:
   - Ekran tepasidagi (Android status bar) yoki kassa ilovasidagi soat/sanani toping.
   - Hozirgi real vaqt: {current_hour_min}.
   - Agar apparatdagi soat real vaqtdan bir necha daqiqa (1-10 min) farq qilsa — bu to'g'ri (xato emas).
   - Agar apparatdagi soat bir necha soatga orqada/oldinda bo'lsa yoki sana umuman boshqa bo'lsa — bu ASOSIY XATOLIK! "⚠️ Apparatdagi soat/vaqt noto'g'ri. Kassa to'g'ri ishlashi uchun sana va vaqtni to'g'rilash kerak." deb yozing va oxiriga [VIDEO:141] belgisini qo'ying.

2. INTERNET VA TARMOQ TEKSHIRUVI:
   - Wi-Fi belgisi, SIM karta tarmoq darajasi yoki "Aloqa yo'q / Tarmoq xatosi / Нет сети / No connection" yozuvini tekshiring.
   - Agar internet yo'q bo'lsa: "⚠️ Apparat internetga ulanmagan. Iltimos, Wi-Fi yoki SIM-karta internetini tekshiring." deb ayting.

3. EKRANDAGI XATOLIK KODI YOKI BLOKLANISH:
   - Ekrandagi xatolik xabarini o'qing.
   - Agar to'lov yoki bloklanganlik ko'rinsa: qarzdorlikni tekshirish uchun korxona INN yoki JSHSHIR raqamini so'rang.

TALABLAR:
- Javob maksimal 2-3 ta qisqa, lo'nda va tushunarli gapdan iborat bo'lsin.
- Agar sana-vaqt xato bo'lsa, oxiriga yangi qatordan [VIDEO:141] qo'shing.
- Agar oylik to'lov/blok bo'lsa, oxiriga [VIDEO:148] qo'shing.
- Foydalanuvchi izohi: "{user_caption}"
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

        return full_text, video_id

    except Exception as e:
        logger.error(f"Image screen analysis error: {e}")
        return (
            "Apparat ekranidagi xatolikni aniqlash uchun korxonangizning <b>INN</b> yoki <b>JSHSHIR</b> raqamini yuboring.",
            None
        )
