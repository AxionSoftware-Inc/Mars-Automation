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

def is_incomplete_inn_text(text: str) -> bool:
    """
    Matnda 'inn' yoki 'stir' prefiksi bilan 1 tadan 8 tagacha raqam yuborilgan bo'lsa
    (lekin to'liq 9 xonali INN yoki 14 xonali JSHSHIR bo'lmasa).
    """
    if not text:
        return False
    t = text.strip()
    if extract_clean_inn(t):
        return False
    match = re.search(r"\b(?:inn|stir|стир|инн|jshshir|жшшир)\b[:\s#№]*\d{1,8}\b", t, re.IGNORECASE)
    return bool(match)

def extract_clean_phone(text: str) -> Optional[str]:
    """
    O'zbekiston telefon raqamini matndan ajratib olish (9 xonali: 901234567).
    Prefikslar: +998, 998, tel:, telefon:, nomer: va h.k.
    """
    if not text:
        return None
    t = text.strip()
    m_full = re.search(r"(?:tel|telefon|nomer|raqam|телефон)?[:\s#№]*(?:\+?998[\s\-]?)?([389]\d[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})\b", t, re.IGNORECASE)
    if m_full:
        digits = re.sub(r"\D", "", m_full.group(1))
        if len(digits) == 9:
            return digits

    m9 = re.search(r"\b([389]\d\d{7})\b", re.sub(r"[\s\.\-]", "", t))
    if m9:
        return m9.group(1)

    return None

def extract_fiscal_module(text: str) -> Optional[str]:
    """
    Fiskal modul seriya raqamini matndan ajratib olish:
    - Odatda chiqarilgan chekda bo'ladi, 2 ta katta harf (LG, YG, FM, UZ va h.k.) + 8-14 ta raqam;
    - Masalan: LG420210630789, YG202106307890, LG 420210630789, LG-420210630789;
    - Yoki FM: / Fiskal modul: bilan kelgan seriya raqami.
    """
    if not text:
        return None
    t = text.strip()

    # 1. 2 ta harf bilan boshlangan format (LG, YG, FM, UZ, TJ va h.k.) + bo'shliq/tire + 8..14 ta raqam
    m_code = re.search(r"\b([A-Za-z]{2})[\s\-_]?(\d{8,14})\b", t, re.IGNORECASE)
    if m_code:
        prefix = m_code.group(1).upper()
        digits = m_code.group(2)
        return f"{prefix}{digits}"

    # 2. Maxsus prefiks bilan: FM:, FM-, Fiskal modul: LG...
    m_pref = re.search(r"(?:fiskal\s*modul|фискал\s*модул|fm|фм)[\s\-_:#№]*([A-Za-z]{0,2}[\s\-_]?\d{8,16})", t, re.IGNORECASE)
    if m_pref:
        cleaned = re.sub(r"[\s\-_:#№]", "", m_pref.group(1)).upper()
        if len(cleaned) >= 8:
            return cleaned

    # 3. Agar matnda aniq fiskal modul so'zi bo'lsa va 10-16 xonali raqam kelsa
    if any(w in t.lower() for w in ["fiskal", "modul", "фискал", "модул"]):
        m_digits = re.search(r"\b(\d{10,16})\b", t)
        if m_digits:
            return m_digits.group(1)

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
class FiscalChekFacts:
    """
    Kassa apparatidan (Onlayn-NKM / Smart POS) chop etilgan savdo cheki yoki fiskal hisobotdan
    olingan sof faktlar (to'lov kvitansiyasi EMAS).
    """
    is_fiscal_chek: bool = False               # Kassa chekimi (haqiqiy kassa/fiskal chek)
    inn: Optional[str] = None                  # 9 xonali STIR / INN
    fiscal_module: Optional[str] = None        # Fiskal modul seriya raqami (LG..., YG..., UZ...)
    org_name: str = ""                         # Korxona / tashkilot nomi
    terminal_id: Optional[str] = None          # Terminal yoki apparat seriya raqami
    check_number: Optional[str] = None         # Chek raqami
    date_time: str = ""                        # Sana va vaqt
    total_amount: float = 0.0                  # Xarid jami summasi
    receipt_type: str = "sale"                 # "sale" (xarid/savdo), "z_report", "x_report", "other"
    raw_text: str = ""                         # Chekdagi matnlar qisqartmasi
    raw_facts: Dict[str, Any] = field(default_factory=dict)
    extraction_error: Optional[str] = None

@dataclass
class ReceiptFacts:
    """
    To'lov kvitansiyasidan (rasm yoki PDF) ajratilgan sof faktlar.
    """
    is_receipt: bool = False               # Bu to'lov kvitansiyasi / chekmi
    is_fiscal_chek: bool = False           # Bu kassa chekimi (Onlayn-NKM savdo cheki)
    fiscal_module: Optional[str] = None    # Fiskal modul seriya raqami (LG..., YG..., UZ...)
    terminal_id: Optional[str] = None      # Terminal ID
    fiscal_facts: Optional[FiscalChekFacts] = None
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
    payment_purpose: str = "monthly_subscription" # "monthly_subscription", "repair", "hardware_purchase", "registration"
    purpose_label: str = "Oylik abonent to'lovi"
    is_old_receipt: bool = False
    old_receipt_warning: Optional[str] = None
    is_duplicate: bool = False
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
    payment_purpose: str = "monthly_subscription"
    purpose_label: str = "Oylik abonent to'lovi"
    is_old_receipt: bool = False
    is_duplicate: bool = False
    tuman: Optional[str] = None

