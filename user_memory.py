import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Xotiraning amal qilish muddati: 12 soat (soniyalarda)
TTL_SECONDS = 12 * 3600  # 43,200 soniya
MAX_HISTORY_TURNS = 6    # Har bir foydalanuvchi uchun oxirgi 6 ta xabar almashinuvi

class UserMemoryManager:
    def __init__(self, ttl_seconds: int = TTL_SECONDS, max_turns: int = MAX_HISTORY_TURNS):
        self.ttl_seconds = ttl_seconds
        self.max_turns = max_turns
        # Xotira kaliti: f"{chat_id}:{user_id}" -> { "last_active": timestamp, "history": [...], "debt_info": {...} }
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def _get_key(self, chat_id: int, user_id: int) -> str:
        return f"{chat_id}:{user_id}"

    def _cleanup_expired(self):
        """Eskirgan (12 soatdan oshgan) sessiyalarni tozalash"""
        now = time.time()
        expired_keys = [
            k for k, v in self.sessions.items()
            if now - v.get("last_active", 0) > self.ttl_seconds
        ]
        for k in expired_keys:
            del self.sessions[k]
        if expired_keys:
            logger.info(f"UserMemory: {len(expired_keys)} ta eskirgan sessiya tozalandi.")

    def _get_or_create_session(self, chat_id: int, user_id: int) -> Dict[str, Any]:
        self._cleanup_expired()
        key = self._get_key(chat_id, user_id)
        now = time.time()
        if key not in self.sessions:
            self.sessions[key] = {
                "last_active": now,
                "history": [],
                "last_id": None,
                "debt_info": None,
                "last_topic": None
            }
        self.sessions[key]["last_active"] = now
        return self.sessions[key]

    def add_user_message(self, chat_id: int, user_id: int, text: str):
        """Foydalanuvchi xabarini xotiraga qo'shish"""
        session = self._get_or_create_session(chat_id, user_id)
        session["history"].append({"role": "user", "text": text.strip()})

        # Xotirani limit doirasida saqlash
        if len(session["history"]) > self.max_turns * 2:
            session["history"] = session["history"][-(self.max_turns * 2):]

    def add_assistant_message(self, chat_id: int, user_id: int, text: str):
        """Bot javobini xotiraga qo'shish"""
        session = self._get_or_create_session(chat_id, user_id)
        session["history"].append({"role": "model", "text": text.strip()})
        if len(session["history"]) > self.max_turns * 2:
            session["history"] = session["history"][-(self.max_turns * 2):]

    def set_last_id(self, chat_id: int, user_id: int, identifier: str, org_name: str = "", debt: float = 0.0):
        """Foydalanuvchi qidirgan oxirgi INN/JSHSHIR va korxona ma'lumotlarini eslab qolish"""
        session = self._get_or_create_session(chat_id, user_id)
        session["last_id"] = str(identifier).strip()
        session["debt_info"] = {
            "identifier": str(identifier).strip(),
            "org_name": org_name,
            "debt": debt
        }

    def get_last_id(self, chat_id: int, user_id: int) -> Optional[str]:
        """Foydalanuvchining oxirgi INN/JSHSHIR raqamini olish"""
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("last_id")

    def get_debt_info(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Oxirgi tekshirilgan qarz ma'lumotlarini olish"""
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("debt_info")

    def set_last_topic(self, chat_id: int, user_id: int, topic: str):
        """Oxirgi mavzuni saqlash (masalan: 'time_error', 'payment', 'debt_history')"""
        session = self._get_or_create_session(chat_id, user_id)
        session["last_topic"] = topic

    def get_last_topic(self, chat_id: int, user_id: int) -> Optional[str]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("last_topic")

    def get_user_history(self, chat_id: int, user_id: int) -> List[Dict[str, str]]:
        """Aynan shu foydalanuvchining suhbat tarixini olish"""
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("history", [])

    def get_context_summary(self, chat_id: int, user_id: int) -> str:
        """AI promptiga qo'shish uchun to'liq kontekst xulosasi"""
        session = self._get_or_create_session(chat_id, user_id)
        history = session.get("history", [])
        debt_info = session.get("debt_info")

        parts = []
        if debt_info and debt_info.get("identifier"):
            d_val = debt_info.get("debt", 0.0)
            org = debt_info.get("org_name") or "Noma'lum korxona"
            ident = debt_info.get("identifier")
            if d_val > 0:
                parts.append(f"[Mijoz holati: Korxona '{org}' (INN/JSHSHIR: {ident}), QARZDORLIK MAVJUD: {d_val:,.0f} so'm. Oylik to'lov to'lanmagan.]")
            elif d_val < 0:
                parts.append(f"[Mijoz holati: Korxona '{org}' (INN/JSHSHIR: {ident}), Qarzdorlik YO'Q (ortiqcha to'lov: {abs(d_val):,.0f} so'm).]")
            else:
                parts.append(f"[Mijoz holati: Korxona '{org}' (INN/JSHSHIR: {ident}), Qarzdorlik YO'Q (0 so'm).]")

        if history:
            for msg in history[-4:]:  # Oxirgi 4 ta xabar yetarli
                role_label = "Mijoz" if msg["role"] == "user" else "Yordamchi"
                parts.append(f"{role_label}: {msg['text']}")

        return "\n".join(parts)

    def set_pending_receipt(self, chat_id: int, user_id: int, receipt_data: Dict[str, Any]):
        """INN aniqlanmagan kvitansiyani foydalanuvchi INN yozgunicha vaqtincha saqlab turish"""
        session = self._get_or_create_session(chat_id, user_id)
        session["pending_receipt"] = receipt_data

    def get_pending_receipt(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("pending_receipt")

    def clear_pending_receipt(self, chat_id: int, user_id: int):
        session = self._get_or_create_session(chat_id, user_id)
        session["pending_receipt"] = None

user_memory = UserMemoryManager()
