import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import Router, BaseMiddleware, types, Bot, F
from aiogram.types import TelegramObject, User

from admin_manager import admin_manager
from ofd_bridge import ofd_bridge
from handlers.admin import router as admin_router
from handlers.commands import router as commands_router
from handlers.media import router as media_router
from handlers.debt import router as debt_router
from handlers.channel import router as channel_router
from handlers.chat import router as chat_router

logger = logging.getLogger(__name__)

class AdminAutoRegisterMiddleware(BaseMiddleware):
    """
    1) Bosh admin (@Yashnarbek_butaev) botga har qanday xabar yozganda uning numeric Telegram ID sini
       avtomatik aniqlab adminlar ro'yxatiga qo'shish.
    2) @ofd943 va maxfiy OFD kanali/guruhidagi xabarlarni tutib olish (cheksiz sikl bo'lmasligi uchun).
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get("event_from_user")
        if user and user.username:
            admin_manager.check_and_register_username(user.id, user.username)

        if isinstance(event, types.Message):
            prefix = "📢 KANAL POSTI" if event.chat.type == "channel" else "📥 XABAR KELDI"
            logger.info(
                f"{prefix} [chat_id={event.chat.id}, type={event.chat.type}, user={user.id if user else None} (@{user.username if user else None})]: "
                f"text={repr(event.text)}, caption={repr(event.caption)}, photo={bool(event.photo)}, doc={bool(event.document)}"
            )
            bot = data.get("bot")
            if await ofd_bridge.handle_incoming_message(event, bot=bot):
                return None

        return await handler(event, data)

main_router = Router(name="main_router")
main_router.message.outer_middleware(AdminAutoRegisterMiddleware())
main_router.edited_message.outer_middleware(AdminAutoRegisterMiddleware())
main_router.callback_query.outer_middleware(AdminAutoRegisterMiddleware())
main_router.channel_post.outer_middleware(AdminAutoRegisterMiddleware())
main_router.edited_channel_post.outer_middleware(AdminAutoRegisterMiddleware())
main_router.my_chat_member.outer_middleware(AdminAutoRegisterMiddleware())

@main_router.my_chat_member()
async def handle_bot_chat_member_update(event: types.ChatMemberUpdated, bot: Bot):
    """Bot yangi guruh yoki kanalga qo'shilganda yoki huquqlari o'zgarganda"""
    chat = event.chat
    status = event.new_chat_member.status
    logger.info(f"🤖 Bot chat a'zoligi yangilandi: chat_id={chat.id}, type={chat.type}, title={repr(chat.title)}, status={status}")
    if status in ("administrator", "member"):
        # OFD bot borligini tekshirib avtomatik ulash
        if await ofd_bridge.check_and_bind_chat_if_ofd(chat.id, bot):
            logger.info(f"✅ Bot qo'shilgan {chat.type} ({chat.id}) OFD ko'prigi sifatida avtomatik ulandi!")

@main_router.callback_query(F.data == "call_support")
async def handle_call_support(callback: types.CallbackQuery):
    """Admin yoki texnik xizmat kontaktlarini ko'rsatish"""
    await callback.answer()
    text = (
        "👨‍💻 <b>Hududiy THKM texnik xizmat ko'rsatish mas'ul xodimlari:</b>\n\n"
        "• Mas'ul xodim: @quvonchbek_admin\n"
        "• Bosh usta: @Yashnarbek_butaev\n\n"
        "Telegram orqali to'g'ridan-to'g'ri bog'lanishingiz mumkin."
    )
    try:
        if callback.message:
            await callback.message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Callback answer xatolik: {e}")

# Routerlar qat'iy ustuvorlik ketma-ketligida ulanadi:
# 1. Admin buyruqlari (/admin, /statistika, /errors, /admins, /add_admin, /contacts, /ofd)
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

__all__ = ["main_router", "AdminAutoRegisterMiddleware", "handle_bot_chat_member_update"]
