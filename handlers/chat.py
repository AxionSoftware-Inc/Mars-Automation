import logging
from aiogram import Router, types, Bot, F
from catalog_manager import catalog_manager
from ai_helper import generate_ai_reply
from user_memory import user_memory

logger = logging.getLogger(__name__)

router = Router(name="chat_router")

SOURCE_CHANNEL_ID = -1001641871516       # @POS_Terminal_UzSmart_Bank

PAYMENT_METHODS_KEYWORDS = [
    "qanday to'layman", "qanday tolayman", "qanaqa to'layman", "qanaqa tolayman",
    "qayerga to'layman", "qayerga tolayman", "qayerga to'lash", "qayerga tolash",
    "click orqali to'lash", "click orqali tolash", "clickdan to'lash", "clickdan tolash",
    "click orqali qanday", "kartadan to'lash", "plastikdan to'lash", "to'lash tartibi",
    "qanday to'lasam bo'ladi", "qanday tolasam boladi", "to'lov qilish tartibi"
]

OPERATOR_KEYWORDS = [
    "operator", "adminga", "admin kerak", "mutaxassis", "usta kerak", "usta chaqir",
    "bog'lanish", "boglanish", "telefon raqam", "aloqaga chiq", "operatorga ula",
    "yordam bering usta", "hal bo'lmadi", "hal bolmadi", "tushunmadim usta",
    "operator bilan gaplashmoqchiman", "menga usta kerak", "bog'laning", "boglaning",
    "operator chaqir", "оператор", "админ", "мастер", "помогите"
]

CONVERSATIONAL_FOLLOWUPS = [
    "qachon qo'shiladi", "qachon qoshiladi", "qachon yoqiladi", "qachon ochiladi",
    "qachon ishlaydi", "qachon aktivlashadi", "qachon yoqasiz", "keyingi to'lov", "keyingi tolov",
    "keyingi to'lovni", "keyingi tolovni", "qancha to'layman", "qancha tolayman", "qancha to'lashim",
    "qancha tolashim", "qancha qarz", "qarzim qancha", "yana to'laymanmi", "yana tolaymanmi",
    "adminga bordimi", "adminga jo'natildimi", "chek tushdimi", "kvitansiya tushdimi",
    "to'lov tushdimi", "tolov tushdimi", "endi nima", "endi nima qilay", "nima qilish kerak",
    "apparatim ishlamayapti", "apparat ishlamayapti", "kassa ishlamayapti", "ishlamayapti",
    "ishlamay qoldi", "ochib qoldi", "o'chib qoldi", "blok bo'ldi", "bloklandi",
    "qarzim bormi", "qancha qarzim bor", "yana to'lashim kerakmi", "yana tolashim kerakmi",
    "rahmat", "tushundim", "yaxshi", "ok", "xa", "ha", "boladi", "bo'ladi",
    "не работает", "когда включите", "чек отправил", "оплатил", "следующая оплата", "сколько платить"
]

@router.message(F.text)
async def handle_user_chat(message: types.Message, bot: Bot):
    """
    Foydalanuvchi bilan ko'p bosqichli (multi-turn) aqlli suhbat:
    0. Matnda INN aniqlansa va qarz/apparat so'ralsa -> Zaxira INN protsessori
    1. To'lov usuli yoki Click bo'yicha to'g'ridan-to'g'ri so'rovlar -> 148-video va rekvizitlar
    2. Operator / Usta talab qilinganda -> Adminga to'g'ridan-to'g'ri eskalatsiya
    3. Davomiy suhbat (qachon qo'shiladi, keyingi to'lov, qarz holati va h.k.) -> AI va boyitilgan xotira
    4. Faqat maxsus texnik qo'llanma so'ralgandagina -> Video katalogdan qidirish
    """
    text = message.text.strip()
    lower_text = text.lower()
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    # 0. AGAR MATNDA INN BO'LSA VA APPARAT/QARZ SO'RALSA (Zaxira xavfsizlik)
    from core.models import extract_clean_inn
    found_inn = extract_clean_inn(text)
    if found_inn:
        from handlers.debt import process_and_send_debt_result
        await process_and_send_debt_result(message, bot, found_inn)
        return

    # 1. AGAR TO'LOV QILISH TARTIBI / CLICK SO'RALSA
    if any(kw in lower_text for kw in PAYMENT_METHODS_KEYWORDS):
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=SOURCE_CHANNEL_ID,
                message_id=148,
                reply_to_message_id=message.message_id
            )
            user_memory.add_user_message(chat_id, user_id, text)

            user_memory.add_assistant_message(chat_id, user_id, "[Click orqali to'lash videosi yuborildi]")
            user_memory.set_last_topic(chat_id, user_id, "payment_instruction")
            return
        except Exception as e:
            logger.error(f"To'lov videosi yuborishda xatolik: {e}")

    # 2. OPERATOR / MUTAXASSIS / USTA TALAB QILINGANDA
    if any(kw in lower_text for kw in OPERATOR_KEYWORDS):
        from core import core_engine
        from admin_manager import admin_manager
        decision = core_engine.escalate_general_issue(text, chat_id, user_id)
        try:
            await message.reply(decision.reply_text, parse_mode="HTML")
        except Exception:
            await message.reply(decision.reply_text)

        user_memory.add_user_message(chat_id, user_id, text)
        user_memory.add_assistant_message(chat_id, user_id, decision.reply_text)

        user_display = message.from_user.full_name if message.from_user else "Mijoz"
        username_str = f"@{message.from_user.username}" if (message.from_user and message.from_user.username) else "Yo'q"
        org_display = decision.org_name if decision.org_name else "Noma'lum"
        inn_display = decision.detected_inn if decision.detected_inn else "-"
        admin_text = (
            f"🚨 <b>MIJOZ OPERATOR / MUTAXASSIS TALAB QILMOQDA!</b>\n\n"
            f"👤 <b>Mijoz:</b> {user_display} ({username_str})\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code> | <b>Chat:</b> <code>{chat_id}</code>\n"
            f"🏢 <b>Korxona / INN:</b> {org_display} (<code>{inn_display}</code>)\n"
            f"💬 <b>Mijoz xabari:</b> <i>{text}</i>"
        )
        await admin_manager.notify_admins(bot, text=admin_text)
        return

    # 3. DAVOMIY KONVERSATSION SAVOLLAR YOKI FAOL SUHBAT KONTEKSTI
    # Agar foydalanuvchi faol kontekstda bo'lsa yoki savoli davomiy xarakterga ega bo'lsa:
    has_active_context = bool(user_memory.get_last_id(chat_id, user_id) or user_memory.get_last_receipt(chat_id, user_id))
    is_conversational = any(kw in lower_text for kw in CONVERSATIONAL_FOLLOWUPS)
    explicit_video_request = any(kw in lower_text for kw in ["video", "rolik", "video tashla", "qo'llanma", "qollanma"])

    # Agar aniq video so'ralmagan bo'lsa va bu davomiy suhbat bo'lsa -> To'g'ridan-to'g'ri AI kontekstiga!
    if is_conversational or (has_active_context and not explicit_video_request):
        context_summary = user_memory.get_context_summary(chat_id, user_id)
        reply_text, ai_video_id = generate_ai_reply(text, context_history=context_summary)

        if not reply_text or not reply_text.strip():
            reply_text = (
                "Savolingiz bo'yicha to'liq ma'lumot berishimiz uchun korxonangiz INN raqamini yuboring "
                "yoki apparat ekranidagi xatolikni rasmga olib yuboring."
            )

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
        return

    # 4. TEXNIK VIDEO KATALOGDAN QIDIRISH (faqat maxsus texnik amallar uchun)
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
            return
        except Exception as e:
            logger.error(f"Video post jo'natishda xatolik (ID: {video_id}): {e}")

    # 5. BOSHQALARI BO'YICHA UMUMIY AI JAVOBI
    context_summary = user_memory.get_context_summary(chat_id, user_id)
    reply_text, ai_video_id = generate_ai_reply(text, context_history=context_summary)

    if not reply_text or not reply_text.strip():
        reply_text = (
            "Savolingiz bo'yicha to'liq ma'lumot berishimiz uchun korxonangiz INN raqamini yuboring "
            "yoki apparat ekranidagi xatolikni rasmga olib yuboring."
        )

    logger.info(f"📤 AI JAVOBI (Umumiy) [chat_id={chat_id}]: {reply_text[:120]}")
    try:
        await message.reply(reply_text, parse_mode="HTML")
    except Exception as e1:
        logger.warning(f"HTML parse_mode xatosi: {e1}, oddiy matnda yuborilmoqda...")
        try:
            await message.reply(reply_text)
        except Exception as e2:
            logger.error(f"Xabar yuborishda jiddiy xatolik: {e2}")

    # Suhbat xotirasiga yozish
    user_memory.add_user_message(chat_id, user_id, text)
    user_memory.add_assistant_message(chat_id, user_id, reply_text)

    # Agar AI tegishli video tavsiya qilgan bo'lsa
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
