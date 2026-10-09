import os
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

ERROR_RULES_FILE = os.path.join(os.path.dirname(__file__), "data", "screen_errors.json")

class ErrorManager:
    """
    Kassa apparati ekrandagi xatoliklarni boshqaruvchi modul.
    Model o'zicha xulosa chiqarmaydi — u faqat ekrandagi faktlarni o'qiydi,
    yakuniy xulosa va yechim ushbu modul qoidalari asosida beriladi.
    """
    def __init__(self, filepath: str = ERROR_RULES_FILE):
        self.filepath = filepath
        self.rules: List[Dict[str, Any]] = []
        self.load_rules()

    def load_rules(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.rules = json.load(f)
                logger.info(f"ErrorManager: {len(self.rules)} ta xatolik qoidasi yuklandi.")
            except Exception as e:
                logger.error(f"ErrorManager qoidalarini yuklashda xatolik: {e}")
                self.rules = []
        else:
            self.rules = []

    def get_rule_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        for rule in self.rules:
            if rule.get("id") == rule_id:
                return rule
        return None

    def match_error(self, screen_facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        AI o'qib bergan ekrandagi faktlarga asosan biz boshqaradigan qoidani tanlash:
        screen_facts = {
            "time_mismatch": bool,
            "has_internet": bool,
            "error_type": str, # "debt", "fiscal_module", "update", "paper", "none"
            "detected_code_or_text": str
        }
        """
        # 1. Soat xatoligi ustuvorligi
        if screen_facts.get("time_mismatch"):
            return self.get_rule_by_id("time_error")

        # 2. Internet yo'qligi ustuvorligi
        if screen_facts.get("has_internet") is False:
            return self.get_rule_by_id("no_internet")

        # 3. Ekrandagi xatolik turi
        err_type = screen_facts.get("error_type", "")
        if err_type == "debt" or err_type == "blocked":
            return self.get_rule_by_id("debt_blocked")
        elif err_type == "fiscal_module":
            return self.get_rule_by_id("fiscal_module_error")
        elif err_type == "update":
            return self.get_rule_by_id("update_required")
        elif err_type == "paper":
            return self.get_rule_by_id("paper_out")

        # 4. Matn/kod bo'yicha qidirish
        raw_text = (screen_facts.get("detected_code_or_text") or "").lower()
        if raw_text:
            for rule in self.rules:
                for kw in rule.get("screen_keywords", []):
                    if kw.lower() in raw_text:
                        return rule

        return None

    def add_or_update_rule(self, rule_id: str, name: str, screen_keywords: List[str], 
                            response_text: str, video_id: Optional[int] = None, require_inn: bool = False):
        """Yangi xatolik qo'shish yoki mavjudini tahrirlash"""
        existing = self.get_rule_by_id(rule_id)
        if existing:
            existing.update({
                "name": name,
                "screen_keywords": screen_keywords,
                "response_text": response_text,
                "video_id": video_id,
                "require_inn": require_inn
            })
        else:
            self.rules.append({
                "id": rule_id,
                "name": name,
                "screen_keywords": screen_keywords,
                "response_text": response_text,
                "video_id": video_id,
                "require_inn": require_inn
            })
        self.save_rules()

    def save_rules(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.rules, f, ensure_ascii=False, indent=2)
            logger.info("ErrorManager: Qoidalar muvaffaqiyatli saqlandi.")
        except Exception as e:
            logger.error(f"ErrorManager saqlashda xatolik: {e}")

error_manager = ErrorManager()
