from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List

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
