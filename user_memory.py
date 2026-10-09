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
        # Xotira kaliti: f"{chat_id}:{user_id}" -> { "last_active": timestamp, "history": [ {"role": "user"|"model", "text": "..."} ] }
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

    def add_user_message(self, chat_id: int, user_id: int, text: str):
        """Foydalanuvchi xabarini xotiraga qo'shish"""
        self._cleanup_expired()
        key = self._get_key(chat_id, user_id)
        now = time.time()

        if key not in self.sessions:
            self.sessions[key] = {"last_active": now, "history": []}

        session = self.sessions[key]
        session["last_active"] = now
        session["history"].append({"role": "user", "text": text.strip()})

        # Xotirani oxirgi limit doirasida saqlash
        if len(session["history"]) > self.max_turns * 2:
            session["history"] = session["history"][-(self.max_turns * 2):]

    def add_assistant_message(self, chat_id: int, user_id: int, text: str):
        """Bot javobini xotiraga qo'shish"""
        key = self._get_key(chat_id, user_id)
        now = time.time()

        if key in self.sessions:
            session = self.sessions[key]
            session["last_active"] = now
            session["history"].append({"role": "model", "text": text.strip()})
            if len(session["history"]) > self.max_turns * 2:
                session["history"] = session["history"][-(self.max_turns * 2):]

    def get_user_history(self, chat_id: int, user_id: int) -> List[Dict[str, str]]:
        """Aynan shu foydalanuvchining eskirib qolmagan suhbat tarixini olish"""
        self._cleanup_expired()
        key = self._get_key(chat_id, user_id)
        if key in self.sessions:
            return self.sessions[key].get("history", [])
        return []

    def get_context_summary(self, chat_id: int, user_id: int) -> str:
        """AI promptiga qo'shish uchun suhbat tarixini qisqa matn qilib berish"""
        history = self.get_user_history(chat_id, user_id)
        if not history:
            return ""

        lines = []
        for msg in history[-4:]:  # Oxirgi 4 ta xabar yetarli
            role_label = "Mijoz" if msg["role"] == "user" else "Yordamchi"
            lines.append(f"{role_label}: {msg['text']}")
        return "\n".join(lines)

user_memory = UserMemoryManager()
