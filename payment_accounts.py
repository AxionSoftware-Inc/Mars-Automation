import re
from typing import Optional, Tuple, Dict, Any

# =============================================================================
# 1. TASHKILOTLAR VA HISOB RAQAMLAR (OYLIK VA YILLIK TO'LOVLAR)
# =============================================================================

# 1.1 OYLIK ABONENT TO'LOVI (Har oyning 6-sanasigacha to'lanadi)
# Xizmat turi: Smart POS kassa apparatiga dasturiy va servis xizmati ko'rsatish
MARS_ORG_NAME = "«MARS ELEKTRON TEXNIKA» MCHJ"
MARS_ACCOUNT = "20208000800208044003"
MARS_INN = "302568138"
MARS_MFO = "01048"
MARS_BANK = "«Ipak Yo'li» AITB Shahrisabz filiali"
MARS_ADDRESS = "Qashqadaryo viloyati, Shahrisabz shahar, Sheroziy ko'chasi 1-uy"
MARS_PHONES = "+998 94 299 77 99, +998 91 945 32 89"
MARS_MONTHLY_FEE = 100000.0  # 1 oylik abonent to'lovi (so'm)
MARS_DUE_DAY = 6             # Har oyning 6-sanasigacha
MARS_VIDEO_ID = 148          # Click orqali oylik to'lash videosi
MARS_POST_ID = 85            # Rekvizit matni

# 1.2 YILLIK FISKAL MODUL TO'LOVI (Yilda 1 marta to'lanadi)
# Xizmat turi: Davlat Soliq Qo'mitasi huzuridagi Yangi Texnologiyalar DUK fiskal modul sertifikati
YANGI_TEXNOLOGIYALAR_ORG_NAME = "«Yangi Texnologiyalar» DUK"
YANGI_TEXNOLOGIYALAR_ACCOUNT = "20210000100431200010"
YANGI_TEXNOLOGIYALAR_INN = "201589463"
YANGI_TEXNOLOGIYALAR_MFO = "01018"
YANGI_TEXNOLOGIYALAR_BANK = "ATB «Kapitalbank» Toshkent"
YANGI_TEXNOLOGIYALAR_PAYMENT_CODE = "00668"
YANGI_TEXNOLOGIYALAR_ANNUAL_FEE = 440000.0  # 1 yillik fiskal modul to'lovi (so'm)
YANGI_TEXNOLOGIYALAR_PHONE = "+998 71 202-32-32"
YANGI_TEXNOLOGIYALAR_VIDEO_ID = 145         # Click orqali yillik to'lash videosi
YANGI_TEXNOLOGIYALAR_POST_ID = 34           # Rekvizit matni


# Kalit so'zlar
MARS_KEYWORDS = [
    "mars", "марс", "mars elektron texnika", "марс электрон техника",
    "20208000800208044003", "302568138", "abonent to'lov", "abonent tulov",
    "oylik to'lov", "oylik tolov", "oylik tulov", "oylik shot"
]

YANGI_TEXNOLOGIYALAR_KEYWORDS = [
    "yangi tehnologiyalar", "yangi texnologiyalar", "янги технологиялар",
    "20210000100431200010", "201589463", "00668", "fiskal modul to'lov",
    "fiskal modul tulov", "fiskal modulning yillik", "yillik to'lov",
    "yillik tolov", "yillik tulov", "yillik shot", "yillik hisob"
]


# =============================================================================
# 2. FORMATLANGAN REKVIZIT KARTALARI
# =============================================================================

def get_monthly_payment_card() -> str:
    """Oylik abonent to'lovi (Mars Elektron Texnika) uchun aniq rekvizitlar kartasi"""
    return (
        "💳 <b>OYLIK ABONENT TO'LOVI REKVIZITLARI</b>\n\n"
        "🏢 <b>Tashkilot:</b> «MARS ELEKTRON TEXNIKA» MCHJ\n"
        "🏦 <b>Hisob raqam (X/R):</b> <code>20208000800208044003</code>\n"
        "🏛 <b>Bank:</b> «Ipak Yo'li» AITB Shahrisabz filiali\n"
        "🔢 <b>MFO:</b> <code>01048</code> | <b>INN (STIR):</b> <code>302568138</code>\n"
        "💰 <b>Summa:</b> <b>100 000 so'm</b> (har oy uchun)\n"
        "⏰ <b>To'lov muddati:</b> Har oyning <b>6-sanasigacha</b>\n"
        "📝 <b>To'lov maqsadi:</b> <code>INN [korxona INN] Abonent to'lovi 100 000 so'm</code>\n"
        "📞 <b>Aloqa:</b> +998 94 299 77 99, +998 91 945 32 89\n\n"
        "📲 <b>Click orqali to'lash:</b>\n"
        "Click dasturi -> <i>To'lovlar</i> -> <i>Rekvizit bo'yicha to'lov</i> (yoki <i>Xizmatlar</i> -> <i>Mars Elektron Texnika</i>)"
    )


def get_annual_payment_card() -> str:
    """Yillik fiskal modul to'lovi (Yangi Texnologiyalar DUK) uchun aniq rekvizitlar kartasi"""
    return (
        "🏛 <b>YILLIK FISKAL MODUL TO'LOVI REKVIZITLARI</b>\n\n"
        "🏢 <b>Tashkilot:</b> «Yangi Texnologiyalar» DUK (Davlat Soliq Qo'mitasi)\n"
        "🏦 <b>Hisob raqam (X/R):</b> <code>20210000100431200010</code>\n"
        "🏛 <b>Bank:</b> ATB «Kapitalbank» Toshkent\n"
        "🔢 <b>MFO:</b> <code>01018</code> | <b>INN (STIR):</b> <code>201589463</code>\n"
        "🔑 <b>To'lov kodi:</b> <code>00668</code>\n"
        "💰 <b>Summa:</b> <b>440 000 so'm</b> (1 yilga)\n"
        "📝 <b>To'lov maqsadi:</b> <code>INN [korxona INN] fiskal modulning yillik to'lovi</code>\n"
        "📞 <b>Telefon:</b> +998 71 202-32-32\n\n"
        "⏳ <b>Ishga tushish vaqti:</b> To'lov qilingandan so'ng <b>2 soatdan 24 soatgacha</b> bo'lgan muddatda Soliq tizimi tomonidan avtomatik uzaytiriladi.\n\n"
        "⚠️ <b>DIQQAT:</b> Ushbu to'lov Davlat Soliq Qo'mitasi («Yangi Texnologiyalar» DUK) ga qaratilgan bo'lib, «Mars Elektron Texnika» oylik abonent to'lovidan mutlaqo alohidadir!"
    )


def get_all_payment_accounts_card() -> str:
    """Ikkala hisob raqamni aniq ajratib ko'rsatuvchi to'liq karta"""
    return (
        "💳 <b>SMART POS KASSA APPARATLARI UCHUN TO'LOV REKVIZITLARI</b>\n\n"
        "⚠️ <b>QAT'IY QOIDA:</b> Oylik abonent to'lovi va Yillik fiskal modul to'lovi <b>2 xil alohida tashkilotga</b> to'lanadi. Ularni mutlaqo adashtirmaslik lozim!\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ <b>OYLIK ABONENT TO'LOVI (Har oyning 6-sanasigacha):</b>\n"
        "🏢 <b>Kompaniya:</b> «MARS ELEKTRON TEXNIKA» MCHJ\n"
        "🏦 <b>Hisob raqam (X/R):</b> <code>20208000800208044003</code>\n"
        "🏛 <b>Bank:</b> «Ipak Yo'li» AITB Shahrisabz, MFO: <code>01048</code>\n"
        "🔢 <b>INN:</b> <code>302568138</code> | 💰 <b>Summa:</b> 100 000 so'm\n"
        "📝 <b>To'lov maqsadi:</b> <code>INN [korxonangiz INN] abonent to'lov</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "2️⃣ <b>YILLIK FISKAL MODUL TO'LOVI (Yilda 1 marta):</b>\n"
        "🏢 <b>Tashkilot:</b> «Yangi Texnologiyalar» DUK (Davlat Soliq Qo'mitasi)\n"
        "🏦 <b>Hisob raqam (X/R):</b> <code>20210000100431200010</code>\n"
        "🏛 <b>Bank:</b> ATB «Kapitalbank» Toshkent, MFO: <code>01018</code>\n"
        "🔢 <b>INN:</b> <code>201589463</code> | 🔑 <b>To'lov kodi:</b> <code>00668</code>\n"
        "💰 <b>Summa:</b> 440 000 so'm (1 yillik sertifikat)\n"
        "📝 <b>To'lov maqsadi:</b> <code>INN [korxonangiz INN] fiskal modulning yillik to'lovi</code>\n"
        "📞 <b>Telefon:</b> +998 71 202-32-32 (2-24 soat ichida faollashadi)\n\n"
        "📲 <i>Ikkala to'lovni ham Click orqali «Rekvizit bo'yicha to'lov» bo'limida amalga oshirish mumkin.</i>"
    )


# =============================================================================
# 3. MXIK (IKPU - MAHSULOT VA XIZMATLAR KODI) BILIMLAR BAZASI
# =============================================================================

def get_mxik_guidance(query: str = "") -> Tuple[str, int]:
    """
    MXIK (IKPU / Tasnif / Soliq) bo'yicha professional tushuntirish va tegishli video.
    Qaytaradi: (tushuntirish_matni, video_post_id)
    """
    q = query.lower()

    # 1. Agar qidirish yoki tasnif sayti so'ralgan bo'lsa (Post 28)
    if any(w in q for w in ["tasnif", "qidirish", "sayt", "topish", "qayerdan"]):
        text = (
            "🔍 <b>MXIK kodlarni Tasnif.soliq.uz saytidan qidirish:</b>\n\n"
            "Davlat Soliq Qo'mitasining rasmiy <b>tasnif.soliq.uz</b> portali orqali har qanday tovar yoki xizmatning 17 xonali MXIK (IKPU) kodini tezkor topishingiz mumkin.\n\n"
            "📌 <b>Tartibi:</b>\n"
            "1. <a href='https://tasnif.soliq.uz'>tasnif.soliq.uz</a> saytiga kiring;\n"
            "2. Qidiruv qatoriga tovar nomini yozing (masalan: <i>Non</i>, <i>Sut</i>, <i>Xizmat</i>);\n"
            "3. Korxonangiz faoliyatiga mos 17 xonali MXIK kodni nusxalab oling;\n"
            "4. Kassa apparatiga tovar qo'shishda ushbu kodni kiriting."
        )
        return text, 28

    # 2. Agar tekshirish yoki soliq jarimasi so'ralgan bo'lsa (Post 17)
    if any(w in q for w in ["tekshirish", "jarima", "soliq jarima", "xato kod", "to'g'rilash", "togrilash"]):
        text = (
            "⚠️ <b>Tovarlardagi MXIK kodni tekshirish va soliq jarimalari:</b>\n\n"
            "Soliq qonunchiligiga (VMQ-943) ko'ra, chekda noto'g'ri yoki faoliyatingizga mos kelmaydigan MXIK kodi ko'rsatilsa, soliq organlari tomonidan <b>jarima</b> qo'llaniladi.\n\n"
            "📌 <b>Nimalarga e'tibor berish lozim:</b>\n"
            "🔹 Tovarlaringiz MXIK kodi to'g'ri tanlanganini tekshiring;\n"
            "🔹 O'lchov birligi (dona, kg, litr) mos kelishini nazorat qiling;\n"
            "🔹 Xato kiritilgan tovarlarni kassa dasturidan to'g'irlab qo'ying."
        )
        return text, 17

    # 3. Naqdga savdo qilib bo'lmaydigan tovarlar (Post 133)
    if any(w in q for w in ["zapravka", "alkogol", "tamaki", "naqd", "naqt", "bloklab urish"]):
        text = (
            "🚫 <b>Naqd pulga savdo qilib bo'lmaydigan MXIK tovarlar:</b>\n\n"
            "Soliq talabiga ko'ra, <b>Zapravkalar, Alkogol, Tamaki</b> va davlat tashkilotlari xizmatlari MXIK kodi kiritilganda naqd pulga chek urib bo'lmaydi.\n\n"
            "📌 <b>Tavsiya:</b>\n"
            "Bunday holatda to'lovni bank kartasi orqali amalga oshiring yoki apparat dasturini yangilang."
        )
        return text, 133

    # 4. Asosiy: Tovar qo'shish va MXIK kod kiritish (Post 15)
    text = (
        "📦 <b>Tovarlarni qo'shish va MXIK kod kiritish tartibi:</b>\n\n"
        "<b>MXIK (ИКПУ)</b> — bu Mahsulot va xizmatlarning yagona identifikatsiya kodi bo'lib, har bir fiskal chekda aks ettirilishi shart (Davlat Soliq Qo'mitasi talabi).\n\n"
        "📌 <b>Kassa apparatiga tovar qo'shish bosqichlari:</b>\n"
        "1. Kassa dasturida <b>«Tovar qo'shish»</b> bo'limiga kiring;\n"
        "2. Tovar nomini va narxini yozing;\n"
        "3. <b>tasnif.soliq.uz</b> saytidan olingan 17 xonali MXIK kodni kiriting;\n"
        "4. O'lchov birligini tanlab saqlang."
    )
    return text, 15


# =============================================================================
# 4. SO'ROV VA KVITANSIYA TURLARINI ANIQLASH (DISPATCHER)
# =============================================================================

def classify_payment_intent(text: str) -> Optional[str]:
    """
    Foydalanuvchi xabarida to'lov rekvizitlari so'ralganini aniqlash.
    Qaytaradi:
    - 'annual': Faqat yillik fiskal modul to'lovi rekvizitlari
    - 'monthly': Faqat oylik Mars abonent to'lovi rekvizitlari
    - 'both': Umumiy to'lov / barcha rekvizitlar
    - None: To'lov rekviziti so'ralmagan
    """
    t = text.lower().strip()

    # Yillik to'lov alomatlari
    is_annual = any(w in t for w in [
        "yillik shot", "yillik hisob", "yillik rekvizit", "fiskal modul shot",
        "fiskal modul hisob", "yillik to'lov", "yillik tolov", "yillik tulov",
        "yangi texnologiyalar", "yillik qancha", "440000", "440 000"
    ])

    # Oylik to'lov alomatlari
    is_monthly = any(w in t for w in [
        "oylik shot", "oylik hisob", "oylik rekvizit", "mars hisob", "mars shot",
        "abonent to'lov", "abonent tolov", "abonent tulov", "marsga to'lov",
        "oylik to'lov", "oylik tolov", "oylik tulov", "100000", "100 000"
    ])

    if is_annual and not is_monthly:
        return "annual"
    if is_monthly and not is_annual:
        return "monthly"

    # Umumiy rekvizit yoki to'lov so'rovlari
    general_payment_words = [
        "shot raqam", "shot raqamlar", "hisob raqam", "hisob raqamlar",
        "rekvizit", "rekvizitlar", "/tolov", "to'lov qilish tartibi",
        "qayerga to'layman", "qayerga tolayman", "qayerga to'lash kerak",
        "bank rekvizitlari", "to'lov hisobi", "shotini ber"
    ]
    if any(w in t for w in general_payment_words) or (is_annual and is_monthly):
        return "both"

    return None


def is_mxik_intent(text: str) -> bool:
    """Matn MXIK / IKPU / Tasnif / Tovar qo'shish mavzusiga tegishlimi?"""
    t = text.lower().strip()
    mxik_words = [
        "mxik", "mixk", "мхик", "михк", "ikpu", "икпу",
        "tasnif", "tasnif.soliq", "тасниф",
        "tovar qo'shish", "tovar qushish", "tovar kiritish",
        "tovarga kod", "mxik kod", "mxik nima", "mxik xatosi",
        "mxik jarima", "mxik qayerdan"
    ]
    return any(w in t for w in mxik_words)


def classify_receipt_target(recipient_account: str, amount: float, raw_text: str = "") -> str:
    """
    To'lov kvitansiyasidagi faktlar bo'yicha to'lov qaysi tashkilotga yo'naltirilganini aniqlash.
    Qaytaradi:
    - 'annual': «Yangi Texnologiyalar» DUK (Yillik fiskal modul)
    - 'monthly': «Mars Elektron Texnika» MCHJ (Oylik abonent)
    - 'other': Begona tashkilot
    """
    clean_acc = re.sub(r"\D", "", recipient_account)
    combined = (recipient_account + " " + raw_text).lower()

    # 1. Yillik to'lov tekshiruvi: 20210000100431200010 yoki Yangi Texnologiyalar yoki 440000
    if YANGI_TEXNOLOGIYALAR_ACCOUNT in clean_acc or any(k in combined for k in YANGI_TEXNOLOGIYALAR_KEYWORDS):
        return "annual"
    if 435000.0 <= amount <= 445000.0 and any(k in combined for k in ["fiskal", "modul", "yillik", "texnologiyalar"]):
        return "annual"

    # 2. Oylik to'lov tekshiruvi: 20208000800208044003 yoki Mars Elektron Texnika
    if MARS_ACCOUNT in clean_acc or any(k in combined for k in MARS_KEYWORDS):
        return "monthly"

    return "other"
