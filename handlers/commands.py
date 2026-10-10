import logging
from aiogram import Router, types, Bot
from aiogram.filters import Command, CommandStart
from excel_manager import excel_manager
from user_memory import user_memory
from payment_accounts import get_all_payment_accounts_card, MARS_VIDEO_ID, YANGI_TEXNOLOGIYALAR_VIDEO_ID

logger = logging.getLogger(__name__)

router = Router(name="commands_router")

SOURCE_CHANNEL_ID = -1001641871516  # @POS_Terminal_UzSmart_Bank

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Start buyrug'i - Bot bilan tanishuv va yo'riqnoma"""
    text = (
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "<b>«Mars Elektron Texnika»</b> Smart POS kassa apparatlari rasmiy yordamchi botiga xush kelibsiz!\n\n"
        "📌 <b>Bot imkoniyatlari:</b>\n"
        "🔹 <b>Qarzdorlikni tekshirish:</b> INN (9 xonali) yoki JSHSHIR (14 xonali) raqamingizni yuboring\n"
        "🔹 <b>To'lov ma'lumotlari:</b> /tolov buyrug'ini bosing\n"
        "🔹 <b>Nosozlik va xatoliklar:</b> Apparat ekranini rasmga olib yuborsangiz, AI xatolik sababini aniqlab beradi\n"
        "🔹 <b>Sozlamalar va qo'llanmalar:</b> Savolingizni yozsangiz tegishli video-qo'llanma yuboriladi\n"
        "🔹 <b>Barcha buyruqlar:</b> /help buyrug'i orqali ko'rishingiz mumkin"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Help buyrug'i - Barcha mavjud komandalar ro'yxati"""
    text = (
        "📖 <b>Mavjud buyruqlar ro'yxati:</b>\n\n"
        "🔹 /start — Botni qayta ishga tushirish va bosh menyu\n"
        "🔹 /help — Buyruqlar bo'yicha yordam va yo'riqnoma\n"
        "🔹 /tekshir <code>[INN/JSHSHIR]</code> — Qarzdorlikni tekshirish (masalan: <code>/tekshir 302568138</code>)\n"
        "🔹 /tolov — Oylik to'lov rekvizitlari va Click qo'llanmasi\n"
        "🔹 /tarix — Oxirgi tekshirilgan korxonaning to'lov tarixi\n\n"
        "💬 <i>Shuningdek, to'g'ridan-to'g'ri INN raqamingizni, apparat ekranidagi nosozlik rasmini yoki savolingizni yuborishingiz mumkin!</i>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("tolov"))
async def cmd_tolov(message: types.Message, bot: Bot):
    """To'lov rekvizitlari (Oylik va Yillik) va Click orqali to'lash videosi"""
    await message.reply(get_all_payment_accounts_card(), parse_mode="HTML")
    try:
        # Click orqali to'lash videosi (Post 148)
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=SOURCE_CHANNEL_ID,
            message_id=MARS_VIDEO_ID,
            reply_to_message_id=message.message_id
        )
    except Exception as e:
        logger.error(f"Click videosini yuborishda xatolik: {e}")


@router.message(Command("tarix"))
@router.message(Command("qarz"))
async def cmd_tarix(message: types.Message):
    """Oxirgi tekshirilgan INN bo'yicha to'lov tarixi"""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    last_id = user_memory.get_last_id(chat_id, user_id)

    if not last_id:
        await message.reply(
            "⚠️ <b>Avval korxona INN yoki JSHSHIR raqamini yuboring.</b>\n"
            "Masalan: <code>/tekshir 302568138</code>",
            parse_mode="HTML"
        )
        return

    results = excel_manager.search(last_id)
    if not results:
        await message.reply(f"❌ <code>{last_id}</code> bo'yicha ma'lumot topilmadi.", parse_mode="HTML")
        return

    history_resp = excel_manager.format_payment_history(results)
    await message.reply(history_resp, parse_mode="HTML")


@router.message(Command("tekshir"))
async def cmd_tekshir(message: types.Message, bot: Bot):
    """Buyruq orqali qarz tekshirish: /tekshir 123456789"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply(
            "⚠️ Iltimos, INN yoki JSHSHIR raqamini ham yozing.\n"
            "Masalan: <code>/tekshir 302568138</code>",
            parse_mode="HTML"
        )
        return

    from handlers.debt import process_and_send_debt_result
    query = args[1].strip()
    await process_and_send_debt_result(message, bot, query)
