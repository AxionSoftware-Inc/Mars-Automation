import logging
import os
import re
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# =============================================================================
# 1. TASHKILOTLAR VA HISOB RAQAMLAR (OYLIK VA YILLIK TO'LOVLAR)
# =============================================================================

SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID", "-1001641871516"))  # @POS_Terminal_UzSmart_Bank
EXCEL_CHANNEL_ID = int(os.getenv("EXCEL_CHANNEL_ID", "-1001795471853"))  # Абонент тулови🏦💸💰
EXCEL_FORWARD_CHANNEL_ID = int(os.getenv("EXCEL_FORWARD_CHANNEL_ID", os.getenv("OYLIK_ABONIT_GROUP_ID", "-1004405333505")))  # Oylik abanit guruhi

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
FISKAL_MODUL_SAMPLE_POST_ID = 149          # Chekdan Fiskal modul va INN topish namunasi (rasmli post)


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


PAYMENT_METHODS_KEYWORDS = [
    "qanday to'layman", "qanday tolayman", "qanaqa to'layman", "qanaqa tolayman",
    "qanday to'lanadi", "qanday tolanadi", "qanday tulanadi",
    "qanday to'lasa bo'ladi", "qanday tolasa boladi", "qanday tulasa boladi",
    "click orqali to'lash", "click orqali tolash", "clickdan to'lash", "clickdan tolash",
    "click orqali qanday", "kartadan to'lash", "plastikdan to'lash", "to'lash tartibi",
    "qanday to'lasam bo'ladi", "qanday tolasam boladi", "to'lov qilish tartibi",
    "to'lash videosi", "tolash videosi", "to'lashni o'rgating", "tolashni orgating",
    "қандай тўланади", "кандай толанади", "қандай тўлайман", "тўлаш тартиби", "тўлаш видеоси"
]


# =============================================================================
# 1.3 KANAL DISPETCHERI VA HISOB RAQAM POSTLARINI UZATISH (MARKAZIY DISPATCHER)
# =============================================================================

async def send_channel_message(
    bot: Any,
    chat_id: int,
    message_id: int,
    reply_to_message_id: Optional[int] = None,
    fallback_text: Optional[str] = None,
    parse_mode: str = "HTML"
) -> bool:
    """Rasmiy kanaldan postni nusxalash, agar muammo bo'lsa fallback matnni yuborish"""
    try:
        kwargs = {}
        if reply_to_message_id:
            kwargs["reply_to_message_id"] = reply_to_message_id
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=SOURCE_CHANNEL_ID,
            message_id=message_id,
            **kwargs
        )
        return True
    except Exception as e:
        logger.warning(f"Kanal postini ({message_id}) nusxalashda xatolik: {e}")
        if fallback_text:
            try:
                await bot.send_message(chat_id=chat_id, text=fallback_text, parse_mode=parse_mode)
            except Exception as e2:
                logger.error(f"Fallback matnni yuborishda ham xatolik: {e2}")
        return False


async def send_monthly_account_post(
    bot: Any,
    chat_id: int,
    reply_to_message_id: Optional[int] = None,
    send_video: bool = False,
    script: str = "latin"
) -> bool:
    """85-post (Mars oylik abonent shoti) va faqat so'ralganda 148-videoni yuborish"""
    from translit_manager import adapt_to_user_script
    fallback = adapt_to_user_script(get_monthly_payment_card(), script)
    ok = await send_channel_message(bot, chat_id, MARS_POST_ID, reply_to_message_id=reply_to_message_id, fallback_text=fallback)
    if send_video:
        await send_channel_message(bot, chat_id, MARS_VIDEO_ID)
    return ok


async def send_annual_account_post(
    bot: Any,
    chat_id: int,
    reply_to_message_id: Optional[int] = None,
    send_video: bool = False,
    script: str = "latin"
) -> bool:
    """34-post (Yangi Texnologiyalar yillik shoti) va faqat so'ralganda 145-videoni yuborish"""
    from translit_manager import adapt_to_user_script
    fallback = adapt_to_user_script(get_annual_payment_card(), script)
    ok = await send_channel_message(bot, chat_id, YANGI_TEXNOLOGIYALAR_POST_ID, reply_to_message_id=reply_to_message_id, fallback_text=fallback)
    if send_video:
        await send_channel_message(bot, chat_id, YANGI_TEXNOLOGIYALAR_VIDEO_ID)
    return ok


async def send_both_account_posts(
    bot: Any,
    chat_id: int,
    reply_to_message_id: Optional[int] = None,
    script: str = "latin"
) -> bool:
    """Ikkala postni (85 va 34) ketma-ket uzatish"""
    from translit_manager import adapt_to_user_script
    fb_month = adapt_to_user_script(get_monthly_payment_card(), script)
    fb_ann = adapt_to_user_script(get_annual_payment_card(), script)
    ok1 = await send_channel_message(bot, chat_id, MARS_POST_ID, reply_to_message_id=reply_to_message_id, fallback_text=fb_month)
    ok2 = await send_channel_message(bot, chat_id, YANGI_TEXNOLOGIYALAR_POST_ID, fallback_text=fb_ann)
    return ok1 and ok2


async def send_fiscal_sample_post(
    bot: Any,
    chat_id: int,
    reply_to_message_id: Optional[int] = None
) -> bool:
    """Fiskal modul chek namunasini (149-post) uzatish"""
    return await send_channel_message(bot, chat_id, FISKAL_MODUL_SAMPLE_POST_ID, reply_to_message_id=reply_to_message_id)


async def send_how_to_pay_video(
    bot: Any,
    chat_id: int,
    account_type: str = "monthly",
    reply_to_message_id: Optional[int] = None
) -> bool:
    """Faqat 'qanday to'lanadi' so'rovi bo'lganda tegishli videoni yuborish"""
    vid_id = YANGI_TEXNOLOGIYALAR_VIDEO_ID if account_type == "annual" else MARS_VIDEO_ID
    return await send_channel_message(bot, chat_id, vid_id, reply_to_message_id=reply_to_message_id)


# =============================================================================
# 2. FORMATLANGAN REKVIZIT KARTALARI
# =============================================================================

def get_monthly_payment_card(script: str = "latin") -> str:
    """Oylik abonent to'lovi (Mars Elektron Texnika) uchun aniq rekvizitlar kartasi"""
    from templates import get_monthly_payment_card as _tpl
    return _tpl(script=script)


def get_annual_payment_card(script: str = "latin") -> str:
    """Yillik fiskal modul to'lovi (Yangi Texnologiyalar DUK) uchun aniq rekvizitlar kartasi"""
    from templates import get_annual_payment_card as _tpl
    return _tpl(script=script)


def get_all_payment_accounts_card(script: str = "latin") -> str:
    """Ikkala hisob raqamni aniq ajratib ko'rsatuvchi to'liq karta"""
    from templates import get_all_payment_accounts_card as _tpl
    return _tpl(script=script)


def get_monthly_post_note(script: str = "latin") -> str:
    """Kanaldan uzatilgan 85-post (Oylik abonent) tagidan yuboriladigan qo'shimcha eslatma"""
    from templates import get_monthly_post_note as _tpl
    return _tpl(script=script)


def get_annual_post_note(script: str = "latin") -> str:
    """Kanaldan uzatilgan 34-post (Yillik fiskal modul) tagidan yuboriladigan qo'shimcha eslatma"""
    from templates import get_annual_post_note as _tpl
    return _tpl(script=script)


def get_both_posts_intro(script: str = "latin") -> str:
    """Ikkala post uzatilishidan oldin adashtirmaslik haqida qat'iy ogohlantirish"""
    from templates import get_both_posts_intro as _tpl
    return _tpl(script=script)


def get_fiscal_module_request_prompt(script: str = "latin") -> str:
    """Yillik to'lovni tekshirish uchun Fiskal modul so'rash va uning nimaligini tushuntirish"""
    from templates import get_fiscal_module_request_prompt as _tpl
    return _tpl(script=script)


# =============================================================================
# 3. MXIK (IKPU - MAHSULOT VA XIZMATLAR KODI) BILIMLAR BAZASI
# =============================================================================

def get_mxik_guidance(query: str = "") -> Tuple[str, int]:
    """
    MXIK (IKPU / Tasnif / Soliq) bo'yicha professional tushuntirish va tegishli video.
    Hech qachon o'zidan 17 xonali kod to'qimaydi, doim tasnif.soliq.uz ga yo'naltiradi.
    Qaytaradi: (tushuntirish_matni, video_post_id)
    """
    from templates import get_mxik_guidance_template as _tpl
    return _tpl(query=query)


# =============================================================================
# 4. SO'ROV VA KVITANSIYA TURLARINI ANIQLASH (DISPATCHER)
# =============================================================================

def _normalize_payment_text(text: str) -> str:
    t = text.lower().strip()
    return t.replace("ʻ", "'").replace("ʼ", "'").replace("‘", "'").replace("’", "'").replace("`", "'")


def classify_payment_intent(text: str) -> Optional[str]:
    """
    Foydalanuvchi xabarida to'lov rekvizitlari so'ralganini aniqlash.
    Qaytaradi:
    - 'annual': Faqat yillik fiskal modul to'lovi rekvizitlari
    - 'monthly': Faqat oylik Mars abonent to'lovi rekvizitlari
    - 'both': Umumiy to'lov / barcha rekvizitlar
    - None: To'lov rekviziti so'ralmagan
    """
    if is_debt_inquiry_or_objection(text):
        return None

    t = _normalize_payment_text(text)

    # Agar savol qarz/tekshirish/muddat/sana, kelgan-kelmaganlik yoki davomiy holat so'rovi ("-kachi", "-danchi", "yillikchi") bo'lsa va unda aniq hisob raqam/shot/rekvizit so'ralmagan bo'lsa -> rekvizit intenti emas!
    if any(w in t for w in [
        "qarz", "tekshir", "bormi", "qarzdorlik", "holat", "sanagacha", "qaysi sana", "muddat", "muddati",
        "qachongacha", "qachon", "vaqti", "vaqt", "kemaganmi", "kelmaganmi", "kemadimi", "kelmadimi",
        "kelganmi", "keldimi", "keldikmi", "chiqmadimi", "chiqmaganmi", "tugaganmi", "tugamaganmi",
        "nima boldi", "nima bo'ldi", "nima gap", "qanaqa", "qanday",
        "yillikkachi", "yilikkachi", "oylikkachi", "yillikdanchi", "oylikdanchi",
        "fiskalchi", "soliqchi", "ofdchi", "fmochi",
        "йилликкачи", "ойликкачи", "йилликданчи", "ойликданчи",
        "кемаганми", "келмаганми", "келмадими", "кемадими", "вақти", "қачонгача", "қачон", "муддат",
        "қайси сана", "санагача", "қарз", "борми", "текшир", "тугаганми", "тугамаганми"
    ]):
        if not any(w in t for w in ["shot", "rekvizit", "xisob", "hisob raqam", "shotini", "kartasi", "karta", "to'lash uchun", "tolash uchun", "to'lashga", "tolashga", "шот", "реквизит", "ҳисоб", "карта"]):
            return None

    # Standalone holat so'rovlari: "fiskal", "ofd" -> bular rekvizit emas, holat intenti
    if t in (
        "fiskal", "fiskal?", "ofd", "ofd?",
        "фискал", "офд"
    ):
        return None

    # Agar savol qayerdaligi, topish, qayerda yozilgani haqida bo'lsa va to'lov/shot so'ralmagan bo'lsa -> rekvizit intenti emas!
    if any(w in t for w in ["qayerda", "qayerdan", "yozilgan", "topish", "topaman", "topsa", "nima", "haqida", "қаерда", "каерда", "қаердан", "ёзилган"]):
        if not any(w in t for w in ["to'la", "tola", "to'lash", "tolash", "shot", "rekvizit", "xisob", "hisob", "тўла", "тола", "шот"]):
            return None

    # Yillik to'lov alomatlari (Lotin va Kirill)
    is_annual = any(w in t for w in [
        "yillik", "yillik?", "yillikchi", "yillikchi?", "yillikch", "yillikcha",
        "yilik", "yilik?", "yilikchi", "yilikchi?",
        "yillik shot", "yillik hisob", "yillik rekvizit", "fiskal modul shot",
        "fiskal modul hisob", "fiskal modul to'lov shot", "fiskal modul tolov shot",
        "yillik to'lov shot", "yillik tolov shot", "yillik to'lov kartasi", "yillik tolov kartasi",
        "yillik to'lash", "yillik tolash",
        "yillik to'lamoqchi", "yillik tolamoqchi", "yillik tulamoqchi",
        "yillik to'lamoqchiydim", "yillik tolamoqchiydim", "yillik tulamoqchiydim",
        "yillik to'lamoqchidim", "yillik tolamoqchidim", "yillik tulamoqchidim",
        "yillik to'lamoqchi edim", "yillik tolamoqchi edim", "yillik tulamoqchi edim",
        "yillikka to'lamoqchi", "yillikka tolamoqchi", "yillikka tulamoqchi",
        "yillikka to'lamoqchiydim", "yillikka tolamoqchiydim", "yillikka tulamoqchiydim",
        "yillikka to'lamoqchi edim", "yillikka tolamoqchi edim", "yillikka tulamoqchi edim",
        "yillik to'lamoqchiman", "yillik tolamoqchiman", "yillik tulamoqchiman",
        "yillik to'lov qilmoqchi", "yillik tolov qilmoqchi", "yillik tulov qilmoqchi",
        "yillik to'lov qilmoqchiman", "yillik tolov qilmoqchiman",
        "yillik to'lab qo'ymoqchi", "yillik tolab qoymoqchi", "yillik tulab quymoqchi",
        "yillik to'layman", "yillik tolayman", "yillik tulayman",
        "yillik to'lay", "yillik tolay", "yillik tulay",
        "yillik to'lasam", "yillik tolasam", "yillik tulasam",
        "yangi texnologiyalar", "yillik qancha", "yillikka qancha", "yillik to'lov qancha", "yillik tolov qancha",
        "yillik narxi", "yillik narxi qancha", "yillik necha pul", "yillik summa", "440000", "440 000",
        "yillikka qancha to'layman", "yillikka qancha tolayman", "yillik qancha to'layman", "yillik qancha tolayman",
        "йиллик", "йиллик?", "йилликчи", "йилликчи?", "йилликч", "йилликча",
        "йиллик шот", "йиллик ҳисоб", "йиллик хисоб", "йиллик реквизит",
        "фискал модул шот", "фискал модул ҳисоб", "фискал модул хисоб",
        "йиллик тўлов шот", "йиллик толов шот", "янги технологиялар",
        "йиллик тўламоқчи", "йиллик толамокчи", "йиллик туламокчи",
        "йиллик тўламоқчийдим", "йиллик толамокчийдим", "йиллик туламокчийдим",
        "йиллик тўламоқчи эдим", "йиллик толамокчи эдим", "йиллик туламокчи эдим",
        "йилликка тўламоқчи", "йилликка толамокчи", "йилликка туламокчи",
        "йилликка тўламоқчийдим", "йилликка толамокчийдим", "йилликка туламокчийдим",
        "йиллик тўламоқчиман", "йиллик толамокчиман", "йиллик туламокчиман",
        "йиллик тўлайман", "йиллик толайман", "йиллик тўлаш", "йиллик толаш",
        "йиллик тўлай", "йиллик толай", "йиллик тулай",
        "йиллик тўласам", "йиллик толасам", "йиллик туласам",
        "йиллик қанча", "йиллик канча", "йилликка қанча", "йиллик тўлов қанча", "йиллик толов қанча",
        "йиллик неча пул", "йиллик нархи", "йиллик нархи қанча", "йилликка қанча тўлайман", "йилликка қанча толайман"
    ])

    # Oylik to'lov alomatlari (Lotin va Kirill)
    is_monthly = any(w in t for w in [
        "oylik", "oylik?", "oylikchi", "oylikchi?", "oylikch", "oylikcha",
        "oylik shot", "oylik hisob", "oylik rekvizit", "mars hisob", "mars shot",
        "abonent to'lov shot", "abonent tolov shot", "marsga to'lov shot",
        "oylik to'lov shot", "oylik tolov shot", "oylik to'lov kartasi",
        "oylik qancha", "oylikka qancha", "oylik to'lov qancha", "oylik tolov qancha",
        "oylik narxi", "oylik narxi qancha", "oylik necha pul", "oylik summa", "100000", "100 000",
        "oylikka qancha to'layman", "oylikka qancha tolayman", "oylik qancha to'layman", "oylik qancha tolayman",
        "oylik to'lash", "oylik tolash",
        "oylik to'lamoqchi", "oylik tolamoqchi", "oylik tulamoqchi",
        "oylik to'lamoqchiydim", "oylik tolamoqchiydim", "oylik tulamoqchiydim",
        "oylik to'lamoqchidim", "oylik tolamoqchidim", "oylik tulamoqchidim",
        "oylik to'lamoqchi edim", "oylik tolamoqchi edim", "oylik tulamoqchi edim",
        "oylikka to'lamoqchi", "oylikka tolamoqchi", "oylikka tulamoqchi",
        "oylikka to'lamoqchiydim", "oylikka tolamoqchiydim", "oylikka tulamoqchiydim",
        "oylikka to'lamoqchi edim", "oylikka tolamoqchi edim", "oylikka tulamoqchi edim",
        "oylik to'lov qilmoqchi", "oylik tolov qilmoqchi", "oylik tulov qilmoqchi",
        "oylik to'lov qilmoqchiman", "oylik tolov qilmoqchiman",
        "oylik to'lab qo'ymoqchi", "oylik tolab qoymoqchi", "oylik tulab quymoqchi",
        "oylik to'lamoqchiman", "oylik tolamoqchiman", "oylik tulamoqchiman",
        "oylik to'layman", "oylik tolayman", "oylik tulayman",
        "oylik to'lay", "oylik tolay", "oylik tulay",
        "oylik to'lasam", "oylik tolasam", "oylik tulasam",
        "oylik to'lab", "oylik tolab", "oylik tulab",
        "ойлик", "ойлик?", "ойликчи", "ойликчи?", "ойликч", "ойликча",
        "ойлик шот", "ойлик ҳисоб", "ойлик хисоб", "ойлик реквизит",
        "марс ҳисоб", "марс хисоб", "марс шот", "абонент тўлов шот",
        "ойлик тўламоқчи", "ойлик толамокчи", "ойлик туламокчи",
        "ойлик тўламоқчийдим", "ойлик толамокчийдим", "ойлик туламокчийдим",
        "ойлик тўламоқчи эдим", "ойлик толамокчи эдим", "ойлик туламокчи эдим",
        "ойликка тўламоқчи", "ойликка толамокчи", "ойликка туламокчи",
        "ойликка тўламоқчийдим", "ойликка толамокчийдим", "ойликка туламокчийдим",
        "ойлик тўламоқчиман", "ойлик толамокчиман", "ойлик туламокчиман",
        "ойлик тўлайман", "ойлик толайман", "ойлик тулайман",
        "ойлик тўлай", "ойлик толай", "ойлик тулай",
        "ойлик тўласам", "ойлик толасам", "ойлик туласам",
        "ойлик тўлаш", "ойлик толаш",
        "ойлик қанча", "ойликка қанча", "ойлик тўлов қанча", "ойлик толов қанча",
        "ойлик неча пул", "ойлик нархи", "ойлик нархи қанча", "ойликка қанча тўлайман", "ойликка қанча толайман"
    ])

    has_annual = any(w in t for w in ["yillik", "fiskal", "soliq", "ofd", "yangi texnologiyalar", "йиллик", "фискал", "солиқ", "солик", "офд"])
    has_monthly = any(w in t for w in ["oylik", "abonent", "mars", "ойлик", "абонент", "марс"])
    has_pay = any(w in t for w in [
        "shot", "hisob", "hsob", "schet", "rekvizit", "to'lov", "tolov", "tulov", "to'lash", "tolash", "tulash",
        "to'lay", "tolay", "tulay", "to'layman", "tolayman", "tulayman",
        "to'lamoqchi", "tolamoqchi", "tulamoqchi",
        "to'lamoqchiydim", "tolamoqchiydim", "tulamoqchiydim",
        "to'lamoqchidim", "tolamoqchidim", "tulamoqchidim",
        "to'lamoqchiman", "tolamoqchiman", "tulamoqchiman",
        "to'lab", "tolab", "tulab", "to'lasam", "tolasam", "tulasam", "qayerga", "qaerga",
        "тўлов", "толов", "тулов", "тўлаш", "толаш", "тулаш", "тўлай", "толай", "тулай",
        "тўлайман", "толайман", "тулайман",
        "тўламоқчи", "толамокчи", "туламокчи",
        "тўламоқчийдим", "толамокчийдим", "туламокчийдим",
        "тўламоқчиман", "толамокчиман", "туламокчиман",
        "тўлаб", "толаб", "тулаб", "тўласам", "толасам", "туласам",
        "шот", "реквизит", "ҳисоб", "хисоб", "счёт", "счет", "қаерга", "каерга"
    ])

    if (has_annual and has_monthly and has_pay) or any(w in t for w in ["ikkala shot", "ikkala hisob", "ikkala to'lov", "ikkala tolov", "иккала шот", "иккала ҳисоб", "иккала тўлов"]):
        return "both"

    if (is_annual or (has_annual and has_pay)) and not (is_monthly or (has_monthly and has_pay)):
        return "annual"
    if (is_monthly or (has_monthly and has_pay)) and not (is_annual or (has_annual and has_pay)):
        return "monthly"


    # Umumiy rekvizit yoki to'lov so'rovlari (Lotin va Kirill)
    general_payment_words = [
        "shot raqam", "shot raqamlar", "hisob raqam", "hisob raqamlar", "hisob raqamlarni",
        "hsob raqam", "hsob raqamlar", "hsob raqamlarni", "hsob",
        "shot tashla", "shot tashlab", "shot tashlab ber", "shot tashlab beriyla", "shot tashlab berilar",
        "shot tashlang", "shot tashvorin", "shot tashvor", "shot ber", "shot bering", "shot beriyla", "shot berilar",
        "shot rekvizit", "shot rekvizitlar", "rekvizit tashla", "rekvizit tashlab ber", "rekvizit ber", "rekvizit bering",
        "hisob raqam tashla", "hisob raqam ber", "hisob raqam bering",
        "rekvizit", "rekvizitlar", "/tolov", "to'lov qilish tartibi",
        "to'lamoqchiman", "tolamoqchiman", "tulamoqchiman", "to'lamoqchi edim", "tulamoqchi edim",
        "to'lab qo'ymoqchiman", "tolab qoymoqchiman", "tulab quymoqchiman",
        "to'lab qo'yay", "tulab quyay", "to'lab quyay", "to'lab quymoqchi",
        "qayerga to'lov", "qayerga tolov", "qayerga tulov",
        "qayerga to'lov qilaman", "qayerga tolov qilaman", "qayerga tulov qilaman",
        "qayerga to'lov qilish", "qayerga tolov qilish", "qayerga tulov qilish",
        "qayerga to'layman", "qayerga tolayman", "qayerga to'lash kerak", "qayerga tolash kerak",
        "qayerga to'lashim kerak", "qayerga tolashim kerak", "qayerga to'lashim kk", "qayerga tolashim kk",
        "qayerga to'lay", "qayerga tolay", "qayerga tulay", "qayerga to'lash", "qayerga tolash", "qayerga tulash",
        "qayerga to'lasam bo'ladi", "qayerga tolasam boladi", "qayerga tolanadi", "qayerga to'lanadi",
        "qayerga o'tkazaman", "qayerga otkazaman", "qayerga tashlayman", "qayerga tashlay",
        "qaerga to'layman", "qaerga tolayman", "qaerga tolash kerak", "qaerga to'lash kerak",
        "qaerga to'lov", "qaerga tolov", "qaerga to'lay", "qaerga tolay",
        "bank rekvizitlari", "to'lov hisobi", "shotini ber", "to'lov uchun shot", "tolov uchun shot",
        "hisob bering", "schet bering", "schet tashlang", "schet tashla",
        "шот рақам", "шот рақамлар", "ҳисоб рақам", "хисоб ракам",
        "ҳисоб рақамлар", "хисоб ракамлар", "хисоб ракамларни", "реквизит", "реквизитlar", "реквизитлар",
        "шот ташла", "шот ташлаб бер", "шот ташлаб берийла", "шот ташланг", "шот беринг", "шот бер",
        "реквизит ташла", "реквизит беринг", "реквизит бер",
        "тўламоқчиман", "толамокчиман", "туламокчиман", "тўлаб қўймоқчиман", "тулаб куймокчиман",
        "тўлов қилиш тартиби", "толов килиш тартиби", "қаерга тўлайман", "каерга толайман",
        "қаерга тўлов", "каерга толов", "қаерга тўлов қиламан", "каерга толов киламан",
        "қаерга тўлаш керак", "каерга толаш керак", "қаерга тўлашим керак", "каерга толашим керак",
        "қаерга тўлай", "каерга толай", "қаерга тўлаш", "каерга толаш",
        "банк реквизитлари", "тўлов ҳисоби", "толов хисоби", "шотини бер",
        "счёт беринг", "счет беринг", "счёт ташланг", "счет ташланг",
        "тўлов учун счёт", "толов учун счет",
        "тўлов учун ҳисоб", "толов учун хисоб", "тўлов учун шот", "толов учун шот"
    ]
    if any(w in t for w in general_payment_words) or (is_annual and is_monthly):
        return "both"

    if t in ("shot", "rekvizit", "hisob", "hsob", "schet", "шот", "реквизит", "ҳисоб", "хисоб", "счёт", "счет"):
        return "both"

    return None


def is_mxik_intent(text: str) -> bool:
    """Matn MXIK / IKPU / Tasnif / Tovar qo'shish / Soliq kodi mavzusiga tegishlimi?"""
    t = text.lower().strip()
    mxik_words = [
        "mxik", "mixk", "мхик", "михк", "ikpu", "икпу",
        "mixik", "mixni", "mixini", "mixikni", "mexik", "mexikni",
        "михик", "михни", "мехик",
        "tasnif", "tasnif.soliq", "тасниф",
        "soliq saytidan kod", "soliq saytidan", "soliqdan kod",
        "tovar qo'shish", "tovar qushish", "tovar kiritish",
        "tovarga kod", "mxik kod", "mxik nima", "mxik xatosi",
        "mxik jarima", "mxik qayerdan", "tovar kodi", "tovar kodlari",
        "mahsulot kodi", "xizmat kodi", "kod qayerdan", "kodini qayerdan",
        "tovarlar bazasi", "tovar bazasi", "baza yuklash", "bazani yuklash",
        "exceldan tovar", "excel tovar", "otkaz qilish", "chekni bekor",
        "tovarni bekor", "qqs stavka", "soliq stavka",
        "tamaki", "sigaret", "alkogol", "zapravka",
        "тамаки", "сигарет", "алкогол", "заправка",
        "солиқ сайтидан", "солиқ сайтидан код", "товар қўшиш", "товар киритиш",
        "товар коди", "товар кодлари", "код қаердан", "кодини қаердан",
        "база юклаш", "товарлар базаси", "бекор қилиш", "отказ қилиш"
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
    if is_mxik_intent(text) or is_debt_inquiry_or_objection(text):
        return False

    t = _normalize_payment_text(text)

    # Agar aniq hisob raqam / shot / karta so'ralayotgan bo'lsa va tekshirish/qarz so'zi bo'lmasa -> bu to'lov kartasi so'rovi!
    if any(w in t for w in ["shot", "shotini", "rekvizit", "hisob raqam", "xisob", "karta", "kartasi", "шот", "реквизит", "ҳисоб", "карта"]):
        if not any(w in t for w in ["qarz", "tekshir", "bormi", "qarzdorlik", "holat", "қарз", "борми", "текшир"]):
            return False

    # Agar narx yoki summa so'ralayotgan bo'lsa ("qancha", "necha pul", "narxi") va qarz/tekshir so'zi bo'lmasa -> bu to'lov summasi/kartasi so'rovi!
    if any(w in t for w in ["qancha", "necha pul", "narxi", "summa", "қанча", "неча пул", "нархи", "сумма"]):
        if not any(w in t for w in ["qarz", "tekshir", "bormi", "qarzdorlik", "қарз", "борми", "текшир"]):
            return False

    # Standalone yillik/fiskal holat so'rovi -> mijoz fiskal holatini bilmoqchi
    if t in (
        "fiskal", "fiskal?", "ofd", "ofd?", "fiskalchi", "soliqchi", "ofdchi",
        "фискал", "офд", "фискалчи", "солиқчи", "офдчи"
    ):
        return True
    
    # Tezkor davomiy qarzdorlik iboralari ("yillikdanchi?", "yillikkachi?", "fiskaldanchi?")
    followup_words = [
        "yillikdanchi", "yilikdanchi", "yillikkachi", "yilikkachi", "yillikgachi",
        "fiskaldanchi", "soliqdanchi", "fiskalgachi", "soliqgachi",
        "ofddanchi", "fmodanchi",
        "йилликданчи", "йилликкачи",
        "фискалданчи", "солиқданчи", "офдданчи"
    ]
    if any(w in t for w in followup_words):
        return True

    phrases = [
        "yillik qarz", "yillikni tekshir", "yillik tekshir", "yillikni tekshirib",
        "yillik to'lovni tekshir", "yillik tolovni tekshir", "yillik tulovni tekshir",
        "yillik tulovniyam tekshir", "yillik to'lovniyam tekshir", "yillik tolovniyam tekshir",
        "yillik to'lovim bormi", "yillik tolovim bormi", "yillik tulovim bormi",
        "yillik qarzim bormi", "yillik qarzdorlik", "yillik muddat", "yillik holati",
        "yillikni qayta tekshir", "yillik qayta tekshir", "yillik to'lov", "yillik tolov", "yillik tulov",
        "yillik to'lov haqida", "yillik tolov haqida", "yillik haqida", "yillik tolovim", "yillik to'lovim",
        "yillikka kemaganmi", "yillikka kelmaganmi", "yillikka kemadimi", "yillikka kelmadimi",
        "yillikdan kemaganmi", "yillikdan kelmaganmi", "yillik kemaganmi", "yillik kelmaganmi",
        "yillik kelmadimi", "yillik kemadimi", "yillik kelganmi", "yillik keldimi",
        "yillikchi nima bo'ldi", "yillikchi nima boldi", "yillik nima bo'ldi", "yillik nima boldi",
        "yillikdan nima gap", "yillik qanaqa", "yillik qanday", "yillik qachon", "yillik vaqti",
        "yillik tugaganmi", "yillik tugamaganmi", "yillik to'lovchi", "yillik tolovchi",
        "yillik tolovga kemaganmi", "yillik to'lovga kelmaganmi", "yillikka to'lashim kerakmi", "yillikka tolashim kerakmi",
        "ofd tekshir", "ofdni tekshir", "ofd qarz", "ofd qarzdorlik", "ofd to'lov", "ofd tolov",
        "soliq qarz", "soliqni tekshir", "fiskal modul tekshir", "fiskal modul muddat",
        "fiskal modulimni tekshir", "fmo qarz", "fmo tekshir", "fiskal to'lov", "fiskal tolov",
        "fiskalchi", "fiskaldan kemaganmi", "fiskal kemaganmi", "soliqchi", "ofdchi",
        "йиллик қарз", "йиллик карз", "йилликни текшир", "йиллик текшир",
        "йиллик тўловни текшир", "йиллик толовни текшир", "офд текшир",
        "йилликка кемаганми", "йилликка келмаганми", "йилликка келмадими", "йилликка кемадими",
        "йилликдан кемаганми", "йилликдан келмаганми", "йиллик нима бўлди", "йиллик муддати", "йиллик вақти",
        "фискал модул текшир", "фискал модул муддат", "фискалчи", "солиқчи", "офдчи"
    ]
    if any(p in t for p in phrases):
        return True

    has_target = any(w in t for w in ["yillik", "yilik", "fiskal", "ofd", "fmo", "soliq", "йиллик", "фискал", "офд", "фмо", "солиқ", "солик"])
    has_action = any(w in t for w in [
        "tekshir", "kurib", "ko'rib", "korib", "qarz", "bormi", "muddat", "holat",
        "to'lov", "tolov", "tulov", "qayta", "qancha", "xabar", "ma'lumot", "malumot",
        "tugaydi", "tugash", "tugagan", "tugamagan", "kemagan", "kelmagan", "kemadi", "kelmadi",
        "kelgan", "keldi", "keldik", "vaqt", "vaqti", "chiqdi", "chiqmadi", "chiqmagan", "nima", "qanaqa", "qanday",
        "провер", "текшир", "қарз", "карз", "борми", "муддат", "ҳолат", "холат", "тўлов", "толов",
        "кемаган", "келмаган", "келмади", "кемади", "вақти", "тугаган", "тугамаган"
    ])
    return has_target and has_action


def is_monthly_check_intent(text: str) -> bool:
    """Foydalanuvchi oylik abonent to'lovi (Mars) qarzdorligini tekshirishni so'rayaptimi?"""
    if is_mxik_intent(text) or is_debt_inquiry_or_objection(text):
        return False

    t = _normalize_payment_text(text)

    # Agar aniq hisob raqam / shot / karta so'ralayotgan bo'lsa va tekshirish/qarz so'zi bo'lmasa -> bu to'lov kartasi so'rovi!
    if any(w in t for w in ["shot", "shotini", "rekvizit", "hisob raqam", "xisob", "karta", "kartasi", "шот", "реквизит", "ҳисоб", "карта"]):
        if not any(w in t for w in ["qarz", "tekshir", "bormi", "qarzdorlik", "holat", "қарз", "борми", "текшир"]):
            return False

    # Agar narx yoki summa so'ralayotgan bo'lsa ("qancha", "necha pul", "narxi") va qarz/tekshir so'zi bo'lmasa -> bu to'lov summasi/kartasi so'rovi!
    if any(w in t for w in ["qancha", "necha pul", "narxi", "summa", "қанча", "неча пул", "нархи", "сумма"]):
        if not any(w in t for w in ["qarz", "tekshir", "bormi", "qarzdorlik", "қарз", "борми", "текшир"]):
            return False

    # Standalone oylik/mars holat so'rovi -> mijoz oylik holatini bilmoqchi
    if t in (
        "mars", "abonent",
        "марс", "абонент"
    ):
        return True

    # Tezkor davomiy qarzdorlik iboralari ("oylikdanchi?", "oylikkachi?", "marsdanchi?")
    followup_words = [
        "oylikdanchi", "oylikdanam", "oylikdan-chi", "oylikkachi", "oylikgachi",
        "marsdanchi", "abonentdanchi",
        "ойликданчи", "ойликкачи", "ойликданам",
        "марсданчи", "абонентданчи"
    ]
    if any(w in t for w in followup_words):
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
    if is_debt_inquiry_or_objection(text):
        return False
    t = _normalize_payment_text(text)
    phrases = [
        "ikkalasidanchi", "ikkalasidan", "ikkala tolov", "ikkala to'lov", "ikkalasiyam",
        "ikkala tolovdan", "ikkala to'lovdan", "umumiy qarz", "umumiy qarzim",
        "jami qarz", "jami qarzim", "barcha qarz", "qarzlarim bormi", "qarzlarimni tekshir",
        "qarzlar bormi", "har ikkala", "ikkisi ham", "ikkisidan",
        "иккаласиданчи", "иккаласидан", "умумий қарз", "жами қарз", "қарзларим борми"
    ]
    return any(p in t for p in phrases)


def is_general_debt_check_intent(text: str) -> bool:
    """
    Foydalanuvchi umumiy yoki aniqlashtirilmagan qarz haqida so'rayaptimi?
    (Masalan: 'qarzm bormi', 'qancha qarzim bor', 'qarzim qancha', 'qarzdorligim bormi', 'qancha tolay', 'qarz bormi')
    """
    t = _normalize_payment_text(text)
    # Hisob raqam so'rovi bo'lsa va tekshir/qancha so'zi bo'lmasa -> bu to'lov intenti
    if any(w in t for w in ["shot", "rekvizit", "hisob raqam", "xisob raqam", "shotini", "kartasi", "шот", "реквизит"]):
        if not any(w in t for w in ["qarz", "qarzdor", "qancha", "bormi", "текшир", "қарз"]):
            return False

    phrases = [
        "qarzm bormi", "qarzim bormi", "qarzdorligim bormi", "qarzdorlik bormi", "qarz bormi",
        "qancha qarzim bor", "qancha qarzm bor", "qancha qarzman", "qancha qarz",
        "qarzim qancha", "qarzm qancha", "qancha tolay", "qancha to'lay", "qancha to'lashim kerak",
        "qancha tolashim kerak", "qancha to'lashim kk", "qancha tolashim kk",
        "qancha to'layman", "qancha tolayman", "qarzni tekshir",
        "qarz tekshir", "qarzimni tekshir", "qarzdorlikni tekshir", "qarzim bormi yoqmi",
        "qarzim bormi yo'qmi", "qarz bormi yoqmi", "qarz bormi yo'qmi", "qarz holati",
        "qaysi inn boyicha qarz bor", "qaysi inn bo'yicha qarz bor", "qaysi inn",
        "қарзм борми", "қарзим борми", "қарздорлигим борми", "қарздорлик борми", "қарз борми",
        "қанча қарзим бор", "қанча қарзм бор", "қанча қарзман", "қанча қарз",
        "қарзим қанча", "қарзм қанча", "қанча тўлай", "қанча толай", "қанча тўлашим керак",
        "қарзни текшир", "қарз текшир", "қарзимни текшир"
    ]
    if any(p in t for p in phrases):
        return True

    # Standalone yoki qisqa so'zlar
    if t in ("qarz", "qarzim", "qarzm", "qarzdorlik", "qarzimchi", "qarzchi", "qarzmi", "qarzimmi", "қарз", "қарзим", "қарздорлик"):
        return True

    has_debt_word = any(w in t for w in ["qarz", "qarzdor", "qarzm", "қарз", "қарздор"])
    has_question_word = any(w in t for w in [
        "bormi", "qancha", "qanaqa", "holat", "tekshir", "ko'r", "kor", "ayt", "nechi", "necha",
        "борми", "қанча", "қанақа", "ҳолат", "холат", "текшир", "кўр", "айт", "?"
    ])
    if has_debt_word and has_question_word:
        return True

    return False


def is_debt_inquiry_or_objection(text: str) -> bool:
    """
    Foydalanuvchi qarzdan e'tiroz/norozilik bildirayotganini yoki to'lov tarixini so'rayotganini aniqlash.
    (Masalan: 'tulaganmanku', 'to'lagandimku', 'nimaga qarzga chiqdi', 'to'laganmizku', 'to'lov tarixi' va h.k.)
    Bu holatda kvitansiya so'ramay, oylik to'lovlar tarixini lo'nda va aniq ro'yxat qilib chiqarish lozim!
    """
    if not text:
        return False
    t = _normalize_payment_text(text)

    # 1. Aniq e'tiroz va norozilik iboralari (-ku bilan yoki to'langanligi e'tirozi)
    objection_phrases = [
        # Lotin
        "to'laganmanku", "tolaganmanku", "tulaganmanku", "tölaganmanku", "tòlaganmanku",
        "to'lagandimku", "tolagandimku", "tulagandimku", "to'lagandim-ku", "tolagandim-ku",
        "to'ladimku", "toladimku", "tuladimku", "to'ladim-ku", "toladim-ku",
        "to'ladikku", "toladikku", "tuladikku", "to'ladik-ku",
        "to'laganmizku", "tolaganmizku", "tulaganmizku", "to'lagandikku", "tolagandikku",
        "to'lagan edimku", "tolagan edimku", "tulagan edimku", "to'lagan edikku", "tolagan edikku",
        "to'langan ediku", "tolangan ediku", "to'langaniku", "tolanganiku", "to'langanku", "tolanganku",
        "to'langan edi", "tolangan edi", "to'lagan edim", "tolagan edim",
        "to'lov qilganmanku", "tolov qilganmanku", "tulov qilganmanku",
        "to'lov qilgandimku", "tolov qilgandimku", "tulov qilgandimku",
        "to'lov qildimku", "tolov qildimku", "tulov qildimku",
        "to'lab bo'lganmanku", "tolab bolganmanku", "to'lab qo'yganmanku", "tolab qoyganmanku",
        "to'lab bo'lgandimku", "tolab bolgandimku", "to'lab qo'ygandimku", "tolab qoygandimku",
        "pul o'tkazganmanku", "pul otkazganmanku", "pul to'laganmanku", "pul tolaganmanku",
        "pul to'ladimku", "pul toladimku", "pul tuladimku", "pul o'tkazdimku", "pul otkazdimku",
        "to'lagandima", "tolagandima", "tulagandima", "to'laganmanu", "tolaganmanu",
        "to'laganman axir", "tolaganman axir", "to'lagandik axir",

        # Nimaga / nega / qayerdan qarzga chiqdi
        "nimaga qarzga chiqdi", "nega qarzga chiqdi", "qayerdan qarzga chiqdi", "qanaqasiga qarzga chiqdi",
        "nimaga qarz chiqdi", "nega qarz chiqdi", "qayerdan qarz chiqdi",
        "nimaga qarz bo'ldi", "nega qarz bo'ldi", "nimaga qarz boldi", "nega qarz boldi",
        "nimaga qarz chiqyapti", "nega qarz chiqyapti", "nimaga qarz chiqvotti", "nega qarz chiqvotti",
        "nimaga qarz ko'rsatyapti", "nega qarz korsatyapti", "nimaga qarz beryapti", "nega qarz beryapti",
        "nimaga qarz", "nega qarz", "qayerdan qarz", "qanaqa qarz", "qanaqasiga qarz", "qanaqa qarz bu",
        "qayerdan kelib chiqdi", "qayerdan chiqdi", "qayerdan bu qarz", "qayerdan keldi bu qarz",
        "qarzim yo'qku", "qarzim yoqku", "qarzim yuqku", "qarz yo'qku", "qarz yoqku", "qarz yuqku",
        "qarz emas ediku", "qarzmas ediku", "qarzmasku", "qarz emasku",
        "qarzim yo'q edi", "qarzim yoq edi", "qarz yo'q edi",
        "summa noto'g'ri", "summa notogri", "noto'g'ri qarz", "notogri qarz", "xato qarz",

        # To'lov tarixi so'rovlari
        "to'lov tarixi", "tolov tarixi", "tulov tarixi", "tarixni ko'rsat", "tarixni korsat", "to'lovlar tarixi",
        "qachon to'laganman", "qachon tolaganman", "qachon to'lagandim", "qachon tolagandim",
        "qachon to'langan", "qachon tolangan", "qachon to'lov qilganman", "qachon tolov qilganman",
        "qaysi oy", "qaysi oylar", "qaysi oyga to'langan", "qaysi oyga tolangan",
        "qaysi oylarga to'langan", "qaysi oylarga tolangan", "qaysi oy uchun qarz", "qaysi oylar uchun qarz",
        "qaysi oylar to'lanmagan", "qaysi oylar tolanmagan", "qaysi oylardan qarz",

        # Kirill
        "тўлаганманку", "тулаганманку", "толаганманку",
        "тўлагандимку", "тулагандимку", "толагандимку",
        "тўладимку", "туладимку", "толадимку",
        "тўладикку", "туладикку", "толадикку",
        "тўлаганмизку", "тулаганмизку", "толаганмизку",
        "тўланганку", "туланганку", "толанганку",
        "тўланган эдику", "туланган эдику", "тўлаган эдикку",
        "тўланган эди", "туланган эди", "тўлаган эдим",
        "тўлов қилганманку", "тулов килганманку",
        "тўлов қилдимку", "тулов килдимку",
        "пул тўладимку", "пул тўлаганманку", "пул ўтказганманку", "пул утказганманку",
        "нимага қарзга чиқди", "нега қарзга чиқди", "қаердан қарзга чиқди", "қанақасига қарзга чиқди",
        "нимага қарз чиқди", "нега қарз чиқди", "қаердан қарз чиқди",
        "нимага қарз бўлди", "нега қарз бўлди", "нимага қарз бўляпти", "нега қарз бўляпти",
        "нимага қарз кўрсатяпти", "нега қарз кўрсатяпти",
        "нимага қарз", "нега қарз", "қаердан қарз", "қанақа қарз", "қанақасига қарз",
        "қаердан келиб чиқди", "қаердан чиқди", "қаердан бу қарз",
        "қарзим йўқку", "қарзим йукку", "қарз йўқку", "қарз йукку",
        "қарз эмас эдику", "қарзмаску", "сумма нотўғри", "нотўғри қарз",
        "тўлов тарихи", "тулов тарихи", "тарихни кўрсат", "тарихни курсат",
        "қачон тўлаганман", "қачон тулаганман", "қайси ойларга тўланган", "қайси ойлар учун қарз"
    ]
    if any(op in t for op in objection_phrases):
        return True

    # 2. To'lov so'zi va qarz/e'tiroz so'zlari birgalikda kelsa
    # Masalan: "to'laganman qarz emas", "qarzim yo'q to'lagandim", "to'lagan edim lekin qarz chiqyapti"
    has_paid_word = any(w in t for w in [
        "to'lagan", "tolagan", "tulagan", "to'lagandim", "tolagandim", "tulagandim",
        "to'lov qilgan", "tolov qilgan", "pul to'lagan", "pul o'tkazgan",
        "тўлаган", "тулаган", "толаган", "тўлагандим", "тулагандим"
    ])
    has_objection_context = any(w in t for w in [
        "qarz", "chiqdi", "chiqyapti", "chiqib", "emas", "yo'q", "yoq", "yuq", "lekin", "ammo", "noto'g'ri",
        "қарз", "чиқди", "чиқяпти", "эмас", "йўқ", "йук", "лекин", "нотўғри"
    ])
    if has_paid_word and has_objection_context:
        return True

    return False


def is_payment_claim(text: str) -> bool:
    """
    Foydalanuvchi to'lov qilinganini bildiruvchi xabar yozganmi?
    (Masalan: 'to'ladim', 'tuladim', 'toladim', 'to'lov qildim', 'pul o'tkazdim', 'to'lab bo'ldik', 'to'lab qo'ydim' va h.k.)

    Qaytaradi: True agar to'lov qilingani da'vo qilinayotgan bo'lsa.
    Bunday holatda agar kvitansiya biriktirilmagan bo'lsa, bot albatta to'lov kvitansiyasini so'rashi shart!
    """
    if not text:
        return False

    # Agar bu qarz e'tirozi yoki to'lov tarixi so'rovi bo'lsa -> bu to'lov da'vosi emas!
    if is_debt_inquiry_or_objection(text):
        return False

    t = _normalize_payment_text(text)

    # 1. Kelgusi zamon yoki to'lash istagi / savol bo'lsa -> bu to'lov da'vosi emas!
    future_or_inquiry = [
        "to'lamoqchi", "tolamoqchi", "tulamoqchi", "to'lamoqchiman", "tolamoqchiman", "tulamoqchiman",
        "to'lamoqchi edim", "tolamoqchi edim", "tulamoqchi edim", "to'lamoqchiydim", "tolamoqchiydim",
        "to'layman", "tolayman", "tulayman", "to'lay", "tolay", "tulay",
        "to'lash kerak", "tolash kerak", "to'lasam", "tolasam", "tulasam", "to'lasak", "tolasak",
        "qanday to'la", "qanday tola", "qayerga to'la", "qayerga tola", "qachongacha to'la", "qachongacha tola",
        "to'lash tartibi", "tolash tartibi", "to'lash videosi", "tolash videosi",
        "тўламоқчи", "толамокчи", "туламокчи", "тўламоқчиман", "толамокчиман", "туламокчиман",
        "тўлайман", "толайман", "тўлай", "толай", "тўлаш керак", "толаш керак",
        "тўласам", "толасам", "туласам", "қаерга тўла", "каерга тола", "қандай тўла", "кандай тола"
    ]
    if any(fi in t for fi in future_or_inquiry):
        return False

    # 2. To'lov qilinganini bildiruvchi aniq iboralar
    exact_phrases = [
        # Lotin
        "to'ladim", "toladim", "tuladim", "tòladim", "töladim",
        "to'ladik", "toladik", "tuladik",
        "to'lab bo'ldim", "tolab boldim", "tulab buldim",
        "to'lab bo'ldik", "tolab boldik", "tulab buldik",
        "to'lab qo'ydim", "tolab qoydim", "tulab quydim",
        "to'lab qo'ydik", "tolab qoydik", "tulab quydik",
        "to'lab qo'yganman", "tolab qoyganman", "to'lab qo'yganmiz", "tolab qoyganmiz",
        "to'lab tashladim", "tolab tashladim", "tulab tashladim",
        "to'lab tashladik", "tolab tashladik", "tulab tashladik",
        "to'lab tashadim", "tolab tashadim", "tulab tashadim",
        "to'lab berdim", "tolab berdim", "tulab berdim",
        "to'lab berdik", "tolab berdik", "tulab berdik",
        "to'lab bo'lganman", "tolab bolganman", "to'lab bo'lganmiz", "tolab bolganmiz",
        "to'lov qildim", "tolov qildim", "tulov qildim",
        "to'lov qildik", "tolov qildik", "tulov qildik",
        "to'lov qilindi", "tolov qilindi", "tulov qilindi",
        "to'lov qilganman", "tolov qilganman", "tulov qilganman",
        "to'lov qilganmiz", "tolov qilganmiz", "tulov qilganmiz",
        "to'lov qilgandim", "tolov qilgandim", "tulov qilgandim",
        "to'lov qilgandik", "tolov qilgandik", "tulov qilgandik",
        "to'lov qilib bo'ldim", "tolov qilib boldim", "tulov qilib buldim",
        "to'lov qilib bo'ldik", "tolov qilib boldik", "tulov qilib buldik",
        "to'lov qilib qo'ydim", "tolov qilib qoydim", "tulov qilib quydim",
        "to'lov o'tkazdim", "tolov otkazdim", "tulov otkazdim",
        "pul o'tkazdim", "pul otkazdim", "pul o'tkazdik", "pul otkazdik",
        "pul o'tkazildi", "pul otkazildi", "pul tashladim", "pul tashladik", "pul tashadim", "pul tashadik",
        "pul tashlab qo'ydim", "pul tashlab qoydim", "pul tashavorganman", "pul tashavorganmiz",
        "pul to'ladim", "pul toladim", "pul tuladim",
        "to'laganman", "tolaganman", "tulaganman",
        "to'lagandim", "tolagandim", "tulagandim", "to'lagandik", "tolagandik",
        "to'langan", "tolangan", "tulangan", "to'langan edi", "tolangan edi",
        "to'landi", "tolandi", "tulandi",
        "shotga tashladim", "shotga tashadik", "shotga pul tashladim",
        "kartaga tashladim", "kartaga pul tashladim",
        "clickdan to'ladim", "clickdan toladim", "clickdan tuladim",
        "paymedan to'ladim", "paymedan toladim", "paymedan tuladim",
        "click qildim", "payme qildim",
        "ertalab to'laganman", "ertalab to'ladim", "kecha to'laganman", "kecha to'ladim",
        "kecha to'lagandim", "kecha tolagandim", "ertalab to'lagandim", "ertalab tolagandim",
        "hozir to'ladim", "hozir toladim", "hozir tuladim",
        "to'lab qo'ygan edim", "tolab qoygan edim", "to'lagan edim", "tolagan edim",
        "to'lov qilib qo'yganman", "tolov qilib qoyganman", "to'lov qiluvdim", "tolov qiluvdim",
        "pul to'lab qo'ydim", "pul tolab qoydim", "pul o'tkazib qo'ydim", "pul otkazib qoydim",
        "mana to'ladim", "mana toladim", "mana tuladim",
        "mana to'ladik", "mana toladik", "mana tuladik",
        "mana to'lov", "mana tolov", "mana tulov",

        # Kirill
        "тўладим", "туладим", "толадим",
        "тўладик", "туладик", "толадик",
        "тўлаб бўлдим", "тулаб булдим", "толаб болдим",
        "тўлаб бўлдик", "тулаб булдик", "толаб болдик",
        "тўлаб қўйдим", "тулаб куйдим", "толаб койдим",
        "тўлаб қўйдик", "тулаб куйдик", "толаб койдик",
        "тўлаб қўйганман", "тулаб куйганман", "тўлаб қўйганмиз", "тулаб куйганмиз",
        "тўлаб ташладим", "тулаб ташладим", "тўлаб ташладик", "тулаб ташладик",
        "тўлаб бердим", "тулаб бердим", "тўлаб бердик", "тулаб бердик",
        "тўлаб бўлганман", "тулаб булганман", "тўлаб бўлганмиз", "тулаб булганмиз",
        "тўлов қилдим", "тулов килдим", "толов килдим", "тулов кылдым",
        "тўлов қилдик", "тулов килдик", "толов килдик",
        "тўлов қилинди", "тулов килинди", "толов килинди",
        "тўлов бўлди", "тулов булди", "толов болди",
        "тўлов қилганман", "тулов килганман", "толов килганман",
        "тўлов қилганмиз", "тулов килганмиз", "толов килганмиз",
        "тўлов қилгандим", "тулов килгандим", "толов килгандим",
        "тўлов қилиб бўлдим", "тулов килиб булдим",
        "тўлов қилиб бўлдик", "тулов килиб булдик",
        "тўлов қилиб қўйдим", "тулов килиб куйдим",
        "пул ўтказдим", "пул откасдим", "пул отказиб куйдим", "пул ўтказдик", "пул откасдик",
        "пул ташладим", "пул ташладик", "пул тўладим", "пул толадим", "пул туладим",
        "тўлаганман", "тулаганман", "толаганман",
        "тўлагандим", "тулагандим", "толагандим", "тўлагандик", "тулагандик",
        "тўланган", "туланган", "тўланди", "туланди",
        "кликдан тўладим", "кликдан туладим", "клик килдим",
        "паймедан тўладим", "паймедан туладим", "пайме килдим",
        "эрталаб тўладим", "кеча тўладим", "кеча тўлагандим", "ҳозир тўладим", "хозир туладим",
        "мана туладим", "мана тўладим", "мана толадим", "тўладим мана",

        # Ruscha
        "оплатил", "оплатила", "оплатили", "я оплатил", "чек оплатил",
        "деньги перевел", "деньги перевели", "перевел деньги", "перевела деньги",
        "оплачено", "перевел"
    ]

    for phrase in exact_phrases:
        if phrase in t:
            return True

    words = t.split()
    single_claim_words = {
        "to'ladim", "toladim", "tuladim", "to'ladik", "toladik", "tuladik",
        "to'ladimku", "toladimku", "tuladimku",
        "to'laganman", "tolaganman", "tulaganman", "to'lagandim", "tolagandim", "tulagandim",
        "to'langan", "tolangan", "tulangan", "to'landi", "tolandi", "tulandi",
        "тўладим", "туладим", "толадим", "тўладик", "туладик", "толадик",
        "тўладимку", "туладимку", "толадимку",
        "тўлаганман", "тулаганман", "толаганман", "тўлагандим", "тулагандим",
        "тўланган", "туланган", "тўланди", "туланди",
        "оплатил", "оплатила", "оплатили"
    }
    if any(w in single_claim_words for w in words):
        return True

    return False


def is_how_to_pay_video_intent(text: str) -> bool:
    """
    Foydalanuvchi qanday to'lashni yoki to'lash videosi/yo'riqnomasini so'rayaptimi?
    (Masalan: 'qanday to'lanadi', 'to'lash videosi', 'qanday to'lash kerak', 'o'rgatilgan video', 'to'lash tartibini o'rgating')
    """
    t = _normalize_payment_text(text)
    
    # Aniq video so'rovlari
    video_words = [
        "video", "videosi", "videoni", "videolar", "videoni tashla", "videoni ber",
        "videoni yubor", "video bormi", "видео", "видеоси", "видеони", "видео ташла"
    ]
    if any(w in t for w in video_words):
        return True
        
    # Aniq 'qanday to'lanadi' va 'o'rgatish' iboralari
    how_to_phrases = [
        "qanday to'lanadi", "qanday tolanadi", "qanday tulanadi",
        "qanday to'lasa bo'ladi", "qanday tolasa boladi", "qanday tulasa boladi",
        "qanday to'lasam bo'ladi", "qanday tolasam boladi", "qanday tulasam boladi",
        "qanday to'lash kerak", "qanday tolash kerak", "qanday tulash kerak",
        "qanday to'layman", "qanday tolayman", "qanday tulayman",
        "qanaqa to'lanadi", "qanaqa tolanadi", "qanaqa to'layman", "qanaqa tolayman",
        "to'lash tartibi", "tolash tartibi", "tulash tartibi",
        "to'lash tartibini", "tolash tartibini", "tulash tartibini",
        "to'lov qilish tartibi", "tolov qilish tartibi",
        "to'lashni o'rgating", "tolashni orgating", "tulashni orgating",
        "to'lashni o'rgat", "tolashni orgat", "to'lash tartibini o'rgat",
        "o'rgating", "orgating", "o'rgatilgan", "orgatilgan", "o'rgatuvchi",
        "ko'rsating", "korsating", "yo'riqnoma", "yoriqnoma", "qo'llanma", "qollanma",
        "click orqali qanday", "clickda qanday", "paymeda qanday",
        "қандай тўланади", "кандай толанади", "кандай туланади",
        "қандай тўласа бўлади", "кандай толаса болади",
        "қандай тўласам бўлади", "кандай толасам болади",
        "қандай тўлаш керак", "кандай толаш керак",
        "қандай тўлайман", "кандай толайман",
        "тўлаш тартиби", "толаш тартиби", "тўлов қилиш тартиби",
        "тўлашни ўргатинг", "толашни ургатинг", "ўргатинг", "ургатинг",
        "кўрсатинг", "йўриқнома", "қўлланма"
    ]
    return any(p in t for p in how_to_phrases)


def is_annual_pay_intent(text: str, last_topic: Optional[str] = None) -> bool:
    """Foydalanuvchi yillik to'lov uchun hisob raqam (shot) so'rayaptimi yoki to'lashini aytmoqdami?"""
    t = _normalize_payment_text(text)

    # Agar savol tekshiruv, kelgan-kelmaganlik yoki holat so'rovi bo'lsa va unda aniq hisob raqam/shot/rekvizit so'ralmagan bo'lsa -> to'lov intenti emas!
    if any(w in t for w in [
        "kemaganmi", "kelmaganmi", "kemadimi", "kelmadimi", "kelganmi", "keldimi", "keldikmi",
        "qarz", "qarzdorlik", "bormi", "qachon", "qachongacha", "muddat", "muddati", "vaqti",
        "tugaganmi", "tugamaganmi", "nima bo'ldi", "nima boldi", "nima gap", "qanaqa", "qanday",
        "yillikchi", "yilikchi", "fiskalchi", "soliqchi", "ofdchi",
        "qancha", "qancha to'lay", "qancha tolay", "qancha tulay", "qancha to'lash", "qancha tolash",
        "yana", "yana pul", "yana to'laymanmi", "yana tolaymanmi", "yana tulaymanmi",
        "to'lashim kerakmi", "tolashim kerakmi", "kerakmi", "qaysi biriga", "qaysiga", "qaysi",
        "кемаганми", "келмаганми", "борми", "қарз", "муддат", "йилликчи", "қанча", "яна"
    ]):
        if not any(w in t for w in ["shot", "rekvizit", "hisob raqam", "xisob", "karta", "kartasi", "to'lash uchun", "tolash uchun", "to'lashga", "tolashga", "to'lamoqchi", "tolamoqchi", "tulamoqchi", "шот", "реквизит"]):
            return False

    # 1. Agar foydalanuvchi yaqinda yillik qarz tekshirgan bo'lsa va endi to'lashini aytsa (kontekst ustun)
    if last_topic in ("annual_debt_exists", "annual_debt_clear", "annual_check"):
        has_monthly = any(w in t for w in ["oylik", "abonent", "mars", "ойлик", "абонент", "марс"])
        if not has_monthly:
            general_pay_phrases = [
                "to'layman", "tolayman", "tulayman", "to'lashim kerak", "tolashim kerak", "to'lashim kk", "tolashim kk",
                "to'lay", "tolay", "tulay",
                "to'lamoqchi", "tolamoqchi", "tulamoqchi",
                "to'lamoqchiman", "tolamoqchiman", "tulamoqchiman",
                "to'lamoqchiydim", "tolamoqchiydim", "tulamoqchiydim",
                "to'lamoqchidim", "tolamoqchidim", "tulamoqchidim",
                "to'lamoqchi edim", "tolamoqchi edim", "tulamoqchi edim",
                "to'lab qo'ymoqchiydim", "tolab qoymoqchiydim", "tulab quymoqchiydim",
                "to'lab qo'ymoqchiman", "tolab qoymoqchiman", "tulab quymoqchiman",
                "to'lab qo'yay", "tulab quyay", "to'lab quyay", "to'lab quymoqchi",
                "shot raqam tashla", "shot tashla", "shot tashlab", "shot tashlab ber", "shot tashlab beriyla",
                "shot raqam", "shotini ber", "shot ber", "shot bering", "shot beriyla", "shotini tashla",
                "rekvizit tashla", "rekvizit ber", "rekvizit bering", "rekvizit", "rekvizitlar",
                "hisob raqam", "hisob raqamlar", "hisob raqamlarni", "hsob", "hsob raqam", "hsob raqamlar", "hsob raqamlarni",
                "hisob raqam tashla", "hisob raqam ber", "hisob raqam bering",
                "qayerga to'layman", "qayerga tolayman", "qayerga to'lash", "qayerga tolash",
                "qanday to'layman", "qanday tolayman",
                "тўлайман", "толайман", "тулайман",
                "тўламоқчи", "толамокчи", "туламокчи",
                "тўламоқчиман", "толамокчиман", "туламокчиман",
                "тўламоқчийдим", "толамокчийдим", "туламокчийдим",
                "тўламоқчи эдим", "толамокчи эдим", "туламокчи эдим",
                "тўлаб қўймоқчиман", "тулаб куймокчиман", "тўлашим керак", "толашим керак",
                "шот ташла", "шот ташлаб бер", "шот ташлаб берийла", "шот беринг", "шот бер",
                "реквизит", "реквизитлар", "реквизит ташла", "реквизит беринг",
                "ҳисоб рақам", "хисоб ракам", "ҳисоб рақамлар", "хисоб ракамлар", "хисоб ракамларни",
                "қаерга тўлашим керак", "каерга толашим керак", "қаерга тўлайман", "каерга толайман"
            ]
            if any(w in t for w in general_pay_phrases) or any(w in t for w in ["shot", "shotini", "rekvizit", "to'layman", "tolayman", "tulayman", "to'lamoqchi", "tolamoqchi", "tulamoqchi", "to'lamoqchiman", "tulamoqchiman", "hisob raqam", "hsob"]):
                return True

    if classify_payment_intent(text) == "both":
        return False

    # 2. Aniq yillik to'lov so'rovi
    has_annual = any(w in t for w in ["yillik", "fiskal", "soliq", "ofd", "yangi texnologiyalar", "йиллик", "фискал", "солиқ", "солик", "офд"])
    has_pay = any(w in t for w in [
        "to'lov", "tolov", "tulov", "to'lovlar", "tolovlar",
        "to'layman", "tolayman", "tulayman", "to'lash", "tolash", "tulash", "to'lay", "tolay", "tulay",
        "to'lamoqchi", "tolamoqchi", "tulamoqchi",
        "to'lamoqchiman", "tolamoqchiman", "tulamoqchiman",
        "to'lamoqchiydim", "tolamoqchiydim", "tulamoqchiydim",
        "to'lamoqchidim", "tolamoqchidim", "tulamoqchidim",
        "to'lamoqchi edim", "tolamoqchi edim", "tulamoqchi edim",
        "qilmoqchi", "qilmoqchiman", "qilmoqchiydim", "qilmoqchi edim",
        "to'lab", "tolab", "tulab", "to'lasam", "tolasam", "tulasam",
        "shot", "shot raqam", "shot tashla", "shot tashlab", "shot tashlab ber", "shot tashlab beriyla",
        "shotini tashla", "shot ber", "shotini ber", "shot bering", "shot beriyla",
        "rekvizit", "hisob raqam", "hsob", "qayerga to'lay", "qayerga tolay", "qayerga to'lash",
        "тўлов", "толов", "тулов", "тўлаш", "толаш", "тулаш",
        "тўлайман", "толайман", "тулайман",
        "тўламоқчи", "толамокчи", "туламокчи",
        "тўламоқчиман", "толамокчиман", "туламокчиман",
        "тўламоқчийдим", "толамокчийдим", "туламокчийдим",
        "тўламоқчи эдим", "толамокчи эдим", "туламокчи эдим",
        "қилмоқчи", "қилмоқчиман",
        "тўлаб", "толаб", "тулаб", "тўласам", "толасам", "туласам",
        "шот ташла", "шот ташлаб бер", "реквизит ташла"
    ])
    has_monthly = any(w in t for w in ["oylik", "abonent", "mars", "ойлик", "абонент", "марс"])
    if has_annual and has_pay and not has_monthly:
        return True

    return False


def is_monthly_pay_intent(text: str, last_topic: Optional[str] = None) -> bool:
    """Foydalanuvchi oylik to'lov uchun hisob raqam (shot) so'rayaptimi yoki to'lashini aytmoqdami?"""
    t = _normalize_payment_text(text)

    # Agar savol tekshiruv, qachon to'lanishi yoki holat so'rovi bo'lsa (va shot/rekvizit so'ralmagan bo'lsa) -> to'lov intenti emas
    if any(w in t for w in [
        "qachon", "qachongacha", "qaysi sana", "nechanchi sana", "muddat", "muddati", "vaqti",
        "qarz", "qarzdorlik", "bormi", "oylikchi", "oylikdanchi", "tekshir",
        "qancha", "qancha to'lay", "qancha tolay", "qancha tulay", "qancha to'lash", "qancha tolash",
        "yana", "yana pul", "yana to'laymanmi", "yana tolaymanmi", "yana tulaymanmi",
        "to'lashim kerakmi", "tolashim kerakmi", "kerakmi",
        "қачон", "қачонгача", "муддат", "қарз", "борми", "ойликчи", "қанча", "яна", "тўлашим керакми"
    ]):
        if not any(w in t for w in ["shot", "rekvizit", "hisob", "xisob", "hsob", "karta", "kartasi", "to'lash uchun", "tolash uchun", "to'lashga", "tolashga", "to'lamoqchi", "tolamoqchi", "tulamoqchi", "шот", "реквизит", "ҳисоб"]):
            return False

    # 1. Agar foydalanuvchi yaqinda oylik qarz tekshirgan bo'lsa va endi to'lashini aytsa (kontekst ustun)
    if last_topic in ("monthly_debt_exists", "monthly_debt_clear", "debt_checked", "awaiting_inn_for_monthly_debt", "fiscal_receipt_checked", "general_debt_inquiry", "inn_checked", "monthly_check"):
        has_annual = any(w in t for w in ["yillik", "fiskal", "soliq", "ofd", "yangi texnologiyalar", "йиллик", "фискал", "солиқ", "солик", "офд"])
        if not has_annual:
            general_pay_phrases = [
                "to'layman", "tolayman", "tulayman", "to'lashim kerak", "tolashim kerak", "to'lashim kk", "tolashim kk",
                "to'lay", "tolay", "tulay",
                "to'lamoqchi", "tolamoqchi", "tulamoqchi",
                "to'lamoqchiman", "tolamoqchiman", "tulamoqchiman",
                "to'lamoqchiydim", "tolamoqchiydim", "tulamoqchiydim",
                "to'lamoqchidim", "tolamoqchidim", "tulamoqchidim",
                "to'lamoqchi edim", "tolamoqchi edim", "tulamoqchi edim",
                "to'lab qo'ymoqchiydim", "tolab qoymoqchiydim", "tulab quymoqchiydim",
                "to'lab qo'ymoqchiman", "tolab qoymoqchiman", "tulab quymoqchiman",
                "to'lab qo'yay", "tulab quyay", "to'lab quyay", "to'lab quymoqchi",
                "shot raqam tashla", "shot tashla", "shot tashlab", "shot tashlab ber", "shot tashlab beriyla",
                "shot raqam", "shotini ber", "shot ber", "shot bering", "shot beriyla", "shotini tashla",
                "rekvizit tashla", "rekvizit ber", "rekvizit bering", "rekvizit", "rekvizitlar",
                "hisob raqam", "hisob raqamlar", "hisob raqamlarni", "hsob", "hsob raqam", "hsob raqamlar", "hsob raqamlarni",
                "hisob raqam tashla", "hisob raqam ber", "hisob raqam bering",
                "qayerga to'layman", "qayerga tolayman", "qayerga to'lashim kerak", "qayerga tolashim kerak",
                "qayerga to'lash kerak", "qayerga tolash kerak", "qayerga to'lash", "qayerga tolash",
                "qanday to'layman", "qanday tolayman",
                "тўлайман", "толайман", "тулайман",
                "тўламоқчи", "толамокчи", "туламокчи",
                "тўламоқчиман", "толамокчиман", "туламокчиман",
                "тўламоқчийдим", "толамокчийдим", "туламокчийдим",
                "тўламоқчи эдим", "толамокчи эдим", "туламокчи эдим",
                "тўлаб қўймоқчиман", "тулаб куймокчиман", "тўлашим керак", "толашим керак",
                "шот ташла", "шот ташлаб бер", "шот ташлаб берийла", "шот беринг", "шот бер",
                "реквизит", "реквизитlar", "реквизитлар", "реквизит ташла", "реквизит беринг",
                "ҳисоб рақам", "хисоб ракам", "ҳисоб рақамлар", "хисоб ракамlar", "хисоб ракамларни",
                "қаерга тўлашим керак", "каерга толашим керак", "қаерга тўлайман", "каерга толайман"
            ]
            if any(w in t for w in general_pay_phrases) or any(w in t for w in ["shot", "shotini", "rekvizit", "to'layman", "tolayman", "tulayman", "to'lamoqchi", "tolamoqchi", "tulamoqchi", "to'lamoqchiman", "tulamoqchiman", "hisob raqam", "hsob"]):
                return True

    if classify_payment_intent(text) == "both":
        return False

    # 2. Aniq oylik to'lov so'rovi
    has_annual = any(w in t for w in ["yillik", "fiskal", "soliq", "ofd", "yangi texnologiyalar", "йиллик", "фискал", "солиқ", "солик", "офд"])
    has_monthly = any(w in t for w in ["oylik", "abonent", "mars", "ойлик", "абонент", "марс"])
    has_pay = any(w in t for w in [
        "to'lov", "tolov", "tulov", "to'lovlar", "tolovlar",
        "to'layman", "tolayman", "tulayman", "to'lash", "tolash", "tulash", "to'lay", "tolay", "tulay",
        "to'lamoqchi", "tolamoqchi", "tulamoqchi",
        "to'lamoqchiman", "tolamoqchiman", "tulamoqchiman",
        "to'lamoqchiydim", "tolamoqchiydim", "tulamoqchiydim",
        "to'lamoqchidim", "tolamoqchidim", "tulamoqchidim",
        "to'lamoqchi edim", "tolamoqchi edim", "tulamoqchi edim",
        "qilmoqchi", "qilmoqchiman", "qilmoqchiydim", "qilmoqchi edim",
        "to'lab", "tolab", "tulab", "to'lasam", "tolasam", "tulasam",
        "shot", "shot raqam", "shot tashla", "shot tashlab", "shot tashlab ber", "shot tashlab beriyla",
        "shotini tashla", "shot ber", "shotini ber", "shot bering", "shot beriyla",
        "rekvizit", "hisob raqam", "hsob", "qayerga to'lay", "qayerga tolay", "qayerga to'lash",
        "тўлов", "толов", "тулов", "тўлаш", "толаш", "тулаш",
        "тўлайман", "толайман", "тулайман",
        "тўламоқчи", "толамокчи", "туламокчи",
        "тўламоқчиман", "толамокчиман", "туламокчиман",
        "тўламоқчийдим", "толамокчийдим", "туламокчийдим",
        "тўламоқчи эдим", "толамокчи эдим", "туламокчи эдим",
        "қилмоқчи", "қилмоқчиман",
        "тўлаб", "толаб", "тулаб", "тўласам", "толасам", "туласам",
        "шот ташла", "шот ташлаб бер", "реквизит ташла"
    ])
    if has_monthly and has_pay and not has_annual:
        return True

    return False


def parse_ofd_reply_status(ofd_text: Optional[str]) -> str:
    """
    @ofd943_bot javobini 4 ta aniq holatdan biriga ajratadi:
    - "unavailable": javob yo'q (None yoki bo'sh)
    - "not_found": fiskal modul soliq bazasidan topilmadi / mavjud emas
    - "debt": yillik to'lovdan qarzdorlik mavjud
    - "active": yillik to'lovdan qarzdorlik yo'q / litsenziya faol
    """
    if not ofd_text or not str(ofd_text).strip():
        return "unavailable"
    lower = str(ofd_text).lower()
    if any(nf in lower for nf in [
        "bunday fiskal modul", "fiskal modul mavjud emas", "modul mavjud emas",
        "ma'lumot mavjud emas", "malumot mavjud emas", "topilmadi",
        "ro'yxatda yo'q", "ro‘yxatda yo‘q", "royxatda yoq", "не найден"
    ]):
        return "not_found"

    has_no_debt = any(w in lower for w in [
        "qarzdorlik mavjud emas", "qarzdorlik yo'q", "qarzdorlik yo‘q", "qarzi yo'q", "qarzi yo‘q"
    ]) or ("mavjud emas" in lower and "fiskal modul" not in lower)

    is_debt = (not has_no_debt) and any(w in lower for w in [
        "qarzdorlik mavjud", "fmo dan qarzdorlik", "qarzdorlik bor", "qarzdorlik",
        "to‘lov qilish muddati", "to'lov qilish muddati", "muddati o‘tgan", "muddati o'tgan"
    ])
    if is_debt:
        return "debt"
    return "active"


def format_ofd_annual_status(fm_code: str, ofd_text: Optional[str], script: str = "latin") -> str:
    """@ofd943_bot javobini tahlil qilib, qisqa va aniq qarz bor/yo'qligini xabar qilish"""
    from templates import format_ofd_status_template as _tpl
    return _tpl(fm_code=fm_code, ofd_text=ofd_text, script=script)

