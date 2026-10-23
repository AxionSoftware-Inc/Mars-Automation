import logging
from aiogram import types, Bot

from user_memory import user_memory
from translit_manager import adapt_to_user_script
from payment_accounts import is_mxik_intent, get_mxik_guidance, send_channel_message

logger = logging.getLogger(__name__)


class MxikIntentHandler:
    """MXIK (IKPU / Tasnif / Soliq talablari va tovar qo'shish) intentlarini boshqaruvchi modul"""

    async def handle(self, message: types.Message, bot: Bot, user_script: str) -> bool:
        text = message.text.strip()
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else 0

        if not is_mxik_intent(text):
            return False

        mxik_text, mxik_video_id = get_mxik_guidance(text)
        mxik_text = adapt_to_user_script(mxik_text, user_script)
        try:
            await message.reply(mxik_text, parse_mode="HTML")
        except Exception:
            await message.reply(mxik_text)

        if mxik_video_id:
            await send_channel_message(bot, message.chat.id, mxik_video_id, reply_to_message_id=message.message_id)

        user_memory.add_user_message(chat_id, user_id, text)
        user_memory.add_assistant_message(chat_id, user_id, mxik_text)
        user_memory.set_last_topic(chat_id, user_id, "mxik_guidance")
        return True

mxik_intent_handler = MxikIntentHandler()
