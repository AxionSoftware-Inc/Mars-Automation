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
    YANGI_TEXNOLOGIYALAR_INN,
    send_monthly_account_post,
    send_annual_account_post,
    send_fiscal_sample_post,
    parse_ofd_reply_status,
    format_ofd_annual_status
)

logger = logging.getLogger(__name__)

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
    if any(p in lower for p in DEVICE_ISSUE_PHRASES):
        return True

    # Moslashuvchan o'zaklar (har xil xatoliklar, orfografik xatolar va shevalar uchun: "ishklamayapdi", "ishlamayabdi", "kurib beriyla")
    has_device = any(d in lower for d in ["aparat", "apparat", "kassa", "terminal", "pos", "smart one", "p3", "uskuna", "ekran"])
    has_issue_stem = any(s in lower for s in [
        "ishlam", "ishklam", "islam", "ochil", "ochmay", "yonmay", "yoqil", "qotib", "buzil",
        "blok", "xato", "oshibka", "chek chiq", "chek berm", "chek ur"
    ])
    if has_device and has_issue_stem:
        return True

    # "aparatimni kurib beriyla", "kassani tekshirib beringlar", "aparat ishlamay qoldi"
    if has_device and any(v in lower for v in ["kurib ber", "ko'rib ber", "korib ber", "tuzatib ber", "tekshirib ber"]):
        return True

    return False


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

        # 0. Aniq yo'riqnoma yoki katalog videosi so'ralsa (Z-hisobot, soat/vaqt, MXIK, qo'llanmalar) -> tegishli handlerga yo'naltirish
        from payment_accounts import is_mxik_intent
        if is_mxik_intent(text):
            return False

        from catalog_manager import catalog_manager
        norm_t = catalog_manager.normalize(text)

        # A) Soat, vaqt yoki sana bo'yicha har qanday savol/tuzatish/qo'llanma so'rovi (saot, vaqt, sana...)
        is_clock_inquiry = (
            any(w in norm_t for w in ["soat", "vaqt", "sana"]) and
            any(w in norm_t for w in ["togirla", "tuzat", "sozla", "notogri", "xato", "adash", "orqada", "oldinda", "qanday", "vide", "korsat", "urgan"])
        ) or any(w in lower_text for w in [
            "z hisobot", "z-hisobot", "z otchet", "z-otchet", "kunlik hisobot", "x hisobot", "x-hisobot",
            "soatni to'g'rilash", "vaqtni to'g'rilash", "soat videosi", "vaqt videosi",
            "vaqtni qanday", "soatni qanday", "soat noto'g'ri", "vaqt noto'g'ri", "soat xato", "vaqt xato",
            "saot", "soatini", "vaqtini", "soat tuzat", "vaqt tuzat"
        ])
        if is_clock_inquiry:
            return False

        # B) Agar foydalanuvchi video katalogdagi biror aniq qo'llanmani so'rayotgan bo'lsa -> apparat nosozligi sifatida bloklamaslik!
        matching_video_id = catalog_manager.find_post_by_keywords(text)
        if matching_video_id:
            return False

        # C) Agar mijoz "qanday qilinadi", "qanday tuzataman", "qanday olaman" kabi operatsion savol bersa va video katalogda mavjud bo'lsa:
        if any(w in norm_t for w in ["qanday", "qanaqa", "video", "rolik", "kursat", "organ", "qollanma"]):
            if catalog_manager.find_matching_post(text):
                return False

        is_in_issue = user_memory.is_issue_mode(chat_id, user_id)
        has_issue_phrase = is_device_issue(text)

        # Agar foydalanuvchi muammo rejimida bo'lmasa va xabarda nosozlik so'zi bo'lmasa -> bu hardware emas
        if not is_in_issue and not has_issue_phrase:
            return False

        # Agar foydalanuvchi minnatdorchilik bildirsa ("rahmat", "katta rahmat", "tushundim", "tushunarli", "yaxshi"):
        if any(w in lower_text for w in ["rahmat", "katta rahmat", "tushundim", "tushunarli", "рахмат", "тушундим"]):
            user_memory.clear_issue_mode(chat_id, user_id)
            thx_msg = adapt_to_user_script(
                "Arzimaydi! Yana qandaydir savollaringiz yoki kassa apparati bilan muammo bo'lsa, bemalol murojaat qilishingiz mumkin. Xizmatingizdamiz! 🤝",
                user_script
            )
            await message.reply(thx_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, thx_msg)
            return True

        # Muammo rejimini faollashtirish va saqlash
        if has_issue_phrase and not is_in_issue:
            user_memory.set_issue_mode(chat_id, user_id, True, initial_query=text)

        # 0.1 TEZDA ESKALATSIYA: Mijoz bir urinishdan keyin "ishlamadi / bo'lmadi / reboot qildim" deb yozsa
        if any(w in lower_text for w in UNRESOLVED_WORDS):
            remembered_id = user_memory.get_last_id(chat_id, user_id) or ""
            org_name = user_memory.get_org_name(chat_id, user_id) or ""
            last_photo = user_memory.get_last_photo(chat_id, user_id)
            contacts_block = admin_manager.get_contacts_display(inn=remembered_id)
            esc_msg = (
                "👨‍💻 <b>Tushunarli, apparatda texnik nosozlik mavjud.</b>\n\n"
                "Barcha ma'lumotlaringiz hududingiz bo'yicha mas'ul mutaxassisga uzatildi:\n"
                f"{contacts_block}\n\n"
                "Quyidagi tugma orqali to'g'ridan-to'g'ri mas'ul mutaxassis bilan bog'lanishingiz mumkin:\n\n"
                "📸 <i>Iloji bo'lsa, ekranda chiqayotgan xatolik yozuvini rasmga olib tashlang.</i>"
            )
            esc_msg = adapt_to_user_script(esc_msg, user_script)
            kb = get_admin_contact_keyboard(inn=remembered_id)
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
        if found_fm and found_inn and found_inn in found_fm:
            found_inn = None

        # Agar mijoz «Yangi Texnologiyalar» DUK STIR raqamini (201589463) yuborgan bo'lsa
        if found_inn == YANGI_TEXNOLOGIYALAR_INN:
            yt_inn_msg = (
                f"⚠️ <b>Diqqat! Kiritilgan СТИР (<code>{YANGI_TEXNOLOGIYALAR_INN}</code>) — Davlat Soliq Qo'mitasi huzuridagi «Yangi Texnologiyalar» DUK ning STIR raqami hisoblanadi!</b>\n\n"
                "Iltimos, o'zingizning korxonangizga tegishli <b>9 xonali STIR (INN)</b> raqamingizni yuboring."
            )
            yt_inn_msg = adapt_to_user_script(yt_inn_msg, user_script)
            try:
                await message.reply(yt_inn_msg, parse_mode="HTML")
            except Exception:
                await message.reply(yt_inn_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, yt_inn_msg)
            return True

        # Agar mijoz xabarda yangi INN yozgan bo'lsa va u bazada topilmasa -> "0 so'm" demasdan, topilmaganini aytamiz!
        if found_inn:
            found_results = excel_manager.search(found_inn)
            if not found_results and not excel_manager.is_decommissioned(found_inn):
                nf_msg = (
                    f"❌ <b>СТИР (INN): <code>{found_inn}</code> bazadan topilmadi.</b>\n\n"
                    "Iltimos, korxonangizning 9 xonali СТИР (INN) yoki 14 xonali JSHSHIR raqami to'g'ri yozilganini tekshirib qayta yuboring.\n"
                    "👨‍💻 <i>Agar yangi mijoz bo'lsangiz yoki yordam kerak bo'lsa, «Usta kerak» deb yozing.</i>"
                )
                nf_msg = adapt_to_user_script(nf_msg, user_script)
                try:
                    await message.reply(nf_msg, parse_mode="HTML")
                except Exception:
                    await message.reply(nf_msg)
                user_memory.add_user_message(chat_id, user_id, text)
                user_memory.add_assistant_message(chat_id, user_id, nf_msg)
                return True
            user_memory.set_last_id(chat_id, user_id, found_inn)

        remembered_id = user_memory.get_last_id(chat_id, user_id)
        remembered_fm = found_fm or user_memory.get_last_fm(chat_id, user_id)

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

        if not results:
            nf_msg = (
                f"❌ <b>СТИР (INN): <code>{remembered_id}</code> bazadan topilmadi.</b>\n\n"
                "Iltimos, korxonangizning 9 xonali СТИР (INN) raqami to'g'ri kiritilganini tekshirib qayta yuboring.\n"
                "👨‍💻 <i>Yordam kerak bo'lsa, «Usta kerak» deb yozing.</i>"
            )
            nf_msg = adapt_to_user_script(nf_msg, user_script)
            try:
                await message.reply(nf_msg, parse_mode="HTML")
            except Exception:
                await message.reply(nf_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, nf_msg)
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
            except Exception:
                await message.reply(debt_resp)
            await send_monthly_account_post(bot, chat_id, script=user_script)
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

            await send_fiscal_sample_post(bot, message.chat.id)

            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, clear_msg)
            user_memory.set_last_topic(chat_id, user_id, "awaiting_fiscal_module")
            return True

        # Fiskal modul bor -> OFD litsenziyasini tekshirish
        ofd_reply = await ofd_bridge.query_fiscal_module(bot, remembered_fm)
        ofd_status = parse_ofd_reply_status(ofd_reply)
        if ofd_status == "unavailable":
            user_memory.set_annual_status(chat_id, user_id, has_debt=False, details="unavailable", unavailable=True)
            timeout_msg = (
                f"⏳ <b>Davlat Soliq (OFD) tizimi vaqtincha javob bermayapti.</b>\n\n"
                f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id}</code>)\n"
                f"🏛 <b>Fiskal modul:</b> <code>{remembered_fm}</code>\n\n"
                f"Soliq qo'mitasi (@ofd943_bot) tizimi bilan aloqa vaqtincha uzildi yoki serverda profilaktika ketmoqda.\n"
                f"Iltimos, birozdan so'ng qayta urinib ko'ring yoki kassa apparatingiz ekranidagi xatolikni rasmga olib yuboring."
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
            not_found_msg = format_ofd_annual_status(remembered_fm, ofd_reply, user_script)
            try:
                await message.reply(not_found_msg, parse_mode="HTML")
            except Exception:
                await message.reply(not_found_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, not_found_msg)
            return True

        user_memory.set_last_fm(chat_id, user_id, remembered_fm)
        has_ann_debt = (ofd_status == "debt")
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
            except Exception:
                await message.reply(ann_msg)
            await send_annual_account_post(bot, chat_id, script=user_script)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, ann_msg)
            user_memory.set_last_topic(chat_id, user_id, "annual_debt_exists")
            return True

        # =====================================================================
        # 3-BOSQICH: OYLIK VA YILLIK QARZ YO'Q! -> RASM SO'RASH YOKI ADMINGA UZATISH
        # =====================================================================
        last_photo = user_memory.get_last_photo(chat_id, user_id)
        kb = get_admin_contact_keyboard(inn=remembered_id)
        contacts_block = admin_manager.get_contacts_display(inn=remembered_id)

        if last_photo:
            # Rasm allaqachon mavjud -> barcha ma'lumotlar bilan birga zudlik bilan adminga uzatish
            step3_msg = (
                f"🟢 <b>To'lovlar bo'yicha hech qanday qarzdorlik yo'q!</b>\n\n"
                f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id}</code>)\n"
                f"🏛 <b>Fiskal modul:</b> <code>{remembered_fm}</code>\n"
                f"✅ <b>Oylik to'lov:</b> To'langan (0 so'm)\n"
                f"✅ <b>Yillik litsenziya:</b> Faol (Muddati joyida)\n\n"
                f"👨‍💻 <b>Iltimos kuting, barcha ma'lumotlaringiz (INN, Fiskal modul va apparat rasmi) hududingiz bo'yicha mas'ul adminga yuborildi!</b>\n\n"
                f"{contacts_block}\n\n"
                f"Mas'ul ustamiz tez orada siz bilan bog'lanadi yoki quyidagi tugma orqali to'g'ridan-to'g'ri yozishingiz mumkin:"
            )
        else:
            # Rasm hali olinmagan -> Ekran rasmini so'rash va internet/soat/reboot bo'yicha ko'rsatma berish
            step3_msg = (
                f"🟢 <b>To'lovlar bo'yicha hech qanday qarzdorlik yo'q!</b>\n\n"
                f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{remembered_id}</code>)\n"
                f"🏛 <b>Fiskal modul:</b> <code>{remembered_fm}</code>\n"
                f"✅ <b>Oylik abonent to'lovi:</b> To'langan (0 so'm)\n"
                f"✅ <b>Yillik Soliq (OFD) litsenziyasi:</b> Faol (Litsenziya muddati joyida)\n\n"
                f"{contacts_block}\n\n"
                f"📸 <b>Iltimos, apparat ekranidagi xatolik yozuvini rasmga olib yuboring!</b>\n\n"
                f"📌 <i>Shuningdek tekshirib ko'ring:</i>\n"
                f"1️⃣ <b>Internet aloqasi:</b> Wi-Fi yoki SIM-karta tarmog'i borligini;\n"
                f"2️⃣ <b>Soat va sana:</b> Hozirgi aniq vaqt to'g'riligini;\n"
                f"3️⃣ <b>Qayta yoqish:</b> Kassa apparatini o'chirib qayta yoqishni (Reboot).\n\n"
                f"👨‍💻 <b>Rasm tashlashingiz bilan barcha ma'lumotlar hududingiz bo'yicha mas'ul adminga to'liq yetkaziladi!</b>"
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
