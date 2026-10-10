from aiogram import Router

from handlers.admin import router as admin_router
from handlers.commands import router as commands_router
from handlers.media import router as media_router
from handlers.debt import router as debt_router
from handlers.channel import router as channel_router
from handlers.chat import router as chat_router

main_router = Router(name="main_router")

# Routerlar qat'iy ustuvorlik ketma-ketligida ulanadi:
# 1. Admin buyruqlari (/admin, /statistika, /admins, /add_admin, /contacts)
# 2. Umumiy bot buyruqlari (/start, /help, /tekshir, /tolov, /tarix)
# 3. Media fayllar (Kassa rasmlari, to'lov kvitansiyalari, Excel bazasi)
# 4. Qarz tekshirish va to'lov tarixi so'rovlari (INN/JSHSHIR)
# 5. Kanal xabarlari (Postlarni uzatish va yangi videolarni avto-indekslash)
# 6. Erkin matnli suhbat, katalog qidiruvi, operator eskalatsiyasi va AI muloqoti
main_router.include_router(admin_router)
main_router.include_router(commands_router)
main_router.include_router(media_router)
main_router.include_router(debt_router)
main_router.include_router(channel_router)
main_router.include_router(chat_router)

__all__ = ["main_router"]
