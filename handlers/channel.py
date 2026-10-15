import os
import logging
from aiogram import Router, types, Bot
from catalog_manager import catalog_manager

logger = logging.getLogger(__name__)

router = Router(name="channel_router")

DESTINATION_CHANNEL_ID = int(os.getenv("DESTINATION_CHANNEL_ID", "-1003784534841"))  # marsfayllar
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID", "-1001641871516"))            # @POS_Terminal_UzSmart_Bank


@router.channel_post()
async def handle_source_channel_post(message: types.Message, bot: Bot):
    """
    @POS_Terminal_UzSmart_Bank kanalidan yangi post kelganda:
    1. Uni bizning kanalga uzatish (forward);
    2. Yangi postni katalog uchun avtomatik indekslash.
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
