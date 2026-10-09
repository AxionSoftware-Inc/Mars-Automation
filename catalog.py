import re
from typing import Optional, List, Dict, Any

def normalize(text: str) -> str:
    """
    O'zbekcha imlo xatolari, shevalar va lotin/kirill harflarni universal tozalash:
    - Har xil apostroflarni (', `, ’, ʻ) tozalash
    - Kirillcha asosiy harflarni lotinga o'tkazish
    - Tovush almashishlarini yumshatish (x/h, k/q, y/i)
    """
    if not text:
        return ""
    t = text.lower()
    
    # Kirill harflarini lotinga keltirish
    cyr_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'j', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'x', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sh', 'ъ': '',
        'ы': 'i', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya', 'ў': 'o', 'қ': 'q',
        'ғ': 'g', 'ҳ': 'x'
    }
    for c, l in cyr_map.items():
        t = t.replace(c, l)

    # Apostroflarni olib tashlash
    t = re.sub(r"[’‘`ʻʼ'\"]", "", t)
    
    # Sheva va imlo yaqinlashuvlari:
    # "ishlame" -> "ishlamay"
    t = re.sub(r"ishlam[aei]+[p]?[d]?[i]?", "ishlamay", t)
    # "karz" -> "qarz"
    t = t.replace("karz", "qarz")
    # "tulov", "tulash" -> "tolov", "tolash"
    t = t.replace("tulov", "tolov").replace("tulash", "tolash")
    
    return t

def find_video_post(text: str) -> Optional[int]:
    """
    Har qanday sheva va so'z tartibida tegishli video postni topish:
    148: Oylik to'lov (Click, video, qanday to'layman, rekvizit)
    145: Yillik to'lov
    140: Narx o'zgartirish
    141: Vaqt, soat, sana
    139: Markirovka
    138: Ma'lumotlarni yuklash
    125: Dasturni yangilash / o'lchov birligi
    137: Fiskal modul aktivlashtirish
    134: Fiskal modulni o'chirib qayta o'rnatish
    """
    t = normalize(text)

    # 1. Yillik to'lov
    if "yillik" in t:
        return 145

    # 2. Narx o'zgartirish
    if "narx" in t:
        return 140

    # 3. Markirovka
    if "markiro" in t:
        return 139

    # 4. Vaqt / soat / sana
    if any(k in t for k in ["vaqt", "soat", "sana"]):
        # "tolov vaqti" kabi gaplarda to'lovga ketib qolmasligi uchun
        if any(w in t for w in ["notogri", "togirlash", "adash", "korsat"]):
            return 141

    # 5. Dastur yangilash
    if any(k in t for k in ["yangila", "obnov", "obnav"]):
        return 125

    # 6. Analitika
    if "analitika" in t:
        return 136

    # 7. Ma'lumotlarni yuklash
    if "yukla" in t and ("malumot" in t or "tovar" in t or "baza" in t):
        return 138

    # 8. Fiskal modul
    if "aktiv" in t:
        return 137
    if "ochirib qayta" in t or "qayta ornat" in t:
        return 134

    # 9. Oylik to'lov videosi yoki qanday to'lash (shevalar bilan: "qande tolash", "qatta toliman", "clickdan")
    is_payment_guide = (
        ("tolov" in t or "tolash" in t or "pul" in t) and
        any(w in t for w in ["qanday", "qande", "qanaqa", "video", "qilaman", "qilamiz", "kere", "tashlang", "bering", "click", "klik", "qayerga", "qatta", "rekvizit"])
    ) or any(w in t for w in ["clickdan", "klikdan", "kartadan tolash", "qayerga tolayman", "rekvizit bering"])

    if is_payment_guide:
        return 148

    return None

def is_debt_inquiry(text: str) -> bool:
    """
    Foydalanuvchi apparat ishlamay qolganini aytayotgani yoki qarzini bilmoqchiligini aniqlash.
    Shevalar qamrab olingan: "ishlame qoldi", "ishlamayapdi", "ishlamayaptiku", "ochiqqan", "karzim bormikan", "kassam ochilmayapti"
    """
    t = normalize(text)
    
    trouble_roots = [
        "ishlamay", "ishlamadi", "ishlamas", "ochilmay", "ochilmadi",
        "ochib qol", "ochiq qol", "blok", "chek chiqmay", "chek bermay",
        "qarzim", "qarz bormi", "qarzdorlik", "qarz tekshir"
    ]
    return any(tr in t for tr in trouble_roots)
