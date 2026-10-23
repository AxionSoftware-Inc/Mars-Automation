import os
import json
import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Xotiraning amal qilish muddati: 1 soat (soniyalarda)
TTL_SECONDS = 3600  # 3,600 soniya (1 soat)
MAX_HISTORY_TURNS = 10   # Har bir foydalanuvchi uchun oxirgi 10 ta xabar almashinuvi (20 ta xabar)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SESSIONS_FILE = os.path.join(DATA_DIR, "user_sessions.json")

class UserMemoryManager:
    def __init__(self, ttl_seconds: int = TTL_SECONDS, max_turns: int = MAX_HISTORY_TURNS):
        self.ttl_seconds = ttl_seconds
        self.max_turns = max_turns
        # Xotira kaliti: f"{chat_id}:{user_id}" -> { "last_active": timestamp, "history": [...], "debt_info": {...} }
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.load_sessions()

    def _get_key(self, chat_id: int, user_id: int) -> str:
        return f"{chat_id}:{user_id}"

    def load_sessions(self):
        """Diskdan avvalgi sessiyalarni yuklab olish"""
        if not os.path.exists(SESSIONS_FILE):
            return
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    now = time.time()
                    # Faqat eskirib ketmagan (2 soat ichidagi) sessiyalarni yuklash
                    self.sessions = {
                        k: v for k, v in data.items()
                        if now - v.get("last_active", 0) <= self.ttl_seconds
                    }
                    logger.info(f"UserMemory: Diskdan {len(self.sessions)} ta faol sessiya yuklandi.")
        except Exception as e:
            logger.warning(f"UserMemory: Sessiyalarni yuklashda xatolik: {e}")

    def save_sessions(self):
        """Sessiyalarni diskka xavfsiz saqlash"""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            temp_file = SESSIONS_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, SESSIONS_FILE)
        except Exception as e:
            logger.warning(f"UserMemory: Sessiyalarni saqlashda xatolik: {e}")

    def _cleanup_expired(self):
        """Eskirgan (2 soatdan oshgan) sessiyalarni tozalash"""
        now = time.time()
        expired_keys = [
            k for k, v in self.sessions.items()
            if now - v.get("last_active", 0) > self.ttl_seconds
        ]
        for k in expired_keys:
            del self.sessions[k]
        if expired_keys:
            logger.info(f"UserMemory: {len(expired_keys)} ta eskirgan sessiya tozalandi.")
            self.save_sessions()

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

    def set_last_id(self, chat_id: int, user_id: int, identifier: str, org_name: str = "", debt: Optional[float] = None, device_models: str = ""):
        """Foydalanuvchi qidirgan oxirgi INN/JSHSHIR va korxona ma'lumotlarini eslab qolish"""
        session = self._get_or_create_session(chat_id, user_id)
        new_id = str(identifier).strip()
        is_new_identifier = (session.get("last_id") != new_id)

        session["last_id"] = new_id

        if is_new_identifier:
            # Yangi INN kiritilganda eski korxona va eski qarz ma'lumotlarini tozalash!
            session["org_name"] = None
            session["device_models"] = None
            session["debt_info"] = None

        if org_name:
            session["org_name"] = str(org_name).strip()
        if device_models:
            session["device_models"] = str(device_models).strip()

        # Agar baza orqali tekshirish imkoni bo'lsa va org_name/debt to'liq berilmagan bo'lsa avto-lookup
        if (not session.get("org_name") or debt is None) and (len(new_id) in (9, 14) and new_id.isdigit()):
            try:
                from excel_manager import excel_manager
                d_res = excel_manager.check_debt(new_id)
                if d_res and d_res.get("record"):
                    rec = d_res["record"]
                    if not session.get("org_name"):
                        session["org_name"] = rec.get("org_name", "")
                    if debt is None:
                        debt = float(rec.get("debt_amount", 0.0) or 0.0)
                    if not session.get("device_models"):
                        search_res = excel_manager.search(new_id)
                        session["device_models"] = excel_manager.get_device_model_summary(search_res)
            except Exception as e:
                logger.warning(f"set_last_id avto-lookup xatolik: {e}")

        # Agar bu o'sha INN bo'lsa va debt None bo'lsa, mavjudini saqlash
        existing_debt = 0.0
        if not is_new_identifier and session.get("debt_info") and "debt" in session["debt_info"]:
            existing_debt = session["debt_info"]["debt"]
        final_debt = debt if debt is not None else existing_debt

        session["debt_info"] = {
            "identifier": new_id,
            "org_name": session.get("org_name") or "",
            "debt": final_debt,
            "device_models": session.get("device_models") or ""
        }

        # Barcha tekshirilgan INNlar tarixini xotirada saqlash
        if "checked_inns" not in session:
            session["checked_inns"] = {}
        session["checked_inns"][new_id] = {
            "identifier": new_id,
            "org_name": session.get("org_name") or "",
            "debt": final_debt
        }
        self.save_sessions()

    def _fallback_from_group(self, chat_id: int, field: str, user_id: Optional[int] = None) -> Any:
        """Guruh chatlarida (chat_id < 0) biror xodim yozgan ma'lumotni guruh kontekstidan topish"""
        if chat_id >= 0:
            return None
        prefix = f"{chat_id}:"
        user_key = f"{chat_id}:{user_id}" if user_id is not None else None
        user_inn = self.sessions.get(user_key, {}).get("last_id") if user_key else None

        # Oxirgi faol bo'lgan sessiyalarni saralash
        sorted_sessions = sorted(
            [(k, s) for k, s in self.sessions.items() if k.startswith(prefix)],
            key=lambda x: x[1].get("last_active", 0),
            reverse=True
        )

        # Agar guruhda bir nechta turli korxonalar (INN) faol bo'lsa,
        # INNi yo'q yangi foydalanuvchiga tasodifiy korxonani biriktirmaymiz (ambiguity guardrail)
        if field == "last_id":
            distinct_inns = {s.get("last_id") for _, s in sorted_sessions if s.get("last_id")}
            if len(distinct_inns) > 1:
                return None

        for k, s in sorted_sessions:
            if user_key and k == user_key:
                continue
            # Agar foydalanuvchida o'z INNi bo'lsa va bu boshqa sessiyaning INNisiga to'g'ri kelmasa,
            # begona korxonaning fiskal modulini yoki boshqa ma'lumotlarini o'zlashtirmaymiz!
            if user_inn and s.get("last_id") and s.get("last_id") != user_inn:
                continue
            val = s.get(field)
            if val is not None and val != "":
                return val
        return None

    def get_checked_inns(self, chat_id: int, user_id: int) -> Dict[str, Dict[str, Any]]:
        """Sessiyada tekshirilgan barcha INNlar va ularning qarz ma'lumotlarini olish"""
        session = self._get_or_create_session(chat_id, user_id)
        inns = session.get("checked_inns", {})
        if not inns and chat_id < 0:
            fb_inns = self._fallback_from_group(chat_id, "checked_inns", user_id)
            if fb_inns and isinstance(fb_inns, dict):
                return fb_inns
        return inns

    def set_annual_status(self, chat_id: int, user_id: int, has_debt: bool, details: str = "", unavailable: bool = False):
        """Yillik Davlat Soliq (OFD) to'lovi holatini xotiraga saqlash"""
        session = self._get_or_create_session(chat_id, user_id)
        session["annual_status"] = {
            "has_debt": has_debt,
            "details": details,
            "unavailable": unavailable
        }
        self.save_sessions()

    def get_annual_status(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Yillik Davlat Soliq (OFD) to'lovi holatini olish"""
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("annual_status") or self._fallback_from_group(chat_id, "annual_status", user_id)

    def get_last_id(self, chat_id: int, user_id: int) -> Optional[str]:
        """Foydalanuvchining oxirgi INN/JSHSHIR raqamini olish"""
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("last_id") or self._fallback_from_group(chat_id, "last_id", user_id)

    def get_org_name(self, chat_id: int, user_id: int) -> Optional[str]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("org_name") or self._fallback_from_group(chat_id, "org_name", user_id)

    def set_last_receipt(self, chat_id: int, user_id: int, receipt_info: Dict[str, Any]):
        """Yuborilgan to'lov kvitansiyasi holatini xotiraga saqlash (kunlik Excel qarzini o'zgartirmasdan!)"""
        session = self._get_or_create_session(chat_id, user_id)
        session["last_receipt"] = receipt_info
        if "receipt_history" not in session or not isinstance(session["receipt_history"], list):
            session["receipt_history"] = []
        session["receipt_history"].append({
            "time": time.time(),
            "info": receipt_info
        })
        # Faqat oxirgi 10 ta kvitansiyani saqlash
        session["receipt_history"] = session["receipt_history"][-10:]
        self.save_sessions()

    def get_todays_paid_total(self, chat_id: int, user_id: int, inn: Optional[str] = None) -> float:
        """Foydalanuvchi bugun shu INN bo'yicha yuborgan kvitansiyalar summasi yig'indisi"""
        session = self._get_or_create_session(chat_id, user_id)
        rec_hist = session.get("receipt_history") or []
        now = time.time()
        total = 0.0
        for item in rec_hist:
            # Oxirgi 12 soat ichidagi va eski deb topilmagan kvitansiyalar
            if now - item.get("time", 0) <= 12 * 3600:
                inf = item.get("info") or {}
                if not inf.get("is_old_receipt"):
                    item_inn = inf.get("inn")
                    if not inn or not item_inn or item_inn == inn:
                        total += float(inf.get("amount", 0) or 0)
        return total

    def is_recent_duplicate_receipt(self, chat_id: int, user_id: int, tx_id: Optional[str], amount: float, p_date: Optional[str] = None) -> bool:
        """Oxirgi 1 soat ichida aynan shu tranzaksiya yoki bir xil summa/sana yuborilganmi?"""
        if not tx_id and amount <= 0:
            return False
        session = self._get_or_create_session(chat_id, user_id)
        rec_hist = session.get("receipt_history") or []
        now = time.time()
        for item in rec_hist:
            if now - item.get("time", 0) <= 3600:  # 1 soat ichida
                inf = item.get("info") or {}
                # 1) Tranzaksiya raqami mos kelsa
                if tx_id and inf.get("transaction_id") and str(inf.get("transaction_id")) == str(tx_id):
                    return True
                # 2) Bir xil summa va bir xil to'lov sanasi bo'lsa
                if amount > 0 and inf.get("amount") == amount and p_date and inf.get("date") == p_date:
                    return True
        return False

    def get_last_receipt(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("last_receipt") or self._fallback_from_group(chat_id, "last_receipt", user_id)

    def get_debt_info(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Oxirgi tekshirilgan qarz ma'lumotlarini olish"""
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("debt_info") or self._fallback_from_group(chat_id, "debt_info", user_id)

    def set_last_topic(self, chat_id: int, user_id: int, topic: str):
        """Oxirgi mavzuni saqlash (masalan: 'receipt_submitted', 'debt_checked', 'time_error')"""
        session = self._get_or_create_session(chat_id, user_id)
        session["last_topic"] = topic
        self.save_sessions()

    def set_issue_mode(self, chat_id: int, user_id: int, enabled: bool = True, initial_query: str = ""):
        """Foydalanuvchi apparat nosozligi/muammosi rejimida ekanligini belgilash"""
        session = self._get_or_create_session(chat_id, user_id)
        session["issue_mode"] = enabled
        if initial_query:
            session["issue_initial_query"] = str(initial_query).strip()
        self.save_sessions()

    def is_issue_mode(self, chat_id: int, user_id: int) -> bool:
        """Foydalanuvchi nosozlikni hal qilish pipeline'ida turibdimi? (Faqat shu user uchun)"""
        session = self._get_or_create_session(chat_id, user_id)
        return bool(session.get("issue_mode", False))

    def clear_issue_mode(self, chat_id: int, user_id: int):
        """Muammo to'liq hal bo'lgach yoki eskalatsiya qilingach rejimni yopish"""
        session = self._get_or_create_session(chat_id, user_id)
        session["issue_mode"] = False
        session["issue_initial_query"] = None
        self.save_sessions()

    def get_issue_initial_query(self, chat_id: int, user_id: int) -> Optional[str]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("issue_initial_query")

    def get_last_topic(self, chat_id: int, user_id: int) -> Optional[str]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("last_topic")

    def mark_escalated_to_admin(self, chat_id: int, user_id: int, reason: str = ""):
        """Foydalanuvchi adminga/ustaga yo'naltirilganini xotiraga belgilash"""
        session = self._get_or_create_session(chat_id, user_id)
        session["is_escalated_to_admin"] = True
        session["escalated_time"] = time.time()
        session["escalation_reason"] = reason
        session["escalation_repeat_count"] = 0
        self.save_sessions()

    def is_escalated_to_admin(self, chat_id: int, user_id: int, max_wait_seconds: int = 900) -> bool:
        """
        Foydalanuvchi adminga yo'naltirilgan va hali admin javobini kutyaptimi?
        MUHIM: Guruhda bitta odam eskalatsiya bo'lsa, guruhdagi boshqa odamlarga ta'sir qilmasligi shart!
        """
        session = self._get_or_create_session(chat_id, user_id)
        if not session.get("is_escalated_to_admin"):
            return False
        esc_time = session.get("escalated_time", 0)
        if time.time() - esc_time > max_wait_seconds:
            session["is_escalated_to_admin"] = False
            session["escalation_repeat_count"] = 0
            self.save_sessions()
            return False
        return True

    def increment_escalation_repeats(self, chat_id: int, user_id: int) -> int:
        """Eskalatsiyadan keyingi takroriy xabarlar sonini oshirish"""
        session = self._get_or_create_session(chat_id, user_id)
        cnt = session.get("escalation_repeat_count", 0) + 1
        session["escalation_repeat_count"] = cnt
        self.save_sessions()
        return cnt

    def clear_escalation(self, chat_id: int, user_id: int):
        """Eskalatsiya holatini tozalash"""
        session = self._get_or_create_session(chat_id, user_id)
        session["is_escalated_to_admin"] = False
        session["escalated_time"] = 0
        session["escalation_repeat_count"] = 0
        self.save_sessions()

    def get_user_turn_count(self, chat_id: int, user_id: int) -> int:
        """Foydalanuvchi yuborgan jami xabarlar soni"""
        session = self._get_or_create_session(chat_id, user_id)
        return len([m for m in session.get("history", []) if m.get("role") == "user"])

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

        checked_inns = session.get("checked_inns", {})
        if len(checked_inns) > 1:
            parts.append("=== MIJOZ TEKSHIRGAN BARCHA KORXONALAR RO'YXATI ===")
            for c_id, c_data in checked_inns.items():
                try:
                    from excel_manager import excel_manager
                    live_res = excel_manager.search(c_id)
                    c_d = sum(item.get("debt", 0.0) for item in live_res) if live_res else c_data.get("debt", 0.0)
                    c_n = live_res[0].get("name", "") if live_res else c_data.get("org_name", "")
                except Exception:
                    c_d = c_data.get("debt", 0.0)
                    c_n = c_data.get("org_name", "")
                if c_d > 0:
                    parts.append(f"• Korxona: {c_n} (INN: {c_id}) -> QARZDORLIK: {c_d:,.0f} so'm MAVJUD")
                else:
                    parts.append(f"• Korxona: {c_n} (INN: {c_id}) -> Qarzdorlik yo'q (0 so'm)")
        elif last_id:
            try:
                from excel_manager import excel_manager
                live_res = excel_manager.search(last_id)
                if live_res:
                    live_debt = sum(item.get("debt", 0.0) for item in live_res)
                    if live_debt > 0:
                        parts.append(f"• «Mars» oylik abonent to'lovidan joriy qarzdorlik: {live_debt:,.0f} so'm mavjud.")
                    elif live_debt < 0:
                        parts.append(f"• «Mars» oylik abonent to'lovi: Qarzdorlik YO'Q (ortiqcha to'lov: {abs(live_debt):,.0f} so'm).")
                    else:
                        parts.append("• «Mars» oylik abonent to'lovidan joriy qarzdorlik: 0 so'm (Qarzdorlik yo'q).")
                elif debt_info:
                    d_val = debt_info.get("debt", 0.0)
                    if d_val > 0:
                        parts.append(f"• «Mars» oylik abonent to'lovidan joriy qarzdorlik: {d_val:,.0f} so'm mavjud.")
                    elif d_val < 0:
                        parts.append(f"• «Mars» oylik abonent to'lovi: Qarzdorlik YO'Q (ortiqcha to'lov: {abs(d_val):,.0f} so'm).")
                    else:
                        parts.append("• «Mars» oylik abonent to'lovidan joriy qarzdorlik: 0 so'm (Qarzdorlik yo'q).")
            except Exception:
                if debt_info:
                    d_val = debt_info.get("debt", 0.0)
                    if d_val > 0:
                        parts.append(f"• «Mars» oylik abonent to'lovidan joriy qarzdorlik: {d_val:,.0f} so'm mavjud.")
                    elif d_val < 0:
                        parts.append(f"• «Mars» oylik abonent to'lovi: Qarzdorlik YO'Q (ortiqcha to'lov: {abs(d_val):,.0f} so'm).")
                    else:
                        parts.append("• «Mars» oylik abonent to'lovidan joriy qarzdorlik: 0 so'm (Qarzdorlik yo'q).")
        elif debt_info:
            d_val = debt_info.get("debt", 0.0)
            if d_val > 0:
                parts.append(f"• «Mars» oylik abonent to'lovidan joriy qarzdorlik: {d_val:,.0f} so'm mavjud.")
            elif d_val < 0:
                parts.append(f"• «Mars» oylik abonent to'lovi: Qarzdorlik YO'Q (ortiqcha to'lov: {abs(d_val):,.0f} so'm).")
            else:
                parts.append("• «Mars» oylik abonent to'lovidan joriy qarzdorlik: 0 so'm (Qarzdorlik yo'q).")

        ann_st = self.get_annual_status(chat_id, user_id)
        if ann_st:
            if ann_st.get("unavailable"):
                parts.append("• Davlat Soliq (OFD) yillik to'lovi: Tizim vaqtincha javob bermadi (aniqlanmagan).")
            elif ann_st.get("has_debt"):
                parts.append("• Davlat Soliq (OFD) yillik to'lovi: QARZDORLIK MAVJUD (440 000 so'm, Yangi Texnologiyalar DUK).")
            else:
                det = ann_st.get("details", "")
                parts.append(f"• Davlat Soliq (OFD) yillik to'lovi: QARZDORLIK YO'Q (Litsenziya faol{', ' + det if det else ''}).")

        if last_receipt:
            amt = last_receipt.get("amount", 0.0)
            parts.append("=== YAQINDAGI TO'LOV KVITANSIYASI HOLATI ===")
            parts.append(f"• Mijoz yaqinda to'lov kvitansiyasini yubordi (Summa: {amt:,.0f} so'm).")
            parts.append("• Kvitansiya tekshirish uchun mas'ul adminga yetkazilgan. Qarzdorlik holati faqat kunlik Excel bazasi bo'yicha hisoblanadi.")

        parts.append("• Tizim qoidasi: Abonent to'lovi har oyning 6-sanasigacha to'lanadi. 6-sanada to'lanmasa avtomatik to'xtaydi.")

        if history:
            parts.append("\n=== SUHBAT TARIXI (oxirgi xabarlar) ===")
            for msg in history[-8:]:
                role_label = "Mijoz" if msg["role"] == "user" else "Yordamchi (Bot)"
                parts.append(f"{role_label}: {msg['text']}")

        return "\n".join(parts)

    def _load_pending_receipts_disk(self) -> Dict[str, Any]:
        p = os.path.join(os.path.dirname(__file__), "data", "pending_receipts.json")
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_pending_receipts_disk(self, data: Dict[str, Any]):
        p = os.path.join(os.path.dirname(__file__), "data", "pending_receipts.json")
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Pending receipt disk save error: {e}")

    def set_pending_receipt(self, chat_id: int, user_id: int, receipt_data: Dict[str, Any]):
        """INN aniqlanmagan kvitansiyani foydalanuvchi INN yozgunicha vaqtincha saqlab turish (RAM + Disk)"""
        session = self._get_or_create_session(chat_id, user_id)
        session["pending_receipt"] = receipt_data
        key = self._get_key(chat_id, user_id)
        disk_data = self._load_pending_receipts_disk()
        disk_data[key] = receipt_data
        self._save_pending_receipts_disk(disk_data)

    def get_pending_receipt(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        session = self._get_or_create_session(chat_id, user_id)
        res = session.get("pending_receipt")
        if not res:
            key = self._get_key(chat_id, user_id)
            disk_data = self._load_pending_receipts_disk()
            res = disk_data.get(key)
            if res:
                session["pending_receipt"] = res
        return res

    def clear_pending_receipt(self, chat_id: int, user_id: int):
        session = self._get_or_create_session(chat_id, user_id)
        session["pending_receipt"] = None
        key = self._get_key(chat_id, user_id)
        disk_data = self._load_pending_receipts_disk()
        if key in disk_data:
            del disk_data[key]
            self._save_pending_receipts_disk(disk_data)

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
        self.save_sessions()

    def clear_last_fm(self, chat_id: int, user_id: int):
        """Xato yoki topilmagan Fiskal modul raqamini xotiradan tozalash"""
        session = self._get_or_create_session(chat_id, user_id)
        session["last_fm"] = None
        self.save_sessions()

    def get_last_fm(self, chat_id: int, user_id: int) -> Optional[str]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("last_fm") or self._fallback_from_group(chat_id, "last_fm", user_id)

    def set_last_photo(self, chat_id: int, user_id: int, file_id: str):
        """Oxirgi yuborilgan kassa rasmi file_id sini saqlash"""
        session = self._get_or_create_session(chat_id, user_id)
        session["last_photo"] = file_id
        self.save_sessions()

    def get_last_photo(self, chat_id: int, user_id: int) -> Optional[str]:
        session = self._get_or_create_session(chat_id, user_id)
        return session.get("last_photo") or self._fallback_from_group(chat_id, "last_photo", user_id)

    def clear_context(self, chat_id: int, user_id: int):
        """Foydalanuvchi suhbat va qarz kontekstini tozalash"""
        key = self._get_key(chat_id, user_id)
        if key in self.sessions:
            del self.sessions[key]
            self.save_sessions()

    def clear(self):
        """Barcha sessiyalarni tozalash (testlar va qayta ishga tushirish uchun)"""
        self.sessions.clear()
        self.save_sessions()

user_memory = UserMemoryManager()
