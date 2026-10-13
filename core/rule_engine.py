"""
core/rule_engine.py
===================
Modulli Patch va Qoidalar Tizimi (Plug & Play Rule Engine):
Loyiha yadrosiga (CoreEngine) tegmasdan, istalgan 10-20 ta mayda shartlar,
istisnolar, maxsus javoblar yoki mijoz talablarini xavfsiz va bir-biriga
xalal bermaydigan holda qo'shish, o'chirish va boshqarish imkonini beradi.

Har bir qoida (Rule):
1. O'zining prioritetiga ega (yuqori prioritet avval ishlaydi).
2. can_handle(ctx) orqali tekshiriladi.
3. handle(ctx) orqali DecisionResult qaytaradi (yoki None qaytarib zanjirni davom ettiradi).
4. Deklarativ rejimda: data/custom_patches.json orqali kodi o'zgartirilmasdan ham boshqariladi.
"""

import os
import re
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable

from core.models import DecisionResult, ActionType
from user_memory import user_memory

logger = logging.getLogger(__name__)

PATCHES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "custom_patches.json")

@dataclass
class RuleContext:
    """
    Qoida tekshiruvi uchun zarur bo'lgan barcha ma'lumotlar to'plami.
    """
    text: str
    clean_text: str
    lower_text: str
    chat_id: int
    user_id: int
    user_name: str = "Mijoz"
    user_username: str = ""
    user_script: str = "latin"
    found_inn: Optional[str] = None
    found_fm: Optional[str] = None
    remembered_id: Optional[str] = None
    bot: Optional[Any] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class BaseRule(ABC):
    """
    Barcha qoidalar uchun asosiy abstrakt sinf.
    """
    name: str = "base_rule"
    priority: int = 50   # 100: eng yuqori (favqulodda patchlar), 50: standart, 10: fallback
    enabled: bool = True

    @abstractmethod
    async def can_handle(self, ctx: RuleContext) -> bool:
        """Ushbu qoida xabarga to'g'ri keladimi?"""
        pass

    @abstractmethod
    async def handle(self, ctx: RuleContext) -> Optional[DecisionResult]:
        """Qoidani ijro etish va natija qaytarish."""
        pass


class DeclarativePatchRule(BaseRule):
    """
    data/custom_patches.json faylida belgilangan deklarativ patchlarni ijro etuvchi qoida.
    Bu orqali dasturchi yoki admin kod yozmasdan turib ham mayda patchlarni kiritishi mumkin.
    """
    name: str = "declarative_patch_rule"
    priority: int = 85   # Odatiy tekshiruvlardan oldin ishlaydi
    enabled: bool = True

    def __init__(self, patch_data: Dict[str, Any]):
        self.patch_data = patch_data
        self.id = patch_data.get("id", "patch_unknown")
        self.name = f"patch_{self.id}"
        self.priority = patch_data.get("priority", 85)
        self.enabled = patch_data.get("enabled", True)
        self.keywords = [k.lower() for k in patch_data.get("keywords", [])]
        self.match_mode = patch_data.get("match_mode", "any_keyword") # any_keyword, all_keywords, exact, regex
        self.condition = patch_data.get("condition", "always") # always, has_inn, no_inn, has_fm, no_fm
        self.reply_template = patch_data.get("reply_text", "")
        self.video_id = patch_data.get("video_id")
        self.action = ActionType[patch_data.get("action", "DIAGNOSE_AND_REPLY")]
        self.should_notify_admin = patch_data.get("should_notify_admin", False)
        self.admin_alert_text = patch_data.get("admin_alert_text")

    async def can_handle(self, ctx: RuleContext) -> bool:
        if not self.enabled:
            return False

        # Shartlarni tekshirish:
        if self.condition == "has_inn" and not (ctx.found_inn or ctx.remembered_id):
            return False
        if self.condition == "no_inn" and (ctx.found_inn or ctx.remembered_id):
            return False
        if self.condition == "has_fm" and not ctx.found_fm:
            return False
        if self.condition == "no_fm" and ctx.found_fm:
            return False

        # Matn mosligini tekshirish:
        if self.match_mode == "exact":
            return ctx.lower_text == self.patch_data.get("exact_text", "").lower()
        elif self.match_mode == "regex":
            pattern = self.patch_data.get("regex", "")
            return bool(re.search(pattern, ctx.clean_text, re.IGNORECASE))
        elif self.match_mode == "all_keywords":
            return all(kw in ctx.lower_text for kw in self.keywords)
        else: # any_keyword
            return any(kw in ctx.lower_text for kw in self.keywords)

    async def handle(self, ctx: RuleContext) -> Optional[DecisionResult]:
        # Reply template ichidagi parametrlarni to'ldirish:
        reply = self.reply_template.format(
            user_name=ctx.user_name,
            inn=ctx.found_inn or ctx.remembered_id or "-",
            fm=ctx.found_fm or "-"
        )
        return DecisionResult(
            action=self.action,
            reply_text=reply,
            video_id=self.video_id,
            should_notify_admin=self.should_notify_admin,
            admin_alert_text=self.admin_alert_text or f"Patch {self.id} triggered: {ctx.clean_text}",
            log_reason=f"Declarative patch triggered: {self.id}"
        )


class FunctionalRule(BaseRule):
    """
    Python funksiyalari orqali tezkor yangi qoida yaratish uchun adapter.
    """
    def __init__(
        self,
        name: str,
        condition_fn: Callable[[RuleContext], bool],
        handler_fn: Callable[[RuleContext], Any],
        priority: int = 50,
        enabled: bool = True
    ):
        self.name = name
        self.condition_fn = condition_fn
        self.handler_fn = handler_fn
        self.priority = priority
        self.enabled = enabled

    async def can_handle(self, ctx: RuleContext) -> bool:
        if not self.enabled:
            return False
        res = self.condition_fn(ctx)
        if asyncio.iscoroutine(res):
            return await res
        return bool(res)

    async def handle(self, ctx: RuleContext) -> Optional[DecisionResult]:
        res = self.handler_fn(ctx)
        if asyncio.iscoroutine(res):
            return await res
        return res


class RuleEngine:
    """
    Markaziy Qoidalar Dvigateli.
    Barcha qoidalar, patchlar va istisnolarni ro'yxatga oladi, tartiblaydi va ijro etadi.
    """
    def __init__(self, patches_path: str = PATCHES_FILE):
        self.patches_path = patches_path
        self._rules: List[BaseRule] = []
        self._load_declarative_patches()

    def _load_declarative_patches(self):
        """data/custom_patches.json faylidan patchlarni yuklash"""
        if not os.path.exists(self.patches_path):
            try:
                os.makedirs(os.path.dirname(self.patches_path), exist_ok=True)
                with open(self.patches_path, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"custom_patches.json yaratishda xatolik: {e}")
            return

        try:
            with open(self.patches_path, "r", encoding="utf-8") as f:
                patches = json.load(f)
            for p in patches:
                if isinstance(p, dict) and p.get("id"):
                    self.register_rule(DeclarativePatchRule(p))
            logger.info(f"RuleEngine: {len(patches)} ta deklarativ patch yuklandi.")
        except Exception as e:
            logger.error(f"RuleEngine: custom_patches.json yuklashda xatolik: {e}")

    def reload_patches(self):
        """Barcha deklarativ patchlarni qayta yuklash"""
        self._rules = [r for r in self._rules if not isinstance(r, DeclarativePatchRule)]
        self._load_declarative_patches()

    def register_rule(self, rule: BaseRule):
        """Yangi qoidani ro'yxatga olish va prioritet bo'yicha tartiblash"""
        # Avval mavjud xuddi shu nomli qoidani olib tashlaymiz (takrorlanish bo'lmasligi uchun)
        self.unregister_rule(rule.name)
        self._rules.append(rule)
        # Prioritet bo'yicha kamayish tartibida saralash (eng katta raqam avval ishlaydi)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.debug(f"RuleEngine: Yangi qoida qo'shildi: {rule.name} (priority={rule.priority})")

    def unregister_rule(self, name: str):
        """Qoidani nomiga ko'ra olib tashlash"""
        self._rules = [r for r in self._rules if r.name != name]

    def add_patch(
        self,
        patch_id: str,
        keywords: List[str],
        reply_text: str,
        video_id: Optional[int] = None,
        priority: int = 85,
        condition: str = "always",
        match_mode: str = "any_keyword"
    ) -> bool:
        """
        Dastur orqali yangi deklarativ patch qo'shish va faylga saqlash.
        Bu orqali kodni o'zgartirmasdan yangi shart qo'shiladi!
        """
        try:
            patches = []
            if os.path.exists(self.patches_path):
                with open(self.patches_path, "r", encoding="utf-8") as f:
                    patches = json.load(f)

            # Mavjud bo'lsa yangilaymiz, bo'lmasa qo'shamiz
            patches = [p for p in patches if p.get("id") != patch_id]
            new_patch = {
                "id": patch_id,
                "enabled": True,
                "priority": priority,
                "keywords": keywords,
                "match_mode": match_mode,
                "condition": condition,
                "reply_text": reply_text,
                "video_id": video_id,
                "action": "DIAGNOSE_AND_REPLY"
            }
            patches.append(new_patch)

            with open(self.patches_path, "w", encoding="utf-8") as f:
                json.dump(patches, f, indent=2, ensure_ascii=False)

            self.reload_patches()
            logger.info(f"RuleEngine: Yangi patch saqlandi va faollashtirildi: {patch_id}")
            return True
        except Exception as e:
            logger.error(f"RuleEngine: Patch qo'shishda xatolik: {e}")
            return False

    def remove_patch(self, patch_id: str) -> bool:
        """Patchni fayldan o'chirish"""
        try:
            if not os.path.exists(self.patches_path):
                return False
            with open(self.patches_path, "r", encoding="utf-8") as f:
                patches = json.load(f)
            patches = [p for p in patches if p.get("id") != patch_id]
            with open(self.patches_path, "w", encoding="utf-8") as f:
                json.dump(patches, f, indent=2, ensure_ascii=False)
            self.reload_patches()
            return True
        except Exception as e:
            logger.error(f"RuleEngine: Patch o'chirishda xatolik: {e}")
            return False

    async def evaluate(self, ctx: RuleContext) -> Optional[DecisionResult]:
        """
        Barcha faol qoidalarni navbatma-navbat tekshirib, mos kelgan birinchi qoidaning natijasini qaytaradi.
        Agar hech bir qoida mos kelmasa -> None qaytaradi (asosiy yadro o'z ishini davom ettiradi).
        """
        for rule in self._rules:
            if not rule.enabled:
                continue
            try:
                if await rule.can_handle(ctx):
                    logger.info(f"🎯 RuleEngine: Qoida ishga tushdi -> '{rule.name}' (priority={rule.priority})")
                    result = await rule.handle(ctx)
                    if result is not None:
                        return result
            except Exception as e:
                logger.error(f"RuleEngine: '{rule.name}' qoidasini ijro etishda xatolik: {e}", exc_info=True)
                # Bitta patchdagi xatolik boshqa qoidalarni to'xtatib qo'ymasligi shart!
                continue

        return None

    def get_rules_summary(self) -> List[Dict[str, Any]]:
        """Barcha qoidalar ro'yxatini qaytaradi"""
        return [
            {"name": r.name, "priority": r.priority, "enabled": r.enabled}
            for r in self._rules
        ]

import asyncio

rule_engine = RuleEngine()
