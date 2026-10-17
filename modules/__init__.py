"""
modules/__init__.py
===================
Mars Smart POS Botining Tashqi va Ichki Katta Modullar Paketi (Modular Architecture).

Mavjud modullar:
1. AdminModule (`modules/admin_module.py`) — Admin panel, statistika, eskalatsiya va OFD ko'prigi
2. CommandsModule (`modules/commands_module.py`) — Standart buyruqlar (/start, /help, /tekshir, /tolov, /tarix)
3. MediaModule (`modules/media_module.py`) — Kvitansiyalar, Fiskal chek, Kassa ekrani va Excel yangilash
4. ChannelModule (`modules/channel_module.py`) — Kanal postlarini uzatish va avto-indekslash
5. BillingModule (`modules/billing_module.py`) — Qarz, To'lov tizimlari (Click/Payme integratsiyaga tayyor)
6. GroupSupportModule (`modules/group_support_module.py`) — Guruh va chatlarda 8 qadamli aqlli javob berish

Yangi katta modul (masalan: CRMModule, ClickMerchantModule, AnalyticsModule) qo'shish uchun:
`BaseBotModule` dan meros olib `module_registry.register(MyNewModule())` chaqiriladi!
"""

from core.module_registry import BaseBotModule, module_registry
from modules.admin_module import AdminModule, regional_admin_service, RegionalAdminRouterService


class CommandsModule(BaseBotModule):
    name = "commands_module"
    version = "2.0.0"
    description = "Asosiy Telegram komandalar (/start, /help, /tekshir, /tolov, /tarix)"
    priority = 90

    def get_router(self):
        from handlers.commands import router as commands_router
        return commands_router


class MediaModule(BaseBotModule):
    name = "media_module"
    version = "2.0.0"
    description = "To'lov kvitansiyalari (PDF/Rasm), Fiskal chek, Kassa ekrani va Excel sinxronizatsiyasi"
    priority = 80

    def get_router(self):
        from handlers.media import router as media_router
        return media_router


class BillingModule(BaseBotModule):
    name = "billing_module"
    version = "2.0.0"
    description = "Oylik (Mars) va Yillik (OFD) qarzdorlik, to'lov tarixi va rekvizitlar moduli"
    priority = 70

    def get_router(self):
        from handlers.debt import router as debt_router
        return debt_router

    def get_services(self):
        from excel_manager import excel_manager
        from ofd_bridge import ofd_bridge
        return {
            "excel_manager": excel_manager,
            "ofd_bridge": ofd_bridge
        }


class ChannelModule(BaseBotModule):
    name = "channel_module"
    version = "2.0.0"
    description = "Rasmiy kanal postlarini uzatish va video katalogni avto-indekslash"
    priority = 60

    def get_router(self):
        from handlers.channel import router as channel_router
        return channel_router

    def get_services(self):
        from catalog_manager import catalog_manager
        return {"catalog_manager": catalog_manager}


class GroupSupportModule(BaseBotModule):
    name = "group_support_module"
    version = "2.0.0"
    description = "Guruh va shaxsiy chatlarda 8 qadamli aqlli javob berish va diagnostika moduli"
    priority = 50

    def get_router(self):
        from handlers.chat import router as chat_router
        return chat_router

    def get_services(self):
        from core.group_responder import group_responder
        from core.rule_engine import rule_engine
        from user_memory import user_memory
        return {
            "group_responder": group_responder,
            "rule_engine": rule_engine,
            "user_memory": user_memory
        }


def register_default_modules():
    """
    1. Barcha standart modullarni reestrga ro'yxatdan o'tkazish.
    2. `modules/` papkasiga tashlangan har qanday yangi `*_module.py` faylni avtomatik topib ulash!
    3. Agar yangi modulda `handle_group_message` переопределение (override) qilingan bo'lsa,
       uni avtomatik `group_responder` zanjiriga ulash!
    """
    module_registry.register(AdminModule())
    module_registry.register(CommandsModule())
    module_registry.register(MediaModule())
    module_registry.register(BillingModule())
    module_registry.register(ChannelModule())
    module_registry.register(GroupSupportModule())

    # modules/ papkasidagi barcha yangi modullarni avto-kashf qilish
    module_registry.autodiscover("modules")

    # Har bir faol modulning guruh javob qadamini (agar yozilgan bo'lsa) GroupResponder'ga ulash
    from core.group_responder import group_responder
    for mod in module_registry.get_active_modules():
        if type(mod).handle_group_message is not BaseBotModule.handle_group_message:
            if mod.handle_group_message not in group_responder._custom_steps:
                group_responder.register_custom_step(mod.handle_group_message)


__all__ = [
    "AdminModule",
    "CommandsModule",
    "MediaModule",
    "BillingModule",
    "ChannelModule",
    "GroupSupportModule",
    "register_default_modules",
    "module_registry"
]

