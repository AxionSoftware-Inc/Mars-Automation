import logging
from aiogram import Router, types, Bot, F

from ai_helper import generate_ai_reply, generate_ai_reply_ex, generate_ai_reply_ex_async
from core.group_responder import group_responder, PROLONGED_CHAT_PHRASES

logger = logging.getLogger(__name__)

router = Router(name="chat_router")

SOURCE_CHANNEL_ID = -1001641871516  # @POS_Terminal_UzSmart_Bank


@router.message(F.text)
async def handle_user_chat(message: types.Message, bot: Bot):
    """
    Guruh va shaxsiy chatlarda barcha matnli murojaatlarni Yagona 8-Qadamli
    Orkestrator (core/group_responder.py) orqali qayta ishlash:

    1-Qadam: Alifbo va kontekstni (INN, FM) darhol xotiraga saqlash + Pending kvitansiyani ulash.
    2-Qadam: Plug & Play Qoidalar (RuleEngine & data/custom_patches.json).
    3-Qadam: Usta / Admin chaqirish yoki gapni cho'zish (Eskalatsiya).
    4-Qadam: Apparat ishlamayapti / Xatolik (3 bosqichli oltin qoida — istalgan qadamdan kirsa ham ishlaydi).
    5-Qadam: Qarz va to'lov tarixini tekshirish (INN, Telefon, Fiskal modul, Oylik, Yillik, Ikkalasi).
    6-Qadam: Hisob raqam (Shot / Rekvizit) va To'lov savollari.
    7-Qadam: Aniq Texnik Yo'riqnomalar (MXIK / Tasnif / Video Katalog).
    8-Qadam: Erkin suhbat va AI Yordamchi (Gemini AI).
    """
    ai_func = generate_ai_reply_ex_async or generate_ai_reply_ex
    await group_responder.process_message(message, bot, ai_func=ai_func)
