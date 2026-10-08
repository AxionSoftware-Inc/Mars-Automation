import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# @POS_Terminal_UzSmart_Bank kanalidagi tayyor yechim va yo'riqnoma postlari ID lari
CHANNEL_POSTS = {
    # Oylik abonent to'lovini Click orqali to'lash videosi
    "oylik_tulov": {
        "message_id": 148,
        "title": "Oylik abonent to'lovini Click orqali to'lash qo'llanmasi",
        "keywords": ["oylik to'lov", "oylik tulov", "clickdan to'lash", "clickdan tulash", "qanday to'layman", "rekvizit"]
    },
    # Yillik fiskal modul to'lovini Click orqali to'lash videosi
    "yillik_tulov": {
        "message_id": 145,
        "title": "Yillik fiskal modul to'lovini Click orqali to'lash qo'llanmasi",
        "keywords": ["yillik", "fiskal modul to'lov", "feskal modul tulov", "yillik tolov", "yillik tulov"]
    },
    # Har oyning 6-sanasida o'chishi haqida ogohlantirish
    "oylik_ogohlantirish": {
        "message_id": 130,
        "title": "Oylik to'lov va apparat o'chish sanasi haqida",
        "keywords": ["qachon o'chadi", "6-sana", "nechanchi sana o'chadi", "har oyning 6"]
    },
    # Fiskal modulni aktivlashtirish
    "fiskal_aktiv": {
        "message_id": 137,
        "title": "Fiskal modul ilovasini aktivlashtirish videosi",
        "keywords": ["fiskal modul aktiv", "feskal aktiv", "modulni aktivlashtirish"]
    },
    # Fiskal modulni o'chirib qayta o'rnatish
    "fiskal_ochirish": {
        "message_id": 134,
        "title": "Fiskal modul ilovasini o'chirib qayta o'rnatish",
        "keywords": ["qayta o'rnatish", "modulni o'chirish", "modul ochirish"]
    },
    # Sana va vaqtni to'g'irlash
    "sana_vaqt": {
        "message_id": 141,
        "title": "Sana va vaqtni to'g'irlash bo'yicha qo'llanma",
        "keywords": ["sana va vaqt", "vaqt noto'g'ri", "soat noto'g'ri", "vaqtni to'g'irlash", "vaqtni togirlash"]
    },
    # Tovarlar o'lchov birligi va dasturni yangilash
    "dastur_yangilash": {
        "message_id": 125,
        "title": "Dasturni yangilash va o'lchov birliklari",
        "keywords": ["dasturni yangilash", "o'lchov birligi", "ulchov birlik", "obnovleniya"]
    },
    # Narxni o'zgartirish
    "narx_ozgartirish": {
        "message_id": 140,
        "title": "Tovarlar narxini o'zgartirish qo'llanmasi",
        "keywords": ["narxni o'zgartirish", "narx uzgartirish", "narx qo'yish"]
    }
}

def find_relevant_post(text: str) -> Optional[int]:
    """Foydalanuvchi aynan qo'llanma/video yoki qanday to'lashni so'raganda kanal post ID sini aniqlash"""
    t = text.lower().strip()
    
    # 1. Yillik fiskal modul to'lovi
    if any(k in t for k in ["yillik to'lov", "yillik tolov", "yillik tulov", "yillik to'lash", "yillik qanday"]):
        return CHANNEL_POSTS["yillik_tulov"]["message_id"]

    # 2. Oylik to'lovni qanday to'lash, clickdan to'lash, video qo'llanma so'ralganda
    # DIQQAT: "qarzim bormi", "apparati ishlamayapti" deganida emas, aynan to'lash tartibi so'ralganda!
    if any(k in t for k in [
        "qanday to'layman", "qanday tolash", "qanday to'lasa bo'ladi", 
        "clickdan to'lash", "clickdan qanday", "klikdan", "to'lov qilish videosi", 
        "rekvizit", "to'lash tartibi", "videoni tashlang", "video tashlang"
    ]):
        return CHANNEL_POSTS["oylik_tulov"]["message_id"]

    # 3. Sana va vaqt
    if any(k in t for k in ["vaqtni to'g'irlash", "vaqt noto'g'ri", "soat noto'g'ri", "vaqtini togirlash"]):
        return CHANNEL_POSTS["sana_vaqt"]["message_id"]

    # 4. Dastur yangilash
    if any(k in t for k in ["dasturni yangilash", "dastur yangilash", "obnovleniya", "o'lchov birlik"]):
        return CHANNEL_POSTS["dastur_yangilash"]["message_id"]

    # 5. Fiskal modul aktivlashtirish
    if any(k in t for k in ["modulni aktiv", "fiskal modul aktiv", "feskal aktiv"]):
        return CHANNEL_POSTS["fiskal_aktiv"]["message_id"]

    return None
