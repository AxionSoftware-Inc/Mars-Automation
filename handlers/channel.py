import os
import logging
from aiogram import Router, types, Bot
from catalog_manager import catalog_manager
from payment_accounts import SOURCE_CHANNEL_ID, EXCEL_CHANNEL_ID, EXCEL_FORWARD_CHANNEL_ID
from state_manager import get_last_forwarded_excel_channel_msg_id, set_last_forwarded_excel_channel_msg_id

logger = logging.getLogger(__name__)

router = Router(name="channel_router")

DESTINATION_CHANNEL_ID = int(os.getenv("DESTINATION_CHANNEL_ID", "-1003784534841"))  # marsfayllar


async def _relay_excel_channel_message(message: types.Message, bot: Bot):
    """
    Oylik abonent Excel fayllar tashlanadigan kanaldan (EXCEL_CHANNEL_ID)
    har qanday yangi narsa (xabar, fayl, rasm, va h.k.) tashlanganda
    avtomatik yangi guruhga (EXCEL_FORWARD_CHANNEL_ID) uzatish.
    """
    last_fwd_id = get_last_forwarded_excel_channel_msg_id() or 0
    if message.message_id <= last_fwd_id:
        return

    try:
        logger.info(
            f"📥 Excel kanaldan ({message.chat.id}) yangi xabar keldi (ID: {message.message_id}), "
            f"Oylik abanit ({EXCEL_FORWARD_CHANNEL_ID}) ga uzatilmoqda..."
        )
        try:
            await bot.forward_message(
                chat_id=EXCEL_FORWARD_CHANNEL_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
        except Exception as e:
            logger.warning(f"forward_message xatolik ({e}), copy_message orqali sinab ko'rilmoqda...")
            await bot.copy_message(
                chat_id=EXCEL_FORWARD_CHANNEL_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
        set_last_forwarded_excel_channel_msg_id(message.message_id)
        logger.info(f"✅ Xabar (ID: {message.message_id}) muvaffaqiyatli uzatildi.")
    except Exception as e:
        logger.error(f"❌ Xabarni Oylik abanit guruhiga uzatishda xatolik: {e}")


@router.channel_post()
async def handle_source_channel_post(message: types.Message, bot: Bot):
    """
    1. @POS_Terminal_UzSmart_Bank kanalidan yangi post kelganda:
       - Bizning kanalga uzatish (forward);
       - Katalog uchun avtomatik indekslash.
    2. EXCEL_CHANNEL_ID dan yangi post kelganda:
       - Oylik abanit guruhiga avtomatik uzatish.
    """
    if message.chat.id == SOURCE_CHANNEL_ID:
        # 1. Forward qilish
        try:
            logger.info(f"@POS_Terminal_UzSmart_Bank dan yangi post keldi (ID: {message.message_id}), uzatilmoqda...")
            await bot.forward_message(
                chat_id=DESTINATION_CHANNEL_ID,
                from_chat_id=SOURCE_CHANNEL_ID,
                message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"Postni kanalga uzatishda xatolik: {e}")

        # 2. Yangi kanal postini avtomatik indekslash
        try:
            post_text = message.text or message.caption or ""
            if post_text:
                catalog_manager.auto_index_new_post(post_id=message.message_id, post_text=post_text)
        except Exception as e:
            logger.error(f"Yangi postni avto-indekslashda xatolik: {e}")

    elif message.chat.id == EXCEL_CHANNEL_ID:
        await _relay_excel_channel_message(message, bot)


@router.message()
async def handle_excel_channel_group_message(message: types.Message, bot: Bot):
    """
    Agar EXCEL_CHANNEL_ID supergroup ko'rinishida bo'lsa, xabarlar message sifatida kelishi mumkin.
    """
    if message.chat.id == EXCEL_CHANNEL_ID:
        await _relay_excel_channel_message(message, bot)
