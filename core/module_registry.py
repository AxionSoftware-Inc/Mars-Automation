"""
core/module_registry.py
=======================
Professional Modulli Arxitektura (Plugin / Module Bus) tizimi.
Har qanday ichki yoki tashqi katta modul (To'lov moduli, Administratsiya moduli,
Guruhda javob berish moduli, CRM va h.k.) BaseBotModule interfeysini meros olib,
ModuleRegistry orqali tizimga bir qator kod bilan ulanadi.
"""

import logging
from abc import ABC
from typing import List, Dict, Any, Optional
from aiogram import Router, Bot, Dispatcher

logger = logging.getLogger(__name__)


class BaseBotModule(ABC):
    """
    Barcha katta va kichik modullar uchun asosiy shablon (Interface).
    Yangi modul qo'shish uchun ushbu klassdan meros olinadi.
    """
    name: str = "unnamed_module"
    version: str = "1.0.0"
    description: str = ""
    priority: int = 50  # Router va pipeline ulanish ustuvorligi (katta raqam = yuqori ustuvorlik)
    enabled: bool = True

    def get_router(self) -> Optional[Router]:
        """Agar modulning o'z Telegram Router'i bo'lsa, shu yerda qaytaradi."""
        return None

    async def on_startup(self, bot: Bot, dp: Dispatcher) -> None:
        """Bot ishga tushganda modulning boshlang'ich yuklanish vazifalari."""
        pass

    async def on_shutdown(self, bot: Bot, dp: Dispatcher) -> None:
        """Bot to'xtaganda resurslarni xavfsiz yopish."""
        pass

    def get_health_status(self) -> Dict[str, Any]:
        """Modulning joriy holati (Admin diagnostika uchun)."""
        return {
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "description": self.description,
            "priority": self.priority
        }


class ModuleRegistry:
    """
    Markaziy Modullar Reestri (Service & Plugin Bus).
    Modullarni ro'yxatga oladi, ustuvorlik bo'yicha saralaydi va Dispatcher'ga ulaydi.
    """
    def __init__(self):
        self._modules: Dict[str, BaseBotModule] = {}

    def register(self, module: BaseBotModule) -> None:
        """Yangi modulni tizimga ulash"""
        self._modules[module.name] = module
        logger.info(
            f"🧩 Modul ro'yxatga olindi: [{module.name} v{module.version}] (priority={module.priority})"
        )

    def unregister(self, module_name: str) -> bool:
        """Modulni tizimdan uzish"""
        if module_name in self._modules:
            del self._modules[module_name]
            return True
        return False

    def get_module(self, module_name: str) -> Optional[BaseBotModule]:
        """Nomi bo'yicha modulni olish"""
        return self._modules.get(module_name)

    def get_active_modules(self) -> List[BaseBotModule]:
        """Barcha faol modullarni ustuvorlik (priority) bo'yicha kamayish tartibida olish"""
        active = [m for m in self._modules.values() if m.enabled]
        active.sort(key=lambda m: m.priority, reverse=True)
        return active

    def list_modules_info(self) -> List[Dict[str, Any]]:
        """Barcha modullar haqida ma'lumot"""
        return [m.get_health_status() for m in self.get_active_modules()]


module_registry = ModuleRegistry()
