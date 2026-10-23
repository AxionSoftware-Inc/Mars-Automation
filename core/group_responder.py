"""
core/group_responder.py
=======================
GURUHDA VA CHATLARDAGI JAVOB BERISH BO'LIMI (Yagona, Tartibli va Buzilmaydigan Orkestrator).

Bu modul mijoz qaysi qadamdan (1-qadamdanmi, 3-qadamdanmi yoki 6-qadamdanmi) boshlashidan
qat'i nazar hech qachon yiqilmasdan, barcha shartlarni oddiy inson tilidagi 8 ta qat'iy
qoida asosida tekshiradi:

1-QADAM: Alifbo (Lotin/Kirill) va xabardagi INN / Fiskal modul / Telefonni darhol xotiraga saqlash.
         + Agar foydalanuvchi avval INN-siz kvitansiya tashlagan bo'lsa va endi INN yuborsa -> kvitansiyaga ulash!
2-QADAM: Deklarativ va Dinamik Qoidalar (RuleEngine & data/custom_patches.json) — kodga tegmasdan yangi qoida qo'shish.
3-QADAM: Usta / Admin chaqirish yoki gapni cho'zib yuborish (Eskalatsiya qoidasi).
4-QADAM: «Apparat ishlamayapti / Xatolik chiqyapti» (3 bosqichli oltin qoida — istalgan bosqichdan kirsa ham ishlaydi).
5-QADAM: Qarzni va to'lov tarixini tekshirish (INN, Telefon, Fiskal modul, Oylik, Yillik, Ikkalasi).
6-QADAM: Hisob raqam (Shot / Rekvizit) va To'lov savollari (Oylik shot, Yillik shot, bitta hisobga to'lash, 6-sana, pul tushishi).
7-QADAM: Aniq Texnik Yo'riqnomalar (MXIK / Tasnif / Tovar qo'shish va Video Katalog).
8-QADAM: Erkin suhbat va AI Yordamchi (Gemini AI kontekst bilan).
"""

import logging
from typing import Optional, List, Callable, Awaitable
from aiogram import types, Bot

from user_memory import user_memory
from translit_manager import adapt_to_user_script
from core.rule_engine import rule_engine, RuleContext
from core.models import (
    extract_clean_inn,
    extract_fiscal_module,
    extract_clean_phone,
    is_incomplete_inn_text
)
from admin_manager import admin_manager, get_admin_contact_keyboard

logger = logging.getLogger(__name__)

SOURCE_CHANNEL_ID = -1001641871516  # @POS_Terminal_UzSmart_Bank

# Sabrsizlik yoki gapni cho'zish iboralari (3-Qadam uchun)
PROLONGED_CHAT_PHRASES = [
    "qachon javob", "qachon qaraysiz", "qachon qaraysilar", "qachon qaraysizlar",
    "javob bering", "javob bervoring", "javob beringlar", "javob yo'qku", "javob yoqku",
    "javob bermaysizmi", "javob bermaysanmi", "nega indamaysiz", "nega indamaysan",
    "nega javob yo'q", "nega javob yoq", "indamaysan", "indamaysiz", "gapirsangchi", "gapiring",
    "alo", "alo alo", "eshityapsizmi", "eshityapsanmi", "kimdir bormi", "odam bormi",
    "tirikmisiz", "tirikmisan", "bormisiz", "bormisan",
    "tezroq bo'l", "tezroq bol", "tezroq qiling", "tezroq qilib bering", "tezroq qib bering",
    "tezroq yoq", "tezroq yoqing", "tezroq yoqvoring", "bo'laqol", "bolaqol",
    "qachon yoqiladi", "qachon yoqasiz", "qachon yoqasizlar", "qachon tuzatiladi", "qachon tuzatasiz",
    "qachon bo'ladi", "qachon boladi", "bo'ladimi o'zi", "boladimi ozi", "bo'ladimi ozi",
    "kutib qoldim", "qachongacha kutaman", "qachongacha kutish kerak", "jonga tegdi",
    "e nima bo'ldi", "ee nima boldi", "nima bo'ldi", "nima boldi", "nima qilyapsiz",
    "admin qani", "admin qayerda", "usta qani", "kim javob beradi", "oxshamadi baribir",
    "o'zing top", "ozing top", "senga nima",
    "qanaqa bot bu", "tushunarsiz bot", "tushunmayapsan", "axmoq", "jinni", "ha qachon", "qachon endi",
    "tashladimku boya", "tashladimku", "tashadimku", "hudoga soldim", "hudodan top",
    "gap qaytarma", "lekin ishlamayabdida",
    "ishlamayaptida baribir", "ishlamayabdida"
]


class GroupResponseOrchestrator:
    """
    Guruh va shaxsiy chatlarda barcha matnli murojaatlarni qabul qiluvchi
    va 8 qadamli qoida bo'yicha adashmasdan javob beruvchi markaziy sinf.

    Shuningdek, istalgan vaqtda `register_custom_step` orqali yangi qoida/modul ulash mumkin.
    """

    def __init__(self):
        # Tashqi modullar o'zlarining maxsus handlerlarini ulashi uchun ro'yxat
        self._custom_steps: List[Callable[[types.Message, Bot, str], Awaitable[bool]]] = []

    def register_custom_step(self, step_fn: Callable[[types.Message, Bot, str], Awaitable[bool]]):
        """Yangi qoida yoki tashqi modul qadamini zanjirga ulash"""
        self._custom_steps.append(step_fn)

    async def process_message(self, message: types.Message, bot: Bot, ai_func=None) -> bool:
        """
        Guruh yoki shaxsiy chatdan kelgan xabarni 1 dan 8 gacha qadamlar bo'yicha tahlil qiladi.
        Mijoz qaysi qadamdan boshlashidan qat'i nazar (1, 3, 5 yoki 6) kontekstni yo'qotmaydi.
        """
        from handlers.intents import (
            billing_intent_handler,
            hardware_intent_handler,
            mxik_intent_handler,
            operator_intent_handler,
            conversation_intent_handler
        )
        from handlers.intents.hardware import is_device_issue, UNRESOLVED_WORDS
        from handlers.intents.operator import OPERATOR_KEYWORDS
        from handlers.debt import (
            is_debt_inquiry,
            handle_debt_inquiry,
            is_inn_or_phone_query_message,
            process_and_send_debt_result
        )
        from excel_manager import excel_manager

        user_id = message.from_user.id if message.from_user else 0
        username = message.from_user.username if message.from_user else None
        chat_id = message.chat.id
        raw_text = message.text or ""
        clean_text = raw_text.strip()
        lower_text = clean_text.lower()

        if not clean_text:
            return False

        # =====================================================================
        # 0-QADAM: GURUHDA ADMIN YOKI BOSHQA INSONGA YOZILGAN REPLY LARNI FILTRLASH
        # =====================================================================
        chat_type = getattr(message.chat, "type", "private")
        if chat_type in ("group", "supergroup"):
            replied_msg = getattr(message, "reply_to_message", None)
            replied_user = getattr(replied_msg, "from_user", None) if replied_msg else None
            replied_is_bot = bool(getattr(replied_user, "is_bot", False)) if replied_user else False

            # A) Agar guruhda ro'yxatdan o'tgan Admin/Usta mijozga reply qilib javob yozayotgan bo'lsa:
            # Mijozning eskalatsiya/muammo holatini yopamiz va bot sukut saqlaydi (adminga xalaqit bermaydi!)
            if admin_manager.is_admin(user_id, username) and replied_user and not replied_is_bot:
                target_uid = getattr(replied_user, "id", 0)
                if target_uid:
                    user_memory.clear_issue_mode(chat_id, target_uid)
                    user_memory.clear_escalation(chat_id, target_uid)
                return True

            # B) Agar Admin guruhda mijozlarga ko'rsatma yozsa ("hozir yoqib beraman", "yoqildi", "tekshirib ko'ring"):
            if admin_manager.is_admin(user_id, username):
                admin_operator_phrases = [
                    "yoqib beraman", "hozir yoqib", "ochib beraman", "hozir ochib",
                    "yoqildi", "ochildi", "faollashtirildi", "ishlatib ko'ring",
                    "o'chirib yoqing", "perezagruzka qiling", "tekshirib ko'ring"
                ]
                if any(ap in lower_text for ap in admin_operator_phrases):
                    return True

        # =====================================================================
        # 1-QADAM: ALIFBO VA KONTEKSTNI DARHOL ESLAB QOLISH (Har qanday qadamdan kirganda ham!)
        # =====================================================================
        user_script = user_memory.detect_and_update_script(chat_id, user_id, raw_text)

        found_fm = extract_fiscal_module(clean_text)
        found_inn = extract_clean_inn(clean_text)
        if found_fm and found_inn and found_inn in found_fm:
            found_inn = None

        # Agar mijoz xabar ichida bazada mavjud INN yozgan bo'lsa,
        # darhol xotiraga yozib qo'yamiz (noto'g'ri/begona 9 xonali raqam eski INN ni buzmasligi uchun tekshiramiz!)
        if found_inn and (excel_manager.search(found_inn) or excel_manager.is_decommissioned(found_inn)):
            user_memory.set_last_id(chat_id, user_id, found_inn)

        # 1.1 Agar mijoz avval INN-siz to'lov kvitansiyasi tashlagan bo'lsa va endi INN yozsa -> darhol ulash!
        if found_inn:
            from core import core_engine
            pending_res = core_engine.resolve_pending_receipt_if_any(found_inn, chat_id, user_id)
            if pending_res:
                reply_m = adapt_to_user_script(pending_res.reply_text, user_script)
                try:
                    await message.reply(reply_m, parse_mode="HTML")
                except Exception:
                    await message.reply(reply_m)

                user_memory.add_user_message(chat_id, user_id, f"Mening INN raqamim: {found_inn}")
                user_memory.add_assistant_message(chat_id, user_id, reply_m)

                if pending_res.should_notify_admin and pending_res.receipt_facts:
                    await admin_manager.notify_receipt_escalation(
                        bot=bot,
                        user=message.from_user,
                        chat_id=chat_id,
                        receipt_facts=pending_res.receipt_facts,
                        debt_status_info=pending_res.debt_status_info,
                        file_id=pending_res.file_id,
                        is_photo=pending_res.is_photo
                    )
                return True

        # =====================================================================
        # 2-QADAM: PLUG & PLAY QOIDALAR (RuleEngine va data/custom_patches.json)
        # =====================================================================
        rule_ctx = RuleContext(
            text=raw_text,
            clean_text=clean_text,
            lower_text=lower_text,
            chat_id=chat_id,
            user_id=user_id,
            user_name=message.from_user.full_name if message.from_user else "Mijoz",
            user_username=message.from_user.username if message.from_user else "",
            user_script=user_script,
            found_inn=found_inn,
            found_fm=found_fm,
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
                    await bot.copy_message(
                        chat_id=chat_id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=patch_result.video_id
                    )
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
            return True

        # Tashqi ulangan custom modullar qadamlari (agar qo'shilgan bo'lsa)
        for custom_step in self._custom_steps:
            if await custom_step(message, bot, user_script):
                return True

        # =====================================================================
        # 2.5-QADAM: SALOMLASHISH / GREETINGS (Mutlaqo xavfsiz, adminga yo'naltirmaydi)
        # =====================================================================
        PURE_GREETINGS = {
            "salom", "assalomu alaykum", "assalomu aleykum", "assalom alaykum", "assalom aleykum",
            "salom alaykum", "salomalaykum", "salom hammaga", "salomlar",
            "privet", "привет", "салом", "ассалому алайкум", "ассалому алейкум",
            "здравствуйте", "добрый день", "доброе утро", "добрый вечер",
            "hayrli kun", "xayrli kun", "hayrli tong", "xayrli tong", "hayrli kech", "xayrli kech"
        }
        words = lower_text.split()
        is_pure_greeting = (
            lower_text in PURE_GREETINGS
            or (len(words) <= 4 and any(lower_text.startswith(w) for w in ["salom", "assalomu alaykum", "assalomu aleykum", "салом", "ассалому алайкум", "привет", "здравствуйте"])
                and not any(action_kw in lower_text for action_kw in [
                    "ishlamay", "ishlamayapti", "qarz", "shot", "hisob", "chek", "kvitansiya", "video", "admin", "usta",
                    "inn", "fm", "fiskal", "yillik", "oylik", "operat", "tuzat", "blok", "och", "yoq", "tolash", "to'lash"
                ]))
        )
        if is_pure_greeting:
            user_memory.clear_issue_mode(chat_id, user_id)
            user_memory.clear_escalation(chat_id, user_id)
            user_memory.set_last_topic(chat_id, user_id, "greeting")
            welcome_msg = (
                "👋 <b>Assalomu alaykum! «Mars» elektron xizmat ko'rsatish markazining rasmiy yordamchi botiga xush kelibsiz.</b>\n\n"
                "Sizga qanday yordam bera olaman?\n"
                "🔹 <b>Qarzdorlikni tekshirish:</b> Korxona <b>СТИР (INN)</b> yoki <b>Fiskal modul (LG..., YG...)</b> raqamini yuboring;\n"
                "🔹 <b>To'lov rekvizitlari:</b> «Oylik shot» yoki «Yillik shot» deb yozing;\n"
                "🔹 <b>Apparat nosozligi:</b> Muammo haqida yozing yoki ekran fotosuratini tashlang;\n"
                "🔹 <b>Kassa bo'yicha yo'riqnoma:</b> Qiziqtirgan mavzuni yozing (masalan: <i>X-hisobot</i>, <i>Tovar qo'shish</i>, <i>Vozvrat</i>)."
            )
            welcome_msg = adapt_to_user_script(welcome_msg, user_script)
            try:
                await message.reply(welcome_msg, parse_mode="HTML")
            except Exception:
                await message.reply(welcome_msg)
            user_memory.add_user_message(chat_id, user_id, raw_text)
            user_memory.add_assistant_message(chat_id, user_id, welcome_msg)
            return True

        # =====================================================================
        # 2.6-QADAM: MINNATDORCHILIK / RAHMAT / TUSHUNDIM (Mutlaqo xavfsiz, adminga o'tkazmaydi)
        # =====================================================================
        GRATITUDE_WORDS = [
            "rahmat", "katta rahmat", "raxmat", "katta raxmat", "tashakkur", "tushundim",
            "tushunarli", "boldi tushundim", "bo'ldi tushundim", "ha tushundim",
            "yordamingiz uchun rahmat", "spasibo", "спасибо", "раҳмат", "катта раҳмат", "тушундим", "тушунарли"
        ]
        is_gratitude = (
            lower_text in GRATITUDE_WORDS
            or any(w in lower_text for w in ["rahmat", "raxmat", "tashakkur", "раҳмат", "спасибо"])
        ) and not any(w in lower_text for w in ["lekin", "ammo", "ishlamadi", "ishlamayapti", "qarz", "xato"])

        if is_gratitude:
            user_memory.clear_issue_mode(chat_id, user_id)
            user_memory.clear_escalation(chat_id, user_id)
            user_memory.set_last_topic(chat_id, user_id, "resolved")
            gratitude_msg = (
                "😊 <b>Arzimaydi! Sizga yordam bera olganimizdan xursandmiz.</b>\n\n"
                "«Mars» elektron xizmat ko'rsatish markazi doimo xizmatingizda. Yana savollaringiz yoki kassa apparatingiz bo'yicha yordam kerak bo'lsa, bemalol murojaat qiling! Salomat bo'ling! 🤝"
            )
            gratitude_msg = adapt_to_user_script(gratitude_msg, user_script)
            try:
                await message.reply(gratitude_msg, parse_mode="HTML")
            except Exception:
                await message.reply(gratitude_msg)
            user_memory.add_user_message(chat_id, user_id, raw_text)
            user_memory.add_assistant_message(chat_id, user_id, gratitude_msg)
            return True

        # =====================================================================
        # 3-QADAM: USTA / ADMIN CHAQIRISH YOKI GAPNI CHO'ZISH (Eskalatsiya qoidasi)
        # =====================================================================
        is_command = clean_text.startswith("/")

        # 3.1 Agar mijoz to'g'ridan-to'g'ri "usta kerak", "admin", "operator" desa (hatto 1-xabarda aytsa ham!):
        if any(kw in lower_text for kw in OPERATOR_KEYWORDS) and not any(w in lower_text for w in UNRESOLVED_WORDS):
            if await operator_intent_handler.handle(message, bot, user_script):
                return True

        # 3.2 Agar mijoz ALLAQACHON adminga topshirilgan bo'lsa:
        # MUHIM: Agar mijoz yangi mavzu boshlasa ("aparatim ishlamay qoldi", "qarzim bormi", "oylik shot", "mxik" va h.k.),
        # eskalatsiya qulfini ochamiz va unga normal javob beramiz!
        # Faqat sabrsizlik/noo'rin davomiy gaplarda ("tashladimku boya", "qachon javob", "hudoga soldim", "gap qaytarma") "Admin javobini kuting" deymiz.
        is_new_meaningful_intent = (
            bool(found_inn)
            or bool(found_fm)
            or is_command
            or is_device_issue(clean_text)
            or is_debt_inquiry(message)
        )
        if is_new_meaningful_intent and user_memory.is_escalated_to_admin(chat_id, user_id):
            user_memory.clear_escalation(chat_id, user_id)

        if not is_new_meaningful_intent:
            if user_memory.is_escalated_to_admin(chat_id, user_id):
                # Tekshiramiz: balki mijoz aniq hisob raqam, MXIK yoki video katalog so'ragandir?
                from payment_accounts import (
                    classify_payment_intent,
                    is_annual_check_intent,
                    is_monthly_check_intent,
                    is_both_check_intent,
                    is_general_debt_check_intent,
                    is_mxik_intent,
                    is_how_to_pay_video_intent
                )
                from handlers.intents.billing import PAYMENT_METHODS_KEYWORDS
                from catalog_manager import catalog_manager
                is_structured_request = (
                    bool(classify_payment_intent(clean_text))
                    or is_annual_check_intent(clean_text)
                    or is_monthly_check_intent(clean_text)
                    or is_both_check_intent(clean_text)
                    or is_general_debt_check_intent(clean_text)
                    or is_mxik_intent(clean_text)
                    or is_how_to_pay_video_intent(clean_text)
                    or any(kw in lower_text for kw in PAYMENT_METHODS_KEYWORDS)
                    or bool(catalog_manager.find_post_by_keywords(clean_text))
                )
                if is_structured_request:
                    user_memory.clear_escalation(chat_id, user_id)
                else:
                    repeats = user_memory.increment_escalation_repeats(chat_id, user_id)
                    remembered_id = user_memory.get_last_id(chat_id, user_id)
                    org_name = user_memory.get_org_name(chat_id, user_id)
                    last_photo = user_memory.get_last_photo(chat_id, user_id)
                    esc_ack = (
                        "👨‍💻 <b>Murojaatingiz hududiy mas'ul administratorga yo'naltirilgan. Iltimos, admin javobini kuting!</b>\n\n"
                        f"{admin_manager.get_contacts_display(inn=remembered_id)}\n\n"
                        "Mutaxassisimiz navbat bo'yicha tez orada siz bilan bog'lanadi.\n"
                        "Quyidagi tugmalar orqali to'g'ridan-to'g'ri aloqaga chiqishingiz mumkin:"
                    )
                    esc_ack = adapt_to_user_script(esc_ack, user_script)
                    kb = get_admin_contact_keyboard(inn=remembered_id)
                    try:
                        await message.reply(esc_ack, parse_mode="HTML", reply_markup=kb)
                    except Exception:
                        await message.reply(esc_ack, reply_markup=kb)

                    user_memory.add_user_message(chat_id, user_id, raw_text)
                    user_memory.add_assistant_message(chat_id, user_id, esc_ack)

                    if repeats in (1, 3, 5):
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
                    return True

            # 3.3 Agar mijoz aniq sabrsizlik iboralarini yozsa (masalan: "alo", "qachon javob", "tashladimku boya"):
            from payment_accounts import (
                classify_payment_intent,
                is_annual_check_intent,
                is_monthly_check_intent,
                is_both_check_intent,
                is_general_debt_check_intent,
                is_mxik_intent
            )
            from catalog_manager import catalog_manager
            has_structured_intent = (
                bool(classify_payment_intent(clean_text))
                or is_annual_check_intent(clean_text)
                or is_monthly_check_intent(clean_text)
                or is_both_check_intent(clean_text)
                or is_general_debt_check_intent(clean_text)
                or is_mxik_intent(clean_text)
                or bool(catalog_manager.find_matching_post(clean_text))
            )
            is_prolonged = (not has_structured_intent) and any(p in lower_text for p in PROLONGED_CHAT_PHRASES)

            if is_prolonged:
                user_memory.mark_escalated_to_admin(chat_id, user_id, reason="User gapni cho'zdi / sabrsizlik")
                remembered_id = user_memory.get_last_id(chat_id, user_id)
                org_name = user_memory.get_org_name(chat_id, user_id)
                last_photo = user_memory.get_last_photo(chat_id, user_id)

                esc_msg = (
                    "👨‍💻 <b>Sizni hududiy mas'ul administratorga yo'naltirdik. Iltimos, admin javobini kuting!</b>\n\n"
                    f"{admin_manager.get_contacts_display(inn=remembered_id)}\n\n"
                    "Barcha yozishmalaringiz va ma'lumotlaringiz mas'ul xodimimizga yetkazildi.\n"
                    "Quyidagi tugmalar orqali to'g'ridan-to'g'ri aloqaga chiqishingiz mumkin:"
                )
                esc_msg = adapt_to_user_script(esc_msg, user_script)
                kb = get_admin_contact_keyboard(inn=remembered_id)
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
                return True

        # =====================================================================
        # 4-QADAM: APPARAT NOSOZLIGI PIPELINE'I (3 bosqichli oltin qoida)
        # Mijoz qaysi qadamdan boshlashidan qat'i nazar:
        # - Avval INN tashlab, keyin "ishlamayapti" deydimi,
        # - Avval FM tashlab, keyin "ishlamayapti" deydimi,
        # - Yoki bitta xabarda hammasini yozadimi — HardwareIntentHandler xotiradagi borini olib,
        #   faqat yetishmayotganini so'raydi!
        # =====================================================================
        # Maxsus istisno: agar mijoz yillik tekshiruv ("yillik", "fiskal"), hisob raqam ("oylik shot", "yillik shot"),
        # yoki fiskal modul yuborayotgan bo'lsa — buni AVVAL billing_intent_handler tekshiradi!
        # Chunki yillik tekshiruv uchun INN emas, aynan Fiskal Modul (LG/YG) talab qilinadi.
        # =====================================================================
        from payment_accounts import (
            is_annual_check_intent,
            is_monthly_check_intent,
            is_both_check_intent,
            classify_payment_intent
        )
        is_asking_fm_location = any(p in lower_text for p in [
            "fiskal modul qayerda", "fiskal modul qayerdan", "fm raqamini qayerdan",
            "modul raqami qayerda", "fiskal modulni qanday topaman", "fiskal modul nima",
            "fiskal raqam nima", "fiskal raqam qayerda", "fiskal qayerda", "fiskal raqamni qayerdan",
            "chek yo'q", "chek yoq", "chekim yo'q", "chekim yoq", "chek chiqmayapti", "chek chiqmayapdi",
            "чек чиқмаяпти", "чек чикмаяпти", "чек йўқ", "чек йук",
            "фискал модул қаерда", "фискал модул каерда", "фискал модул нима"
        ])
        is_billing_or_payment_intent = (
            bool(found_fm)
            or is_annual_check_intent(clean_text)
            or is_monthly_check_intent(clean_text)
            or is_both_check_intent(clean_text)
            or bool(classify_payment_intent(clean_text))
            or is_asking_fm_location
            or is_incomplete_inn_text(clean_text)
            or (clean_text.isdigit() and 1 <= len(clean_text) <= 8 and not found_fm)
        )
        if is_billing_or_payment_intent:
            if await billing_intent_handler.handle(message, bot, user_script):
                return True

        # Agar mijoz muammo rejimida bo'lsa yoki apparat nosozligi iborasini yozsa:
        if user_memory.is_issue_mode(chat_id, user_id) or is_device_issue(raw_text):
            if await hardware_intent_handler.handle(message, bot, user_script):
                return True

        # =====================================================================
        # 5-QADAM VA 6-QADAM: QARZ TEKSHIRUVI, TO'LOV TARIXI VA HISOB RAQAMLAR (SHOTLAR)
        # =====================================================================
        # 5.1 To'lov tarixi / "Nega qarz?" / "To'laganmanku" e'tirozlari:
        if is_debt_inquiry(message):
            await handle_debt_inquiry(message)
            return True

        # 5.2 va 6-Qadam: Oylik/Yillik/Ikkala qarz tekshiruvi, Fiskal modul, Hisob raqamlar (Post 85 / Post 34),
        # Bitta hisobga to'lash taqiqi, 6-sana muddati, Pul yechildi lekin yonmadi:
        if await billing_intent_handler.handle(message, bot, user_script):
            return True

        # 5.3 Agar ro'yxatdan o'tgan telefon raqami orqali qarz tekshirilayotgan bo'lsa:
        if is_inn_or_phone_query_message(message):
            query_num = extract_clean_inn(clean_text) or extract_clean_phone(clean_text)
            if query_num:
                await process_and_send_debt_result(message, bot, query_num)
                return True

        # Qo'shimcha nosozlik va "ishlamadi" so'zlari (agar muammo rejimidan tashqarida yozilsa):
        if await hardware_intent_handler.handle(message, bot, user_script):
            return True

        # =====================================================================
        # 7-QADAM: ANIQ TEXNIK YO'RIQNOMALAR (MXIK / TASNIF / VIDEO KATALOG)
        # =====================================================================
        if await mxik_intent_handler.handle(message, bot, user_script):
            return True

        if await operator_intent_handler.handle(message, bot, user_script):
            return True

        # =====================================================================
        # 8-QADAM: VIDEO KATALOG VA ERKIN SUHBAT (GEMINI AI)
        # =====================================================================
        await conversation_intent_handler.handle(message, bot, user_script, ai_func=ai_func)
        return True


group_responder = GroupResponseOrchestrator()
