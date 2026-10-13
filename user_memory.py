import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Xotiraning amal qilish muddati: 12 soat (soniyalarda)
TTL_SECONDS = 12 * 3600  # 43,200 soniya
MAX_HISTORY_TURNS = 10   # Har bir foydalanuvchi uchun oxirgi 10 ta xabar almashinuvi (20 ta xabar)

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
                "org_name": None,
                "debt_info": None,
                "last_receipt": None,
                "last_topic": None,
                "pending_receipt": None,
                "preferred_script": "latin"
            }
        self.sessions[key]["last_active"] = now
        return self.sessions[key]

    def add_user_message(self, chat_id: int, user_id: int, text: str):
        """Foydalanuvchi xabarini xotiraga qo'shish va alifbo afzalligini aniqlash"""
        session = self._get_or_create_session(chat_id, user_id)
        session["history"].append({"role": "user", "text": text.strip()})

        # Alifbo turini aniqlash va yangilash
        from translit_manager import detect_script
        sc = detect_script(text)
        if sc in ("cyrillic", "latin"):
            session["preferred_script"] = sc

        # Xotirani limit doirasida saqlash
        if len(session["history"]) > self.max_turns * 2:
            session["history"] = session["history"][-(self.max_turns * 2):]

    def get_preferred_script(self, chat_id: int, user_id: int) -> str:
        """Foydalanuvchi qaysi alifboda (latin yoki cyrillic) muloqot qilayotganini olish"""
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("preferred_script") or "latin"

    def detect_and_update_script(self, chat_id: int, user_id: int, text: str) -> str:
        """Yangi matn bo'yicha alifboni aniqlab, xotirani yangilash va qaytarish"""
        session = self._get_or_create_session(chat_id, user_id)
        from translit_manager import detect_script
        sc = detect_script(text)
        if sc in ("cyrillic", "latin"):
            session["preferred_script"] = sc
            return sc
        return session.get("preferred_script") or "latin"

    def add_assistant_message(self, chat_id: int, user_id: int, text: str):
        """Bot javobini xotiraga qo'shish"""
        session = self._get_or_create_session(chat_id, user_id)
        session["history"].append({"role": "model", "text": text.strip()})
        if len(session["history"]) > self.max_turns * 2:
            session["history"] = session["history"][-(self.max_turns * 2):]

    def set_last_id(self, chat_id: int, user_id: int, identifier: str, org_name: str = "", debt: float = 0.0, device_models: str = ""):
        """Foydalanuvchi qidirgan oxirgi INN/JSHSHIR va korxona ma'lumotlarini eslab qolish"""
        session = self._get_or_create_session(chat_id, user_id)
        session["last_id"] = str(identifier).strip()
        if org_name:
            session["org_name"] = str(org_name).strip()
        if device_models:
            session["device_models"] = str(device_models).strip()
        session["debt_info"] = {
            "identifier": str(identifier).strip(),
            "org_name": session.get("org_name") or org_name,
            "debt": debt,
            "device_models": session.get("device_models") or device_models
        }

    def get_last_id(self, chat_id: int, user_id: int) -> Optional[str]:
        """Foydalanuvchining oxirgi INN/JSHSHIR raqamini olish"""
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("last_id")

    def get_org_name(self, chat_id: int, user_id: int) -> Optional[str]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("org_name")

    def set_last_receipt(self, chat_id: int, user_id: int, receipt_info: Dict[str, Any]):
        """Yuborilgan to'lov kvitansiyasi holatini xotiraga saqlash"""
        session = self._get_or_create_session(chat_id, user_id)
        session["last_receipt"] = receipt_info
        # Agar qoldiq qarz ko'rsatilgan bo'lsa, joriy qarzni yangilash
        rem = receipt_info.get("remaining_debt")
        if rem is not None:
            if session.get("debt_info"):
                session["debt_info"]["debt"] = rem
            else:
                session["debt_info"] = {
                    "identifier": session.get("last_id") or "",
                    "org_name": session.get("org_name") or "",
                    "debt": rem
                }


    def get_last_receipt(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("last_receipt")

    def get_debt_info(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Oxirgi tekshirilgan qarz ma'lumotlarini olish"""
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("debt_info")

    def set_last_topic(self, chat_id: int, user_id: int, topic: str):
        """Oxirgi mavzuni saqlash (masalan: 'receipt_submitted', 'debt_checked', 'time_error')"""
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
        """AI promptiga qo'shish uchun boyitilgan, strukturaviy kontekst xulosasi"""
        session = self._get_or_create_session(chat_id, user_id)
        history = session.get("history", [])
        debt_info = session.get("debt_info")
        last_receipt = session.get("last_receipt")
        org_name = session.get("org_name")
        last_id = session.get("last_id")

        parts = []
        parts.append("=== MIJOZNING ANIQLANGAN TIZIMDAGI MA'LUMOTLARI ===")
        if last_id:
            org_str = org_name or (debt_info.get("org_name") if debt_info else "Noma'lum korxona")
            parts.append(f"• Korxona nomi: {org_str}")
            parts.append(f"• INN / JSHSHIR: {last_id}")
            dev_models = session.get("device_models") or (debt_info.get("device_models") if debt_info else "")
            if dev_models:
                parts.append(f"• Korxonaning kassa apparati modeli: {dev_models}")
            parts.append("• QAT'IY QOIDA: Ushbu mijozning INN raqami va korxonasi ALLAQACHON ma'lum! Qayta INN so'rash qat'iyan taqiqlanadi!")
        else:
            parts.append("• Ushbu mijoz tizimga hali o'z korxona INN/JSHSHIR raqamini kiritmagan va to'lov kvitansiyasini yubormagan.")
            parts.append("• Uning qaysi korxonaga tegishliligi noma'lum. Shaxsiy qarz, apparat holati yoki qo'shilish vaqti so'ralsa, avval korxona INN raqamini so'rang.")

        if debt_info:
            d_val = debt_info.get("debt", 0.0)
            if d_val > 0:
                parts.append(f"• Joriy qarzdorlik: {d_val:,.0f} so'm mavjud (oylik to'lov to'lanmagan).")
            elif d_val < 0:
                parts.append(f"• Joriy qarzdorlik: Qarzdorlik YO'Q (ortiqcha to'lov: {abs(d_val):,.0f} so'm).")
            else:
                parts.append("• Joriy qarzdorlik: 0 so'm (Qarzdorlik yo'q).")

        if last_receipt:
            amt = last_receipt.get("amount", 0.0)
            rem = last_receipt.get("remaining_debt", 0.0)
            covered = last_receipt.get("debt_covered", False)
            parts.append("=== YAQINDAGI TO'LOV KVITANSIYASI HOLATI ===")
            parts.append(f"• Mijoz yaqinda to'lov kvitansiyasini yubordi (Summa: {amt:,.0f} so'm).")
            parts.append("• Kvitansiya mas'ul adminga yetkazildi.")
            if covered:
                parts.append("• To'lov mavjud barcha qarzni TO'LIQ yopdi! Tizimda apparat tez orada (15-30 daqiqa ichida) yoqiladi.")
                parts.append("• Keyingi abonent to'lovi muddati: Kelgusi oyning 6-sanasigacha.")
            else:
                parts.append(f"• To'lov qisman qabul qilindi. Qolgan qarzdorlik: {rem:,.0f} so'm.")

        parts.append("• Tizim qoidasi: Abonent to'lovi har oyning 6-sanasigacha to'lanadi. 6-sanada to'lanmasa avtomatik to'xtaydi.")

        if history:
            parts.append("\n=== SUHBAT TARIXI (oxirgi xabarlar) ===")
            for msg in history[-8:]:
                role_label = "Mijoz" if msg["role"] == "user" else "Yordamchi (Bot)"
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

    def set_pending_device_screen(self, chat_id: int, user_id: int, device_data: Dict[str, Any]):
        """INN aniqlanmagan ekran rasmini foydalanuvchi INN yozgunicha (Excel rangi P3/SmartPOS tekshirilishi uchun) saqlash"""
        session = self._get_or_create_session(chat_id, user_id)
        session["pending_device_screen"] = device_data

    def get_pending_device_screen(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("pending_device_screen")

    def clear_pending_device_screen(self, chat_id: int, user_id: int):
        session = self._get_or_create_session(chat_id, user_id)
        session["pending_device_screen"] = None

    def set_last_fm(self, chat_id: int, user_id: int, fm_code: str):
        """Foydalanuvchining oxirgi kiritgan Fiskal modul raqamini saqlash"""
        session = self._get_or_create_session(chat_id, user_id)
        session["last_fm"] = str(fm_code).strip().upper()

    def get_last_fm(self, chat_id: int, user_id: int) -> Optional[str]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("last_fm")

    def set_last_photo(self, chat_id: int, user_id: int, file_id: str):
        """Oxirgi yuborilgan kassa rasmi file_id sini saqlash"""
        session = self._get_or_create_session(chat_id, user_id)
        session["last_photo"] = file_id

    def get_last_photo(self, chat_id: int, user_id: int) -> Optional[str]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("last_photo")

    def clear_context(self, chat_id: int, user_id: int):
        """Foydalanuvchi suhbat va qarz kontekstini tozalash"""
        key = self._get_key(chat_id, user_id)
        if key in self.sessions:
            del self.sessions[key]

user_memory = UserMemoryManager()
