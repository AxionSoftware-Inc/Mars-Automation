import logging
from typing import Optional
from aiogram import types, Bot

from user_memory import user_memory
from translit_manager import adapt_to_user_script
from core.models import extract_clean_inn, extract_fiscal_module, is_incomplete_inn_text
from ofd_bridge import ofd_bridge
from payment_accounts import (
    classify_payment_intent,
    is_both_check_intent,
    is_general_debt_check_intent,
    is_annual_check_intent,
    is_monthly_check_intent,
    is_annual_pay_intent,
    is_monthly_pay_intent,
    format_ofd_annual_status,
    get_monthly_payment_card,
    get_annual_payment_card,
    get_monthly_post_note,
    get_annual_post_note,
    get_both_posts_intro,
    get_fiscal_module_request_prompt,
    MARS_POST_ID,
    MARS_VIDEO_ID,
    YANGI_TEXNOLOGIYALAR_POST_ID,
    YANGI_TEXNOLOGIYALAR_VIDEO_ID,
    FISKAL_MODUL_SAMPLE_POST_ID
)

logger = logging.getLogger(__name__)

SOURCE_CHANNEL_ID = -1001641871516  # @POS_Terminal_UzSmart_Bank

PAYMENT_METHODS_KEYWORDS = [
    "qanday to'layman", "qanday tolayman", "qanaqa to'layman", "qanaqa tolayman",
    "qayerga to'layman", "qayerga tolayman", "qayerga to'lash", "qayerga tolash",
    "click orqali to'lash", "click orqali tolash", "clickdan to'lash", "clickdan tolash",
    "click orqali qanday", "kartadan to'lash", "plastikdan to'lash", "to'lash tartibi",
    "qanday to'lasam bo'ladi", "qanday tolasam boladi", "to'lov qilish tartibi"
]

TECH_QUESTION_WORDS = [
    "qanday", "qanaqa", "qilish kerak", "qo'yish", "urish", "bekor qilish",
    "vozvrat", "qaytaring", "qaytarish", "zaryad", "zaryatka", "qog'oz", "qogoz",
    "x-otchet", "x otchet", "z-otchet", "z otchet", "inkassatsiya", "wifi",
    "parol", "ulanish", "ochish", "yoqish", "ulash", "tushuntiring", "yo'riqnoma",
    "как", "как пробить", "возврат", "зарядка", "бумага", "инкассация"
]


class BillingIntentHandler:
    """Oylik va yillik to'lovlar, hisob raqamlar, qarz tekshiruvi va kvitansiya intentlarini boshqaruvchi modul"""

    async def handle(self, message: types.Message, bot: Bot, user_script: str) -> bool:
        text = message.text.strip()
        lower_text = text.lower()
        user_id = message.from_user.id if message.from_user else 0
        chat_id = message.chat.id
        last_topic = user_memory.get_last_topic(chat_id, user_id)

        # 0.9 Chala yoki noto'g'ri kiritilgan INN (masalan: "INN 12345" yoki faqat 1..8 xonali raqam "123")
        is_short_digits = text.isdigit() and 1 <= len(text) <= 8 and not extract_fiscal_module(text)
        if is_incomplete_inn_text(text) or is_short_digits:
            incomplete_msg = (
                "⚠️ <b>Kiritilgan СТИР (INN) raqami to'liq emas.</b>\n\n"
                "Korxona INN raqami <b>9 xonali</b> (yoki JSHSHIR 14 xonali) bo'lishi kerak.\n"
                "Iltimos, korxona INN raqamingizni to'liq tekshirib qayta yuboring (masalan: <code>302568138</code>)."
            )
            incomplete_msg = adapt_to_user_script(incomplete_msg, user_script)
            try:
                await message.reply(incomplete_msg, parse_mode="HTML")
            except Exception:
                await message.reply(incomplete_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, incomplete_msg)
            return True

        # 1. Matnda INN va Fiskal modul (LG..., YG..., UZ...) borligini aniqlash
        found_fm = extract_fiscal_module(text)
        found_inn = extract_clean_inn(text)
        if found_fm and found_inn and found_inn in found_fm:
            found_inn = None

        if found_inn:
            user_memory.set_last_id(chat_id, user_id, found_inn)
        if found_fm:
            user_memory.set_last_fm(chat_id, user_id, found_fm)

        # 1.5 Tekshirilgan korxonalar bo'yicha qaysi birida qarz borligi so'ralsa
        if any(w in lower_text for w in [
            "qaysi inn boyicha", "qaysi inn bo'yicha", "qaysi inn", "qaysi birida", "qaysi korxona",
            "кайси инн буйича", "кайси инн бўйича", "кайси инн", "кайси бирида"
        ]):
            inns = user_memory.get_checked_inns(chat_id, user_id)
            if inns:
                lines = ["📋 <b>Tekshirilgan korxonalar qarzdorlik holati:</b>\n"]
                for idx, (inn_k, info) in enumerate(inns.items(), 1):
                    d = info.get("debt", 0.0)
                    name = info.get("org_name") or "Noma'lum korxona"
                    if d > 0:
                        lines.append(f"{idx}️⃣ 🏢 <b>{name}</b> (СТИР: <code>{inn_k}</code>)\n🔴 <b>Qarzdorlik:</b> {d:,.0f} so'm".replace(",", " "))
                    else:
                        lines.append(f"{idx}️⃣ 🏢 <b>{name}</b> (СТИР: <code>{inn_k}</code>)\n🟢 <b>Qarzdorlik yo'q (0 so'm)</b>")
                lines.append("\n💡 <i>To'lov rekvizitlarini olish uchun «Oylik shot» deb yozing.</i>")
                summary_msg = adapt_to_user_script("\n\n".join(lines), user_script)
                try:
                    await message.reply(summary_msg, parse_mode="HTML")
                except Exception:
                    await message.reply(summary_msg)
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, summary_msg)
                return True

        # 1.9 Maxsus holat: Ikkala to'lovni bitta hisob raqamga to'lash mumkinmi deb so'ralsa
        single_account_query = any(w in lower_text for w in [
            "bitta hisob", "bitta shot", "bitta xisob", "bitta raqam", "birga to'la", "birga tola",
            "bitta qilib to'la", "bitta qilib tola", "qo'shib to'la", "qoshib tola", "bitta schet",
            "битта ҳисоб", "битта хисоб", "битта шот", "бирга тўла", "бирга тола", "битта счёт"
        ])
        if single_account_query and any(w in lower_text for w in ["oylik", "yillik", "fiskal", "soliq", "ikkala", "ikki", "ҳам", "ham", "иккала", "to'lasam", "tolasam", "o'tkazsam", "otkazsam"]):
            single_warn = (
                "❌ <b>Yo'q, mutlaqo bo'lmaydi!</b>\n\n"
                "Oylik va yillik to'lovlar <b>ikkita alohida, mustaqil tashkilotga</b> to'lanadi:\n\n"
                "1️⃣ <b>«Mars» oylik abonent to'lovi (100 000 so'm/oy):</b>\n"
                "Kassa apparatiga servis xizmati ko'rsatish uchun <b>«Mars Elektron Texnika» MChJ</b> hisob raqamiga to'lanadi.\n\n"
                "2️⃣ <b>Davlat Soliq (OFD) yillik litsenziyasi (440 000 so'm/yil):</b>\n"
                "Fiskal modulning 1 yillik ishlash muddatini uzaytirish uchun to'g'ridan-to'g'ri Davlat Soliq Qo'mitasi huzuridagi <b>«Yangi Texnologiyalar» DUK</b> hisob raqamiga to'lanadi.\n\n"
                "⚠️ <b>Agar ikkalasini bitta hisob raqamga to'lasangiz, Soliq tizimi litsenziyangizni uzaytirmaydi!</b> Har birini o'zining hisob raqamiga alohida to'lashingiz shart.\n\n"
                "👇 <i>Quyida har ikkala tashkilotning alohida to'lov rekvizitlari yuborildi:</i>"
            )
            single_warn = adapt_to_user_script(single_warn, user_script)
            try:
                await message.reply(single_warn, parse_mode="HTML")
            except Exception:
                await message.reply(single_warn)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, single_warn)

            try:
                await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=MARS_POST_ID)
                await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=YANGI_TEXNOLOGIYALAR_POST_ID)
            except Exception:
                pass
            user_memory.set_last_topic(chat_id, user_id, "payment_info_both")
            return True

        # 2. Ikkala to'lov / umumiy qarzdorlik so'ralsa yoki bitta xabarda ham yillik, ham oylik/INN bo'lsa
        is_both = is_both_check_intent(text) or (bool(found_fm) and bool(found_inn)) or (is_annual_check_intent(text) and (is_monthly_check_intent(text) or bool(found_inn)))
        is_general_debt = is_general_debt_check_intent(text)

        if is_both or (is_general_debt and not is_annual_check_intent(text) and not is_monthly_check_intent(text)):
            remembered_id = found_inn or user_memory.get_last_id(chat_id, user_id)
            remembered_fm = found_fm or user_memory.get_last_fm(chat_id, user_id)

            if is_both and remembered_id and remembered_fm:
                from handlers.debt import process_and_send_debt_result
                await process_and_send_debt_result(message, bot, remembered_id)
                ofd_reply = await ofd_bridge.query_fiscal_module(bot, remembered_fm)
                ofd_text = format_ofd_annual_status(remembered_fm, ofd_reply, user_script)
                try:
                    await message.reply(ofd_text, parse_mode="HTML")
                except Exception:
                    await message.reply(ofd_text)
                return True
            elif remembered_id:
                from handlers.debt import process_and_send_debt_result
                await process_and_send_debt_result(message, bot, remembered_id)
                if is_both and not remembered_fm:
                    fm_ask = (
                        "🏛 <b>Yillik Soliq (OFD) to'lovini tekshirish uchun:</b>\n\n"
                        "Kassa chekining eng pastki qismidagi <b>Fiskal modul seriya raqamini (LG..., YG...)</b> yuboring yoki chekni rasmga olib tashlang."
                    )
                    fm_ask = adapt_to_user_script(fm_ask, user_script)
                    try:
                        await message.answer(fm_ask, parse_mode="HTML")
                    except Exception:
                        await message.answer(fm_ask)
                    try:
                        await bot.copy_message(
                            chat_id=message.chat.id,
                            from_chat_id=SOURCE_CHANNEL_ID,
                            message_id=FISKAL_MODUL_SAMPLE_POST_ID
                        )
                    except Exception as e:
                        logger.warning(f"Fiskal modul namunasi postini yuborishda xatolik: {e}")
                    user_memory.set_last_topic(chat_id, user_id, "awaiting_fiscal_module")
                return True
            elif remembered_fm and not remembered_id:
                ofd_reply = await ofd_bridge.query_fiscal_module(bot, remembered_fm)
                ofd_text = format_ofd_annual_status(remembered_fm, ofd_reply, user_script)
                try:
                    await message.reply(ofd_text, parse_mode="HTML")
                except Exception:
                    await message.reply(ofd_text)
                inn_ask = (
                    "🏢 <b>«Mars» oylik abonent to'lovini ham tekshirish uchun:</b>\n\n"
                    "Korxonangizning 9 xonali <b>СТИР (INN) raqamini</b> yuboring."
                )
                inn_ask = adapt_to_user_script(inn_ask, user_script)
                try:
                    await message.answer(inn_ask, parse_mode="HTML")
                except Exception:
                    await message.answer(inn_ask)
                user_memory.set_last_topic(chat_id, user_id, "awaiting_inn_for_monthly_debt")
                return True
            else:
                both_ask = (
                    "🔍 <b>To'lovni tekshirish:</b>\n\n"
                    "🔹 <b>Oylik abonent to'lovi:</b> Korxona <b>СТИР (INN)</b> raqamini yuboring;\n"
                    "🔹 <b>Yillik Soliq (OFD) to'lovi:</b> Kassa chekidagi <b>Fiskal modul raqamini (LG..., YG...)</b> yuboring yoki chekni rasmga olib tashlang."
                )
                both_ask = adapt_to_user_script(both_ask, user_script)
                try:
                    await message.reply(both_ask, parse_mode="HTML")
                except Exception:
                    await message.reply(both_ask)
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, both_ask)
                return True

        # 2.1 Agar to'g'ridan-to'g'ri faqat Fiskal modul (LG..., YG..., UZ...) yuborilgan bo'lsa -> darhol OFD tekshiruvi!
        if found_fm and not is_annual_check_intent(text):
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
            return True

        # 2.2 Fiskal modul qayerdaligi / chekdan topish haqidagi savollar
        fm_where_phrases = [
            "fiskal modul qayerda", "fiskal modul qayerdan", "fiskal modul qayerda yozilgan",
            "fiskal modul qayerda boladi", "fiskal modul qayerda bo'ladi", "modul raqami qayerda",
            "fiskal modulni qanday topaman", "fiskal modul topish", "modul topish",
            "fiskal modul nima", "fiskal modul raqami nima", "fiskal modul haqida",
            "fiskal modulni bilish", "fiskal modul qayeri", "fiskal modul qayerida",
            "фискал модул қаерда", "фискал модул каерда", "фискал модул қаердан", "модул рақами қаерда",
            "фискал модул нима"
        ]
        if any(p in lower_text for p in fm_where_phrases):
            fm_guide = get_fiscal_module_request_prompt(user_script)
            try:
                await message.reply(fm_guide, parse_mode="HTML")
            except Exception:
                await message.reply(fm_guide)
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=FISKAL_MODUL_SAMPLE_POST_ID,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.warning(f"Fiskal modul namunasi postini yuborishda xatolik: {e}")
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, fm_guide)
            user_memory.set_last_topic(chat_id, user_id, "awaiting_fiscal_module")
            return True

        # 2.3 Hisob raqamlar postini kanaldan uzatish / to'lov intentlari ("oylikchi", "yillikchi", "to'layman", "shot tashla")
        payment_intent = classify_payment_intent(text)
        is_ann_pay = is_annual_pay_intent(text, last_topic) or payment_intent == "annual"
        is_mon_pay = is_monthly_pay_intent(text, last_topic) or payment_intent == "monthly"
        is_explicit_both = any(w in lower_text for w in ["ikkala", "har ikkala", "ikkisidan", "иккала", "ҳар иккала"])
        is_both_pay = (payment_intent == "both" and not is_ann_pay and not is_mon_pay) or is_explicit_both

        if (is_ann_pay or is_mon_pay or is_both_pay) and not found_fm and not found_inn:
            if is_both_pay:
                # Kanaldan ikkala hisob raqam postini to'g'ridan-to'g'ri uzatish
                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=MARS_POST_ID,
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Post 85 nusxalashda xatolik: {e}")
                    await message.reply(adapt_to_user_script(get_monthly_payment_card(), user_script), parse_mode="HTML")

                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=YANGI_TEXNOLOGIYALAR_POST_ID
                    )
                except Exception as e:
                    logger.warning(f"Post 34 nusxalashda xatolik: {e}")
                    await message.answer(adapt_to_user_script(get_annual_payment_card(), user_script), parse_mode="HTML")

                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, "[Ikkala shot posti (85 va 34) kanaldan uzatildi]")
                user_memory.set_last_topic(chat_id, user_id, "payment_info_both")
                return True

            elif is_mon_pay:
                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=MARS_POST_ID,
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Oylik shot postini (85) nusxalashda xatolik: {e}")
                    monthly_card = adapt_to_user_script(get_monthly_payment_card(), user_script)
                    await message.reply(monthly_card, parse_mode="HTML")

                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=MARS_VIDEO_ID
                    )
                except Exception as e:
                    logger.warning(f"Video 148 nusxalashda xatolik: {e}")

                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, "[Oylik shot posti (85) kanaldan uzatildi]")
                user_memory.set_last_topic(chat_id, user_id, "monthly_payment_card_sent")
                return True

            elif is_ann_pay:
                ann_st = user_memory.get_annual_status(chat_id, user_id)
                is_explicit_acc_ask = any(w in lower_text for w in [
                    "shot", "rekvizit", "hisob", "xisob", "kartasi", "karta", "to'lash uchun", "tolash uchun",
                    "to'lashga", "tolashga", "шот", "реквизит", "ҳисоб", "счёт", "счет"
                ])
                # Agar mijoz shunchaki "yillikchi" yoki "yillik" deb so'ragan bo'lsa va xotirada yillikdan qarz yo'qligi ma'lum bo'lsa:
                if ann_st and not ann_st.get("has_debt") and not is_explicit_acc_ask:
                    clear_msg = "🟢 <b>Yillik Soliq (OFD) to'lovidan qarzdorlik yo'q!</b> (Litsenziya faol)"
                    clear_msg = adapt_to_user_script(clear_msg, user_script)
                    try:
                        await message.reply(clear_msg, parse_mode="HTML")
                    except Exception:
                        await message.reply(clear_msg)
                    user_memory.add_user_message(chat_id, user_id, text)
                    user_memory.add_assistant_message(chat_id, user_id, clear_msg)
                    user_memory.set_last_topic(chat_id, user_id, "annual_debt_clear")
                    return True

                if ann_st and ann_st.get("has_debt") and not is_explicit_acc_ask:
                    target_fm = user_memory.get_last_fm(chat_id, user_id)
                    fm_line = f"🏛 <b>Fiskal modul:</b> <code>{target_fm}</code>\n" if target_fm else ""
                    debt_msg = (
                        f"🔴 <b>Yillik Soliq (OFD) to'lovidan QARZDORLIK MAVJUD!</b>\n\n"
                        f"{fm_line}"
                        f"💰 <b>Summa:</b> <b>440 000 so'm</b> (1 yilga)\n\n"
                        f"💳 <i>To'lov rekvizitlari quyida kanaldan uzatildi:</i>"
                    )
                    debt_msg = adapt_to_user_script(debt_msg, user_script)
                    try:
                        await message.reply(debt_msg, parse_mode="HTML")
                    except Exception:
                        await message.reply(debt_msg)
                    user_memory.add_assistant_message(chat_id, user_id, debt_msg)

                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=YANGI_TEXNOLOGIYALAR_POST_ID,
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Yillik shot postini (34) nusxalashda xatolik: {e}")
                    annual_card = adapt_to_user_script(get_annual_payment_card(), user_script)
                    await message.reply(annual_card, parse_mode="HTML")

                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=YANGI_TEXNOLOGIYALAR_VIDEO_ID
                    )
                except Exception as e:
                    logger.warning(f"Video 145 nusxalashda xatolik: {e}")

                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, "[Yillik shot posti (34) kanaldan uzatildi]")
                user_memory.set_last_topic(chat_id, user_id, "annual_payment_card_sent")
                return True

        # 3. Yillik qarz tekshiruvi ("yillik qarzim bormi", "ofd tekshir", "yillikdanchi", "yillikchi")
        if is_annual_check_intent(text):
            ann_st = user_memory.get_annual_status(chat_id, user_id)
            target_fm = found_fm or user_memory.get_last_fm(chat_id, user_id)

            # Agar xotirada yillikdan qarz yo'qligi allaqachon ma'lum bo'lsa va yangi FM kiritilmagan bo'lsa:
            if ann_st and not ann_st.get("has_debt") and not found_fm:
                clear_msg = "🟢 <b>Yillik Soliq (OFD) to'lovidan qarzdorlik yo'q!</b> (Litsenziya faol)"
                clear_msg = adapt_to_user_script(clear_msg, user_script)
                try:
                    await message.reply(clear_msg, parse_mode="HTML")
                except Exception:
                    await message.reply(clear_msg)
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, clear_msg)
                user_memory.set_last_topic(chat_id, user_id, "annual_debt_clear")
                return True

            if target_fm:
                ofd_reply = await ofd_bridge.query_fiscal_module(bot, target_fm)
                has_ann_debt = False
                if ofd_reply:
                    lower_ofd = ofd_reply.lower()
                    has_no_debt = any(w in lower_ofd for w in ["qarzdorlik mavjud emas", "qarzdorlik yo'q", "qarzdorlik yo‘q", "qarzi yo'q", "qarzi yo‘q", "faol"])
                    if not has_no_debt and any(w in lower_ofd for w in ["qarzdorlik mavjud", "fmo dan qarzdorlik", "qarzdorlik", "muddati o'tgan"]):
                        has_ann_debt = True

                user_memory.set_annual_status(chat_id, user_id, has_debt=has_ann_debt, details="Qarzdorlik" if has_ann_debt else "Faol")

                if has_ann_debt:
                    ofd_text = (
                        f"🔴 <b>Yillik Soliq (OFD) to'lovidan QARZDORLIK MAVJUD!</b>\n\n"
                        f"🏛 <b>Fiskal modul:</b> <code>{target_fm}</code>\n"
                        f"💰 <b>Summa:</b> <b>440 000 so'm</b> (1 yilga)\n\n"
                        f"💳 <i>To'lov rekvizitlari quyida kanaldan uzatildi:</i>"
                    )
                    ofd_text = adapt_to_user_script(ofd_text, user_script)
                    try:
                        await message.reply(ofd_text, parse_mode="HTML")
                    except Exception:
                        await message.reply(ofd_text)
                    user_memory.add_user_message(chat_id, user_id, text)
                    user_memory.add_assistant_message(chat_id, user_id, ofd_text)
                    user_memory.set_last_topic(chat_id, user_id, "annual_debt_exists")

                    try:
                        await bot.copy_message(
                            chat_id=message.chat.id,
                            from_chat_id=SOURCE_CHANNEL_ID,
                            message_id=YANGI_TEXNOLOGIYALAR_POST_ID,
                            reply_to_message_id=message.message_id
                        )
                        await bot.copy_message(
                            chat_id=message.chat.id,
                            from_chat_id=SOURCE_CHANNEL_ID,
                            message_id=YANGI_TEXNOLOGIYALAR_VIDEO_ID
                        )
                    except Exception as e:
                        logger.warning(f"Post 34 nusxalashda xatolik: {e}")
                    return True
                else:
                    # QARZ YO'Q! Hisob raqam uzatilmaydi!
                    ofd_text = (
                        f"🟢 <b>Yillik Soliq (OFD) to'lovidan QARZDORLIK YO'Q!</b>\n\n"
                        f"🏛 <b>Fiskal modul:</b> <code>{target_fm}</code>\n"
                        f"✅ <b>Holati:</b> To'langan va faol (Litsenziya muddati joyida)."
                    )
                    ofd_text = adapt_to_user_script(ofd_text, user_script)
                    try:
                        await message.reply(ofd_text, parse_mode="HTML")
                    except Exception:
                        await message.reply(ofd_text)
                    user_memory.add_user_message(chat_id, user_id, text)
                    user_memory.add_assistant_message(chat_id, user_id, ofd_text)
                    user_memory.set_last_topic(chat_id, user_id, "annual_debt_clear")
                    return True
            else:
                # OFD tizimi faqat Fiskal modul (LG/YG/UZ) bilan ishlaydi, INN bilan emas
                fm_prompt = get_fiscal_module_request_prompt(user_script)
                try:
                    await message.reply(fm_prompt, parse_mode="HTML")
                except Exception:
                    await message.reply(fm_prompt)

                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=FISKAL_MODUL_SAMPLE_POST_ID,
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Fiskal modul namunasi postini yuborishda xatolik: {e}")

                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, fm_prompt)
                user_memory.set_last_topic(chat_id, user_id, "awaiting_fiscal_module")
                return True

        # 4. Oylik qarz tekshiruvi ("oylik qarzim bormi", "oylikdanchi", "marsdan qarz")
        if is_monthly_check_intent(text):
            remembered_id = extract_clean_inn(text) or user_memory.get_last_id(chat_id, user_id)
            if remembered_id:
                from handlers.debt import process_and_send_debt_result
                await process_and_send_debt_result(message, bot, remembered_id)
                return True
            else:
                ask_inn = (
                    "🏢 <b>«Mars» oylik abonent to'lovini tekshirish:</b>\n\n"
                    "Korxonangizning 9 xonali <b>СТИР (INN)</b> yoki 14 xonali JSHSHIR raqamini yuboring (masalan: <code>302568138</code>)."
                )
                ask_inn = adapt_to_user_script(ask_inn, user_script)
                try:
                    await message.reply(ask_inn, parse_mode="HTML")
                except Exception:
                    await message.reply(ask_inn)
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, ask_inn)
                user_memory.set_last_topic(chat_id, user_id, "awaiting_inn_for_monthly_debt")
                return True

        # 7. Matnda INN aniqlanganda (texnik savol bo'lmasa -> qarz natijasini chiqarish)
        found_inn = extract_clean_inn(text)
        if found_inn:
            user_memory.set_last_id(chat_id, user_id, found_inn)
            if not any(tw in lower_text for tw in TECH_QUESTION_WORDS):
                from handlers.debt import process_and_send_debt_result
                await process_and_send_debt_result(message, bot, found_inn)
                return True


        # 9. Click orqali to'lov tartibi so'ralganda
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
                return True
            except Exception as e:
                logger.error(f"To'lov videosi yuborishda xatolik: {e}")

        # 10. Pul yechilgan / to'langan lekin apparat yoqilmagan bo'lsa
        paid_not_active_words = [
            "yechildi lekin", "yechib oldi lekin", "yechildi ammo", "pul ketdi lekin",
            "toladim lekin", "to'ladim lekin", "to'lov qildim lekin", "tolov qildim lekin",
            "to'langan lekin", "tolangan lekin", "yechildi hali", "pul yechildi", "ечилди лекин", "тўладим лекин"
        ]
        if any(w in lower_text for w in paid_not_active_words) and any(w in lower_text for w in ["yonmadi", "yoqmadi", "ishlamadi", "ochilmadi", "blok", "xali", "hali", "apparat", "kassa", "аппарат"]):
            resp = (
                "💳 <b>To'lovingiz qabul qilinmoqda:</b>\n\n"
                "Bank yoki to'lov tizimlarida (Click, Payme va h.k.) mablag' hisob raqamga o'tirishi uchun <b>15 daqiqadan 2 soatgacha</b> vaqt talab etilishi mumkin.\n\n"
                "📌 <b>Tezlashtirish uchun:</b>\n"
                "1️⃣ To'lov kvitansiyasini (chekini) rasm yoki PDF shaklida shu yerga yuboring;\n"
                "2️⃣ Kassa apparatini to'liq o'chirib qayta yoqing (Reboot)."
            )
            resp = adapt_to_user_script(resp, user_script)
            try:
                await message.reply(resp, parse_mode="HTML")
            except Exception:
                await message.reply(resp)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, resp)
            user_memory.set_last_topic(chat_id, user_id, "paid_pending_activation")
            return True

        return False

billing_intent_handler = BillingIntentHandler()
