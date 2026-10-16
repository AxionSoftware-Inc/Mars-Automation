import logging
from aiogram import Router, types, Bot, F
from ai_helper import generate_ai_reply, generate_ai_reply_ex, generate_ai_reply_ex_async
from user_memory import user_memory
from translit_manager import adapt_to_user_script
from core.rule_engine import rule_engine, RuleContext
from core.models import extract_clean_inn, extract_fiscal_module
from admin_manager import admin_manager, get_admin_contact_keyboard
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

PROLONGED_CHAT_PHRASES = [
    "qachon javob", "qachon qaraysiz", "qachon qaraysilar", "qachon qaraysizlar",
    "javob bering", "javob bervoring", "javob beringlar", "javob yo'qku", "javob yoqku",
    "javob bermaysizmi", "javob bermaysanmi", "nega indamaysiz", "nega indamaysan",
    "nega javob yo'q", "nega javob yoq", "indamaysan", "indamaysiz", "gapirsangchi", "gapiring",
    "alo", "alo alo", "eshityapsizmi", "eshityapsanmi", "kimdir bormi", "odam bormi",
    "tirikmisiz", "tirikmisan", "bormisiz", "bormisan",
    "tezroq bo'l", "tezroq bol", "tezroq qiling", "tezroq qilib bering", "tezroq qib bering",
    "tezroq yoq", "tezroq yoqing", "tezroq yoqvoring", "tezroq", "bo'laqol", "bolaqol",
    "qachon yoqiladi", "qachon yoqasiz", "qachon yoqasizlar", "qachon tuzatiladi", "qachon tuzatasiz",
    "qachon bo'ladi", "qachon boladi", "bo'ladimi o'zi", "boladimi ozi", "bo'ladimi ozi",
    "kutib qoldim", "qachongacha kutaman", "qachongacha kutish kerak", "jonga tegdi",
    "e nima bo'ldi", "ee nima boldi", "nima bo'ldi", "nima boldi", "nima qilyapsiz",
    "admin qani", "admin qayerda", "usta qani", "kim javob beradi", "oxshamadi baribir",
    "o'zing top", "ozing top", "bilmayman", "qayerdan bilay", "nimaga kerak", "senga nima",
    "qanaqa bot bu", "tushunarsiz bot", "tushunmayapsan", "axmoq", "jinni", "ha qachon", "qachon endi",
    "tashladimku boya", "tashladimku", "tashadimku", "hudoga soldim", "hudodan top",
    "gap qaytarma", "nma qilay endi", "nima qilay endi", "lekin ishlamayabdida",
    "ishlamayaptida baribir", "ishlamayabdida"
]


@router.message(F.text)
async def handle_user_chat(message: types.Message, bot: Bot):
    """
    Foydalanuvchi bilan qat'iy modulli intentlar pipeline'i (Arxitektura 2.0):
    0. Rule Engine & Custom Patches (data/custom_patches.json deklarativ patchlar)
    1. Billing & Debt Intent (Fiskal modul, INN, oylik/yillik qarz tekshiruvi, hisob raqamlar, Click video)
    2. Hardware Diagnosis Intent (Apparat nosozligi: 1-bosqich oylik qarz, 2-bosqich yillik qarz, 3-bosqich tezkor internet/reboot, muammo hal bo'lmasa -> tezda usta/adminga eskalatsiya!)
    3. MXIK Intent (IKPU / Tasnif / Soliq talablari va tovar qo'shish)
    4. Operator / Usta Intent (Mutaxassis talabi va admin eskalatsiyasi)
    5. Conversational & AI Intent (Davomiy suhbat, video katalog va Gemini AI)
    """
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    raw_text = message.text or ""

    # Foydalanuvchi alifbosini aniqlash va yangilash (Lotin yoki Kirill)
    user_script = user_memory.detect_and_update_script(chat_id, user_id, raw_text)

    # 0. Rule Engine va Custom Patches (data/custom_patches.json)
    clean_text = raw_text.strip()
    rule_ctx = RuleContext(
        text=raw_text,
        clean_text=clean_text,
        lower_text=clean_text.lower(),
        chat_id=chat_id,
        user_id=user_id,
        user_name=message.from_user.full_name if message.from_user else "Mijoz",
        user_username=message.from_user.username if message.from_user else "",
        user_script=user_script,
        found_inn=extract_clean_inn(clean_text),
        found_fm=extract_fiscal_module(clean_text),
        remembered_id=user_memory.get_last_id(chat_id, user_id),
        bot=bot
    )
    patch_result = await rule_engine.evaluate(rule_ctx)
    if patch_result is not None and patch_result.reply_text:
        resp = adapt_to_user_script(patch_result.reply_text, user_script)
        try:
            await message.reply(resp, parse_mode="HTML")
        except Exception:
            await message.reply(resp)
        user_memory.add_user_message(chat_id, user_id, raw_text)
        user_memory.add_assistant_message(chat_id, user_id, resp)
        if patch_result.video_id:
            try:
                await bot.copy_message(chat_id=chat_id, from_chat_id=SOURCE_CHANNEL_ID, message_id=patch_result.video_id)
            except Exception as e:
                logger.error(f"Patch video yuborishda xatolik: {e}")
        if patch_result.should_notify_admin:
            await admin_manager.notify_user_query_escalation(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                query_text=raw_text,
                reason=patch_result.admin_alert_text or "Maxsus patch eskalatsiyasi",
                inn=patch_result.detected_inn
            )
        return

    # 0.5 GOBNI CHO'ZGAN YOKI ALLAQACHON ADMINGA YO'NALTIRILGAN USERLARNI USHLASH:
    found_inn = extract_clean_inn(clean_text)
    found_fm = extract_fiscal_module(clean_text)
    is_command = clean_text.startswith("/")

    if not found_inn and not found_fm and not is_command:
        # A) User ALLAQACHON adminga yo'naltirilgan bo'lsa va yana xabar yozsa:
        if user_memory.is_escalated_to_admin(chat_id, user_id):
            repeats = user_memory.increment_escalation_repeats(chat_id, user_id)
            esc_ack = (
                "👨‍💻 <b>Murojaatingiz mas'ul administratorga yo'naltirilgan. Iltimos, admin javobini kuting!</b>\n\n"
                "Apparatingiz va barcha ma'lumotlaringiz Hududiy THKM texnik xizmat ko'rsatish mas'ul xodimlarimizga (@quvonchbek_admin, @Yashnarbek_butaev) yetkazilgan.\n"
                "Mutaxassisimiz navbat bo'yicha tez orada siz bilan bog'lanadi.\n\n"
                "Quyidagi tugmalar orqali to'g'ridan-to'g'ri aloqaga chiqishingiz mumkin:"
            )
            esc_ack = adapt_to_user_script(esc_ack, user_script)
            kb = get_admin_contact_keyboard()
            try:
                await message.reply(esc_ack, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await message.reply(esc_ack, reply_markup=kb)

            user_memory.add_user_message(chat_id, user_id, raw_text)
            user_memory.add_assistant_message(chat_id, user_id, esc_ack)

            if repeats in (1, 3, 5):
                remembered_id = user_memory.get_last_id(chat_id, user_id)
                org_name = user_memory.get_org_name(chat_id, user_id)
                last_photo = user_memory.get_last_photo(chat_id, user_id)
                await admin_manager.notify_user_query_escalation(
                    bot=bot,
                    user=message.from_user,
                    chat_id=chat_id,
                    query_text=f"Mijoz admin javobini kutayotgan paytda qo'shimcha xabar yozdi: {raw_text}",
                    reason="Admin javobini kutayotgan mijozdan xabar",
                    inn=remembered_id,
                    org_name=org_name,
                    photo_file_id=last_photo
                )
            return

        # B) User gapni cho'zsa (sabrsizlik, behuda so'roqlar yoki savolni ko'paytirish):
        lower_clean = clean_text.lower()
        is_prolonged = any(p in lower_clean for p in PROLONGED_CHAT_PHRASES)
        turn_cnt = user_memory.get_user_turn_count(chat_id, user_id)

        from handlers.intents.hardware import is_device_issue
        has_device_problem = is_device_issue(clean_text)

        if is_prolonged or (turn_cnt >= 4 and len(clean_text.split()) > 1 and not has_device_problem):
            user_memory.mark_escalated_to_admin(chat_id, user_id, reason="User gapni cho'zdi / uzoq suhbat")
            remembered_id = user_memory.get_last_id(chat_id, user_id)
            org_name = user_memory.get_org_name(chat_id, user_id)
            last_photo = user_memory.get_last_photo(chat_id, user_id)

            esc_msg = (
                "👨‍💻 <b>Sizni mas'ul administratorga yo'naltirdik. Iltimos, admin javobini kuting!</b>\n\n"
                "Barcha yozishmalaringiz va ma'lumotlaringiz Hududiy THKM texnik xizmat ko'rsatish mas'ul xodimlarimizga (@quvonchbek_admin, @Yashnarbek_butaev) yetkazildi.\n"
                "Ular tez orada siz bilan bog'lanib, masalangizni hal qilib berishadi.\n\n"
                "Quyidagi tugmalar orqali to'g'ridan-to'g'ri aloqaga chiqishingiz mumkin:"
            )
            esc_msg = adapt_to_user_script(esc_msg, user_script)
            kb = get_admin_contact_keyboard()
            try:
                await message.reply(esc_msg, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await message.reply(esc_msg, reply_markup=kb)

            user_memory.add_user_message(chat_id, user_id, raw_text)
            user_memory.add_assistant_message(chat_id, user_id, esc_msg)

            await admin_manager.notify_user_query_escalation(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                query_text=raw_text,
                reason="Mijoz gapni cho'zdi / tezkor admin aralashuvi talab etiladi",
                inn=remembered_id,
                org_name=org_name,
                photo_file_id=last_photo
            )
            return

    # 1. Hardware Issue Pipeline (Agar mijoz muammo rejimida bo'lsa yoki apparat nosozligidan yozgan bo'lsa):
    # Hech qanday chalg'ishlarsiz birinchi navbatda hardware_intent_handler qat'iy pipeline asosida ishlaydi!
    from handlers.intents.hardware import is_device_issue
    if user_memory.is_issue_mode(chat_id, user_id) or is_device_issue(raw_text):
        if await hardware_intent_handler.handle(message, bot, user_script):
            return

    # 2. Billing & Debt Intent (Oylik, yillik, fiskal modul, hisob raqamlar - oddiy so'rovlar uchun)
    if await billing_intent_handler.handle(message, bot, user_script):
        return

    # 2.1 Hardware Intent (Agar yuqorida tutilmagan qo'shimcha nosozlik bo'lsa)
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
