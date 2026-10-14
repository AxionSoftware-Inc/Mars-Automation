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
    "oylik to'lov", "oylik tolov", "oylik tulov", "oylik shot",
    "абонент тўлов", "абонент толов", "абонент тулов",
    "ойлик тўлов", "ойлик толов", "ойлик тулов", "ойлик шот", "марс шот"
]

YANGI_TEXNOLOGIYALAR_KEYWORDS = [
    "yangi tehnologiyalar", "yangi texnologiyalar", "янги технологиялар",
    "20210000100431200010", "201589463", "00668", "fiskal modul to'lov",
    "fiskal modul tulov", "fiskal modulning yillik", "yillik to'lov",
    "yillik tolov", "yillik tulov", "yillik shot", "yillik hisob",
    "фискал модул тўлов", "фискал модул толов", "фискал модулнинг йиллик",
    "йиллик тўлов", "йиллик толов", "йиллик тулов", "йиллик шот", "йиллик ҳисоб"
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


def get_monthly_post_note(script: str = "latin") -> str:
    """Kanaldan uzatilgan 85-post (Oylik abonent) tagidan yuboriladigan qo'shimcha eslatma"""
    from translit_manager import adapt_to_user_script
    text = (
        "💡 <b>Eslatma:</b> Ushbu hisob raqam <b>«MARS ELEKTRON TEXNIKA» MCHJ</b> ga Smart POS apparatlariga oylik servis va dasturiy ta'minot xizmati uchun (100 000 so'm/oy).\n"
        "⏰ <b>Muddat:</b> Har oyning <b>6-sanasigacha</b> to'lanishi shart.\n\n"
        "👇 <i>Quyida Click orqali to'lov qilish bo'yicha video-qo'llanma yuborildi:</i>"
    )
    return adapt_to_user_script(text, script)


def get_annual_post_note(script: str = "latin") -> str:
    """Kanaldan uzatilgan 34-post (Yillik fiskal modul) tagidan yuboriladigan qo'shimcha eslatma"""
    from translit_manager import adapt_to_user_script
    text = (
        "💡 <b>Eslatma:</b> Ushbu hisob raqam Davlat Soliq Qo'mitasi huzuridagi <b>«Yangi Texnologiyalar» DUK</b> ga 1 yillik fiskal modul sertifikati uchun (440 000 so'm/yil).\n"
        "⏳ <b>Faollashishi:</b> To'lov qilingach <b>2 soatdan 24 soatgacha</b> bo'lgan muddatda Soliq tizimida avtomatik ishga tushadi.\n"
        "⚠️ <b>DIQQAT:</b> Ushbu to'lov «Mars Elektron Texnika» oylik to'lovidan mutlaqo alohidadir!\n\n"
        "👇 <i>Quyida Click orqali to'lov qilish bo'yicha video-qo'llanma yuborildi:</i>"
    )
    return adapt_to_user_script(text, script)


def get_both_posts_intro(script: str = "latin") -> str:
    """Ikkala post uzatilishidan oldin adashtirmaslik haqida qat'iy ogohlantirish"""
    from translit_manager import adapt_to_user_script
    text = (
        "⚠️ <b>QAT'IY QOIDA:</b> Smart POS kassa apparatlarida <b>2 xil alohida to'lov</b> mavjud bo'lib, ular <b>2 xil alohida tashkilotga</b> to'lanadi. Ularni mutlaqo adashtirmaslik lozim!\n\n"
        "1️⃣ <b>Oylik abonent to'lovi (100 000 so'm)</b> — «MARS ELEKTRON TEXNIKA» MCHJ ga\n"
        "2️⃣ <b>Yillik fiskal modul to'lovi (440 000 so'm)</b> — «Yangi Texnologiyalar» DUK ga\n\n"
        "👇 <i>Quyida rasmiy kanaldan ikkala hisob raqamning matnli postlari va video-qo'llanmalari uzatilmoqda:</i>"
    )
    return adapt_to_user_script(text, script)


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
    if any(w in q for w in [
        "tasnif", "qidirish", "sayt", "topish", "qayerdan",
        "тасниф", "қидириш", "кидириш", "сайт", "топиш", "қаердан", "каердан"
    ]):
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
    if any(w in q for w in [
        "tekshirish", "jarima", "soliq jarima", "xato kod", "to'g'rilash", "togrilash",
        "текшириш", "жарима", "солиқ жарима", "солик жарима", "хато код", "тўғрилаш", "тогрилаш"
    ]):
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
    if any(w in q for w in [
        "zapravka", "alkogol", "tamaki", "naqd", "naqt", "bloklab urish",
        "заправка", "алкогол", "тамаки", "нақд", "накт"
    ]):
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

    # Agar savol qarz/tekshirish bo'lsa va unda aniq hisob raqam/shot/rekvizit so'ralmagan bo'lsa -> rekvizit intenti emas!
    if any(w in t for w in ["qarz", "tekshir", "bormi", "qarzdorlik", "holat", "қарз", "борми", "текшир"]):
        if not any(w in t for w in ["shot", "rekvizit", "xisob", "hisob raqam", "shotini", "шот", "реквизит"]):
            return None

    # Yillik to'lov alomatlari (Lotin va Kirill)
    is_annual = any(w in t for w in [
        "yillik shot", "yillik hisob", "yillik rekvizit", "fiskal modul", "fiskal modul shot",
        "fiskal modul hisob", "fiskal modul to'lov", "fiskal modul tolov", "fiskal modul tulov",
        "yillik to'lov", "yillik tolov", "yillik tulov",
        "yangi texnologiyalar", "yillik qancha", "440000", "440 000",
        "йиллик шот", "йиллик ҳисоб", "йиллик хисоб", "йиллик реквизит",
        "фискал модул", "фискал модуль", "фискал модул шот", "фискал модул ҳисоб", "фискал модул хисоб",
        "фискал модул тўлов", "фискал модул толов", "фискал модул тулов",
        "йиллик тўлов", "йиллик толов", "йиллик тулов", "янги технологиялар",
        "йиллик қанча", "йиллик канча"
    ])

    # Oylik to'lov alomatlari (Lotin va Kirill)
    is_monthly = any(w in t for w in [
        "oylik shot", "oylik hisob", "oylik rekvizit", "mars hisob", "mars shot",
        "abonent to'lov", "abonent tolov", "abonent tulov", "marsga to'lov",
        "oylik to'lov", "oylik tolov", "oylik tulov", "100000", "100 000",
        "ойлик шот", "ойлик ҳисоб", "ойлик хисоб", "ойлик реквизит",
        "марс ҳисоб", "марс хисоб", "марс шот", "абонент тўлов",
        "абонент толов", "абонент тулов", "марсга тўлов", "марсга толов",
        "ойлик тўлов", "ойлик толов", "ойлик тулов"
    ])

    has_annual = any(w in t for w in ["yillik", "fiskal", "soliq", "ofd", "yangi texnologiyalar", "йиллик", "фискал", "солиқ", "солик", "офд"])
    has_monthly = any(w in t for w in ["oylik", "abonent", "mars", "ойлик", "абонент", "марс"])
    has_pay = any(w in t for w in ["shot", "hisob", "rekvizit", "to'lov", "tolov", "tulov", "тўлов", "толов", "шот", "реквизит", "ҳисоб", "хисоб"])

    if (has_annual and has_monthly and has_pay) or any(w in t for w in ["ikkala shot", "ikkala hisob", "ikkala to'lov", "ikkala tolov", "иккала шот", "иккала ҳисоб", "иккала тўлов"]):
        return "both"

    if is_annual and not is_monthly:
        return "annual"
    if is_monthly and not is_annual:
        return "monthly"

    # Umumiy rekvizit yoki to'lov so'rovlari (Lotin va Kirill)
    general_payment_words = [
        "shot raqam", "shot raqamlar", "hisob raqam", "hisob raqamlar",
        "rekvizit", "rekvizitlar", "/tolov", "to'lov qilish tartibi",
        "qayerga to'layman", "qayerga tolayman", "qayerga to'lash kerak",
        "bank rekvizitlari", "to'lov hisobi", "shotini ber", "shot bering",
        "shot tashlang", "shot tashvorin", "to'lov uchun shot", "tolov uchun shot",
        "hisob raqam bering", "hisob bering", "schet bering", "schet tashlang",
        "шот рақам", "шот рақамлар", "ҳисоб рақам", "хисоб ракам",
        "ҳисоб рақамлар", "хисоб ракамлар", "реквизит", "реквизитlar", "реквизитлар",
        "тўлов қилиш тартиби", "толов килиш тартиби", "қаерга тўлайман", "каерга толайман",
        "қаерга тўлаш керак", "каерга толаш керак", "банк реквизитлари",
        "тўлов ҳисоби", "толов хисоби", "шотини бер",
        "счёт беринг", "счет беринг", "счёт ташланг", "счет ташланг",
        "шот беринг", "шот ташланг", "тўлов учун счёт", "толов учун счет",
        "тўлов учун ҳисоб", "толов учун хисоб", "тўлов учун шот", "толов учун шот"
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


def is_annual_check_intent(text: str) -> bool:
    """Foydalanuvchi yillik to'lov yoki fiskal modul (OFD/Soliq) qarzdorligini tekshirishni so'rayaptimi?"""
    t = text.lower().strip()
    
    # Tezkor davomiy iboralar ("yillikdanchi?", "fiskalchi?", "yillikchi?")
    followup_words = [
        "yillikdanchi", "yillikchi", "yilikdanchi", "yilikchi",
        "fiskaldanchi", "fiskalchi", "soliqdanchi", "soliqchi",
        "ofddanchi", "ofdchi", "fmodanchi", "fmochi",
        "йилликданчи", "йилликчи", "фискалданчи", "фискалчи", "солиқданчи", "солиқчи", "офдданчи"
    ]
    if any(w in t for w in followup_words) or t in ("yillik", "fiskal", "ofd", "йиллик", "фискал", "офд"):
        return True

    phrases = [
        "yillik qarz", "yillikni tekshir", "yillik tekshir", "yillikni tekshirib",
        "yillik to'lovni tekshir", "yillik tolovni tekshir", "yillik tulovni tekshir",
        "yillik tulovniyam tekshir", "yillik to'lovniyam tekshir", "yillik tolovniyam tekshir",
        "yillik to'lovim bormi", "yillik tolovim bormi", "yillik tulovim bormi",
        "yillik qarzim bormi", "yillik qarzdorlik", "yillik muddat", "yillik holati",
        "ofd tekshir", "ofdni tekshir", "ofd qarz", "ofd qarzdorlik",
        "soliq qarz", "soliqni tekshir", "fiskal modul tekshir", "fiskal modul muddat",
        "fiskal modulimni tekshir", "fmo qarz", "fmo tekshir",
        "йиллик қарз", "йиллик карз", "йилликни текшир", "йиллик текшир",
        "йиллик тўловни текшир", "йиллик толовни текшир", "офд текшир",
        "фискал модул текшир", "фискал модул муддат"
    ]
    if any(p in t for p in phrases):
        return True

    has_target = any(w in t for w in ["yillik", "yilik", "fiskal", "ofd", "fmo", "soliq", "йиллик", "фискал", "офд", "фмо", "солиқ", "солик"])
    has_action = any(w in t for w in [
        "tekshir", "kurib", "ko'rib", "korib", "qarz", "bormi", "muddat", "holat",
        "провер", "текшир", "қарз", "карз", "борми", "муддат", "ҳолат", "холат"
    ])
    return has_target and has_action


def is_monthly_check_intent(text: str) -> bool:
    """Foydalanuvchi oylik abonent to'lovi (Mars) qarzdorligini tekshirishni so'rayaptimi?"""
    t = text.lower().strip()

    # Tezkor davomiy iboralar ("oylikdanchi?", "oylikchi?", "marsdanchi?")
    followup_words = [
        "oylikdanchi", "oylikchi", "oylikdanam", "oylikdan-chi", "oylikchi-chi",
        "marsdanchi", "marschi", "abonentdanchi", "abonentchi",
        "ойликданчи", "ойликчи", "ойликданам", "марсданчи", "абонентданчи"
    ]
    if any(w in t for w in followup_words) or t in ("oylik", "oylik?", "mars", "mars?", "ойлик", "ойлик?"):
        return True

    phrases = [
        "oylik qarz", "oylik qarzim", "oylik qarzim bormi", "oylikdan qarz",
        "oylikdan qarzim bormi", "oylikdan qarzdorlik bormi", "oylik qarzdorlik",
        "oylik holati", "oylik to'lov holati", "oylik tolov holati",
        "oylikni tekshir", "oylikni tekshirib", "oylikni tekshirib ber",
        "oylik to'lovni tekshir", "oylik tolovni tekshir", "oylik tulovni tekshir",
        "oylik to'lovniyam tekshir", "oylik tolovniyam tekshir", "oylik tulovniyam tekshir",
        "oylik to'lovim bormi", "oylik tolovim bormi", "oylik tulovim bormi",
        "marsdan qarzim bormi", "marsga qarzim bormi", "mars qarzim", "marsni tekshir",
        "marsdan qarz", "abonent to'lovini tekshir", "abonent qarz",
        "ойлик қарз", "ойлик қарзим", "ойлик қарзим борми", "ойликдан қарзим борми",
        "ойлик тўловни текшир", "марсдан қарз", "марс қарзим борми", "марсни текшир"
    ]
    if any(p in t for p in phrases):
        return True

    has_target = any(w in t for w in ["oylik", "abonent", "mars", "ойлик", "абонент", "марс"])
    has_action = any(w in t for w in [
        "tekshir", "kurib", "ko'rib", "korib", "qarz", "bormi", "holat", "qarzdorlik",
        "провер", "текшир", "қарз", "карз", "борми", "ҳолат", "холат"
    ])
    return has_target and has_action


def is_both_check_intent(text: str) -> bool:
    """Foydalanuvchi ikkala to'lov (oylik va yillik) yoki umumiy qarzdorlikni so'rayaptimi?"""
    t = text.lower().strip()
    phrases = [
        "ikkalasidanchi", "ikkalasidan", "ikkala tolov", "ikkala to'lov", "ikkalasiyam",
        "ikkala tolovdan", "ikkala to'lovdan", "umumiy qarz", "umumiy qarzim",
        "jami qarz", "jami qarzim", "barcha qarz", "qarzlarim bormi", "qarzlarimni tekshir",
        "qarzlar bormi", "har ikkala", "ikkisi ham", "ikkisidan",
        "иккаласиданчи", "иккаласидан", "умумий қарз", "жами қарз", "қарзларим борми"
    ]
    return any(p in t for p in phrases)


def is_annual_pay_intent(text: str, last_topic: Optional[str] = None) -> bool:
    """Foydalanuvchi yillik to'lov uchun hisob raqam (shot) so'rayaptimi yoki to'lashini aytmoqdami?"""
    if classify_payment_intent(text) == "both":
        return False
    t = text.lower().strip()

    # 1. Aniq yillik to'lov so'rovi
    has_annual = any(w in t for w in ["yillik", "fiskal", "soliq", "ofd", "yangi texnologiyalar", "йиллик", "фискал", "солиқ", "солик", "офд"])
    has_pay = any(w in t for w in [
        "to'layman", "tolayman", "to'lash", "tolash", "to'lay", "tolay",
        "shot", "shot raqam", "shot tashla", "shot raqam tashla", "shotini tashla", "shot ber", "shotini ber",
        "rekvizit", "qayerga to'lay", "qayerga tolay", "qayerga to'lash",
        "тўлайман", "толайман", "шот ташла", "реквизит ташла"
    ])
    has_monthly = any(w in t for w in ["oylik", "abonent", "mars", "ойлик", "абонент", "марс"])
    if has_annual and has_pay and not has_monthly:
        return True

    # 2. Agar foydalanuvchi yaqinda yillik qarz tekshirgan bo'lsa va endi to'lashini aytsa
    if last_topic in ("annual_debt_exists", "awaiting_fiscal_module", "annual_check"):
        general_pay_phrases = [
            "to'layman", "tolayman", "to'lashim kerak", "tolashim kerak", "to'lay", "tolay",
            "shot raqam tashla", "shot tashla", "shot raqam", "shotini ber", "shot ber", "shotini tashla",
            "rekvizit tashla", "rekvizit ber", "qayerga to'layman", "qayerga tolayman",
            "qayerga to'lash", "hisob raqam tashla", "qanday to'layman", "qanday tolayman",
            "тўлайман", "толайман", "шот ташла", "шот беринг"
        ]
        if any(w in t for w in general_pay_phrases) or any(w in t for w in ["shot", "shotini", "rekvizit", "to'layman", "tolayman"]):
            return True

    return False


def is_monthly_pay_intent(text: str, last_topic: Optional[str] = None) -> bool:
    """Foydalanuvchi oylik to'lov uchun hisob raqam (shot) so'rayaptimi yoki to'lashini aytmoqdami?"""
    if classify_payment_intent(text) == "both":
        return False
    t = text.lower().strip()

    # 1. Aniq oylik to'lov so'rovi
    has_annual = any(w in t for w in ["yillik", "fiskal", "soliq", "ofd", "yangi texnologiyalar", "йиллик", "фискал", "солиқ", "солик", "офд"])
    has_monthly = any(w in t for w in ["oylik", "abonent", "mars", "ойлик", "абонент", "марс"])
    has_pay = any(w in t for w in [
        "to'layman", "tolayman", "to'lash", "tolash", "to'lay", "tolay",
        "shot", "shot raqam", "shot tashla", "shot raqam tashla", "shotini tashla", "shot ber", "shotini ber",
        "rekvizit", "qayerga to'lay", "qayerga tolay", "qayerga to'lash",
        "тўлайман", "толайман", "шот ташла", "реквизит ташла"
    ])
    if has_monthly and has_pay and not has_annual:
        return True

    # 2. Agar foydalanuvchi yaqinda oylik qarz tekshirgan bo'lsa va endi to'lashini aytsa
    if last_topic in ("monthly_debt_exists", "debt_checked", "awaiting_inn_for_monthly_debt"):
        general_pay_phrases = [
            "to'layman", "tolayman", "to'lashim kerak", "tolashim kerak", "to'lay", "tolay",
            "shot raqam tashla", "shot tashla", "shot raqam", "shotini ber", "shot ber", "shotini tashla",
            "rekvizit tashla", "rekvizit ber", "qayerga to'layman", "qayerga tolayman",
            "qayerga to'lash", "hisob raqam tashla", "qanday to'layman", "qanday tolayman",
            "тўлайман", "толайман", "шот ташла", "шот беринг"
        ]
        if any(w in t for w in general_pay_phrases) or any(w in t for w in ["shot", "shotini", "rekvizit", "to'layman", "tolayman"]):
            return True

    return False


def format_ofd_annual_status(fm_code: str, ofd_text: Optional[str], script: str = "latin") -> str:
    """@ofd943_bot javobini tahlil qilib, qisqa va aniq qarz bor/yo'qligini xabar qilish"""
    from translit_manager import adapt_to_user_script

    if not ofd_text:
        res = (
            f"🏛 <b>Fiskal modul:</b> <code>{fm_code}</code>\n\n"
            f"⏳ Davlat Soliq (OFD) tizimi bilan vaqtincha aloqa o'rnatib bo'lmadi.\n"
            f"📌 <b>Apparatni tekshirish uchun:</b>\n"
            f"1️⃣ Agar Yillik Soliq (440 000 so'm) to'langan bo'lsa, apparatda internet va soat/sana to'g'riligini tekshiring;\n"
            f"2️⃣ Kassa dasturidan to'liq chiqib qayta kiring yoki apparatni o'chirib qayta yoqing (Перезагрузка / Reboot).\n\n"
            f"💳 <i>Yillik to'lov rekvizitlari kerak bo'lsa, «Shot raqam» deb yozing.</i>\n"
            f"🛠 <i>Usta kerak bo'lsa, «Usta kerak» deb yozing.</i>"
        )
        return adapt_to_user_script(res, script)

    lower = ofd_text.lower()

    if "bunday fiskal modul" in lower or ("mavjud emas" in lower and "bunday" in lower) or "topilmadi" in lower:
        res = (
            f"❌ <b>Fiskal modul topilmadi:</b> <code>{fm_code}</code>\n\n"
            f"Soliq (OFD) tizimida bunday fiskal modul raqami ro'yxatda yo'q. "
            f"Iltimos, kassa chekining eng pastki qismidagi seriya raqamini to'g'ri kiritganingizni tekshirib qaytadan yuboring.\n"
            f"Masalan: <code>LG420210630789</code> yoki <code>UZ200701040469</code>."
        )
        return adapt_to_user_script(res, script)

    has_no_debt = any(w in lower for w in [
        "qarzdorlik mavjud emas", "qarzdorlik yo'q", "qarzdorlik yo‘q", "qarzi yo'q", "qarzi yo‘q"
    ]) or ("mavjud emas" in lower and "fiskal modul" not in lower)

    is_debt = (not has_no_debt) and any(w in lower for w in [
        "qarzdorlik mavjud", "fmo dan qarzdorlik", "qarzdorlik bor", "qarzdorlik",
        "to‘lov qilish muddati", "to'lov qilish muddati", "muddati o‘tgan", "muddati o'tgan"
    ])

    clean_summary = ofd_text.strip()

    if is_debt:
        res = (
            f"🔴 <b>Yillik Soliq (OFD) to'lovidan QARZDORLIK MAVJUD!</b>\n\n"
            f"🏛 <b>Fiskal modul:</b> <code>{fm_code}</code>\n"
            f"📋 <b>OFD tizimi xabari:</b>\n<i>{clean_summary}</i>\n\n"
            f"💰 <b>To'lov summasi:</b> <b>440 000 so'm</b> (1 yilga)\n\n"
            f"💳 <b>To'lash uchun:</b> <b>«To'layman»</b> yoki <b>«Shot raqam»</b> deb yozing, to'lov rekvizitlarini yuboraman."
        )
    else:
        res = (
            f"🟢 <b>Yillik Soliq (OFD) to'lovidan QARZDORLIK YO'Q!</b>\n\n"
            f"🏛 <b>Fiskal modul:</b> <code>{fm_code}</code>\n"
            f"✅ <b>OFD holati:</b>\n<i>{clean_summary}</i>\n\n"
            f"ℹ️ Kassa apparatingiz Davlat Soliq Qo'mitasi (OFD) bazasida faol holatda va yillik to'lov muddati joyida.\n\n"
            f"📌 Agar apparat chek urmayotgan bo'lsa, internet (Wi-Fi/SIM) va soat/sanani tekshirib, apparatni o'chirib yoqing (Reboot)."
        )

    return adapt_to_user_script(res, script)
