from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List

class ActionType(Enum):
    IGNORE = "IGNORE"                      # Begona rasm yoki ob'ekt — javob bermay jim turish
    ASK_FULL_SCREEN = "ASK_FULL_SCREEN"    # Status bar (soat va tarmoq) ko'rinmagan — to'liq ekranni talab qilish
    DIAGNOSE_AND_REPLY = "DIAGNOSE_AND_REPLY"  # Aniq tashxis, qarz holati va yechim videosi
    DEBT_INFO = "DEBT_INFO"                # Faqat qarz tekshiruvi natijasi
    FALLBACK_SAFE = "FALLBACK_SAFE"        # Zanjir uzilib qolganda xavfsiz zaxira javobi

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
class DecisionResult:
    """
    Yadro (Core Engine) tomonidan chiqarilgan yakuniy qaror.
    Handler ushbu natijaga qarab Telegramga javob beradi.
    """
    action: ActionType
    reply_text: Optional[str] = None
    video_id: Optional[int] = None
    detected_inn: Optional[str] = None
    debt_amount: Optional[float] = None
    org_name: Optional[str] = None
    log_reason: str = ""
