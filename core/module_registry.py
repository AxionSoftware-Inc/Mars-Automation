"""
core/module_registry.py
=======================
Professional Modulli Arxitektura (Enterprise Plugin, Service & Event Bus) tizimi.

Har qanday ichki yoki tashqi katta modul (To'lov moduli, Administratsiya moduli,
Guruhda javob berish moduli, CRM va h.k.) `BaseBotModule` interfeysini meros olib:
1. `modules/` papkasiga tashlanishi bilan avtomatik topiladi (`autodiscover_modules`);
2. O'zining Telegram Router'ini (`get_router`) va Guruh javob qadamini (`handle_group_message`) ulaydi;
3. Boshqa modullar bilan `get_service()` (Service Container) va `emit_event()` / `subscribe()` (Event Bus)
   orqali kodni buzmasdan integratsiya qiladi;
4. Bot yonganda va o'chganda `on_startup` / `on_shutdown` lifecycle metodlarini ishga tushiradi.
"""

import os
import inspect
import importlib
import logging
from abc import ABC
from typing import List, Dict, Any, Optional, Callable, Awaitable
from aiogram import Router, Bot, Dispatcher, types

logger = logging.getLogger(__name__)

EventCallback = Callable[[str, Dict[str, Any]], Awaitable[None]]


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
        """Agar modulning o'z Telegram Router'i (komanda, tugma, media) bo'lsa, shu yerda qaytaradi."""
        return None

    def get_services(self) -> Dict[str, Any]:
        """
        Ushbu modul boshqa modullarga taqdim etadigan xizmatlar (Service Container uchun).
        Masalan: {"regional_admin": regional_admin_service}
        """
        return {}

    async def handle_group_message(self, message: types.Message, bot: Bot, user_script: str) -> bool:
        """
        Agar modul Guruhda javob berish zanjiriga (`group_responder`) o'z shartini qo'shmoqchi bo'lsa,
        shu metodni переопределение (override) qiladi. True qaytarsa, xabar ushbu modul tomonidan javoblangan hisoblanadi.
        """
        return False

    async def on_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Boshqa modullardan kelgan global hodisalarni (Event Bus) qabul qilish."""
        pass

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
            "priority": self.priority,
            "services": list(self.get_services().keys())
        }


class ModuleRegistry:
    """
    Markaziy Modullar Reestri (Plugin, Service & Event Bus).
    - Modullarni ro'yxatga oladi va `modules/` papkasidan avtomatik topadi;
    - Modullararo xizmatlar almashinuvini (`get_service` / `register_service`) ta'minlaydi;
    - Modullararo hodisalar (`emit` / `subscribe`) tizimini boshqaradi;
    - Ustuvorlik (`priority`) bo'yicha saralab Dispatcher va GroupResponder'ga ulaydi.
    """
    def __init__(self):
        self._modules: Dict[str, BaseBotModule] = {}
        self._services: Dict[str, Any] = {}
        self._subscribers: Dict[str, List[EventCallback]] = {}

    def register(self, module: BaseBotModule) -> None:
        """Yangi modulni tizimga ulash va uning xizmatlarini Service Container'ga qo'shish"""
        if module.name in self._modules:
            return
        self._modules[module.name] = module
        for svc_name, svc_obj in (module.get_services() or {}).items():
            self._services[svc_name] = svc_obj
        logger.info(
            f"🧩 Modul ro'yxatga olindi: [{module.name} v{module.version}] (priority={module.priority})"
        )

    def unregister(self, module_name: str) -> bool:
        """Modulni tizimdan uzish"""
        if module_name in self._modules:
            mod = self._modules.pop(module_name)
            for svc_name in (mod.get_services() or {}).keys():
                self._services.pop(svc_name, None)
            return True
        return False

    def register_service(self, name: str, service_obj: Any) -> None:
        """Alohida xizmat (masalan: excel_manager, user_memory, payment_gateway) ni reestrga qo'shish"""
        self._services[name] = service_obj

    def get_service(self, name: str) -> Optional[Any]:
        """Boshqa modul taqdim etgan xizmatni nomi bo'yicha olish (Dependency Injection)"""
        return self._services.get(name)

    def subscribe(self, event_name: str, callback: EventCallback) -> None:
        """Muayyan hodisaga (`event_name`, masalan 'payment.verified' yoki 'admin.escalated') obuna bo'lish"""
        self._subscribers.setdefault(event_name, []).append(callback)

    async def emit(self, event_name: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """
        Tizimdagi barcha faol modullarga va obunachilarga hodisa (Event) yuborish.
        Masalan: To'lov moduli to'lov o'tganda `await module_registry.emit('payment.completed', {'inn': '302568138'})`
        deb chaqirsa, Admin va Billing modullari buni darhol qabul qiladi!
        """
        data = payload or {}
        for cb in self._subscribers.get(event_name, []):
            try:
                await cb(event_name, data)
            except Exception as e:
                logger.error(f"Event subscriber error ({event_name}): {e}")

        for mod in self.get_active_modules():
            try:
                await mod.on_event(event_name, data)
            except Exception as e:
                logger.error(f"Module {mod.name}.on_event({event_name}) error: {e}")

    def autodiscover(self, package_name: str = "modules") -> List[str]:
        """
        `modules/` papkasidagi barcha `*_module.py` fayllarni avtomatik skanerlab,
        ichidagi `BaseBotModule` klasslarini tizimga ulaydi.
        """
        discovered = []
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), package_name)
        if not os.path.isdir(base_dir):
            return discovered

        for fname in sorted(os.listdir(base_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            mod_stem = fname[:-3]
            full_import = f"{package_name}.{mod_stem}"
            try:
                py_mod = importlib.import_module(full_import)
                for _, obj in inspect.getmembers(py_mod, inspect.isclass):
                    if issubclass(obj, BaseBotModule) and obj is not BaseBotModule:
                        instance = obj()
                        if instance.name not in self._modules:
                            self.register(instance)
                            discovered.append(instance.name)
            except Exception as e:
                logger.error(f"Modulni avto-yuklashda xatolik ({full_import}): {e}")
        return discovered

    async def startup_all(self, bot: Bot, dp: Dispatcher) -> None:
        """Barcha faol modullarning `on_startup` metodini ishga tushirish"""
        for mod in self.get_active_modules():
            try:
                await mod.on_startup(bot, dp)
            except Exception as e:
                logger.error(f"Modul on_startup xatoligi ({mod.name}): {e}")

    async def shutdown_all(self, bot: Bot, dp: Dispatcher) -> None:
        """Barcha faol modullarning `on_shutdown` metodini ishga tushirish"""
        for mod in self.get_active_modules():
            try:
                await mod.on_shutdown(bot, dp)
            except Exception as e:
                logger.error(f"Modul on_shutdown xatoligi ({mod.name}): {e}")

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

