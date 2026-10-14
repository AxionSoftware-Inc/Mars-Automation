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
    MARS_POST_ID,
    MARS_VIDEO_ID,
    YANGI_TEXNOLOGIYALAR_POST_ID,
    YANGI_TEXNOLOGIYALAR_VIDEO_ID
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

        # 0.9 Chala yoki noto'g'ri kiritilgan INN (masalan: "INN 12345")
        if is_incomplete_inn_text(text):
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
        if found_inn:
            user_memory.set_last_id(chat_id, user_id, found_inn)
        if found_fm:
            user_memory.set_last_fm(chat_id, user_id, found_fm)

        # 2. Ikkala to'lov / umumiy qarzdorlik so'ralsa yoki bitta xabarda ham yillik, ham oylik/INN bo'lsa
        is_both = is_both_check_intent(text) or (bool(found_fm) and bool(found_inn)) or (is_annual_check_intent(text) and (is_monthly_check_intent(text) or bool(found_inn)))
        if is_both:
            remembered_id = found_inn or user_memory.get_last_id(chat_id, user_id)
            remembered_fm = found_fm or user_memory.get_last_fm(chat_id, user_id)

            if remembered_id and remembered_fm:
                from handlers.debt import process_and_send_debt_result
                await process_and_send_debt_result(message, bot, remembered_id)
                ofd_reply = await ofd_bridge.query_fiscal_module(bot, remembered_fm)
                ofd_text = format_ofd_annual_status(remembered_fm, ofd_reply, user_script)
                try:
                    await message.reply(ofd_text, parse_mode="HTML")
                except Exception:
                    await message.reply(ofd_text)
                return True
            elif remembered_id and not remembered_fm:
                from handlers.debt import process_and_send_debt_result
                await process_and_send_debt_result(message, bot, remembered_id)
                fm_ask = (
                    "🏛 <b>Yillik Soliq (OFD) qarzdorligini ham tekshirish uchun:</b>\n\n"
                    "Kassa chekining eng pastki qismidagi <b>Fiskal modul seriya raqamini (LG..., YG..., UZ...)</b> yuboring."
                )
                fm_ask = adapt_to_user_script(fm_ask, user_script)
                try:
                    await message.answer(fm_ask, parse_mode="HTML")
                except Exception:
                    await message.answer(fm_ask)
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
                    "🔍 <b>Smart POS kassa apparatlarida 2 xil to'lov tekshiriladi:</b>\n\n"
                    "1️⃣ <b>«Mars» oylik abonent to'lovi (100 000 so'm/oy):</b>\n"
                    "Tekshirish uchun korxonangiz <b>СТИР (INN)</b> raqamini yuboring;\n\n"
                    "2️⃣ <b>Davlat Soliq (OFD) yillik to'lovi (440 000 so'm/yil):</b>\n"
                    "Tekshirish uchun kassa chekining eng pastki qismidagi <b>Fiskal modul seriya raqamini (LG..., YG...)</b> yuboring.\n\n"
                    "<i>Qaysi birini tekshirmoqchi bo'lsangiz, raqamini yuboring.</i>"
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

        # 3. Yillik qarz tekshiruvi ("yillik qarzim bormi", "ofd tekshir", "yillikdanchi")
        if is_annual_check_intent(text):
            target_fm = found_fm or user_memory.get_last_fm(chat_id, user_id)
            if target_fm:
                ofd_reply = await ofd_bridge.query_fiscal_module(bot, target_fm)
                ofd_text = format_ofd_annual_status(target_fm, ofd_reply, user_script)
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
            else:
                # OFD tizimi faqat Fiskal modul (LG/YG/UZ) bilan ishlaydi, INN bilan emas
                fm_prompt = (
                    "🏛 <b>Davlat Soliq (OFD) yillik to'lovini tekshirish:</b>\n\n"
                    "OFD tizimi faqat <b>Fiskal modul seriya raqami</b> orqali tekshiriladi (STIR/INN bilan tekshirib bo'lmaydi).\n\n"
                    "Iltimos, kassa chekining eng pastki qismidagi (yoki apparat orqasidagi) "
                    "<b>Fiskal modul raqamini (masalan: <code>LG...</code>, <code>YG...</code>, <code>UZ...</code>)</b> yuboring."
                )
                fm_prompt = adapt_to_user_script(fm_prompt, user_script)
                try:
                    await message.reply(fm_prompt, parse_mode="HTML")
                except Exception:
                    await message.reply(fm_prompt)
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
                    "🏢 <b>«Mars» oylik abonent to'lovidan qarzdorlikni tekshirish uchun:</b>\n\n"
                    "Korxonangizning 9 xonali <b>СТИР (INN) raqamini</b> yuboring (masalan: <code>302568138</code>).\n\n"
                    "<i>Baza orqali oylik abonent to'lovi holatini tekshirib beramiz.</i>"
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

        # 5. Yillik to'lov kartasi / to'lash intenti ("yillik to'layman", "yillik shot tashla")
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
            return True

        # 6. Oylik to'lov kartasi / to'lash intenti ("oylik to'layman", "oylik shot tashla")
        if is_monthly_pay_intent(text, last_topic):
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=MARS_POST_ID,
                    reply_to_message_id=message.message_id
                )
            except Exception:
                monthly_card = adapt_to_user_script(get_monthly_payment_card(), user_script)
                await message.reply(monthly_card, parse_mode="HTML")

            note = get_monthly_post_note(user_script)
            try:
                await message.answer(note, parse_mode="HTML")
            except Exception:
                await message.answer(note)

            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=MARS_VIDEO_ID
                )
            except Exception as e:
                logger.warning(f"Video 148 nusxalashda xatolik: {e}")

            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, note)
            user_memory.set_last_topic(chat_id, user_id, "monthly_payment_card_sent")
            return True

        # 7. Matnda INN aniqlanganda (texnik savol bo'lmasa -> qarz natijasini chiqarish)
        found_inn = extract_clean_inn(text)
        if found_inn:
            user_memory.set_last_id(chat_id, user_id, found_inn)
            if not any(tw in lower_text for tw in TECH_QUESTION_WORDS):
                from handlers.debt import process_and_send_debt_result
                await process_and_send_debt_result(message, bot, found_inn)
                return True

        # 8. Umumiy to'lov rekvizitlari va hisob raqamlar so'ralganda
        payment_intent = classify_payment_intent(text)
        if payment_intent and not found_fm and not found_inn:
            if payment_intent == "monthly":
                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=MARS_POST_ID,
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Oylik shot postini (85) nusxalashda xatolik: {e}")
                    reply_card = adapt_to_user_script(get_monthly_payment_card(), user_script)
                    await message.reply(reply_card, parse_mode="HTML")

                note = get_monthly_post_note(user_script)
                try:
                    await message.answer(note, parse_mode="HTML")
                except Exception:
                    await message.answer(note)

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
                return True

            elif payment_intent == "annual":
                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=YANGI_TEXNOLOGIYALAR_POST_ID,
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Yillik shot postini (34) nusxalashda xatolik: {e}")
                    reply_card = adapt_to_user_script(get_annual_payment_card(), user_script)
                    await message.reply(reply_card, parse_mode="HTML")

                note = get_annual_post_note(user_script)
                try:
                    await message.answer(note, parse_mode="HTML")
                except Exception:
                    await message.answer(note)

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
                return True

            else:  # both / general
                intro = get_both_posts_intro(user_script)
                try:
                    await message.reply(intro, parse_mode="HTML")
                except Exception:
                    await message.reply(intro)

                try:
                    await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=MARS_POST_ID)
                except Exception as e:
                    logger.warning(f"Post 85 nusxalashda xatolik: {e}")

                try:
                    await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=YANGI_TEXNOLOGIYALAR_POST_ID)
                except Exception as e:
                    logger.warning(f"Post 34 nusxalashda xatolik: {e}")

                try:
                    await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=MARS_VIDEO_ID)
                except Exception as e:
                    logger.warning(f"Video 148 nusxalashda xatolik: {e}")

                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, intro)
                user_memory.set_last_topic(chat_id, user_id, "payment_info_both")
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
