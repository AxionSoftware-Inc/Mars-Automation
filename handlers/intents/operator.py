import logging
from aiogram import types, Bot

from user_memory import user_memory
from translit_manager import adapt_to_user_script
from core import core_engine
from admin_manager import admin_manager, get_admin_contact_keyboard

logger = logging.getLogger(__name__)

OPERATOR_KEYWORDS = [
    "operator", "adminga", "admin kerak", "mutaxassis", "usta kerak", "usta chaqir",
    "bog'lan", "boglan", "telefon raqam", "aloqa", "kontakt", "operatorga ula",
    "yordam bering usta", "hal bo'lmadi", "hal bolmadi", "tushunmadim usta",
    "operator bilan", "menga usta kerak", "admin bilan", "usta bilan",
    "operator chaqir", "оператор", "админ", "мастер", "помогите",
    "боғлан", "боглан", "админ билан", "уста билан",
    "ishlamadi", "ishlamayapti baribir", "baribir ishlamadi", "ochmadi",
    "o'xshamadi", "oxshamadi", "yoqilmadi", "reboot qildim ishlamadi",
    "ochirib yoqdim ishlamadi", "usta yuboring", "usta jonating", "usta jo'nating",
    "admin bilan gaplashaman", "admin bilan gaplashmoqchiman", "ustaxonaga", "qilolmadim",
    "usta raqam", "usta raqami", "usta nomer", "usta nomeri", "admin raqam", "admin raqami", "admin nomer", "admin nomeri",
    "telefon nomer", "telefon nomeri", "telefon nomerini", "nomerini tashlang", "raqamini tashlang", "telefonini tashlang",
    "уста рақам", "уста рақами", "уста номер", "уста номери", "админ рақам", "админ номер", "телефон номер"
]


class OperatorIntentHandler:
    """Operator, usta yoki mas'ul mutaxassisni chaqirish intentini boshqaruvchi modul"""

    async def handle(self, message: types.Message, bot: Bot, user_script: str) -> bool:
        text = message.text.strip()
        lower_text = text.lower()
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else 0

        if not any(kw in lower_text for kw in OPERATOR_KEYWORDS):
            return False

        decision = core_engine.escalate_general_issue(text, chat_id, user_id)
        reply_msg = adapt_to_user_script(decision.reply_text, user_script)
        kb = get_admin_contact_keyboard(inn=decision.detected_inn, tuman=decision.tuman)
        try:
            await message.reply(reply_msg, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await message.reply(reply_msg, reply_markup=kb)

        user_memory.add_user_message(chat_id, user_id, text)
        user_memory.add_assistant_message(chat_id, user_id, reply_msg)

        saved_photo = user_memory.get_last_photo(chat_id, user_id)
        await admin_manager.notify_user_query_escalation(
            bot=bot,
            user=message.from_user,
            chat_id=chat_id,
            query_text=text,
            reason="Mijoz operator / usta talab qilmoqda",
            inn=decision.detected_inn if decision.detected_inn != "-" else None,
            org_name=decision.org_name if decision.org_name != "-" else None,
            photo_file_id=saved_photo
        )
        user_memory.mark_escalated_to_admin(chat_id, user_id, reason="Mijoz operator / usta talab qildi")
        return True

operator_intent_handler = OperatorIntentHandler()
