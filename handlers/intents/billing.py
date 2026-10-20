import logging
from typing import Optional
from aiogram import types, Bot

from user_memory import user_memory
from excel_manager import excel_manager
from translit_manager import adapt_to_user_script
from core.models import (
    extract_clean_inn,
    extract_fiscal_module,
    is_incomplete_inn_text,
    extract_bank_card_number,
    extract_bank_account_number,
    is_invalid_digit_length
)
from ofd_bridge import ofd_bridge
from payment_accounts import (
    classify_payment_intent,
    is_both_check_intent,
    is_general_debt_check_intent,
    is_annual_check_intent,
    is_monthly_check_intent,
    is_annual_pay_intent,
    is_monthly_pay_intent,
    parse_ofd_reply_status,
    format_ofd_annual_status,
    get_monthly_payment_card,
    get_annual_payment_card,
    get_monthly_post_note,
    get_annual_post_note,
    get_both_posts_intro,
    get_fiscal_module_request_prompt,
    MARS_POST_ID,
    MARS_VIDEO_ID,
    YANGI_TEXNOLOGIYALAR_INN,
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

        # 0.7 16 xonali bank plastik karta raqami (masalan: 8600..., 9860...)
        card_num = extract_bank_card_number(text)
        if card_num:
            card_msg = (
                f"💳 <b>Kiritilgan karta raqami:</b> <code>{card_num}</code>\n\n"
                "⚠️ <b>DIQQAT: To'lovlar kartadan-kartaga (P2P) qabul qilinmaydi!</b>\n\n"
                "Onlayn-NKM apparatlari uchun to'lovlar faqat rasmiy tashkilotlarning <b>20 xonali bank hisob raqamlariga (X/R)</b> amalga oshiriladi.\n\n"
                "🔹 <b>«Mars» oylik to'lovi:</b> Click / Payme ilovalarida «To'lovlar» bo'limida <b>«Mars Elektron Texnika»</b> xizmatini tanlab, INN kiritib to'lanadi;\n"
                "🔹 <b>Davlat Soliq (OFD) yillik to'lovi:</b> Click / Payme orqali Soliq to'lovlari («Yangi Texnologiyalar») bo'limidan 440 000 so'm to'lanadi.\n\n"
                "<i>Rasmiy to'lov rekvizitlarini olish uchun «Oylik shot» yoki «Yillik shot» deb yozing.</i>"
            )
            card_msg = adapt_to_user_script(card_msg, user_script)
            try:
                await message.reply(card_msg, parse_mode="HTML")
            except Exception:
                await message.reply(card_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, card_msg)
            return True

        # 0.8 20 xonali bank hisob raqami (20208..., 20210... va h.k.)
        acc_num = extract_bank_account_number(text)
        if acc_num:
            if "20208" in acc_num:
                acc_msg = (
                    f"🏢 <b>«Mars» oylik abonent to'lovi hisob raqami:</b> <code>{acc_num}</code>\n\n"
                    "Ushbu hisob raqam onlayn-NKM apparatlariga servis va dasturiy xizmat ko'rsatish («Mars Elektron Texnika») oylik abonent to'lovi uchun mo'ljallangan.\n"
                    "Rasmiy rekvizitlar va to'lov videosi quyida keltirilgan:"
                )
                acc_msg = adapt_to_user_script(acc_msg, user_script)
                try:
                    await message.reply(acc_msg, parse_mode="HTML")
                    await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=MARS_POST_ID)
                    await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=MARS_VIDEO_ID)
                except Exception as e:
                    logger.warning(f"Mars post 85 uzatishda xatolik: {e}")
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, acc_msg)
                return True
            elif "20210" in acc_num:
                acc_msg = (
                    f"🏛 <b>Davlat Soliq («Yangi Texnologiyalar» DUK) hisob raqami:</b> <code>{acc_num}</code>\n\n"
                    "Ushbu hisob raqam Davlat Soliq Qo'mitasi huzuridagi «Yangi Texnologiyalar» Ilmiy-axborot markazining "
                    "Fiskal modul yillik litsenziyasi (440 000 so'm) uchun mo'ljallangan.\n"
                    "Rasmiy to'lov posti va videosi quyida keltirilgan:"
                )
                acc_msg = adapt_to_user_script(acc_msg, user_script)
                try:
                    await message.reply(acc_msg, parse_mode="HTML")
                    await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=YANGI_TEXNOLOGIYALAR_POST_ID)
                    await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=YANGI_TEXNOLOGIYALAR_VIDEO_ID)
                except Exception as e:
                    logger.warning(f"Yangi Texnologiyalar post 34 uzatishda xatolik: {e}")
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, acc_msg)
                return True
            else:
                acc_msg = (
                    f"🔢 <b>Kiritilgan hisob raqam:</b> <code>{acc_num}</code>\n\n"
                    "Onlayn kassa tizimi uchun 2 xil rasmiy hisob raqam mavjud:\n"
                    "1️⃣ <b>«Mars» oylik to'lovi</b> — servis va dasturiy ta'minot uchun;\n"
                    "2️⃣ <b>«Yangi Texnologiyalar» yillik to'lovi</b> — Soliq (OFD) litsenziyasi uchun (440 000 so'm).\n\n"
                    "Qaysi biri kerak bo'lsa, «Oylik shot» yoki «Yillik shot» deb yozing."
                )
                acc_msg = adapt_to_user_script(acc_msg, user_script)
                try:
                    await message.reply(acc_msg, parse_mode="HTML")
                except Exception:
                    await message.reply(acc_msg)
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, acc_msg)
                return True

        # 0.85 10..13 xonali noto'g'ri uzunlikdagi son kiritilganda
        invalid_len = is_invalid_digit_length(text)
        if invalid_len:
            inv_msg = (
                f"⚠️ <b>Kiritilgan raqam {invalid_len} xonali bo'lib, standart formatlarga to'g'ri kelmaydi.</b>\n\n"
                "Iltimos, tekshiring:\n"
                "🔹 <b>СТИР (INN):</b> aniq <b>9 xonali</b> son (masalan: <code>302568138</code>);\n"
                "🔹 <b>JSHSHIR:</b> aniq <b>14 xonali</b> son (jismoniy shaxs / YaTT uchun);\n"
                "🔹 <b>Telefon raqam:</b> 9 xonali (masalan: <code>901234567</code>);\n"
                "🔹 <b>Fiskal modul:</b> 2 ta harf va raqamlar (masalan: <code>LG420210630789</code>).\n\n"
                "Iltimos, raqamni to'g'rilab qayta yuboring."
            )
            inv_msg = adapt_to_user_script(inv_msg, user_script)
            try:
                await message.reply(inv_msg, parse_mode="HTML")
            except Exception:
                await message.reply(inv_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, inv_msg)
            return True

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

        # 0.95 Bir nechta apparat / kassa bo'yicha so'rov ("2 ta apparat", "ikkita kassa", "3 ta apparat bor")
        multi_device_keywords = [
            "2 ta apparat", "2 ta kassa", "ikkita apparat", "ikkita kassa", "2 ta apparatim",
            "3 ta apparat", "3 ta kassa", "uchta apparat", "uchta kassa", "bir nechta apparat",
            "apparatlarim", "kassalarim", "2ta apparat", "2ta kassa", "3ta apparat", "3ta kassa",
            "2 та аппарат", "2 та касса", "иккита аппарат", "иккита касса"
        ]
        if any(w in lower_text for w in multi_device_keywords) and not extract_clean_inn(text):
            multi_dev_msg = (
                "📟 <b>Bir nechta kassa apparatlari bo'yicha to'lov tartibi:</b>\n\n"
                "1️⃣ <b>«Mars» oylik abonent to'lovi:</b> Har bir kassa apparati uchun alohida oylik to'lov hisoblanadi. "
                "Bitta INN ostidagi barcha apparatlarning umumiy qarzini bilish uchun korxona INN raqamingizni yuboring.\n\n"
                "2️⃣ <b>Davlat Soliq (OFD) yillik to'lovi:</b> Har bir apparatning ichida alohida <b>Fiskal modul (LG..., YG...)</b> bo'ladi va "
                "har bir apparat uchun Soliqqa <b>440 000 so'm</b>dan alohida to'lanadi. Qaysi fiskal modul to'lansa, aynan o'sha apparat faollashadi.\n\n"
                "👉 Qaysi apparat holatini bilmoqchi bo'lsangiz, o'sha kassa chekining pastki qismidagi Fiskal modul raqamini yuboring."
            )
            multi_dev_msg = adapt_to_user_script(multi_dev_msg, user_script)
            try:
                await message.reply(multi_dev_msg, parse_mode="HTML")
            except Exception:
                await message.reply(multi_dev_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, multi_dev_msg)
            return True

        # 0.98 "To'laganman / Ertalab to'lagandim / To'lab bo'ldik"
        payment_done_words = [
            "to'laganman", "tolaganman", "to'lagandim", "tolagandim", "to'ladim", "toladim",
            "to'lab bo'ldik", "tolab boldik", "to'lab qo'ydik", "tolab qoydik", "to'lab bo'lganmiz",
            "ertalab to'lagan", "ertalab tolagan", "kecha to'lagan", "kecha tolagan",
            "to'lov qilganman", "tolov qilganman", "to'lov qildik", "tolov qildik", "to'lov qilindi", "tolov qilindi",
            "pul o'tkazdim", "pul otkazdim", "pul tashladim", "pul tashlaganmiz",
            "тўлаганман", "тўладим", "тўлаб бўлдик", "тўлов қилинди", "тўлов қилдик"
        ]
        is_complaint = any(w in lower_text for w in ["yonmadi", "yoqmadi", "ishlamadi", "ochilmadi", "blok", "xatolik", "qachon"])
        if any(w in lower_text for w in payment_done_words) and not is_complaint and not extract_clean_inn(text) and not extract_fiscal_module(text):
            paid_prompt = (
                "✅ <b>To'lov qilganingiz uchun tashakkur!</b>\n\n"
                "To'lovingizni tizimda zudlik bilan tasdiqlashimiz va apparatingizni faollashtirishimiz uchun "
                "<b>to'lov kvitansiyasini (Click, Payme skrinshoti yoki bank chekining rasmi/PDF)</b> shu yerga yuboring.\n\n"
                "Operatorlarimiz chekni ko'rib, apparatingizni tezkorlik bilan ochib berishadi."
            )
            paid_prompt = adapt_to_user_script(paid_prompt, user_script)
            try:
                await message.reply(paid_prompt, parse_mode="HTML")
            except Exception:
                await message.reply(paid_prompt)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, paid_prompt)
            user_memory.set_last_topic(chat_id, user_id, "awaiting_receipt_after_payment_claim")
            return True

        # 1. Matnda INN va Fiskal modul (LG..., YG..., UZ...) borligini aniqlash
        found_fm = extract_fiscal_module(text)
        found_inn = extract_clean_inn(text)
        if found_fm and found_inn and found_inn in found_fm:
            found_inn = None

        # 1.05 Agar mijoz «Yangi Texnologiyalar» DUK STIR raqamini (201589463) o'zining STIR raqami sifatida yuborgan bo'lsa
        if found_inn == YANGI_TEXNOLOGIYALAR_INN:
            yt_inn_msg = (
                f"⚠️ <b>Diqqat! Kiritilgan СТИР (<code>{YANGI_TEXNOLOGIYALAR_INN}</code>) — Davlat Soliq Qo'mitasi huzuridagi «Yangi Texnologiyalar» DUK ning STIR raqami hisoblanadi!</b>\n\n"
                "Bu sizning korxonangiz STIR raqami emas (bu raqam to'lov rekvizitlarida qabul qiluvchi tashkilot STIRi sifatida yozilgan).\n\n"
                "👉 <b>O'zingizning korxonangiz qarzini tekshirish uchun:</b> Korxonangiz guvohnomasidagi yoki kassa cheki yuqorisidagi <b>9 xonali STIR (INN)</b> raqamingizni yuboring.\n"
                "👉 <b>Yillik Soliq (OFD) litsenziyasini tekshirish uchun:</b> Kassa chekining eng pastki qismidagi <b>Fiskal modul (LG..., YG...)</b> raqamini yuboring."
            )
            yt_inn_msg = adapt_to_user_script(yt_inn_msg, user_script)
            try:
                await message.reply(yt_inn_msg, parse_mode="HTML")
            except Exception:
                await message.reply(yt_inn_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, yt_inn_msg)
            return True

        # Faqat bazada mavjud (yoki hisobdan chiqarilgan) INN ni xotiraga yozamiz (noto'g'ri terilgan 9 xonali raqam eski to'g'ri INN ni buzmasligi uchun)
        if found_inn and (excel_manager.search(found_inn) or excel_manager.is_decommissioned(found_inn)):
            user_memory.set_last_id(chat_id, user_id, found_inn)

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
            "bitta hisob", "bitta shot", "bitta xisob", "bitta raqam", "bitta karta", "bitta plastik",
            "birga to'la", "birga tola", "birga tashla", "birga tashvor",
            "bitta qilib to'la", "bitta qilib tola", "bitta qilib tashla", "bitta qilib tashvor", "bitta qilib",
            "qo'shib to'la", "qoshib tola", "qoshib tashla", "qo'shib tashla", "bitta schet",
            "битта ҳисоб", "битта хисоб", "битта шот", "битта карта", "бирга тўла", "бирга тола", "битта счёт"
        ])
        if single_account_query and any(w in lower_text for w in ["oylik", "yillik", "fiskal", "soliq", "ikkala", "ikki", "ҳам", "ham", "иккала", "to'lasam", "tolasam", "o'tkazsam", "otkazsam", "tashlasam", "tashvorsam", "tashlasak", "yuborsam"]):
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

        # 1.5 To'lov muddatlari haqidagi so'rovlar ("qachongacha to'lash kerak", "oylik to'lov muddati")
        due_date_queries = [
            "qachongacha to'lash", "qachongacha tolash", "qachongacha to'lash kerak",
            "qachongacha tolash kerak", "qachongacha to'lanadi", "qachongacha tolanadi",
            "to'lov muddati", "tolov muddati", "to'lov qachongacha", "tolov qachongacha",
            "oylik to'lov qachongacha", "oylik tolov qachongacha", "oylik qachongacha"
        ]
        if any(q in lower_text for q in due_date_queries):
            due_msg = (
                "📅 <b>«Mars» oylik abonent to'lovi muddati:</b>\n\n"
                "🔹 Har oyning <b>6-sanasigacha</b> to'lanishi shart (100 000 so'm/oy).\n"
                "⚠️ Agar 6-sanasigacha to'lanmasa, apparat tizim tomonidan avtomatik ravishda to'xtatiladi (bloklanadi).\n\n"
                "🏛 <i>Davlat Soliq (OFD) yillik to'lovi esa har yili 1 marta (440 000 so'm) to'lanadi.</i>"
            )
            due_msg = adapt_to_user_script(due_msg, user_script)
            try:
                await message.reply(due_msg, parse_mode="HTML")
            except Exception:
                await message.reply(due_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, due_msg)
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
        if found_fm and not found_inn and not is_annual_check_intent(text):
            ofd_reply = await ofd_bridge.query_fiscal_module(bot, found_fm)
            ofd_status = parse_ofd_reply_status(ofd_reply)
            if ofd_status == "unavailable":
                user_memory.set_last_fm(chat_id, user_id, found_fm)
                user_memory.set_annual_status(chat_id, user_id, has_debt=False, details="unavailable", unavailable=True)
                timeout_msg = (
                    f"⏳ <b>Davlat Soliq (OFD) tizimi vaqtincha javob bermayapti.</b>\n\n"
                    f"🏛 <b>Fiskal modul:</b> <code>{found_fm}</code>\n\n"
                    f"Soliq qo'mitasi (@ofd943_bot) tizimi bilan aloqa vaqtincha uzildi yoki serverda profilaktika ketmoqda.\n"
                    f"Iltimos, birozdan so'ng qayta urinib ko'ring."
                )
                timeout_msg = adapt_to_user_script(timeout_msg, user_script)
                try:
                    await message.reply(timeout_msg, parse_mode="HTML")
                except Exception:
                    await message.reply(timeout_msg)
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, timeout_msg)
                return True

            if ofd_status == "not_found":
                user_memory.clear_last_fm(chat_id, user_id)
                not_found_msg = format_ofd_annual_status(found_fm, ofd_reply, user_script)
                try:
                    await message.reply(not_found_msg, parse_mode="HTML")
                except Exception:
                    await message.reply(not_found_msg)
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, not_found_msg)
                return True

            user_memory.set_last_fm(chat_id, user_id, found_fm)
            has_ann_debt = (ofd_status == "debt")
            user_memory.set_annual_status(chat_id, user_id, has_debt=has_ann_debt, details=ofd_reply or "")

            is_issue = user_memory.is_issue_mode(chat_id, user_id)
            remembered_id = user_memory.get_last_id(chat_id, user_id)
            org_name = user_memory.get_org_name(chat_id, user_id) or ""

            if has_ann_debt:
                ofd_text = (
                    f"🔴 <b>Yillik Soliq (OFD) to'lovidan QARZDORLIK MAVJUD!</b>\n\n"
                    f"🏛 <b>Fiskal modul:</b> <code>{found_fm}</code>\n"
                    f"💰 <b>Summa:</b> <b>440 000 so'm</b> (1 yilga)\n\n"
                )
                if is_issue:
                    ofd_text += (
                        "⚠️ <b>Apparat to'xtab qolishining sababi:</b> Davlat Soliq Qo'mitasi (OFD) yillik litsenziya muddati tugagan.\n\n"
                    )
                ofd_text += "💳 <i>To'lov rekvizitlari quyida kanaldan uzatildi:</i>"
                ofd_text = adapt_to_user_script(ofd_text, user_script)
                try:
                    await message.reply(ofd_text, parse_mode="HTML")
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
                user_memory.set_last_topic(chat_id, user_id, "annual_debt_exists")
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, ofd_text)
                return True
            else:
                # Yillik Soliq litsenziyasi faol (qarz yo'q). Endi oylik qarzni Excel'dan tekshiramiz!
                remembered_id = user_memory.get_last_id(chat_id, user_id)
                excel_res = excel_manager.search(remembered_id) if remembered_id else []
                real_monthly_debt = sum(item.get("debt", 0.0) for item in excel_res) if excel_res else 0.0
                if not org_name and excel_res:
                    org_name = excel_res[0].get("name", "")
                if remembered_id and excel_res:
                    user_memory.set_last_id(chat_id, user_id, remembered_id, org_name=org_name, debt=real_monthly_debt)

                if real_monthly_debt > 0:
                    debt_formatted = f"{real_monthly_debt:,.0f}".replace(",", " ")
                    monthly_debt_msg = (
                        f"🟢 <b>Yillik Soliq (OFD) to'lovidan qarzdorlik yo'q!</b> (Litsenziya faol, FM: <code>{found_fm}</code>)\n\n"
                        f"🔴 <b>Lekin «Mars» oylik abonent to'lovidan QARZDORLIK MAVJUD: {debt_formatted} so'm</b>\n"
                        f"🏢 <b>Korxona:</b> {org_name} (СТИР: <code>{remembered_id}</code>)\n\n"
                    )
                    if is_issue:
                        monthly_debt_msg += (
                            "⚠️ <b>Apparat to'xtab qolishining sababi:</b> «Mars» oylik abonent to'lovidan qarzdorlik.\n"
                            "Quyidagi hisob raqamga to'lov qilingandan so'ng apparat avtomatik faollashadi.\n\n"
                        )
                    monthly_debt_msg += "💳 <i>To'lov rekvizitlari va video yo'riqnoma quyida keltirilgan:</i>"
                    monthly_debt_msg = adapt_to_user_script(monthly_debt_msg, user_script)
                    try:
                        await message.reply(monthly_debt_msg, parse_mode="HTML")
                    except Exception:
                        await message.reply(monthly_debt_msg)
                    try:
                        await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=MARS_POST_ID)
                        await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=MARS_VIDEO_ID)
                    except Exception as e:
                        logger.warning(f"Post 85 yuborishda xatolik: {e}")
                    user_memory.add_user_message(chat_id, user_id, text)
                    user_memory.add_assistant_message(chat_id, user_id, monthly_debt_msg)
                    user_memory.set_last_topic(chat_id, user_id, "monthly_debt_exists")
                    return True
                elif is_issue:
                    # 3-BOSQICH (ESKALATSIYA): Oylik va Yillik to'langan, lekin apparat ishlamayapti!
                    from admin_manager import admin_manager, get_admin_contact_keyboard
                    last_photo = user_memory.get_last_photo(chat_id, user_id)
                    step3_text = (
                        f"🟢 <b>To'lovlar bo'yicha hech qanday qarzdorlik yo'q!</b>\n\n"
                        f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id or 'Aniqlangan'}</code>)\n"
                        f"🏛 <b>Fiskal modul:</b> <code>{found_fm}</code>\n"
                        f"✅ <b>Oylik abonent to'lovi:</b> To'langan (0 so'm)\n"
                        f"✅ <b>Yillik Soliq (OFD) litsenziyasi:</b> Faol (Muddati joyida)\n\n"
                        f"📌 <b>Apparatni ishga tushirish uchun quyidagilarni tekshiring:</b>\n"
                        f"1️⃣ <b>Internet aloqasi:</b> Apparatda Wi-Fi yoki SIM-karta tarmog'i (antenna belgisi) borligini tekshiring;\n"
                        f"2️⃣ <b>Soat va sana:</b> Apparatdagi vaqt hozirgi aniq vaqt bilan to'g'ri kelayotganini tekshiring;\n"
                        f"3️⃣ <b>Qayta yoqish:</b> Kassa dasturidan to'liq chiqib qayta kiring yoki apparatni o'chirib qayta yoqing (Перезагрузка / Reboot);\n"
                        f"4️⃣ <b>Rasm yuborish:</b> Agar baribir ishlamasa, apparat ekranidagi xatolik yozuvini rasmga olib yuboring.\n\n"
                        f"{admin_manager.get_contacts_display(inn=remembered_id)}\n\n"
                        f"👨‍💻 <b>Barcha ma'lumotlaringiz hududingiz bo'yicha mas'ul adminga yetkazildi.</b> Tez orada mutaxassis siz bilan bog'lanadi:"
                    )
                    step3_text = adapt_to_user_script(step3_text, user_script)
                    kb = get_admin_contact_keyboard(inn=remembered_id)
                    try:
                        await message.reply(step3_text, parse_mode="HTML", reply_markup=kb)
                    except Exception:
                        await message.reply(step3_text, reply_markup=kb)

                    init_q = user_memory.get_issue_initial_query(chat_id, user_id) or "Apparat ishlamayapti"
                    await admin_manager.notify_debt_free_device_issue(
                        bot=bot,
                        user=message.from_user,
                        chat_id=chat_id,
                        org_name=org_name,
                        inn=remembered_id or "",
                        issue_summary=f"Dastlabki murojaat: {init_q}. Oylik va Yillik qarz yo'q (to'langan), lekin apparat ishlamayapti. Fiskal modul: {found_fm}",
                        user_comment=text,
                        photo_file_id=last_photo,
                        fiscal_module=found_fm
                    )
                    user_memory.clear_issue_mode(chat_id, user_id)
                    user_memory.set_last_topic(chat_id, user_id, "issue_escalated_to_admin")
                    user_memory.add_user_message(chat_id, user_id, text)
                    user_memory.add_assistant_message(chat_id, user_id, step3_text)
                    return True
                else:
                    ofd_text = format_ofd_annual_status(found_fm, ofd_reply, user_script)
                    try:
                        await message.reply(ofd_text, parse_mode="HTML")
                    except Exception:
                        await message.reply(ofd_text)
                    user_memory.set_last_topic(chat_id, user_id, "annual_debt_clear")
                    user_memory.add_user_message(chat_id, user_id, text)
                    user_memory.add_assistant_message(chat_id, user_id, ofd_text)
                    return True

        # 2.2 Fiskal modul qayerdaligi / chekdan topish haqidagi savollar
        fm_where_phrases = [
            "fiskal modul qayerda", "fiskal modul qayerdan", "fiskal modul qayerda yozilgan",
            "fiskal modul qayerda boladi", "fiskal modul qayerda bo'ladi", "modul raqami qayerda",
            "fiskal modulni qanday topaman", "fiskal modul topish", "modul topish",
            "fiskal modul nima", "fiskal modul raqami nima", "fiskal modul haqida",
            "fiskal raqam nima", "fiskal raqam qayerda", "fiskal qayerda", "fiskal raqamni qayerdan",
            "fiskal modulni bilish", "fiskal modul qayeri", "fiskal modul qayerida",
            "chek yo'q", "chek yoq", "chekim yo'q", "chekim yoq", "chek chiqmayapti", "chek chiqmayapdi",
            "chek chiqara olmay", "chek chiqarolmay", "chek urmayapti", "chek yo'qku", "chek yoqku",
            "чек чиқмаяпти", "чек чикмаяпти", "чек йўқ", "чек йук",
            "фискал модул қаерда", "фискал модул каерда", "фискал модул қаердан", "модул рақами қаерда",
            "фискал модул нима", "фискал рақам нима", "фискал рақам қаерда"
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

        # 2.2.1 Yangi Texnologiyalar DUK nimaligi haqidagi savollar
        if any(p in lower_text for p in [
            "yangi texnologiyalar nima", "yangi texnologiyalar u nima", "yangi texnologiyalar kim",
            "yangi texnologiyalar haqida", "qanaqa yangi texnologiyalar", "yangi texnologiya nima",
            "янги технологиялар нима", "янги технологиялар ким", "янги технологиялар ҳақида", "қанақа янги технологиялар"
        ]):
            yt_text = (
                "🏛 <b>«Yangi Texnologiyalar» Ilmiy-axborot markazi DUK haqida:</b>\n\n"
                "Bu — Oʻzbekiston Respublikasi <b>Davlat soliq qoʻmitasi huzuridagi davlat unitar korxonasi</b> (OFD operatori) hisoblanadi.\n\n"
                "📌 <b>Vazifasi:</b> Barcha Onlayn-NKM va virtual kassalarning Fiskal modul litsenziyasi va cheklarini Soliq bazasiga uzatilishini taʼminlaydi.\n"
                "💰 <b>Yillik litsenziya toʻlovi:</b> 440 000 soʻm (Har yili toʻgʻridan-toʻgʻri ushbu davlat korxonasi hisobiga toʻlanadi).\n\n"
                "👇 <i>Quyida Davlat Soliq Qoʻmitasi huzuridagi «Yangi Texnologiyalar» DUK hisobiga toʻlash tartibi va video yoʻriqnoma keltirilgan:</i>"
            )
            yt_text = adapt_to_user_script(yt_text, user_script)
            try:
                await message.reply(yt_text, parse_mode="HTML")
            except Exception:
                await message.reply(yt_text)
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=SOLIQ_POST_ID,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.warning(f"Soliq postini yuborishda xatolik: {e}")
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=VIDEO_YILLIK_ID,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.warning(f"Yillik videoni yuborishda xatolik: {e}")
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, yt_text)
            user_memory.set_last_topic(chat_id, user_id, "annual_payment_card_sent")
            return True

        # 2.3 Hisob raqamlar postini kanaldan uzatish / to'lov intentlari ("oylikchi", "yillikchi", "to'layman", "shot tashla")
        is_in_payment_card_context = last_topic in (
            "payment_info_both",
            "monthly_payment_card_sent",
            "annual_payment_card_sent",
            "payment_instruction"
        )

        # Agar mijoz hozirgina "shot raqam" / "qayerga to'layman" deb hisob raqam so'ragan bo'lsa,
        # va keyingi gapida "yillikchi", "yillik-chi", "oylikchi" desa — u yillik/oylik SHOT (hisob raqam) so'rayapti!
        is_contextual_ann_shot = is_in_payment_card_context and any(w in lower_text for w in [
            "yillikchi", "yilikchi", "yillik-chi", "yillikkachi", "yillikdanchi", "fiskalchi", "soliqchi", "ofdchi",
            "yillikch", "yillikcha",
            "yillik", "fiskal", "soliq", "ofd", "йилликчи", "йилликкачи", "йилликданчи", "фискалчи", "солиқчи", "йиллик",
            "йилликч", "йилликча"
        ]) and not any(w in lower_text for w in ["qarz", "bormi", "tekshir", "қарз", "борми", "текшир"])

        is_contextual_mon_shot = is_in_payment_card_context and any(w in lower_text for w in [
            "oylikchi", "oylik-chi", "oylikkachi", "oylikdanchi", "marschi", "abonentchi",
            "oylikch", "oylikcha",
            "oylik", "mars", "abonent", "ойликчи", "ойликкачи", "ойликданчи", "марсчи", "ойлик",
            "ойликч", "ойликча"
        ]) and not any(w in lower_text for w in ["qarz", "bormi", "tekshir", "қарз", "борми", "текшир"])

        is_ann_check = is_annual_check_intent(text) and not is_contextual_ann_shot
        is_mon_check = is_monthly_check_intent(text) and not is_contextual_mon_shot

        payment_intent = classify_payment_intent(text)
        is_ann_pay = is_contextual_ann_shot or ((is_annual_pay_intent(text, last_topic) or payment_intent == "annual") and not is_ann_check)
        is_mon_pay = is_contextual_mon_shot or ((is_monthly_pay_intent(text, last_topic) or payment_intent == "monthly") and not is_mon_check)
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
                explicit_inn = extract_clean_inn(text)
                checked_inns = user_memory.get_checked_inns(chat_id, user_id)
                status_header = ""

                if not explicit_inn and len(checked_inns) > 1:
                    lines = ["📊 <b>Siz tekshirgan korxonalar bo'yicha «Mars» oylik abonent to'lovi holati:</b>\n"]
                    has_any_debt = False
                    for c_inn in checked_inns.keys():
                        c_res = excel_manager.search(c_inn)
                        c_debt = sum(item.get("debt", 0.0) for item in c_res) if c_res else 0.0
                        c_name = c_res[0].get("name", "") if c_res else checked_inns[c_inn].get("org_name", "")
                        if c_debt > 0:
                            has_any_debt = True
                            c_fmt = f"{c_debt:,.0f}".replace(",", " ")
                            lines.append(f"🔴 🏢 <b>{c_name}</b> (СТИР: <code>{c_inn}</code>):\n   👉 <b>Qarzdorlik: {c_fmt} so'm</b>")
                        else:
                            lines.append(f"🟢 🏢 <b>{c_name}</b> (СТИР: <code>{c_inn}</code>):\n   👉 <b>Qarzdorlik yo'q (0 so'm)</b>")
                    lines.append("💳 <i>To'lov uchun rasmiy hisob raqam va video yo'riqnoma quyida keltirilgan:</i>")
                    status_header = "\n\n".join(lines)
                    user_memory.set_last_topic(chat_id, user_id, "monthly_debt_exists" if has_any_debt else "monthly_debt_clear")
                else:
                    remembered_id = explicit_inn or user_memory.get_last_id(chat_id, user_id)
                    if remembered_id:
                        excel_res = excel_manager.search(remembered_id)
                        real_monthly_debt = sum(item.get("debt", 0.0) for item in excel_res) if excel_res else 0.0
                        org_name = excel_res[0].get("name", "") if excel_res else (user_memory.get_org_name(chat_id, user_id) or "")
                        if real_monthly_debt == 0:
                            d_info = user_memory.get_debt_info(chat_id, user_id)
                            if d_info and d_info.get("debt", 0) > 0:
                                real_monthly_debt = d_info.get("debt", 0)
                                if not org_name:
                                    org_name = d_info.get("org_name", "")

                        user_memory.set_last_id(chat_id, user_id, remembered_id, org_name=org_name, debt=real_monthly_debt)
                        if real_monthly_debt > 0:
                            debt_formatted = f"{real_monthly_debt:,.0f}".replace(",", " ")
                            status_header = (
                                f"🔴 <b>«Mars» oylik abonent to'lovidan QARZDORLIK MAVJUD: {debt_formatted} so'm</b>\n"
                                f"🏢 <b>Korxona:</b> {org_name} (СТИР: <code>{remembered_id}</code>)\n\n"
                                f"💳 <i>To'lov uchun rasmiy hisob raqam va video yo'riqnoma quyida keltirilgan:</i>"
                            )
                            user_memory.set_last_topic(chat_id, user_id, "monthly_debt_exists")
                        else:
                            status_header = (
                                f"🟢 <b>«Mars» oylik abonent to'lovidan qarzdorlik yo'q (To'langan).</b>\n"
                                f"🏢 <b>Korxona:</b> {org_name} (СТИР: <code>{remembered_id}</code>)\n\n"
                                f"💳 <i>To'lov rekvizitlari quyida keltirilgan:</i>"
                            )
                            user_memory.set_last_topic(chat_id, user_id, "monthly_debt_clear")

                if status_header:
                    status_header = adapt_to_user_script(status_header, user_script)
                    try:
                        await message.reply(status_header, parse_mode="HTML")
                    except Exception:
                        await message.reply(status_header)
                    user_memory.add_assistant_message(chat_id, user_id, status_header)

                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=MARS_POST_ID,
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    logger.warning(f"Oylik shot postini (85) nusxalashda xatolik: {e}")
                    if not status_header:
                        monthly_card = adapt_to_user_script(get_monthly_payment_card(), user_script)
                        await message.reply(monthly_card, parse_mode="HTML")

                wants_video = any(w in lower_text for w in [
                    "video", "videosi", "qanday", "qanaqa", "tartibi", "o'rgating", "orgating", "ko'rsating", "korsating",
                    "видео", "қандай", "кандай", "ўргатинг", "ургатинг"
                ])
                if wants_video:
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
                return True

            elif is_ann_pay:
                ann_st = user_memory.get_annual_status(chat_id, user_id)
                target_fm = user_memory.get_last_fm(chat_id, user_id)
                remembered_id = user_memory.get_last_id(chat_id, user_id)
                excel_res = excel_manager.search(remembered_id) if remembered_id else []
                real_monthly_debt = sum(item.get("debt", 0.0) for item in excel_res) if excel_res else 0.0

                is_explicit_acc_ask = is_contextual_ann_shot or any(w in lower_text for w in [
                    "shot", "rekvizit", "hisob", "xisob", "kartasi", "karta", "to'lash uchun", "tolash uchun",
                    "to'lashga", "tolashga", "шот", "реквизит", "ҳисоб", "счёт", "счет"
                ])
                # Agar mijoz shunchaki "yillikchi" yoki "yillik" deb so'ragan bo'lsa va xotirada yillikdan qarz yo'qligi ma'lum bo'lsa (va hisob raqam kontekstida bo'lmasa):
                if ann_st and not ann_st.get("has_debt") and not is_explicit_acc_ask:
                    clear_msg = "🟢 <b>Yillik Soliq (OFD) to'lovidan qarzdorlik yo'q!</b> (Litsenziya faol)"
                    if real_monthly_debt > 0:
                        debt_f = f"{real_monthly_debt:,.0f}".replace(",", " ")
                        clear_msg += f"\n🔴 <b>«Mars» oylik abonent to'lovidan qarzdorlik: {debt_f} so'm</b>"
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

                wants_video = any(w in lower_text for w in [
                    "video", "videosi", "qanday", "qanaqa", "tartibi", "o'rgating", "orgating", "ko'rsating", "korsating",
                    "видео", "қандай", "кандай", "ўргатинг", "ургатинг"
                ])
                if wants_video:
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
            target_fm = found_fm or user_memory.get_last_fm(chat_id, user_id)

            if target_fm:
                ofd_reply = await ofd_bridge.query_fiscal_module(bot, target_fm)
                ofd_status = parse_ofd_reply_status(ofd_reply)
                if ofd_status == "unavailable":
                    user_memory.set_annual_status(chat_id, user_id, has_debt=False, details="unavailable", unavailable=True)
                    timeout_msg = (
                        f"⏳ <b>Davlat Soliq (OFD) tizimi vaqtincha javob bermayapti.</b>\n\n"
                        f"🏛 <b>Fiskal modul:</b> <code>{target_fm}</code>\n\n"
                        f"Soliq qo'mitasi (@ofd943_bot) tizimi bilan bog'lanish vaqti tugadi yoki serverda profilaktika ketmoqda.\n"
                        f"Iltimos, bir necha daqiqadan so'ng qayta tekshirib ko'ring."
                    )
                    timeout_msg = adapt_to_user_script(timeout_msg, user_script)
                    try:
                        await message.reply(timeout_msg, parse_mode="HTML")
                    except Exception:
                        await message.reply(timeout_msg)
                    user_memory.add_user_message(chat_id, user_id, text)
                    user_memory.add_assistant_message(chat_id, user_id, timeout_msg)
                    return True

                if ofd_status == "not_found":
                    not_found_msg = format_ofd_annual_status(target_fm, ofd_reply, user_script)
                    try:
                        await message.reply(not_found_msg, parse_mode="HTML")
                    except Exception:
                        await message.reply(not_found_msg)
                    user_memory.add_user_message(chat_id, user_id, text)
                    user_memory.add_assistant_message(chat_id, user_id, not_found_msg)
                    return True

                has_ann_debt = (ofd_status == "debt")

                user_memory.set_annual_status(chat_id, user_id, has_debt=has_ann_debt, details="Qarzdorlik" if has_ann_debt else "Faol")

                is_issue = user_memory.is_issue_mode(chat_id, user_id)
                remembered_id = user_memory.get_last_id(chat_id, user_id)
                org_name = user_memory.get_org_name(chat_id, user_id) or ""

                if has_ann_debt:
                    ofd_text = (
                        f"🔴 <b>Yillik Soliq (OFD) to'lovidan QARZDORLIK MAVJUD!</b>\n\n"
                        f"🏛 <b>Fiskal modul:</b> <code>{target_fm}</code>\n"
                        f"💰 <b>Summa:</b> <b>440 000 so'm</b> (1 yilga)\n\n"
                    )
                    if is_issue:
                        ofd_text += (
                            "⚠️ <b>Apparat to'xtab qolishining sababi:</b> Davlat Soliq Qo'mitasi (OFD) yillik litsenziya muddati tugagan.\n\n"
                        )
                    ofd_text += "💳 <i>To'lov rekvizitlari quyida kanaldan uzatildi:</i>"
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
                    except Exception as e:
                        logger.warning(f"Post 34 nusxalashda xatolik: {e}")
                    return True
                else:
                    remembered_id = user_memory.get_last_id(chat_id, user_id)
                    excel_res = excel_manager.search(remembered_id) if remembered_id else []
                    real_monthly_debt = sum(item.get("debt", 0.0) for item in excel_res) if excel_res else 0.0
                    if not org_name and excel_res:
                        org_name = excel_res[0].get("name", "")
                    if real_monthly_debt == 0 and remembered_id:
                        d_info = user_memory.get_debt_info(chat_id, user_id)
                        if d_info and d_info.get("debt", 0) > 0:
                            real_monthly_debt = d_info.get("debt", 0)
                            if not org_name:
                                org_name = d_info.get("org_name", "")
                    if remembered_id and (excel_res or real_monthly_debt > 0):
                        user_memory.set_last_id(chat_id, user_id, remembered_id, org_name=org_name, debt=real_monthly_debt)

                    if real_monthly_debt > 0:
                        debt_formatted = f"{real_monthly_debt:,.0f}".replace(",", " ")
                        monthly_debt_msg = (
                            f"🟢 <b>Yillik Soliq (OFD) to'lovidan qarzdorlik yo'q!</b> (Litsenziya faol, FM: <code>{target_fm}</code>)\n\n"
                            f"🔴 <b>Lekin «Mars» oylik abonent to'lovidan QARZDORLIK MAVJUD: {debt_formatted} so'm</b>\n"
                            f"🏢 <b>Korxona:</b> {org_name} (СТИР: <code>{remembered_id}</code>)\n\n"
                        )
                        if is_issue:
                            monthly_debt_msg += (
                                "⚠️ <b>Apparat to'xtab qolishining sababi:</b> «Mars» oylik abonent to'lovidan qarzdorlik.\n"
                                "Quyidagi hisob raqamga to'lov qilingandan so'ng apparat avtomatik faollashadi.\n\n"
                                "💳 <i>«Mars» oylik to'lovi rekvizitlari quyida kanaldan uzatildi:</i>"
                            )
                        else:
                            monthly_debt_msg += "💡 <i>«Mars» oylik to'lovi rekvizitlarini olish uchun «Oylik shot» deb yozing.</i>"
                        monthly_debt_msg = adapt_to_user_script(monthly_debt_msg, user_script)
                        try:
                            await message.reply(monthly_debt_msg, parse_mode="HTML")
                        except Exception:
                            await message.reply(monthly_debt_msg)
                        if is_issue:
                            try:
                                await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=MARS_POST_ID)
                                await bot.copy_message(chat_id=message.chat.id, from_chat_id=SOURCE_CHANNEL_ID, message_id=MARS_VIDEO_ID)
                            except Exception as e:
                                logger.warning(f"Post 85 uzatishda xatolik: {e}")
                        user_memory.add_user_message(chat_id, user_id, text)
                        user_memory.add_assistant_message(chat_id, user_id, monthly_debt_msg)
                        user_memory.set_last_topic(chat_id, user_id, "monthly_debt_exists")
                        return True
                    elif is_issue:
                        # 3-BOSQICH (ESKALATSIYA): Oylik va Yillik to'langan, lekin apparat ishlamayapti!
                        from admin_manager import admin_manager, get_admin_contact_keyboard
                        last_photo = user_memory.get_last_photo(chat_id, user_id)
                        photo_note = "\n📸 <i>Yuborgan fotosuratingiz ham hududiy mas'ul adminga yetkazildi.</i>\n" if last_photo else ""
                        step3_text = (
                            f"🟢 <b>To'lovlar bo'yicha hech qanday qarzdorlik yo'q!</b>\n\n"
                            f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id or 'Aniqlangan'}</code>)\n"
                            f"🏛 <b>Fiskal modul:</b> <code>{target_fm}</code>\n"
                            f"✅ <b>Oylik abonent to'lovi:</b> To'langan (0 so'm)\n"
                            f"✅ <b>Yillik Soliq (OFD) litsenziyasi:</b> Faol (Muddati joyida)\n\n"
                            f"📌 <b>Apparatni ishga tushirish uchun tekshirib ko'ring:</b>\n"
                            f"1️⃣ <b>Internet aloqasi:</b> Apparatda Wi-Fi yoki SIM-karta tarmog'i (antenna belgisi) borligini tekshiring;\n"
                            f"2️⃣ <b>Soat va sana:</b> Apparatdagi vaqt hozirgi aniq vaqt bilan to'g'ri kelayotganini tekshiring;\n"
                            f"3️⃣ <b>Qayta yoqish:</b> Kassa dasturidan to'liq chiqib qayta kiring yoki apparatni o'chirib qayta yoqing (Перезагрузка / Reboot);\n"
                            f"4️⃣ <b>Rasm yuborish:</b> Agar baribir ishlamasa, apparat ekranidagi xatolik yozuvini rasmga olib yuboring.\n\n"
                            f"{admin_manager.get_contacts_display(inn=remembered_id)}\n"
                            f"{photo_note}"
                            f"👨‍💻 <b>Barcha ma'lumotlaringiz hududingiz bo'yicha mas'ul adminga tezkor yetkazildi!</b>\n"
                            f"Quyidagi tugmalar orqali to'g'ridan-to'g'ri mutaxassis bilan bog'lanishingiz mumkin:"
                        )
                        step3_text = adapt_to_user_script(step3_text, user_script)
                        kb = get_admin_contact_keyboard(inn=remembered_id)
                        try:
                            await message.reply(step3_text, parse_mode="HTML", reply_markup=kb)
                        except Exception:
                            await message.reply(step3_text, reply_markup=kb)

                        init_q = user_memory.get_issue_initial_query(chat_id, user_id) or "Apparat ishlamayapti"
                        await admin_manager.notify_debt_free_device_issue(
                            bot=bot,
                            user=message.from_user,
                            chat_id=chat_id,
                            org_name=org_name,
                            inn=remembered_id or "",
                            issue_summary=f"Dastlabki murojaat: {init_q}. Oxirgi xabar: {text}",
                            user_comment=text,
                            photo_file_id=last_photo,
                            fiscal_module=target_fm
                        )
                        user_memory.clear_issue_mode(chat_id, user_id)
                        user_memory.set_last_topic(chat_id, user_id, "issue_escalated_to_admin")
                        user_memory.mark_escalated_to_admin(chat_id, user_id, reason="Apparat ishlamayapti (Yillik va oylik to'lovlar 0 so'm)")
                        user_memory.add_user_message(chat_id, user_id, text)
                        user_memory.add_assistant_message(chat_id, user_id, step3_text)
                        return True
                    else:
                        # QARZ YO'Q! Oddiy so'rov
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

        # 4. Oylik qarz tekshiruvi ("oylik qarzim bormi", "oylikdanchi", "marsdan qarz", "oylikchi")
        if is_monthly_check_intent(text):
            explicit_inn = extract_clean_inn(text)
            checked_inns = user_memory.get_checked_inns(chat_id, user_id)
            is_multi_inn_query = any(w in lower_text for w in [
                "qaysi", "ikkala", "barcha", "hamma", "har bir", "qaysinisida", "qaysilari",
                "кайси", "иккала", "барча", "ҳамма", "қайси"
            ])
            if not explicit_inn and len(checked_inns) > 1 and is_multi_inn_query:
                # Bir nechta korxona tekshirilgan bo'lsa, barchasining qarz holatini chiqarish
                lines = ["📊 <b>Siz tekshirgan korxonalar bo'yicha «Mars» oylik abonent to'lovi holati:</b>\n"]
                has_any_debt = False
                for c_inn in checked_inns.keys():
                    c_res = excel_manager.search(c_inn)
                    c_debt = sum(item.get("debt", 0.0) for item in c_res) if c_res else 0.0
                    c_name = c_res[0].get("name", "") if c_res else checked_inns[c_inn].get("org_name", "")
                    if c_debt > 0:
                        has_any_debt = True
                        c_fmt = f"{c_debt:,.0f}".replace(",", " ")
                        lines.append(f"🔴 🏢 <b>{c_name}</b> (СТИР: <code>{c_inn}</code>):\n   👉 <b>Qarzdorlik: {c_fmt} so'm</b>")
                    else:
                        lines.append(f"🟢 🏢 <b>{c_name}</b> (СТИР: <code>{c_inn}</code>):\n   👉 <b>Qarzdorlik yo'q (0 so'm)</b>")
                lines.append("💳 <i>To'lov uchun rasmiy hisob raqam va video yo'riqnoma quyida keltirilgan:</i>")
                multi_text = adapt_to_user_script("\n\n".join(lines), user_script)
                try:
                    await message.reply(multi_text, parse_mode="HTML")
                except Exception:
                    await message.reply(multi_text)
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, multi_text)
                user_memory.set_last_topic(chat_id, user_id, "monthly_debt_exists" if has_any_debt else "monthly_debt_clear")
                if has_any_debt:
                    try:
                        await bot.copy_message(
                            chat_id=message.chat.id,
                            from_chat_id=SOURCE_CHANNEL_ID,
                            message_id=MARS_POST_ID,
                            reply_to_message_id=message.message_id
                        )
                    except Exception as e:
                        logger.warning(f"Oylik shot postini uzatishda xatolik: {e}")
                return True

            remembered_id = explicit_inn or user_memory.get_last_id(chat_id, user_id)
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
            if excel_manager.search(found_inn) or excel_manager.is_decommissioned(found_inn):
                user_memory.set_last_id(chat_id, user_id, found_inn)
            if not any(tw in lower_text for tw in TECH_QUESTION_WORDS):
                from handlers.debt import process_and_send_debt_result
                await process_and_send_debt_result(message, bot, found_inn)
                return True


        # 9. Click orqali to'lov tartibi yoki "qayerga/qanday to'layman" so'ralganda:
        # Faqat videoni emas, avval hisob raqam postini (85) va ketidan videoni (148) uzatamiz!
        if any(kw in lower_text for kw in PAYMENT_METHODS_KEYWORDS):
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=MARS_POST_ID,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.warning(f"Post 85 yuborishda xatolik: {e}")
                await message.reply(adapt_to_user_script(get_monthly_payment_card(), user_script), parse_mode="HTML")

            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=MARS_VIDEO_ID
                )
            except Exception as e:
                logger.error(f"To'lov videosi yuborishda xatolik: {e}")

            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, "[Oylik shot posti (85) va Click video (148) yuborildi]")
            user_memory.set_last_topic(chat_id, user_id, "monthly_payment_card_sent")
            return True

        # 10. Pul yechilgan / to'langan lekin apparat yoqilmagan bo'lsa
        paid_not_active_words = [
            "yechildi lekin", "yechib oldi lekin", "yechildi ammo", "pul ketdi lekin", "pul yechildi",
            "toladim lekin", "to'ladim lekin", "to'lov qildim lekin", "tolov qildim lekin",
            "to'langan lekin", "tolangan lekin", "yechildi hali", "to'ladim nega", "toladim nega",
            "to'ladim nimaga", "toladim nimaga", "pul o'tdi lekin", "pul otdi lekin",
            "ечилди лекин", "тўладим лекин", "тўлов қилдим лекин"
        ]
        if any(w in lower_text for w in paid_not_active_words) and any(w in lower_text for w in ["yonmadi", "yoqmadi", "ishlamadi", "ochilmadi", "blok", "xali", "hali", "apparat", "kassa", "ishlamayapti", "ochilmayapti", "аппарат"]):
            resp = (
                "💳 <b>To'lov qilindi, lekin apparat hali ochilmagan bo'lsa:</b>\n\n"
                "To'lov turiga qarab quyidagi holatlarni tekshiring:\n\n"
                "1️⃣ <b>Agar «Mars» oylik to'lovi bo'lsa:</b>\n"
                "   • Kassa apparatida internet (Wi-Fi yoki SIM) va soat/sana to'g'riligini tekshiring;\n"
                "   • Apparatni to'liq o'chirib qayta yoqing (Перезагрузка / Reboot) — ko'pincha apparat qayta yonganda avtomatik ochiladi;\n"
                "   • To'lov chekini (kvitansiyani) shu yerga yuborsangiz, operatorlarimiz zudlik bilan yoqib berishadi.\n\n"
                "2️⃣ <b>Agar Davlat Soliq (OFD) yillik to'lovi (440 000 so'm) bo'lsa:</b>\n"
                "   • Soliq qo'mitasi («Yangi Texnologiyalar» DUK) bank orqali tushgan to'lovni <b>2 soatdan 24 soatgacha</b> bo'lgan muddatda tasdiqlaydi va litsenziyani avtomatik uzaytiradi;\n"
                "   • Soliq bazasida faollashgach apparatni qayta o'chirib yoqsangiz ishlaydi.\n\n"
                "📩 <i>Tezkor yordam uchun to'lov kvitansiyasini shu yerga rasm yoki PDF shaklida yuboring!</i>"
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
