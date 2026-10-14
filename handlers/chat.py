import logging
from aiogram import Router, types, Bot, F
from catalog_manager import catalog_manager
from ai_helper import generate_ai_reply, generate_ai_reply_ex
from user_memory import user_memory
from payment_accounts import (
    classify_payment_intent,
    is_mxik_intent,
    is_annual_check_intent,
    is_annual_pay_intent,
    format_ofd_annual_status,
    get_monthly_payment_card,
    get_annual_payment_card,
    get_all_payment_accounts_card,
    get_monthly_post_note,
    get_annual_post_note,
    get_both_posts_intro,
    get_mxik_guidance,
    MARS_POST_ID,
    MARS_VIDEO_ID,
    YANGI_TEXNOLOGIYALAR_POST_ID,
    YANGI_TEXNOLOGIYALAR_VIDEO_ID
)
from translit_manager import adapt_to_user_script, detect_script

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
    "operator chaqir", "оператор", "админ", "мастер", "помогите",
    "ishlamadi", "ishlamayapti baribir", "baribir ishlamadi", "ochmadi",
    "o'xshamadi", "oxshamadi", "yoqilmadi", "reboot qildim ishlamadi",
    "ochirib yoqdim ishlamadi", "usta yuboring", "usta jonating", "usta jo'nating",
    "admin bilan gaplashaman", "admin bilan gaplashmoqchiman", "ustaxonaga", "qilolmadim"
]

CONVERSATIONAL_FOLLOWUPS = [
    "qachon qo'shiladi", "qachon qoshiladi", "qachon yoqiladi", "qachon ochiladi",
    "qachon ishlaydi", "qachon aktivlashadi", "qachon yoqasiz", "keyingi to'lov", "keyingi tolov",
    "keyingi to'lovni", "keyingi tolovni", "qancha to'layman", "qancha tolayman", "qancha to'lashim",
    "qancha tolashim", "qancha qarz", "qarzim qancha", "yana to'laymanmi", "yana tolaymanmi",
    "adminga bordimi", "adminga jo'natildimi", "chek tushdimi", "kvitansiya tushdimi",
    "to'lov tushdimi", "tolov tushdimi", "endi nima", "endi nima qilay", "nima qilish kerak",
    "qarzim bormi", "qancha qarzim bor", "yana to'lashim kerakmi", "yana tolashim kerakmi",
    "rahmat", "tushundim", "yaxshi", "ok", "xa", "ha", "boladi", "bo'ladi",
    "когда включите", "чек отправил", "оплатил", "следующая оплата", "сколько платить"
]

@router.message(F.text)
async def handle_user_chat(message: types.Message, bot: Bot):
    """
    Foydalanuvchi bilan ko'p bosqichli (multi-turn) aqlli suhbat:
    0. Matnda INN aniqlansa va qarz/apparat so'ralsa -> Zaxira INN protsessori
    1. To'lov rekvizitlari va hisob raqamlar (Oylik Mars va Yillik Yangi Texnologiyalar ajratilishi, kanaldan post nusxalash)
    2. MXIK (IKPU / Tasnif / Soliq talablari va tovar qo'shish)
    3. To'lov usuli yoki Click bo'yicha to'g'ridan-to'g'ri so'rovlar -> 148-video va rekvizitlar
    4. Operator / Usta talab qilinganda -> Adminga to'g'ridan-to'g'ri eskalatsiya
    5. Davomiy suhbat (qachon qo'shiladi, keyingi to'lov, qarz holati va h.k.) -> AI va boyitilgan xotira
    6. Faqat maxsus texnik qo'llanma so'ralgandagina -> Video katalogdan qidirish
    """
    text = message.text.strip()
    lower_text = text.lower()
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    # Foydalanuvchi alifbosini aniqlash va yangilash (Lotin yoki Kirill)
    user_script = user_memory.detect_and_update_script(chat_id, user_id, text)

    # 0. AGAR MATNDA FISKAL MODUL RAQAMI (LG..., YG..., UZ... va h.k.) ANIQLANSA -> @ofd943_bot GA YUBORISH
    from core.models import extract_clean_inn, extract_fiscal_module
    found_fm = extract_fiscal_module(text)
    if found_fm:
        user_memory.set_last_fm(chat_id, user_id, found_fm)
        from ofd_bridge import ofd_bridge
        ofd_reply = await ofd_bridge.query_fiscal_module(bot, found_fm)
        ofd_text = format_ofd_annual_status(found_fm, ofd_reply, user_script)
        try:
            await message.reply(ofd_text, parse_mode="HTML")
        except Exception:
            await message.reply(ofd_text)
        user_memory.add_user_message(chat_id, user_id, text)
        user_memory.add_assistant_message(chat_id, user_id, ofd_text)
        if ofd_reply and any(w in ofd_reply.lower() for w in ["qarzdorlik mavjud", "fmo dan qarzdorlik", "qarzdorlik"]):
            user_memory.set_last_topic(chat_id, user_id, "annual_debt_exists")
        elif ofd_reply and "faol" in ofd_reply.lower():
            user_memory.set_last_topic(chat_id, user_id, "annual_debt_clear")
        return

    # 0.1 AGAR MIJOZ "YILLIK QARZNI TEKSHIR / OFD TEKSHIR" DEB SO'RASA
    if is_annual_check_intent(text):
        remembered_fm = user_memory.get_last_fm(chat_id, user_id)
        if remembered_fm:
            from ofd_bridge import ofd_bridge
            ofd_reply = await ofd_bridge.query_fiscal_module(bot, remembered_fm)
            ofd_text = format_ofd_annual_status(remembered_fm, ofd_reply, user_script)
            try:
                await message.reply(ofd_text, parse_mode="HTML")
            except Exception:
                await message.reply(ofd_text)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, ofd_text)
            if ofd_reply and any(w in ofd_reply.lower() for w in ["qarzdorlik mavjud", "fmo dan qarzdorlik", "qarzdorlik"]):
                user_memory.set_last_topic(chat_id, user_id, "annual_debt_exists")
            elif ofd_reply and "faol" in ofd_reply.lower():
                user_memory.set_last_topic(chat_id, user_id, "annual_debt_clear")
            return
        else:
            fm_ask = (
                "🏛 <b>Yillik Soliq (OFD) qarzdorligini tekshirish uchun:</b>\n\n"
                "Kassa chekining eng pastki qismidagi <b>Fiskal modul seriya raqamini (LG..., YG..., UZ...)</b> yuboring.\n"
                "Masalan: <code>LG420210630789</code> yoki <code>UZ200701040469</code>.\n\n"
                "<i>Ushbu seriya raqami orqali Davlat Soliq Qo'mitasi (OFD) bazasidan qarzdorlikni tekshirib beramiz.</i>"
            )
            fm_ask = adapt_to_user_script(fm_ask, user_script)
            try:
                await message.reply(fm_ask, parse_mode="HTML")
            except Exception:
                await message.reply(fm_ask)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, fm_ask)
            user_memory.set_last_topic(chat_id, user_id, "awaiting_fiscal_module")
            return

    # 0.2 AGAR MIJOZ "TO'LAYMAN / YILLIK SHOT RAQAM TASHLA" DESA
    last_topic = user_memory.get_last_topic(chat_id, user_id)
    if is_annual_pay_intent(text, last_topic):
        annual_card = adapt_to_user_script(get_annual_payment_card(), user_script)
        try:
            await message.reply(annual_card, parse_mode="HTML")
        except Exception:
            await message.reply(annual_card)

        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=SOURCE_CHANNEL_ID,
                message_id=YANGI_TEXNOLOGIYALAR_VIDEO_ID
            )
        except Exception as e:
            logger.warning(f"Video 145 nusxalashda xatolik: {e}")

        user_memory.add_user_message(chat_id, user_id, text)
        user_memory.add_assistant_message(chat_id, user_id, annual_card)
        user_memory.set_last_topic(chat_id, user_id, "annual_payment_card_sent")
        return

    # 0.3 AGAR MATNDA INN BO'LSA
    found_inn = extract_clean_inn(text)
    if found_inn:
        user_memory.set_last_id(chat_id, user_id, found_inn)
        TECH_QUESTION_WORDS = [
            "qanday", "qanaqa", "qilish kerak", "qo'yish", "urish", "bekor qilish",
            "vozvrat", "qaytaring", "qaytarish", "zaryad", "zaryatka", "qog'oz", "qogoz",
            "x-otchet", "x otchet", "z-otchet", "z otchet", "inkassatsiya", "wifi",
            "parol", "ulanish", "ochish", "yoqish", "ulash", "tushuntiring", "yo'riqnoma",
            "как", "как пробить", "возврат", "зарядка", "бумага", "инкассация"
        ]
        # Agar texnik amaliyot yoki yo'riqnoma so'ralmagan bo'lsa -> oylik qarz natijasi yuboriladi
        if not any(tw in lower_text for tw in TECH_QUESTION_WORDS):
            from handlers.debt import process_and_send_debt_result
            await process_and_send_debt_result(message, bot, found_inn)
            return

    # 0.2 4-BOSQICHLI STANDART TASHXIS MODELI (Qarzdorlik -> Texnik -> Reboot -> Hududiy Usta)
    DEVICE_ISSUE_PHRASES = [
        "apparat ishlamayapti", "apparatim ishlamayapti", "kassa ishlamayapti",
        "kassa ishlamay qoldi", "apparat ishlamay qoldi", "chek urmayapti",
        "chek chiqmayapti", "kassa qotib qoldi", "apparat qotib qoldi",
        "ishlamayapti apparat", "ishlamayapti kassa", "ishlamayapti",
        "ishlamay qoldi", "o'chib qoldi", "ochib qoldi", "o'chib qolgan",
        "blok bo'ldi", "bloklandi", "blok bolgan", "buzildi", "buzilib qoldi",
        "xatolik", "xato", "xatolik chiqyapti", "xato chiqyapti", "xatolik beryapti",
        "xato beryapti", "xatolik kodi", "xatolik 406", "kod 406", "kod 102",
        "oshibka", "ошибка", "ne rabotayet", "не работает", "сломался", "заблокирован"
    ]
    if any(phrase in lower_text for phrase in DEVICE_ISSUE_PHRASES):
        remembered_id = user_memory.get_last_id(chat_id, user_id)
        if remembered_id:
            # 1-bosqich: Oylik va Yillik qarzdorlikni tekshirish
            from handlers.debt import format_debt_response
            from excel_manager import excel_manager
            results = excel_manager.search(remembered_id)
            if not results and excel_manager.is_decommissioned(remembered_id):
                decom_list = excel_manager.get_decommissioned(remembered_id)
                decom_org = decom_list[0].get("name", "") if decom_list else ""
                decom_msg = (
                    f"ℹ️ <b>{decom_org}</b> korxonasi xizmat ko'rsatish bazasidan hisobdan chiqarilgan (o'chirilgan).\n"
                    f"Qarzdorlik hisoblanmaydi (0 so'm).\n\n"
                    f"Agar yangitdan xizmat ko'rsatish yoki apparatni qayta faollashtirish kerak bo'lsa, «Usta kerak» yoki «Admin» deb yozishingiz mumkin."
                )
                decom_msg = adapt_to_user_script(decom_msg, user_script)
                try:
                    await message.reply(decom_msg, parse_mode="HTML")
                except Exception:
                    await message.reply(decom_msg)
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, decom_msg)
                return

            total_debt = sum(item.get("debt", 0.0) for item in results) if results else 0.0
            tuman = excel_manager.get_district_for_inn(remembered_id)

            if total_debt > 0:
                # 1-BOSQICH (60%+ holat): QARZDORLIK MAVJUD!
                debt_resp = format_debt_response(results)
                debt_resp = adapt_to_user_script(debt_resp, user_script)
                try:
                    await message.reply(debt_resp, parse_mode="HTML")
                except Exception:
                    await message.reply(debt_resp)
                try:
                    await bot.copy_message(chat_id=chat_id, from_chat_id=SOURCE_CHANNEL_ID, message_id=148)
                except Exception:
                    pass
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, debt_resp)
                return
            else:
                # 2-BOSQICH: MARS QARZI YO'Q -> FISKAL MODULNI TEKSHIRISH
                org_name = results[0].get("name", "") if results else ""
                remembered_fm = user_memory.get_last_fm(chat_id, user_id)
                if not remembered_fm:
                    clear_msg = (
                        f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id}</code>)\n"
                        f"✅ «Mars» oylik abonent to'lovidan qarzdorlik yo'q (0 so'm).\n\n"
                        f"🏛 Yillik Soliq (OFD) litsenziya muddatini tekshirishimiz uchun kassa chekining pastki qismidagi <b>Fiskal modul raqamini (LG... yoki YG...)</b> yuboring."
                    )
                else:
                    # 3-BOSQICH: OYLIK VA YILLIK QARZI BO'LMASA -> INTERNET, SOAT VA REBOOT
                    clear_msg = (
                        f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id}</code>)\n"
                        f"✅ Oylik va yillik to'lovlardan qarzdorlik yo'q.\n\n"
                        f"📌 <b>Apparatni ishga tushirish uchun tekshiring:</b>\n"
                        f"1️⃣ Apparatda internet (Wi-Fi yoki SIM) va soat/sana to'g'ri ekanligini tekshiring;\n"
                        f"2️⃣ Kassa dasturidan to'liq chiqib qayta kiring yoki apparatni o'chirib qayta yoqing (Перезагрузка / Reboot).\n\n"
                        f"🛠 <i>Agar shunda ham ishlamasa, «Usta kerak» deb yozing, hududingiz bo'yicha mutaxassisga bog'laymiz.</i>"
                    )
                clear_msg = adapt_to_user_script(clear_msg, user_script)
                try:
                    await message.reply(clear_msg, parse_mode="HTML")
                except Exception:
                    await message.reply(clear_msg)
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, clear_msg)
                return
        else:
            # INN hali kiritilmagan: qisqa va lo'nda INN so'rash
            guide_msg = "🔍 <b>Kassa apparatingiz holatini tekshirishimiz uchun korxonangiz СТИР (INN) raqamini yuboring.</b>"
            guide_msg = adapt_to_user_script(guide_msg, user_script)
            try:
                await message.reply(guide_msg, parse_mode="HTML")
            except Exception:
                await message.reply(guide_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, guide_msg)
            return

    # 1. TO'LOV REKVIZITLARI VA HISOB RAQAMLAR (agar aniq INN yoki Fiskal modul kiritilmagan bo'lsa)
    payment_intent = classify_payment_intent(text)
    if payment_intent and not found_fm and not found_inn:
        if payment_intent == "monthly":
            # A) Oylik abonent hisob raqami (Post 85 kanaldan nusxalanadi)
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=MARS_POST_ID,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.warning(f"Oylik shot postini (85) nusxalashda xatolik: {e}, zaxira kartani yuboramiz")
                reply_card = adapt_to_user_script(get_monthly_payment_card(), user_script)
                await message.reply(reply_card, parse_mode="HTML")

            # B) Tagidan qo'shimcha tushuntirish va muddat eslatmasi
            note = get_monthly_post_note(user_script)
            try:
                await message.answer(note, parse_mode="HTML")
            except Exception:
                await message.answer(note)

            # C) Click orqali oylik to'lov videosi (Post 148)
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=MARS_VIDEO_ID
                )
            except Exception as e:
                logger.warning(f"Oylik to'lov videosini yuborishda xatolik: {e}")

            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, note)
            user_memory.set_last_topic(chat_id, user_id, "payment_info_monthly")
            return

        elif payment_intent == "annual":
            # A) Yillik fiskal modul hisob raqami (Post 34 kanaldan nusxalanadi)
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=YANGI_TEXNOLOGIYALAR_POST_ID,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.warning(f"Yillik shot postini (34) nusxalashda xatolik: {e}, zaxira kartani yuboramiz")
                reply_card = adapt_to_user_script(get_annual_payment_card(), user_script)
                await message.reply(reply_card, parse_mode="HTML")

            # B) Tagidan qo'shimcha tushuntirish va Soliq tizimi eslatmasi
            note = get_annual_post_note(user_script)
            try:
                await message.answer(note, parse_mode="HTML")
            except Exception:
                await message.answer(note)

            # C) Click orqali yillik to'lov videosi (Post 145)
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=YANGI_TEXNOLOGIYALAR_VIDEO_ID
                )
            except Exception as e:
                logger.warning(f"Yillik to'lov videosini yuborishda xatolik: {e}")

            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, note)
            user_memory.set_last_topic(chat_id, user_id, "payment_info_annual")
            return

        else:  # both / general
            # A) Ikkala to'lovni adashtirmaslik haqida qat'iy ogohlantirish
            intro = get_both_posts_intro(user_script)
            try:
                await message.reply(intro, parse_mode="HTML")
            except Exception:
                await message.reply(intro)

            # B) Kanaldan Oylik shot posti (Post 85)
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=MARS_POST_ID
                )
            except Exception as e:
                logger.warning(f"Post 85 nusxalashda xatolik: {e}")

            # C) Kanaldan Yillik shot posti (Post 34)
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=YANGI_TEXNOLOGIYALAR_POST_ID
                )
            except Exception as e:
                logger.warning(f"Post 34 nusxalashda xatolik: {e}")

            # D) Click orqali to'lov videosi (Post 148)
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=MARS_VIDEO_ID
                )
            except Exception as e:
                logger.warning(f"Video 148 nusxalashda xatolik: {e}")

            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, intro)
            user_memory.set_last_topic(chat_id, user_id, "payment_info_both")
            return

    # 2. MXIK (IKPU / TASNIF / SOLIQ TALABLARI VA TOVAR QO'SHISH)
    if is_mxik_intent(text):
        mxik_text, mxik_video_id = get_mxik_guidance(text)
        mxik_text = adapt_to_user_script(mxik_text, user_script)
        try:
            await message.reply(mxik_text, parse_mode="HTML")
        except Exception:
            await message.reply(mxik_text)

        if mxik_video_id:
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=mxik_video_id,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.warning(f"MXIK videosi yuborishda xatolik: {e}")

        user_memory.add_user_message(chat_id, user_id, text)
        user_memory.add_assistant_message(chat_id, user_id, mxik_text)
        user_memory.set_last_topic(chat_id, user_id, "mxik_guidance")
        return

    # 3. AGAR TO'LOV QILISH TARTIBI / CLICK SO'RALSA
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

    # 4. OPERATOR / MUTAXASSIS / USTA TALAB QILINGANDA
    if any(kw in lower_text for kw in OPERATOR_KEYWORDS):
        from core import core_engine
        from admin_manager import admin_manager
        decision = core_engine.escalate_general_issue(text, chat_id, user_id)
        reply_msg = adapt_to_user_script(decision.reply_text, user_script)
        try:
            await message.reply(reply_msg, parse_mode="HTML")
        except Exception:
            await message.reply(reply_msg)

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
        return

    # 5. DAVOMIY KONVERSATSION SAVOLLAR YOKI FAOL SUHBAT KONTEKSTI
    has_active_context = bool(user_memory.get_last_id(chat_id, user_id) or user_memory.get_last_receipt(chat_id, user_id))
    is_conversational = any(kw in lower_text for kw in CONVERSATIONAL_FOLLOWUPS)
    explicit_video_request = any(kw in lower_text for kw in ["video", "rolik", "video tashla", "qo'llanma", "qollanma"])

    # Agar aniq video so'ralmagan bo'lsa va bu davomiy suhbat bo'lsa -> To'g'ridan-to'g'ri AI kontekstiga!
    if is_conversational or (has_active_context and not explicit_video_request):
        context_summary = user_memory.get_context_summary(chat_id, user_id)
        reply_text, ai_video_id, needs_admin = generate_ai_reply_ex(text, context_history=context_summary, target_script=user_script)

        if not reply_text or not reply_text.strip():
            fallback = "Savolingiz bo'yicha to'liq ma'lumot berishimiz uchun korxonangiz СТИР (INN) raqamini yuboring."
            reply_text = adapt_to_user_script(fallback, user_script)

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

        if needs_admin:
            from admin_manager import admin_manager
            last_id = user_memory.get_last_id(chat_id, user_id)
            saved_photo = user_memory.get_last_photo(chat_id, user_id)
            await admin_manager.notify_user_query_escalation(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                query_text=text,
                reason="Mijoz noma'lum savol berdi (AI bilmadi va adminga yo'naltirdi)",
                inn=last_id,
                photo_file_id=saved_photo
            )

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

    # 6. TEXNIK VIDEO KATALOGDAN QIDIRISH (faqat maxsus texnik amallar uchun)
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

    # 7. BOSHQALARI BO'YICHA UMUMIY AI JAVOBI
    context_summary = user_memory.get_context_summary(chat_id, user_id)
    reply_text, ai_video_id, needs_admin = generate_ai_reply_ex(text, context_history=context_summary, target_script=user_script)

    if not reply_text or not reply_text.strip():
        fallback = "Savolingiz bo'yicha to'liq ma'lumot berishimiz uchun korxonangiz СТИР (INN) raqamini yuboring."
        reply_text = adapt_to_user_script(fallback, user_script)

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

    if needs_admin:
        from admin_manager import admin_manager
        last_id = user_memory.get_last_id(chat_id, user_id)
        saved_photo = user_memory.get_last_photo(chat_id, user_id)
        await admin_manager.notify_user_query_escalation(
            bot=bot,
            user=message.from_user,
            chat_id=chat_id,
            query_text=text,
            reason="Mijoz noma'lum savol berdi (AI bilmadi va adminga yo'naltirdi)",
            inn=last_id,
            photo_file_id=saved_photo
        )

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
