import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List

def extract_clean_inn(text: str) -> Optional[str]:
    """
    Matndan 9 xonali INN (STIR) yoki 14 xonali JSHSHIR raqamini har qanday formatda
    (toza, bo'shliqlar bilan, nuqta, tire, prefikslar bilan) aniq va xatosiz ajratib olish.
    Agar kiritilgan matnda INN bo'lmasa, yoki '000', '000000000', 'null', 'none' kabi
    bo'sh / dummy qiymat bo'lsa -> None qaytaradi.
    """
    if not text:
        return None
    t = text.strip()
    if t.lower() in ["null", "none", "yo'q", "yoq", "topilmadi", "-", "noma'lum", "unknown", "0", "00", "000"]:
        return None

    def is_valid_inn_digits(d: str) -> bool:
        if not d:
            return False
        # Agar barcha raqamlar 0 bo'lsa (masalan "000", "000000000") -> yaroqsiz
        if set(d) == {'0'}:
            return False
        return len(d) in [9, 14]

    prefix_pattern = r"(?:inn|stir|стир|инн|jshshir|жшшир|пинфл|pinfl)[:\s#№]*([0-9\s\.\-]{8,22})"
    prefix_match = re.search(prefix_pattern, t, re.IGNORECASE)
    if prefix_match:
        digits = re.sub(r"\D", "", prefix_match.group(1))
        if is_valid_inn_digits(digits):
            return digits
        elif len(digits) > 9 and len(digits) < 14:
            cand = digits[:9]
            if is_valid_inn_digits(cand):
                return cand

    m14 = re.findall(r"\b(\d{14})\b", t)
    for c in m14:
        if is_valid_inn_digits(c):
            return c

    m9 = re.findall(r"\b(\d{9})\b", t)
    for c in m9:
        if is_valid_inn_digits(c):
            return c

    spaced_9 = re.search(r"\b(\d{3}[\s\.\-]\d{3}[\s\.\-]\d{3})\b", t)
    if spaced_9:
        digits = re.sub(r"\D", "", spaced_9.group(1))
        if is_valid_inn_digits(digits):
            return digits

    spaced_14 = re.search(r"\b(\d{1,3}[\s\.\-]\d{2,6}[\s\.\-]\d{2,6}[\s\.\-]?\d{1,6})\b", t)
    if spaced_14:
        digits = re.sub(r"\D", "", spaced_14.group(1))
        if is_valid_inn_digits(digits):
            return digits

    pure_digits = re.sub(r"\D", "", t)
    if is_valid_inn_digits(pure_digits) and len(t) <= 20:
        return pure_digits

    return None

class ActionType(Enum):
    IGNORE = "IGNORE"                          # Begona rasm yoki ob'ekt — javob bermay jim turish
    ASK_FULL_SCREEN = "ASK_FULL_SCREEN"        # Status bar (soat va tarmoq) ko'rinmagan — to'liq ekranni talab qilish
    DIAGNOSE_AND_REPLY = "DIAGNOSE_AND_REPLY"  # Aniq tashxis, qarz holati va yechim videosi
    DEBT_INFO = "DEBT_INFO"                    # Faqat qarz tekshiruvi natijasi
    RECEIPT_PROCESSED = "RECEIPT_PROCESSED"    # Kvitansiya tahlil qilindi, qarz solishtirildi, adminga yuborildi
    ESCALATE_TO_ADMIN = "ESCALATE_TO_ADMIN"    # Nosozlik (internet bor, qarz yo'q) yoki murakkab holat — adminga eskalatsiya
    FALLBACK_SAFE = "FALLBACK_SAFE"            # Zanjir uzilib qolganda xavfsiz zaxira javobi

@dataclass
class DeviceFacts:
    """
    Kassa apparati tasviridan yoki xabardan olingan sof faktlar.
    Ushbu modelda HECH QANDAY javob matni yoki qaror bo'lmaydi, faqat faktlar.
    """
    is_real_pos_device: bool = False       # Haqiqiy Smart POS apparati yoki kassa ekrani
    is_status_bar_visible: bool = False    # Ekran tepasidagi soat yoki internet qatori
    time_mismatch: bool = False            # Soat real Toshkent vaqtidan farq qiladimi
    has_internet: bool = True              # Wi-Fi yoki mobil tarmoq bormi
    error_type: str = "none"               # "debt", "fiscal_module", "update", "paper", "none"
    detected_inn: Optional[str] = None     # Ekranda yoki matnda aniqlangan INN/JSHSHIR
    screen_text_summary: str = ""          # Ekranda ko'ringan yozuvlar
    raw_facts: Dict[str, Any] = field(default_factory=dict)
    extraction_error: Optional[str] = None # Sensor uzilib qolsa xatolik izohi

@dataclass
class ReceiptFacts:
    """
    To'lov kvitansiyasidan (rasm yoki PDF) ajratilgan sof faktlar.
    """
    is_receipt: bool = False               # Bu to'lov kvitansiyasi / chekmi
    recipient_account: str = ""            # Qabul qiluvchi hisob raqami yoki nomi
    is_mars_recipient: bool = False        # "Mars Elektron Texnika" ga yo'naltirilganmi
    is_annual_fiscal_fee: bool = False     # "Yangi Texnologiyalar" DUK yillik fiskal modul to'lovimi
    payment_category: str = "monthly"      # "monthly", "annual", "other"
    recipient_org_name: str = ""           # Aniqlangan tashkilot nomi
    amount: float = 0.0                    # O'tkazilgan summa (so'm)
    payer_inn: Optional[str] = None        # Kvitansiyada aniqlangan to'lovchi INN/JSHSHIR
    payer_name: str = ""                   # To'lovchi korxona yoki shaxs nomi
    payment_date: str = ""                 # To'lov sanasi va vaqti
    transaction_id: str = ""               # Tranzaksiya yoki chek raqami
    payment_system: str = ""               # Click, Payme, Bank, Munis, Uzum va h.k.
    raw_text: str = ""                     # Kvitansiya matni
    raw_facts: Dict[str, Any] = field(default_factory=dict)
    extraction_error: Optional[str] = None # Sensor uzilib qolsa xatolik izohi

@dataclass
class DecisionResult:
    """
    Yadro (Core Engine) tomonidan chiqarilgan yakuniy qaror.
    Handler ushbu natijaga qarab Telegramga javob beradi va adminga bildirishnoma yuboradi.
    """
    action: ActionType
    reply_text: Optional[str] = None
    video_id: Optional[int] = None
    detected_inn: Optional[str] = None
    debt_amount: Optional[float] = None
    paid_amount: Optional[float] = None
    remaining_debt: Optional[float] = None
    org_name: Optional[str] = None
    log_reason: str = ""
    should_notify_admin: bool = False
    admin_alert_type: Optional[str] = None # "receipt", "tech_issue", "escalation"
    admin_alert_text: Optional[str] = None
    receipt_facts: Optional[ReceiptFacts] = None
    debt_status_info: Dict[str, Any] = field(default_factory=dict)
    file_id: Optional[str] = None
    is_photo: bool = True

