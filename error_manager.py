import os
import json
import re
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

ERROR_RULES_FILE = os.path.join(os.path.dirname(__file__), "data", "screen_errors.json")

class ErrorManager:
    """
    Kassa apparati ekrandagi 20+ turdagi xatoliklarni boshqaruvchi markaziy modul.
    Model o'zicha xulosa chiqarmaydi — u faqat ekrandagi faktlarni o'qiydi,
    yakuniy tashxis, xushmuomala yechim matni va video ushbu modul qoidalari asosida beriladi.
    """
    def __init__(self, filepath: str = ERROR_RULES_FILE):
        self.filepath = filepath
        self.rules: List[Dict[str, Any]] = []
        self.load_rules()

    def load_rules(self):
        """Xatoliklar qoidalarini JSON fayldan yuklash"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.rules = json.load(f)
                logger.info(f"ErrorManager: {len(self.rules)} ta kassa xatoligi qoidasi yuklandi.")
            except Exception as e:
                logger.error(f"ErrorManager qoidalarini yuklashda xatolik: {e}")
                self.rules = []
        else:
            self.rules = []

    def get_all_rules(self) -> List[Dict[str, Any]]:
        return self.rules

    def get_rule_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        for rule in self.rules:
            if rule.get("id") == rule_id:
                return rule
        return None

    def match_error(self, screen_facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        AI ekranda aniqlagan faktlar bo'yicha mos keluvchi xatolik qoidasini topish:
        screen_facts = {
            "time_mismatch": bool,
            "has_internet": bool,
            "error_type": str,
            "screen_text_summary": str,
            "detected_code_or_text": str
        }
        """
        # 1. Soat va sana xatoligi
        if screen_facts.get("time_mismatch"):
            return self.get_rule_by_id("time_error")

        # 2. Internet yo'qligi
        if screen_facts.get("has_internet") is False:
            return self.get_rule_by_id("no_internet")

        # 3. Ekrandagi umumiy xatolik matnlari va kodlarini to'plash
        raw_text_parts = [
            str(screen_facts.get("detected_code_or_text") or ""),
            str(screen_facts.get("screen_text_summary") or "")
        ]
        # raw_facts ichidagi boshqa stringlarni ham tekshirish
        for k, v in screen_facts.items():
            if isinstance(v, str) and k not in ["error_type"]:
                raw_text_parts.append(v)

        combined_text = " ".join(raw_text_parts).lower()

        # 4. Matn va xatolik kodlari bo'yicha kalit so'zlarni solishtirish (Eng uzun/aniq moslik ustuvor)
        best_rule = None
        highest_score = 0

        for rule in self.rules:
            keywords = rule.get("screen_keywords", [])
            for kw in keywords:
                kw_clean = kw.lower().strip()
                if kw_clean and kw_clean in combined_text:
                    # Uzunroq va aniqroq so'z yuqoriroq ball oladi (masalan "kod 204" > "kod")
                    score = len(kw_clean)
                    if score > highest_score:
                        highest_score = score
                        best_rule = rule

        if best_rule:
            return best_rule

        # 5. Standart error_type toifalari bo'yicha zaxira tanlash
        err_type = str(screen_facts.get("error_type", "")).lower()
        if err_type in ["debt", "blocked"]:
            return self.get_rule_by_id("debt_blocked")
        elif err_type == "fiscal_module":
            return self.get_rule_by_id("fiscal_module_error")
        elif err_type == "update":
            return self.get_rule_by_id("update_required")
        elif err_type == "paper":
            return self.get_rule_by_id("paper_out")

        return None

    def add_or_update_rule(
        self,
        rule_id: str,
        name: str,
        screen_keywords: List[str],
        response_text: str,
        video_id: Optional[int] = None,
        require_inn: bool = False,
        escalate_to_admin: bool = False
    ) -> bool:
        """Yangi xatolik qoidasini qo'shish yoki tahrirlash"""
        existing = self.get_rule_by_id(rule_id)
        if existing:
            existing.update({
                "name": name,
                "screen_keywords": screen_keywords,
                "response_text": response_text,
                "video_id": video_id,
                "require_inn": require_inn,
                "escalate_to_admin": escalate_to_admin
            })
        else:
            self.rules.append({
                "id": rule_id,
                "name": name,
                "screen_keywords": screen_keywords,
                "response_text": response_text,
                "video_id": video_id,
                "require_inn": require_inn,
                "escalate_to_admin": escalate_to_admin
            })
        self.save_rules()
        return True

    def delete_rule(self, rule_id: str) -> bool:
        """Qoidani o'chirish"""
        initial_len = len(self.rules)
        self.rules = [r for r in self.rules if r.get("id") != rule_id]
        if len(self.rules) < initial_len:
            self.save_rules()
            return True
        return False

    def save_rules(self):
        """Qoidalarni JSON faylga saqlash"""
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.rules, f, ensure_ascii=False, indent=2)
            logger.info(f"ErrorManager: {len(self.rules)} ta qoida muvaffaqiyatli saqlandi.")
        except Exception as e:
            logger.error(f"ErrorManager saqlashda xatolik: {e}")

error_manager = ErrorManager()
