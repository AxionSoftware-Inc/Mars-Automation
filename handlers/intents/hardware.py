import logging
from aiogram import types, Bot

from user_memory import user_memory
from translit_manager import adapt_to_user_script
from excel_manager import excel_manager
from handlers.debt import format_debt_response

logger = logging.getLogger(__name__)

SOURCE_CHANNEL_ID = -1001641871516  # @POS_Terminal_UzSmart_Bank

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


class HardwareIntentHandler:
    """Apparat nosozligi va xatoliklar bo'yicha 4 bosqichli standart tashxis modelini boshqaruvchi modul"""

    async def handle(self, message: types.Message, bot: Bot, user_script: str) -> bool:
        text = message.text.strip()
        lower_text = text.lower()
        user_id = message.from_user.id if message.from_user else 0
        chat_id = message.chat.id

        if not any(phrase in lower_text for phrase in DEVICE_ISSUE_PHRASES):
            return False

        remembered_id = user_memory.get_last_id(chat_id, user_id)
        if remembered_id:
            # 1-bosqich: Oylik va Yillik qarzdorlikni tekshirish
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
                return True

            total_debt = sum(item.get("debt", 0.0) for item in results) if results else 0.0

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
                return True
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
                return True
        else:
            # INN hali kiritilmagan: INN va kassa chekidagi Fiskal modulni so'rash
            guide_msg = (
                "🔍 <b>Qarzdorlik va apparat holatini tekshirish:</b>\n\n"
                "Kassa apparatlari to'xtab qolishining 60%+ sababi abonent yoki soliq to'lovidagi qarzdorlik bo'ladi.\n\n"
                "Iltimos, korxonangizning <b>СТИР (INN) raqamini yuboring</b> hamda iloji bo'lsa kassa chekining pastki qismidagi <b>Fiskal modul raqamini (LG... yoki YG...)</b> yuboring.\n\n"
                "💡 <i>Biz bir vaqtning o'zida «Mars» oylik abonent to'lovini hamda Davlat Soliq Qo'mitasi (OFD) yillik litsenziya muddatini to'liq tekshirib beramiz!</i>"
            )
            guide_msg = adapt_to_user_script(guide_msg, user_script)
            try:
                await message.reply(guide_msg, parse_mode="HTML")
            except Exception:
                await message.reply(guide_msg)
            user_memory.add_user_message(chat_id, user_id, text)
            user_memory.add_assistant_message(chat_id, user_id, guide_msg)
            return True

hardware_intent_handler = HardwareIntentHandler()
