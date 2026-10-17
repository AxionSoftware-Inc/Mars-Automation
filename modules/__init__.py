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


class AdminModule(BaseBotModule):
    name = "admin_module"
    version = "2.0.0"
    description = "Admin panel, statistika, xatolik qoidalari va OFD ko'prik boshqaruvi"
    priority = 100

    def get_router(self):
        from handlers.admin import router as admin_router
        return admin_router


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


class ChannelModule(BaseBotModule):
    name = "channel_module"
    version = "2.0.0"
    description = "Rasmiy kanal postlarini uzatish va video katalogni avto-indekslash"
    priority = 60

    def get_router(self):
        from handlers.channel import router as channel_router
        return channel_router


class GroupSupportModule(BaseBotModule):
    name = "group_support_module"
    version = "2.0.0"
    description = "Guruh va shaxsiy chatlarda 8 qadamli aqlli javob berish va diagnostika moduli"
    priority = 50

    def get_router(self):
        from handlers.chat import router as chat_router
        return chat_router


def register_default_modules():
    """Barcha standart modullarni reestrga ro'yxatdan o'tkazish"""
    module_registry.register(AdminModule())
    module_registry.register(CommandsModule())
    module_registry.register(MediaModule())
    module_registry.register(BillingModule())
    module_registry.register(ChannelModule())
    module_registry.register(GroupSupportModule())


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
