import logging
from aiogram import Router, types, Bot, F
from ai_helper import generate_ai_reply, generate_ai_reply_ex
from user_memory import user_memory
from handlers.intents import (
    billing_intent_handler,
    hardware_intent_handler,
    mxik_intent_handler,
    operator_intent_handler,
    conversation_intent_handler
)

logger = logging.getLogger(__name__)

router = Router(name="chat_router")

SOURCE_CHANNEL_ID = -1001641871516  # @POS_Terminal_UzSmart_Bank


@router.message(F.text)
async def handle_user_chat(message: types.Message, bot: Bot):
    """
    Foydalanuvchi bilan modulli intentlar pipeline'i (Arxitektura 2.0):
    1. Billing & Debt Intent (Fiskal modul, INN, oylik/yillik qarz tekshiruvi, hisob raqamlar, Click video)
    2. Hardware Diagnosis Intent (Apparat nosozligi: 4 bosqichli standart model)
    3. MXIK Intent (IKPU / Tasnif / Soliq talablari va tovar qo'shish)
    4. Operator / Usta Intent (Mutaxassis talabi va admin eskalatsiyasi)
    5. Conversational & AI Intent (Davomiy suhbat, video katalog va Gemini AI)
    """
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    # Foydalanuvchi alifbosini aniqlash va yangilash (Lotin yoki Kirill)
    user_script = user_memory.detect_and_update_script(chat_id, user_id, message.text)

    # 1. Billing & Debt Intent (Oylik, yillik, fiskal modul, hisob raqamlar)
    if await billing_intent_handler.handle(message, bot, user_script):
        return

    # 2. Hardware Diagnosis Intent (4 bosqichli nosozlik modeli)
    if await hardware_intent_handler.handle(message, bot, user_script):
        return

    # 3. MXIK Intent (Tovar qo'shish va soliq tasnif)
    if await mxik_intent_handler.handle(message, bot, user_script):
        return

    # 4. Operator / Usta Intent (Eskalatsiya)
    if await operator_intent_handler.handle(message, bot, user_script):
        return

    # 5. Conversational, Video Catalog & AI Intent
    await conversation_intent_handler.handle(message, bot, user_script)
