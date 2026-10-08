import re
from typing import Optional, List, Dict, Any

def normalize(text: str) -> str:
    t = text.lower()
    return re.sub(r"[’‘`ʻʼ]", "'", t)

# @POS_Terminal_UzSmart_Bank kanalidagi barcha videopostlar bazasi
CATALOG: List[Dict[str, Any]] = [
    {
        "id": 148,
        "title": "Oylik abonent to'lovini Click orqali to'lash videosi",
        "keywords": [
            "oylik", "abonent", "click", "klik", "qanday to'layman", "qanday tolayman",
            "qanday to'lov", "qanday tolov", "to'lov qilish", "tolov qilish", "tulov qilish",
            "video bormi", "videoni tashlang", "rekvizit", "qayerga to'lash", "qayerga tolayman"
        ]
    },
    {
        "id": 145,
        "title": "Yillik fiskal modul to'lovini Click orqali to'lash videosi",
        "keywords": ["yillik", "fiskal modul to'lov", "feskal modul", "yillik tolov", "yillik tulov"]
    },
    {
        "id": 134,
        "title": "Fiskal modul ilovasini o'chirib qayta o'rnatish videosi",
        "keywords": ["o'chirib qayta", "ochirib qayta", "qayta o'rnatish", "qayta ornatish", "modulni o'chirish"]
    },
    {
        "id": 137,
        "title": "Fiskal modul ilovasini aktivlashtirish videosi",
        "keywords": ["aktivlashtirish", "aktiv qilish", "aktiv", "aktivasiya"]
    },
    {
        "id": 141,
        "title": "Sana va vaqtni to'g'irlash videosi",
        "keywords": ["vaqt", "soat", "sana", "to'g'irlash", "togirlash"]
    },
    {
        "id": 140,
        "title": "Tovarlar narxini o'zgartirish videosi",
        "keywords": ["narx", "narxni", "narxini", "narx o'zgartirish", "narx uzgartirish"]
    },
    {
        "id": 139,
        "title": "Markirofkani o'chirish videosi",
        "keywords": ["markirovka", "markirofka", "markirovkani", "markirofkani"]
    },
    {
        "id": 138,
        "title": "Ma'lumotlarni yuklash videosi",
        "keywords": ["ma'lumotlarni yuklash", "malumotlarni yuklash", "ma'lumot yuklash", "baza yuklash", "yuklash"]
    },
    {
        "id": 136,
        "title": "Analitika bo'limi bo'yicha video",
        "keywords": ["analitika", "hisobot", "otchet", "statistika"]
    },
    {
        "id": 125,
        "title": "Dasturni yangilash va o'lchov birliklarini to'g'irlash videosi",
        "keywords": ["dasturni yangilash", "yangilash", "obnovit", "obnovleniya", "o'lchov", "ulchov"]
    },
    {
        "id": 130,
        "title": "Oylik abonent to'lovi qilinmaganda apparat har oyning 6-sanasida o'chishi haqida",
        "keywords": ["qachon o'chadi", "qachon ochadi", "6-sana", "nechanchi sana"]
    }
]

def find_video_post(text: str) -> Optional[int]:
    """Foydalanuvchi murojaatiga eng mos video post ID sini aniqlash"""
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
        return 141

    # 5. Dastur yangilash
    if any(k in t for k in ["yangila", "obnov"]):
        return 125

    # 6. Analitika
    if "analitika" in t:
        return 136

    # 7. Ma'lumotlarni yuklash
    if "yukla" in t and ("ma'lumot" in t or "malumot" in t or "tovar" in t or "baza" in t):
        return 138

    # 8. Fiskal modul
    if "aktiv" in t:
        return 137
    if "o'chirib qayta" in t or "ochirib qayta" in t:
        return 134

    # 9. Oylik to'lovni qanday to'lash / video bormi / Clickdan to'lash
    if any(k in t for k in ["qanday to'lov", "qanday tolov", "qanday tulov", "qanday to'layman", "qanday tolayman", "video bormi", "videoni tashlang", "rekvizit", "click", "klik"]):
        return 148

    return None
