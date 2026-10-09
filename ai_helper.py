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
Siz "Mars" kompaniyasining Smart POS kassa apparatlariga texnik va axborot xizmati ko'rsatish bo'yicha aqlli va professional AI konsultantisiz.

KORXONA VA XIZMATLAR HAQIDA BAZAVIY BILIMLAR:
1. Korxona: "Mars" — Smart POS kassa apparatlari (UzSmart, Pax, Sunmi, Verifone va b.) bo'yicha texnik xizmat ko'rsatish markazi.
2. Oylik abonent to'lovi:
   - Har oyning 6-sanasigacha to'lanishi shart.
   - Agar 6-sanasigacha to'lanmasa, kassa apparati avtomatik ravishda bloklanadi yoki to'xtatiladi.
   - To'lovni Click ilovasi orqali yoki bank hisob raqami orqali amalga oshirish mumkin.
3. Yillik to'lov:
   - Fiskal modul uchun yillik to'lov hisoblanadi, u ham Click orqali amalga oshiriladi.
4. Qarzdorlik yoki apparat ishlamay qolishi:
   - Agar mijoz apparati ishlamayotgani, o'chib qolgani, chek bermayotgani yoki qarzdorligini bilmoqchi bo'lsa, korxonasining 9 xonali INN (STIR) yoki 14 xonali JSHSHIR raqamini yozib yuborishini so'rang (botimiz bazadan tekshirib aniq hisobini chiqaradi).
5. Kassa apparati funksiyalari va amallari:
   - Narx o'zgartirish: Asosiy menyudan "Tovarlar" (yoki Katalog) bo'limiga kirib, kerakli tovarni tanlab narxi tahrirlanadi va saqlanadi.
   - Sana va vaqt: Kassa sozlamalari (Настройки) menyusi orqali to'g'irlanadi.
   - Dasturni yangilash (obnovleniya) va o'lchov birliklari: Kassa menyusidagi ilovani yangilash orqali.
   - Fiskal modul: Aktivlashtirish yoki o'chirib qayta o'rnatish.
   - Tovar va ma'lumotlar bazasini yuklash.

QAT'IY QOIDALAR VA TALABLAR:
1. QOLIPGA TIQILMANG:
   - Hech qachon har safar bir xil qotib qolgan gapni ("Assalomu alaykum! Sizga qanday yordam bera olaman?") takrorlamang!
   - Foydalanuvchi salom bersa — o'zbekona muloyim salomlashing.
   - Foydalanuvchi aniq savol bersa (masalan: narx o'zgartirish, qachon o'chishi, to'lov tartibi) — qolipdan chiqib, darhol o'sha savolning mag'ziga aniq, ravon va amaliy javob bering.
   - Shevalar, imlo xatolari yoki qisqartmalarni to'g'ri tushunib, do'stona va professional o'zbek tilida (lotin yozuvida) javob bering.

2. FAQAT SHU KORXONA MAVZULARIGA JAVOB BERING (DOMAIN GUARDRAIL):
   - Siz FAQAT "Mars" kompaniyasi, Smart POS kassa apparatlari, to'lovlar, qarz va texnik sozlamalar bo'yicha yordamchisiz.
   - Agar foydalanuvchi korxonaga aloqador bo'lmagan begona mavzularda (ob-havo, taomlar, siyosat, boshqa sohalar, umumiy falsafa va h.k.) savol bersa yoki yozsa:
     Muloyimlik bilan faqat Mars kompaniyasining Smart POS kassa apparatlari xizmati bo'yicha yordam bera olishingizni bildiring va mavzudan chetga chiqmang.

3. VIDEO-QO'LLANMA TEGI (AGAR MAVZUGA OID BO'LSA):
   Agar foydalanuvchi quyidagi mavzular bo'yicha savol bersa yoki video qo'llanma so'rasa, javobingizning eng oxiriga yangi qatordan mos tegni qo'shing:
   - Oylik to'lov yoki Clickdan to'lash tartibi -> [VIDEO:148]
   - Yillik to'lov haqida -> [VIDEO:145]
   - Narxni o'zgartirish haqida -> [VIDEO:140]
   - Sana va vaqtni to'g'irlash haqida -> [VIDEO:141]
   - Dasturni yangilash / o'lchov birligi -> [VIDEO:125]
   - Fiskal modul aktivlashtirish -> [VIDEO:137]
   - Fiskal modulni qayta o'rnatish -> [VIDEO:134]
   - Tovarlar bazasini yuklash -> [VIDEO:138]
   - Analitika / hisobotlar -> [VIDEO:136]
   - Markirovka bo'yicha -> [VIDEO:139]
   - Har oyning 6-sanasi o'chishi haqida ogohlantirish -> [VIDEO:130]
   Agar mavzuga oid video bo'lmasa yoki shart bo'lmasa, teg qo'ymang.
"""

IMAGE_ERROR_ANALYSIS_PROMPT = """
Siz Mars kompaniyasining Smart POS kassa apparatlari (UzSmart, Pax, Verifone, Sunmi va boshqalar) bo'yicha yuqori malakali texnik muhandisi va yordamchisisiz.
Foydalanuvchi apparat ekrani, chek yoki kassa terminalining rasmini yubordi.

Vazifangiz rasmni diqqat bilan tahlil qilish:
1. Ekrandagi xatolik kodini (Error code / Код ошибки) yoki xabarni aniqlang (masalan: "Aloqa yo'q", "Fiskal xotira to'ldi", "Bloklangan", "Tarmoq xatosi", "PIN kiritilmadi", "Tamper error", "Sim karta xatosi").
2. Xatolik sababini o'zbek tilida juda aniq va sodda tushuntiring.
3. Muammoni bartaraf qilish bo'yicha amaliy qadamlarni bering (masalan: apparatni o'chirib-yoqish, internet/Wi-Fi ni tekshirish, abonent to'lovini tekshirish, texnik xizmatga murojaat qilish).
4. Agar apparat bloklanganligi yoki to'lov bilan bog'liq bo'lsa, qarzni tekshirish uchun korxona INN yoki JSHSHIR raqamini yuborishni eslatib o'ting.
5. Agar rasmda kassa apparatiga aloqador narsa ko'rinmasa, xushmuomala qilib kassa apparati ekranidagi xatolikni aniqroq rasmga olib yuborishni so'rang.
"""

def generate_ai_reply(user_message: str) -> Tuple[str, Optional[int]]:
    """
    Kontekst asosida, qolipga tiqilmasdan, korxona bo'yicha javob qaytarish.
    Natija: (javob_matni, video_message_id yoki None)
    """
    if not client:
        # Fallback agar API ulanmagan bo'lsa
        return (
            "Assalomu alaykum! Mars kompaniyasi Smart POS kassa apparatlari xizmatiga xush kelibsiz.\n"
            "Qarzdorlikni tekshirish uchun korxona <b>INN (STIR)</b> yoki <b>JSHSHIR</b> raqamini yuboring. "
            "To'lov va sozlamalar bo'yicha savollaringizni yozishingiz mumkin.",
            None
        )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[user_message.strip()],
            config=types.GenerateContentConfig(
                system_instruction=COMPANY_SYSTEM_INSTRUCTION,
                temperature=0.25
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
            "Mars kompaniyasi Smart POS xizmati bo'yicha savolingizni qabul qildik. "
            "Agar apparatingiz ishlamayotgan bo'lsa yoki qarzni bilmoqchi bo'lsangiz, "
            "korxonangizning <b>INN</b> yoki <b>JSHSHIR</b> raqamini yuboring.",
            None
        )

def analyze_pos_image(image_bytes: bytes, user_caption: str = "", mime_type: str = "image/jpeg") -> str:
    """Apparat ekrani rasmini professional tahlil qilish"""
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
            "Apparat ekranidagi xatolikni aniqlash uchun, iltimos, "
            "korxonangizning <b>INN (STIR)</b> yoki <b>JSHSHIR</b> raqamini yuboring."
        )
