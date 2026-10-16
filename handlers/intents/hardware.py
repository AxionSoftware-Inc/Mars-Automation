import logging
from aiogram import types, Bot

from user_memory import user_memory
from translit_manager import adapt_to_user_script
from excel_manager import excel_manager
from handlers.debt import format_debt_response
from core.models import extract_clean_inn, extract_fiscal_module
from ofd_bridge import ofd_bridge
from admin_manager import admin_manager, get_admin_contact_keyboard
from payment_accounts import (
    FISKAL_MODUL_SAMPLE_POST_ID,
    YANGI_TEXNOLOGIYALAR_POST_ID,
    YANGI_TEXNOLOGIYALAR_VIDEO_ID,
    MARS_POST_ID,
    MARS_VIDEO_ID
)

logger = logging.getLogger(__name__)

SOURCE_CHANNEL_ID = -1001641871516  # @POS_Terminal_UzSmart_Bank

DEVICE_ISSUE_PHRASES = [
    "apparat ishlamayapti", "apparatim ishlamayapti", "aparat ishlamayapti", "aparatim ishlamayapti",
    "aparatim ishlamayapdi", "aparatim ishlamayabdiku", "aparatim ishlamayaptida", "aparatim ishlamayaptiku",
    "kassa ishlamayapti", "kassa ishlamay qoldi", "apparat ishlamay qoldi", "aparat ishlamay qoldi",
    "chek urmayapti", "chek chiqmayapti", "chek chiqarmayabdi", "kassa qotib qoldi", "apparat qotib qoldi", "aparat qotib qoldi",
    "ishlamayapti apparat", "ishlamayapti aparat", "ishlamayapti kassa", "ishlamayapti",
    "ishlamayapdi", "ishlamiyapti", "ishlamiyapdi", "ishlamayaptiku", "ishlamayaptiyu", "ishlamayaptida",
    "ishlamay qoldi", "ishlamay qopti", "ishlamayapti negadir",
    "o'chib qoldi", "ochib qoldi", "o'chib qolgan", "ochib qolgan", "ochib qogan", "o'chib qogan",
    "blok bo'ldi", "bloklandi", "blok bolgan", "blokda", "bloklangan", "blokga tushgan", "blok boldi",
    "buzildi", "buzilib qoldi", "buzilib qolgan",
    "xatolik", "xatolik chiqyapti", "xato chiqyapti", "xatolik beryapti", "xato beryapti", "xato beryapdi",
    "xatolik kodi", "xatolik 406", "kod 406", "kod 102", "xato 406", "xato 102",
    "ochmayapti", "ochmayapdi", "yoqilmayapti", "yoqilmayapdi", "yonmayapti", "yonmayapdi",
    "chek bermayapti", "chek chiqmayapdi", "chek chiqarmayapti", "chek urmayapdi", "chek chiqmaydi",
    "terminal ishlamayapti", "terminal ishlamayapdi", "pos ishlamayapti", "pos ishlamayapdi",
    "qotib qoldi", "qotib qolgan", "qotyapti", "qotib qolyapti",
    "oshibka", "ошибка", "ne rabotayet", "не работает", "сломался", "заблокирован",
    "не печатает", "не включается", "завис", "ошибка 406", "ошибка 102"
]

UNRESOLVED_WORDS = [
    "ishlamadi", "baribir ishlamadi", "o'xshamadi", "oxshamadi", "bo'lmadi", "bolmadi",
    "ochmadi", "yoqilmadi", "reboot qildim", "o'chirib yoqdim", "ochirib yoqdim",
    "qilolmadim", "yana shu xato", "yana xato", "yana o'sha", "tushunmadim"
]


def is_device_issue(text: str) -> bool:
    """Xabarda apparat nosozligi iboralari mavjudligini tekshirish"""
    if not text:
        return False
    lower = text.lower()
    return any(p in lower for p in DEVICE_ISSUE_PHRASES)


class HardwareIntentHandler:
    """
    Apparat nosozligi va xatoliklar bo'yicha qat'iy 3 bosqichli Pipeline:
    1-bosqich: INN so'rab oylik qarzni tekshirish (Mars 100 000 so'm);
    2-bosqich: Oylik to'langan bo'lsa -> Kassa chekidagi Fiskal modul (LG/YG) orqali Davlat Soliq (OFD) yillik litsenziyasini tekshirish (440 000 so'm);
    3-bosqich: Ikkala to'lov ham to'langan bo'lsa -> Internet, Soat/sana va Reboot tekshirish, rasm so'rash hamda ZUDLIK BILAN ADMINGA ESKALATSIYA!
    """

    async def handle(self, message: types.Message, bot: Bot, user_script: str) -> bool:
        text = (message.text or "").strip()
        lower_text = text.lower()
        user_id = message.from_user.id if message.from_user else 0
        chat_id = message.chat.id

        # 0. Aniq soat/vaqt videosi so'ralsa -> videoga yo'naltirish
        if any(w in lower_text for w in ["soatni to'g'rilash", "vaqtni to'g'rilash", "soat videosi", "vaqt videosi"]):
            return False

        is_in_issue = user_memory.is_issue_mode(chat_id, user_id)
        has_issue_phrase = any(phrase in lower_text for phrase in DEVICE_ISSUE_PHRASES)

        # Agar foydalanuvchi muammo rejimida bo'lmasa va xabarda nosozlik so'zi bo'lmasa -> bu hardware emas
        if not is_in_issue and not has_issue_phrase:
            return False

        # Muammo rejimini faollashtirish va saqlash
        if has_issue_phrase and not is_in_issue:
            user_memory.set_issue_mode(chat_id, user_id, True, initial_query=text)

        # 0.1 TEZDA ESKALATSIYA: Mijoz bir urinishdan keyin "ishlamadi / bo'lmadi / reboot qildim" deb yozsa
        if any(w in lower_text for w in UNRESOLVED_WORDS):
            remembered_id = user_memory.get_last_id(chat_id, user_id) or ""
            org_name = user_memory.get_org_name(chat_id, user_id) or ""
            last_photo = user_memory.get_last_photo(chat_id, user_id)
            esc_msg = (
                "👨‍💻 <b>Tushunarli, apparatda texnik nosozlik mavjud.</b>\n\n"
                "Barcha ma'lumotlaringiz Hududiy THKM texnik xizmat ko'rsatish mas'ul xodimlarimizga (@quvonchbek_admin, @Yashnarbek_butaev) uzatildi.\n"
                "Quyidagi tugmalar orqali to'g'ridan-to'g'ri mas'ul mutaxassis bilan bog'lanishingiz mumkin:\n\n"
                "📸 <i>Iloji bo'lsa, ekranda chiqayotgan xatolik yozuvini rasmga olib tashlang.</i>"
            )
            esc_msg = adapt_to_user_script(esc_msg, user_script)
            kb = get_admin_contact_keyboard()
            try:
                await message.reply(esc_msg, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await message.reply(esc_msg, reply_markup=kb)

            await admin_manager.notify_user_query_escalation(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                query_text=text,
                reason="Apparat nosozligi: Qayta yoqilgandan keyin ham ishlamadi (Mutaxassis kutmoqda)",
                inn=remembered_id,
                org_name=org_name,
                photo_file_id=last_photo
            )
            user_memory.clear_issue_mode(chat_id, user_id)
            user_memory.set_last_topic(chat_id, user_id, "issue_escalated_to_admin")
            user_memory.mark_escalated_to_admin(chat_id, user_id, reason="Apparat nosozligi: Qayta yoqilgandan keyin ham ishlamadi")
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, esc_msg)
            return True

        # Yangi kiritilgan INN yoki Fiskal modulni aniqlash
        found_inn = extract_clean_inn(text)
        found_fm = extract_fiscal_module(text)

        if found_inn:
            user_memory.set_last_id(chat_id, user_id, found_inn)
        if found_fm:
            user_memory.set_last_fm(chat_id, user_id, found_fm)

        remembered_id = user_memory.get_last_id(chat_id, user_id)
        remembered_fm = user_memory.get_last_fm(chat_id, user_id)

        # =====================================================================
        # 1-BOSQICH: INN ANIQLANMAGAN BO'LSA -> INN NI SO'RASH
        # =====================================================================
        if not remembered_id:
            guide_msg = (
                "🔍 <b>Apparat holati va qarzdorlikni tekshirish:</b>\n\n"
                "Kassa apparatlari to'xtab qolishining asosiy sababi abonent yoki soliq to'lovidagi qarzdorlik bo'ladi.\n\n"
                "Iltimos, birinchi navbatda korxonangizning <b>СТИР (INN) raqamini yuboring</b>."
            )
            guide_msg = adapt_to_user_script(guide_msg, user_script)
            try:
                await message.reply(guide_msg, parse_mode="HTML")
            except Exception:
                await message.reply(guide_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, guide_msg)
            return True

        # INN aniqlangan bo'lsa -> Excel bazadan oylik qarzni tekshirish
        results = excel_manager.search(remembered_id)
        if not results and excel_manager.is_decommissioned(remembered_id):
            decom_list = excel_manager.get_decommissioned(remembered_id)
            decom_org = decom_list[0].get("name", "") if decom_list else ""
            decom_msg = (
                f"ℹ️ <b>{decom_org}</b> korxonasi xizmat ko'rsatish bazasidan hisobdan chiqarilgan (o'chirilgan).\n"
                f"Qarzdorlik hisoblanmaydi (0 so'm).\n\n"
                f"Agar apparatni qayta faollashtirish kerak bo'lsa, «Usta kerak» yoki «Admin» deb yozing."
            )
            decom_msg = adapt_to_user_script(decom_msg, user_script)
            try:
                await message.reply(decom_msg, parse_mode="HTML")
            except Exception:
                await message.reply(decom_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, decom_msg)
            return True

        org_name = results[0].get("name", "") if results else (user_memory.get_org_name(chat_id, user_id) or "")
        total_debt = sum(item.get("debt", 0.0) for item in results) if results else 0.0
        user_memory.set_last_id(chat_id, user_id, remembered_id, org_name=org_name, debt=total_debt)

        # ---------------------------------------------------------------------
        # 1-BOSQICH XULOSASI: OYLIK ABONENT QARZI BORMI?
        # ---------------------------------------------------------------------
        if total_debt > 0:
            debt_resp = format_debt_response(results)
            debt_resp += (
                "\n\n⚠️ <i>Apparat to'xtab qolishining sababi: «Mars» oylik abonent to'lovidan qarzdorlik mavjud. "
                "Quyidagi hisob raqamga to'lov qilingandan so'ng apparat avtomatik faollashadi.</i>"
            )
            debt_resp = adapt_to_user_script(debt_resp, user_script)
            try:
                await message.reply(debt_resp, parse_mode="HTML")
                await bot.copy_message(chat_id=chat_id, from_chat_id=SOURCE_CHANNEL_ID, message_id=MARS_POST_ID)
                await bot.copy_message(chat_id=chat_id, from_chat_id=SOURCE_CHANNEL_ID, message_id=MARS_VIDEO_ID)
            except Exception as e:
                logger.warning(f"Oylik qarz xabarini uzatishda xatolik: {e}")
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, debt_resp)
            return True

        # =====================================================================
        # 2-BOSQICH: OYLIK QARZ YO'Q (0 SO'M) -> YILLIK SOLIQ LITSENZIYASINI TEKSHIRISH
        # =====================================================================
        if not remembered_fm:
            # Mijoz "chek yo'q", "chiqmayapti", "qayerdan olaman" desa:
            is_no_receipt = any(w in lower_text for w in [
                "chek chiqmayapti", "chek chiqmayapdi", "chek urmayapti", "chek yo'q", "chek yoq",
                "cheki yo'q", "cheki yoq", "chek chiqara olmay", "chek chiqarolmay", "chekni qayerdan",
                "chek yo'qku", "chek yoqku", "chek yo", "чек чиқмаяпти", "чек чикмаяпти", "чек йўқ", "чек йук"
            ])
            is_fm_what = any(w in lower_text for w in [
                "fiskal modul nima", "modul nima", "fiskal nima", "fiskal modul qayerda",
                "фискал модул нима", "модул нима"
            ])

            if is_no_receipt:
                clear_msg = (
                    f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id}</code>)\n"
                    f"✅ «Mars» oylik abonent to'lovidan qarzdorlik yo'q (0 so'm).\n\n"
                    f"⚠️ <b>Agar apparatdan yangi chek chiqmayotgan yoki eski chek bo'lmasa:</b>\n"
                    f"1️⃣ Avvalroq chiqarilgan istalgan <b>eski kassa chekining eng pastki qismiga</b> qarang (Fiskal modul seriya raqami o'zgarmaydi);\n"
                    f"2️⃣ Yoki apparatning <b>orqa qismidagi nakleyka (yorliq)</b> / batareya ostidagi seriya raqamini rasmga olib yuboring;\n"
                    f"3️⃣ Yoki apparat <b>ekranidagi ko'rinish / xatolikni</b> rasmga olib tashlang.\n\n"
                    f"👨‍💻 <i>Yordam kerak bo'lsa, mutaxassisga yo'naltirish uchun «Usta kerak» deb yozing.</i>"
                )
            elif is_fm_what:
                clear_msg = (
                    f"ℹ️ <b>Fiskal modul</b> — bu kassa apparatingiz ichidagi Davlat Soliq xizmati bilan ishlovchi chip.\n\n"
                    f"Uning seriya raqami kassa chekining eng pastki qismida bo'ladi (masalan: <code>LG420210630789</code>).\n"
                    f"Chekdan topolmasangiz, chekning pastki qismini rasmga olib yuborsangiz botimiz o'zi aniqlab tekshiradi."
                )
            else:
                clear_msg = (
                    f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id}</code>)\n"
                    f"✅ «Mars» oylik abonent to'lovidan qarzdorlik yo'q (0 so'm).\n\n"
                    f"🔍 <b>2-bosqich: Davlat Soliq (OFD) yillik litsenziyasini tekshirish</b>\n"
                    f"🏛 Litsenziya muddatini tekshirishimiz uchun kassa chekining eng pastki qismidagi <b>Fiskal modul raqamini (LG... yoki YG...)</b> yuboring."
                )

            clear_msg = adapt_to_user_script(clear_msg, user_script)
            try:
                await message.reply(clear_msg, parse_mode="HTML")
            except Exception:
                await message.reply(clear_msg)

            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=FISKAL_MODUL_SAMPLE_POST_ID
                )
            except Exception as e:
                logger.warning(f"Fiskal modul namunasi postini yuborishda xatolik: {e}")

            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, clear_msg)
            user_memory.set_last_topic(chat_id, user_id, "awaiting_fiscal_module")
            return True

        # Fiskal modul bor -> OFD litsenziyasini tekshirish
        ofd_reply = await ofd_bridge.query_fiscal_module(bot, remembered_fm)
        has_ann_debt = ofd_reply and any(w in ofd_reply.lower() for w in ["qarzdorlik mavjud", "fmo dan qarzdorlik", "qarzdorlik"])
        user_memory.set_annual_status(chat_id, user_id, has_debt=has_ann_debt, details=ofd_reply or "")

        if has_ann_debt:
            # 2-BOSQICH XULOSASI: YILLIK SOLIQ QARZI BOR!
            ann_msg = (
                f"🔴 <b>Yillik Soliq (OFD) to'lovidan QARZDORLIK MAVJUD!</b>\n\n"
                f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id}</code>)\n"
                f"🏛 <b>Fiskal modul:</b> <code>{remembered_fm}</code>\n"
                f"💰 <b>Summa:</b> <b>440 000 so'm</b> (1 yilga)\n\n"
                f"⚠️ <b>Apparat to'xtab qolishining sababi:</b> Davlat Soliq Qo'mitasi (OFD) yillik litsenziya muddati tugagan.\n"
                f"Quyidagi hisob raqamga to'lov qilingandan so'ng litsenziya Soliq tomonidan 2-24 soat ichida faollashtiriladi."
            )
            ann_msg = adapt_to_user_script(ann_msg, user_script)
            try:
                await message.reply(ann_msg, parse_mode="HTML")
                await bot.copy_message(chat_id=chat_id, from_chat_id=SOURCE_CHANNEL_ID, message_id=YANGI_TEXNOLOGIYALAR_POST_ID)
                await bot.copy_message(chat_id=chat_id, from_chat_id=SOURCE_CHANNEL_ID, message_id=YANGI_TEXNOLOGIYALAR_VIDEO_ID)
            except Exception as e:
                logger.warning(f"Yillik qarz postini yuborishda xatolik: {e}")
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, ann_msg)
            user_memory.set_last_topic(chat_id, user_id, "annual_debt_exists")
            return True

        # =====================================================================
        # 3-BOSQICH: OYLIK VA YILLIK QARZ YO'Q! -> RASM SO'RASH YOKI ADMINGA UZATISH
        # =====================================================================
        last_photo = user_memory.get_last_photo(chat_id, user_id)
        kb = get_admin_contact_keyboard()

        if last_photo:
            # Rasm allaqachon mavjud -> barcha ma'lumotlar bilan birga zudlik bilan adminga uzatish
            step3_msg = (
                f"🟢 <b>To'lovlar bo'yicha hech qanday qarzdorlik yo'q!</b>\n\n"
                f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id}</code>)\n"
                f"🏛 <b>Fiskal modul:</b> <code>{remembered_fm}</code>\n"
                f"✅ <b>Oylik to'lov:</b> To'langan (0 so'm)\n"
                f"✅ <b>Yillik litsenziya:</b> Faol (Muddati joyida)\n\n"
                f"👨‍💻 <b>Iltimos kuting, barcha ma'lumotlaringiz (INN, Fiskal modul va apparat rasmi) mas'ul adminga yuborildi!</b>\n\n"
                f"Hududiy THKM texnik xizmat ko'rsatish mas'ul xodimlarimiz (@quvonchbek_admin, @Yashnarbek_butaev) tez orada ko'rib chiqib siz bilan bog'lanishadi.\n"
                f"Quyidagi tugmalar orqali ham to'g'ridan-to'g'ri aloqaga chiqishingiz mumkin:"
            )
        else:
            # Rasm hali olinmagan -> Ekran rasmini so'rash va internet/soat/reboot bo'yicha ko'rsatma berish
            step3_msg = (
                f"🟢 <b>To'lovlar bo'yicha hech qanday qarzdorlik yo'q!</b>\n\n"
                f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id}</code>)\n"
                f"🏛 <b>Fiskal modul:</b> <code>{remembered_fm}</code>\n"
                f"✅ <b>Oylik abonent to'lovi:</b> To'langan (0 so'm)\n"
                f"✅ <b>Yillik Soliq (OFD) litsenziyasi:</b> Faol (Muddati joyida)\n\n"
                f"📸 <b>Iltimos, apparat ekranidagi xatolik yozuvini rasmga olib yuboring!</b>\n\n"
                f"📌 <i>Shuningdek tekshirib ko'ring:</i>\n"
                f"1️⃣ <b>Internet aloqasi:</b> Wi-Fi yoki SIM-karta tarmog'i borligini;\n"
                f"2️⃣ <b>Soat va sana:</b> Hozirgi aniq vaqt to'g'riligini;\n"
                f"3️⃣ <b>Qayta yoqish:</b> Kassa apparatini o'chirib qayta yoqishni (Reboot).\n\n"
                f"👨‍💻 <b>Rasm tashlashingiz bilan barcha ma'lumotlar mas'ul adminga to'liq yetkaziladi. Iltimos, rasm yuboring!</b>"
            )

        step3_msg = adapt_to_user_script(step3_msg, user_script)
        try:
            await message.reply(step3_msg, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await message.reply(step3_msg, reply_markup=kb)

        init_q = user_memory.get_issue_initial_query(chat_id, user_id) or text
        await admin_manager.notify_debt_free_device_issue(
            bot=bot,
            user=message.from_user,
            chat_id=chat_id,
            org_name=org_name,
            inn=remembered_id,
            issue_summary=f"Dastlabki murojaat: {init_q}. Oxirgi xabar: {text}",
            user_comment=text,
            photo_file_id=last_photo,
            fiscal_module=remembered_fm
        )

        user_memory.clear_issue_mode(chat_id, user_id)
        user_memory.set_last_topic(chat_id, user_id, "awaiting_screen_photo" if not last_photo else "issue_escalated_to_admin")
        if last_photo:
            user_memory.mark_escalated_to_admin(chat_id, user_id, reason="Apparat ishlamayapti (To'lovlar to'langan, rasm adminga uzatildi)")
        user_memory.add_user_message(chat_id, user_id, text)
        user_memory.add_assistant_message(chat_id, user_id, step3_msg)
        return True


hardware_intent_handler = HardwareIntentHandler()
