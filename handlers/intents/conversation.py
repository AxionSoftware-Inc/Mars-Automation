import logging
from aiogram import types, Bot

from user_memory import user_memory
from translit_manager import adapt_to_user_script
from catalog_manager import catalog_manager
from admin_manager import admin_manager

logger = logging.getLogger(__name__)

SOURCE_CHANNEL_ID = -1001641871516  # @POS_Terminal_UzSmart_Bank

CONVERSATIONAL_FOLLOWUPS = [
    "qachon qo'shiladi", "qachon qoshiladi", "qachon yoqiladi", "qachon ochiladi",
    "qachon ishlaydi", "qachon aktivlashadi", "qachon yoqasiz", "keyingi to'lov", "keyingi tolov",
    "keyingi to'lovni", "keyingi tolovni", "qancha to'layman", "qancha tolayman", "qancha to'lashim",
    "qancha tolashim", "qancha qarz", "qarzim qancha", "yana to'laymanmi", "yana tolaymanmi",
    "adminga bordimi", "adminga jo'natildimi", "chek tushdimi", "kvitansiya tushdimi",
    "to'lov tushdimi", "tolov tushdimi", "endi nima", "endi nima qilay", "nima qilish kerak",
    "qarzim bormi", "qancha qarzim bor", "yana to'lashim kerakmi", "yana tolashim kerakmi",
    "rahmat", "tushundim", "yaxshi", "ok", "xa", "ha", "boladi", "bo'ladi",
    "когда включите", "чек отправил", "оплатил", "следующая оплата", "сколько платить"
]


class ConversationIntentHandler:
    """Davomiy suhbatlar, video katalog qidiruvi va AI asosiy muloqotini boshqaruvchi modul"""

    async def handle(self, message: types.Message, bot: Bot, user_script: str, ai_func=None) -> bool:
        if ai_func is None:
            import handlers.chat
            ai_func = getattr(handlers.chat, "generate_ai_reply_ex", None)
            if not ai_func:
                from ai_helper import generate_ai_reply_ex
                ai_func = generate_ai_reply_ex

        text = message.text.strip()
        lower_text = text.lower()
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else 0

        has_active_context = bool(user_memory.get_last_id(chat_id, user_id) or user_memory.get_last_receipt(chat_id, user_id))
        is_conversational = any(kw in lower_text for kw in CONVERSATIONAL_FOLLOWUPS)
        explicit_video_request = any(kw in lower_text for kw in ["video", "rolik", "video tashla", "qo'llanma", "qollanma"])

        # 1. Agar aniq video so'ralmagan bo'lsa va bu davomiy suhbat yoki faol kontekst bo'lsa -> AI kontekstiga!
        if is_conversational or (has_active_context and not explicit_video_request):
            context_summary = user_memory.get_context_summary(chat_id, user_id)
            reply_text, ai_video_id, needs_admin = ai_func(text, context_history=context_summary, target_script=user_script)

            if not reply_text or not reply_text.strip():
                fallback = "Savolingiz bo'yicha to'liq ma'lumot berishimiz uchun korxonangiz СТИР (INN) raqamini yuboring."
                reply_text = adapt_to_user_script(fallback, user_script)

            logger.info(f"📤 AI JAVOBI (Kontekst) [chat_id={chat_id}]: {reply_text[:120]}")
            try:
                await message.reply(reply_text, parse_mode="HTML")
            except Exception as e1:
                logger.warning(f"HTML parse_mode xatosi: {e1}, oddiy matnda yuborilmoqda...")
                try:
                    await message.reply(reply_text)
                except Exception as e2:
                    logger.error(f"Xabar yuborishda jiddiy xatolik: {e2}")

            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, reply_text)

            if needs_admin:
                last_id = user_memory.get_last_id(chat_id, user_id)
                saved_photo = user_memory.get_last_photo(chat_id, user_id)
                await admin_manager.notify_user_query_escalation(
                    bot=bot,
                    user=message.from_user,
                    chat_id=chat_id,
                    query_text=text,
                    reason="Mijoz noma'lum savol berdi (AI bilmadi va adminga yo'naltirdi)",
                    inn=last_id,
                    photo_file_id=saved_photo
                )

            if ai_video_id:
                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=ai_video_id,
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    logger.error(f"AI tavsiya qilgan videoni yuborishda xatolik (ID: {ai_video_id}): {e}")
            return True

        # 2. Texnik video katalogdan qidirish (faqat aniq texnik amallar uchun)
        video_id = catalog_manager.find_matching_post(text)
        if video_id:
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=video_id,
                    reply_to_message_id=message.message_id
                )
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, f"[Video qo'llanma yuborildi: ID {video_id}]")
                user_memory.set_last_topic(chat_id, user_id, f"video_{video_id}")
                return True
            except Exception as e:
                logger.error(f"Video post jo'natishda xatolik (ID: {video_id}): {e}")

        # 3. Boshqalari bo'yicha umumiy AI javobi
        context_summary = user_memory.get_context_summary(chat_id, user_id)
        reply_text, ai_video_id, needs_admin = ai_func(text, context_history=context_summary, target_script=user_script)

        if not reply_text or not reply_text.strip():
            fallback = "Savolingiz bo'yicha to'liq ma'lumot berishimiz uchun korxonangiz СТИР (INN) raqamini yuboring."
            reply_text = adapt_to_user_script(fallback, user_script)

        logger.info(f"📤 AI JAVOBI (Umumiy) [chat_id={chat_id}]: {reply_text[:120]}")
        try:
            await message.reply(reply_text, parse_mode="HTML")
        except Exception as e1:
            logger.warning(f"HTML parse_mode xatosi: {e1}, oddiy matnda yuborilmoqda...")
            try:
                await message.reply(reply_text)
            except Exception as e2:
                logger.error(f"Xabar yuborishda jiddiy xatolik: {e2}")

        user_memory.add_user_message(chat_id, user_id, text)
        user_memory.add_assistant_message(chat_id, user_id, reply_text)

        if needs_admin:
            last_id = user_memory.get_last_id(chat_id, user_id)
            saved_photo = user_memory.get_last_photo(chat_id, user_id)
            await admin_manager.notify_user_query_escalation(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                query_text=text,
                reason="Mijoz noma'lum savol berdi (AI bilmadi va adminga yo'naltirdi)",
                inn=last_id,
                photo_file_id=saved_photo
            )

        if ai_video_id:
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=ai_video_id,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.error(f"AI tavsiya qilgan videoni yuborishda xatolik (ID: {ai_video_id}): {e}")
        return True

conversation_intent_handler = ConversationIntentHandler()
