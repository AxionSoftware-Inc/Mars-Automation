import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def normalize_text(text: str) -> str:
    """O'zbekcha turli harflar va belgilarni (o', g', `, ', backtick) normalizatsiya qilish"""
    t = text.lower()
    # Har xil apostroflarni standartlashtirish
    t = re.sub(r"[’‘`ʻʼ]", "'", t)
    return t

CHANNEL_POSTS = {
    "oylik_tulov": 148,      # Oylik to'lovni Click orqali to'lash videosi
    "yillik_tulov": 145,     # Yillik fiskal modul to'lovi videosi
    "sana_vaqt": 141,        # Sana va vaqtni to'g'irlash videosi
    "dastur_yangilash": 125, # Dasturni yangilash videosi
    "fiskal_aktiv": 137,     # Fiskal modulni aktivlashtirish videosi
}

def detect_context(text: str) -> str:
    """
    Kontekstni aniqlash:
    - 'post_148': Oylik to'lovni qanday to'lash, to'lov videosi, Click orqali to'lov
    - 'post_145': Yillik fiskal modul to'lovi
    - 'post_141': Sana va vaqt
    - 'post_125': Dastur yangilash
    - 'post_137': Fiskal modul aktivlashtirish
    - 'check_debt': Apparat ishlamay qolgani, qarz bor-yo'qligi, kassa ochilmayotgani
    - 'other': Boshqa umumiy gaplar
    """
    t = normalize_text(text)

    # 1. Yillik to'lov
    if "yillik" in t and any(w in t for w in ["to'lov", "tolov", "tulov", "fiskal", "modul"]):
        return "post_145"

    # 2. Soat / sana / vaqt
    if any(w in t for w in ["vaqt", "soat", "sana"]) and any(w in t for w in ["noto'g'ri", "notogri", "to'g'irlash", "togirlash", "sozlash"]):
        return "post_141"

    # 3. Dasturni yangilash
    if any(w in t for w in ["dasturni yangilash", "dastur yangilash", "obnovit", "obnovleniya", "o'lchov birlik"]):
        return "post_125"

    # 4. Fiskal modul aktivlashtirish
    if any(w in t for w in ["aktivlashtirish", "aktiv qilish"]):
        return "post_137"

    # 5. Oylik to'lov videosi yoki qanday to'lash (Click, video, tartibi)
    is_asking_how_to_pay = (
        ("to'lov" in t or "tolov" in t or "tulov" in t or "pul" in t) and
        ("qanday" in t or "video" in t or "qilaman" in t or "qilish" in t or "tashlang" in t or "bormi" in t or "tartibi" in t or "click" in t or "klik" in t)
    )
    is_direct_video_request = (
        "video" in t and ("bormi" in t or "tashlang" in t or "bering" in t or "to'lov" in t or "tulov" in t)
    )
    is_payment_method = (
        any(w in t for w in ["clickdan", "klikdan", "qayerga to'layman", "qayerga tolayman", "rekvizit"])
    )

    if is_asking_how_to_pay or is_direct_video_request or is_payment_method:
        return "post_148"

    # 6. Apparat ishlamay qolgani yoki qarz tekshirish
    is_trouble = any(w in t for w in [
        "ishlamay", "ishlamadi", "ishlamayapti", "o'chib", "ochib", "ochilmay",
        "blok", "chek chiqmay", "terminal", "aparat", "apparat", "kassa", "qarz"
    ])
    if is_trouble:
        return "check_debt"

    return "other"
