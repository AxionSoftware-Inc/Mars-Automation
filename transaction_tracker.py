import os
import re
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "processed_transactions.json")

PURPOSE_REPAIR_KEYWORDS = [
    "remont", "ta'mir", "tamir", "zapchast", "ekran almashtirish",
    "plata ta'miri", "batareya almashtirish", "zapchastlar", "remonti",
    "ремонт", "запчасть", "замена экрана", "замена платы"
]

PURPOSE_PURCHASE_KEYWORDS = [
    "apparat sotib", "kassa sotib", "terminal sotib", "apparat narxi",
    "pax sotib", "uzsmart sotib", "yangi apparat", "terminal xaridi",
    "покупка аппарата", "покупка кассы", "новый аппарат", "стоимость кассы"
]

PURPOSE_REGISTRATION_KEYWORDS = [
    "pere-registratsiya", "qayta ro'yxat", "ro'yxatdan o'tkazish",
    "nomiga o'tkazish", "filial ochish", "pere registratsiya",
    "перерегистрация", "регистрация кассы", "постановка на учет"
]

class TransactionTracker:
    """
    To'lov kvitansiyalarini firibgarlik va takrorlanishdan (Fraud & Duplicates) himoya qilish:
    1. Dublikat cheklarni aniqlash (qayta yuborilgan tranzaksiyalar)
    2. Eski sanadagi kvitansiyalarni aniqlash (>30 kun)
    3. To'lov maqsadini aniqlash (Abonent vs Remont vs Yangi kassa vs Registratsiya)
    """
    def __init__(self, filepath: str = TRANSACTIONS_FILE):
        self.filepath = filepath
        self.transactions: Dict[str, Dict[str, Any]] = {}
        self.load_transactions()

    def load_transactions(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.transactions = json.load(f)
                logger.info(f"TransactionTracker: {len(self.transactions)} ta tranzaksiya yuklandi.")
            except Exception as e:
                logger.error(f"Tranzaksiyalarni yuklashda xatolik: {e}")
                self.transactions = {}
        else:
            self.transactions = {}

    def save_transactions(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.transactions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Tranzaksiyalarni saqlashda xatolik: {e}")

    def clean_tx_id(self, tx_id: Optional[str]) -> Optional[str]:
        if not tx_id:
            return None
        t = str(tx_id).strip()
        if t.lower() in ["-", "null", "none", "0", "000", "yo'q", "topilmadi", ""]:
            return None
        # Qisqa dummy belgilardan tozalash
        clean = re.sub(r"[\s\-_]", "", t).lower()
        if len(clean) < 4 or set(clean) == {'0'}:
            return None
        return clean

    def is_duplicate(self, transaction_id: Optional[str]) -> bool:
        clean = self.clean_tx_id(transaction_id)
        if not clean:
            return False
        return clean in self.transactions

    def get_transaction(self, transaction_id: Optional[str]) -> Optional[Dict[str, Any]]:
        clean = self.clean_tx_id(transaction_id)
        if not clean:
            return None
        return self.transactions.get(clean)

    def record_transaction(
        self,
        transaction_id: Optional[str],
        inn: Optional[str] = None,
        amount: float = 0.0,
        user_id: int = 0,
        payment_date: str = ""
    ) -> bool:
        clean = self.clean_tx_id(transaction_id)
        if not clean:
            return False

        now_uzb = datetime.now(ZoneInfo("Asia/Tashkent"))
        self.transactions[clean] = {
            "recorded_at": now_uzb.strftime("%Y-%m-%d %H:%M:%S"),
            "inn": inn,
            "amount": amount,
            "user_id": user_id,
            "payment_date": payment_date
        }
        self.save_transactions()
        return True

    def check_old_receipt(self, date_str: str) -> Tuple[bool, Optional[str]]:
        """
        Kvitansiya sanasi 30 kundan eski yoki o'tgan yilga tegishli ekanligini aniqlash.
        Qaytaradi: (is_old: bool, warning_message: Optional[str])
        """
        if not date_str:
            return False, None

        s = date_str.strip()
        now_uzb = datetime.now(ZoneInfo("Asia/Tashkent"))
        current_year = now_uzb.year

        # 1. Yilni tekshirish (masalan 2024 yoki 2025 yilgi cheklar)
        year_match = re.search(r"\b(202[0-9])\b", s)
        if year_match:
            doc_year = int(year_match.group(1))
            if doc_year < current_year:
                diff_years = current_year - doc_year
                return True, f"Kvitansiya sanasi o'tgan yilgi ({s}). {diff_years} yil oldingi chek qabul qilinmaydi!"

        # 2. To'liq sanani (YYYY-MM-DD yoki DD.MM.YYYY) parslash
        parsed_date = None
        formats = [
            "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d",
            "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y",
            "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"
        ]
        
        # Matndan sana qismini ajratish
        match_iso = re.search(r"\b(\d{4}[./-]\d{2}[./-]\d{2})\b", s)
        match_dm = re.search(r"\b(\d{2}[./-]\d{2}[./-]\d{4})\b", s)
        target_str = match_iso.group(1) if match_iso else (match_dm.group(1) if match_dm else s[:10])

        for fmt in formats:
            try:
                parsed_date = datetime.strptime(target_str, fmt).replace(tzinfo=ZoneInfo("Asia/Tashkent"))
                break
            except Exception:
                continue

        if parsed_date:
            days_ago = (now_uzb.date() - parsed_date.date()).days
            if days_ago > 30:
                return True, f"Kvitansiya sanasi {days_ago} kun avvalgi ({target_str}). Iltimos, joriy oy yangi to'lov chekini yuboring!"

        return False, None

    def detect_payment_purpose(self, text: str) -> Tuple[str, str]:
        """
        Kvitansiya matni yoki izohdan to'lov maqsadini aniqlash.
        Qaytaradi: (purpose_code, purpose_label_uz)
        """
        if not text:
            return "monthly_subscription", "Oylik abonent to'lovi"

        t = text.lower()

        if any(kw in t for kw in PURPOSE_REPAIR_KEYWORDS):
            return "repair", "Apparat ta'miri / Remont xizmati"

        if any(kw in t for kw in PURPOSE_PURCHASE_KEYWORDS):
            return "hardware_purchase", "Yangi kassa apparati xaridi"

        if any(kw in t for kw in PURPOSE_REGISTRATION_KEYWORDS):
            return "registration", "Kassani ro'yxatdan o'tkazish (Pere-registratsiya)"

        return "monthly_subscription", "Oylik abonent to'lovi"


transaction_tracker = TransactionTracker()
