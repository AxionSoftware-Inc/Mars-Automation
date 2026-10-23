import logging
from aiogram import Router, types, Bot
from aiogram.filters import Command, CommandStart
from excel_manager import excel_manager
from user_memory import user_memory
from payment_accounts import (
    get_all_payment_accounts_card,
    get_both_posts_intro,
    send_both_account_posts,
)
from translit_manager import adapt_to_user_script, detect_script

logger = logging.getLogger(__name__)

router = Router(name="commands_router")

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Start buyrug'i - Bot bilan tanishuv va yo'riqnoma"""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    user_script = user_memory.get_preferred_script(chat_id, user_id)

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
    text = adapt_to_user_script(text, user_script)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Help buyrug'i - Barcha mavjud komandalar ro'yxati"""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    user_script = user_memory.get_preferred_script(chat_id, user_id)

    text = (
        "📖 <b>Mavjud buyruqlar ro'yxati:</b>\n\n"
        "🔹 /start — Botni qayta ishga tushirish va bosh menyu\n"
        "🔹 /help — Buyruqlar bo'yicha yordam va yo'riqnoma\n"
        "🔹 /tekshir <code>[INN/JSHSHIR]</code> — Qarzdorlikni tekshirish (masalan: <code>/tekshir 302568138</code>)\n"
        "🔹 /tolov — Oylik to'lov rekvizitlari va Click qo'llanmasi\n"
        "🔹 /tarix — Oxirgi tekshirilgan korxonaning to'lov tarixi\n\n"
        "💬 <i>Shuningdek, to'g'ridan-to'g'ri INN raqamingizni, apparat ekranidagi nosozlik rasmini yoki savolingizni yuborishingiz mumkin!</i>"
    )
    text = adapt_to_user_script(text, user_script)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("tolov"))
async def cmd_tolov(message: types.Message, bot: Bot):
    """To'lov rekvizitlari: Kanaldan Oylik va Yillik rasmiy matn postlarini uzatish"""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    user_script = user_memory.get_preferred_script(chat_id, user_id)

    intro = get_both_posts_intro(user_script)
    try:
        await message.reply(intro, parse_mode="HTML")
    except Exception:
        await message.reply(intro)

    await send_both_account_posts(bot, message.chat.id, script=user_script)

    user_memory.add_user_message(chat_id, user_id, "/tolov")
    user_memory.add_assistant_message(chat_id, user_id, intro)


@router.message(Command("tarix"))
@router.message(Command("qarz"))
async def cmd_tarix(message: types.Message):
    """Oxirgi tekshirilgan INN bo'yicha to'lov tarixi"""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    user_script = user_memory.get_preferred_script(chat_id, user_id)
    last_id = user_memory.get_last_id(chat_id, user_id)

    if not last_id:
        w_msg = adapt_to_user_script(
            "⚠️ <b>Avval korxona INN yoki JSHSHIR raqamini yuboring.</b>\n"
            "Masalan: <code>/tekshir 302568138</code>",
            user_script
        )
        await message.reply(w_msg, parse_mode="HTML")
        return

    results = excel_manager.search(last_id)
    if not results:
        nf_msg = adapt_to_user_script(
            f"❌ <code>{last_id}</code> bo'yicha ma'lumot topilmadi.",
            user_script
        )
        await message.reply(nf_msg, parse_mode="HTML")
        return

    history_resp = excel_manager.format_payment_history(results)
    history_resp = adapt_to_user_script(history_resp, user_script)
    await message.reply(history_resp, parse_mode="HTML")


@router.message(Command("tekshir"))
async def cmd_tekshir(message: types.Message, bot: Bot):
    """Buyruq orqali qarz tekshirish: /tekshir 123456789"""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    user_script = user_memory.get_preferred_script(chat_id, user_id)

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        w_msg = (
            "🔍 <b>Qarzdorlik va apparat holatini tekshirish:</b>\n\n"
            "Kassa apparatlari to'xtab qolishining 60%+ sababi abonent yoki soliq to'lovidagi qarzdorlik bo'ladi.\n\n"
            "Iltimos, korxonangizning <b>INN (9 xonali)</b> raqamini hamda iloji bo'lsa apparat chekining pastki qismidagi <b>Fiskal modul raqamini (LG... yoki YG...)</b> yuboring.\n"
            "Masalan: <code>/tekshir 302568138</code>\n\n"
            "💡 <i>Biz bir vaqtning o'zida «Mars» oylik abonent to'lovini hamda Davlat Soliq Qo'mitasi (OFD) yillik litsenziya muddatini to'liq tekshirib beramiz!</i>"
        )
        w_msg = adapt_to_user_script(w_msg, user_script)
        await message.reply(w_msg, parse_mode="HTML")
        return

    from handlers.debt import process_and_send_debt_result
    query = args[1].strip()
    await process_and_send_debt_result(message, bot, query)
