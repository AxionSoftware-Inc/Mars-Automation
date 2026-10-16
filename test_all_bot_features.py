import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import types
from handlers.chat import handle_user_chat
from user_memory import user_memory
from excel_manager import excel_manager
from payment_accounts import (
    MARS_POST_ID,
    MARS_VIDEO_ID,
    YANGI_TEXNOLOGIYALAR_POST_ID,
    YANGI_TEXNOLOGIYALAR_VIDEO_ID,
    FISKAL_MODUL_SAMPLE_POST_ID,
    classify_payment_intent,
    is_monthly_pay_intent,
    is_annual_pay_intent
)


class TestAllBotFeaturesComprehensive(unittest.IsolatedAsyncioTestCase):
    """
    Botning barcha asosiy funksiyalarini xuddi jonli foydalanuvchi kabi
    so'rab tekshiruvchi to'liq test to'plami.
    """

    def setUp(self):
        user_memory.clear()
        self.chat_id = -1003742874507
        self.user_id = 123456789
        self._msg_counter = 500

    async def _send(self, bot, text: str) -> MagicMock:
        msg = MagicMock(spec=types.Message)
        msg.text = text
        msg.caption = None
        msg.photo = None
        msg.document = None
        msg.chat = MagicMock(id=self.chat_id)
        msg.from_user = MagicMock(id=self.user_id, full_name="Test Foydalanuvchi", username="test_user")
        self._msg_counter += 1
        msg.message_id = self._msg_counter
        msg.reply = AsyncMock()
        msg.answer = AsyncMock()

        await handle_user_chat(msg, bot)
        return msg

    async def test_scenario_1_zero_debt_and_payment_requests(self):
        """1-STSENARIY: Qarzi 0 bo'lgan mijoz shot so'rashi"""
        bot = AsyncMock()
        bot.copy_message = AsyncMock()
        bot.send_message = AsyncMock()

        print("\n--- 1-STSENARIY: Qarzi 0 bo'lganda shot so'rash ---")
        
        # 1. INN tekshirish (qarz 0)
        # Baza qidiruvi: agar 300600431 bo'lmasa, qarz 0 bo'lgan biror INN
        inn_rec = excel_manager.search("300600431")
        inn_debt = sum(r.get("debt", 0.0) for r in inn_rec) if inn_rec else 0.0
        
        msg1 = await self._send(bot, "300600431")
        last_topic = user_memory.get_last_topic(self.chat_id, self.user_id)
        self.assertIn(last_topic, ("monthly_debt_clear", "debt_checked", "monthly_debt_exists"))
        print(f"1. INN 300600431 yuborildi -> topic={last_topic}")

        # 2. 'shot tashlab beriyla' -> Mars Post 85 va Video 148 uzatilishi shart!
        bot.copy_message.reset_mock()
        await self._send(bot, "shot tashlab beriyla")
        copied_ids = [call.kwargs.get("message_id") for call in bot.copy_message.call_args_list]
        self.assertIn(MARS_POST_ID, copied_ids, "Post 85 uzatilmadi!")
        print(f"2. 'shot tashlab beriyla' -> Post {MARS_POST_ID} muvaffaqiyatli uzatildi ✅")

        # 3. 'oylik tulamoqchiman' -> yana Post 85 uzatilishi kerak
        bot.copy_message.reset_mock()
        await self._send(bot, "oylik tulamoqchiman")
        copied_ids = [call.kwargs.get("message_id") for call in bot.copy_message.call_args_list]
        self.assertIn(MARS_POST_ID, copied_ids, "Oylik tulamoqchimanga Post 85 uzatilmadi!")
        print(f"3. 'oylik tulamoqchiman' -> Post {MARS_POST_ID} uzatildi ✅")

        # 4. 'mayli kiyingi oy uchun tulab quymoqchiman' -> yana Post 85
        bot.copy_message.reset_mock()
        await self._send(bot, "mayli kiyingi oy uchun tulab quymoqchiman")
        copied_ids = [call.kwargs.get("message_id") for call in bot.copy_message.call_args_list]
        self.assertIn(MARS_POST_ID, copied_ids, "Keyingi oy to'loviga Post 85 uzatilmadi!")
        print(f"4. 'mayli kiyingi oy uchun tulab quymoqchiman' -> Post {MARS_POST_ID} uzatildi ✅")

        # 5. 'shot tashlab ber' -> yana Post 85
        bot.copy_message.reset_mock()
        await self._send(bot, "shot tashlab ber")
        copied_ids = [call.kwargs.get("message_id") for call in bot.copy_message.call_args_list]
        self.assertIn(MARS_POST_ID, copied_ids, "shot tashlab ber ga Post 85 uzatilmadi!")
        print(f"5. 'shot tashlab ber' -> Post {MARS_POST_ID} uzatildi ✅")

    async def test_scenario_2_debt_exists_and_detailed_inquiry(self):
        """2-STSENARIY: Qarzi bor korxona va keyingi savollar"""
        bot = AsyncMock()
        bot.copy_message = AsyncMock()
        bot.send_message = AsyncMock()

        print("\n--- 2-STSENARIY: Qarzi bor korxona zanjiri ---")
        
        # 206011507 INN qarzli (2 100 000 so'm)
        await self._send(bot, "206011507")
        debt_info = user_memory.get_debt_info(self.chat_id, self.user_id)
        self.assertIsNotNone(debt_info)
        self.assertGreater(debt_info["debt"], 0)
        print(f"1. INN 206011507 tekshirildi -> Qarz: {debt_info['debt']:,.0f} so'm")

        # Qancha to'lay?
        msg2 = await self._send(bot, "qancha tolay")
        reply2 = (msg2.reply.call_args[0][0] if msg2.reply.called else msg2.answer.call_args[0][0]).lower()
        self.assertNotIn("qarzingiz yo'q (0 so'm)", reply2)
        print(f"2. 'qancha tolay' -> Javobda qarz summasi saqlandi ✅")

        # Qayerga to'lashim kerak? -> Post 85 uzatilishi shart
        bot.copy_message.reset_mock()
        await self._send(bot, "qayerga to'lashim kerak")
        copied_ids = [call.kwargs.get("message_id") for call in bot.copy_message.call_args_list]
        self.assertIn(MARS_POST_ID, copied_ids, "Qarzi bor mijozga Post 85 uzatilmadi!")
        print(f"3. 'qayerga to'lashim kerak' -> Post {MARS_POST_ID} uzatildi ✅")

    async def test_scenario_3_annual_flow_with_fiscal_module(self):
        """3-STSENARIY: Yillik to'lov va Fiskal modul orqali tekshirish"""
        bot = AsyncMock()
        bot.copy_message = AsyncMock()
        bot.send_message = AsyncMock()

        print("\n--- 3-STSENARIY: Fiskal modul va Yillik to'lov ---")

        # 1. "yillik tolovni tekshir" -> Bot FM raqamini so'rashi kerak (Post 149 namunasi bilan)
        msg1 = await self._send(bot, "yillik to'lovni tekshirib bering")
        reply1 = msg1.reply.call_args[0][0] if msg1.reply.called else msg1.answer.call_args[0][0]
        self.assertIn("Fiskal modul", reply1)
        copied_ids = [call.kwargs.get("message_id") for call in bot.copy_message.call_args_list]
        self.assertIn(FISKAL_MODUL_SAMPLE_POST_ID, copied_ids, "FM namunaviy rasmi (Post 149) yuborilmadi!")
        print(f"1. 'yillik tolovni tekshir' -> FM so'raldi va Post {FISKAL_MODUL_SAMPLE_POST_ID} namunasi uzatildi ✅")

        # 2. Foydalanuvchi FM kodini yuboradi: LG420210630789
        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", return_value="Fiskal modul: LG420210630789\nHolati: To'langan va faol"):
            msg2 = await self._send(bot, "LG420210630789")
            reply2 = msg2.reply.call_args[0][0] if msg2.reply.called else msg2.answer.call_args[0][0]
            self.assertIn("LG420210630789", reply2)
            print(f"2. FM LG420210630789 yuborildi -> OFD javobi berildi ✅")

        # 3. Yillik to'lov shotini so'rash
        bot.copy_message.reset_mock()
        await self._send(bot, "yillik to'lov shotini tashlang")
        copied_ids = [call.kwargs.get("message_id") for call in bot.copy_message.call_args_list]
        self.assertIn(YANGI_TEXNOLOGIYALAR_POST_ID, copied_ids, "Yillik post 34 uzatilmadi!")
        print(f"3. 'yillik to'lov shotini tashlang' -> Post {YANGI_TEXNOLOGIYALAR_POST_ID} uzatildi ✅")

    async def test_scenario_4_both_accounts_and_single_account_warning(self):
        """4-STSENARIY: Ikkala hisob raqam va bitta hisobga to'lash taqiqi"""
        bot = AsyncMock()
        bot.copy_message = AsyncMock()
        bot.send_message = AsyncMock()

        print("\n--- 4-STSENARIY: Ikkala hisob raqam so'rovi ---")

        # 1. Kontekstsiz umumiy shot so'rash
        user_memory.clear()
        bot.copy_message.reset_mock()
        await self._send(bot, "hsob raqamlarni tashlang")
        copied_ids = [call.kwargs.get("message_id") for call in bot.copy_message.call_args_list]
        self.assertIn(MARS_POST_ID, copied_ids, "Post 85 uzatilmadi!")
        self.assertIn(YANGI_TEXNOLOGIYALAR_POST_ID, copied_ids, "Post 34 uzatilmadi!")
        print(f"1. 'hsob raqamlarni tashlang' -> Ikkala post ({MARS_POST_ID} va {YANGI_TEXNOLOGIYALAR_POST_ID}) uzatildi ✅")

        # 2. Ikkala to'lovni bitta hisobga to'lash mumkinmi?
        bot.copy_message.reset_mock()
        msg2 = await self._send(bot, "ikkala tolovni bitta hisob raqamga tolasam boladimi?")
        reply2 = msg2.reply.call_args[0][0] if msg2.reply.called else msg2.answer.call_args[0][0]
        self.assertIn("bo'lmaydi", reply2.lower())
        copied_ids = [call.kwargs.get("message_id") for call in bot.copy_message.call_args_list]
        self.assertIn(MARS_POST_ID, copied_ids)
        self.assertIn(YANGI_TEXNOLOGIYALAR_POST_ID, copied_ids)
        print(f"2. Bitta hisobga to'lash so'rovi -> Qat'iy rad etildi va har ikkala post yuborildi ✅")

    async def test_scenario_5_strict_separation_no_sermon(self):
        """5-STSENARIY: Oylik uchun INN, Yillik uchun FM talab qilinishi (qisqa, dostonlarsiz)"""
        bot = AsyncMock()
        bot.copy_message = AsyncMock()

        print("\n--- 5-STSENARIY: Qisqa va lo'nda javoblar (doston yozmaslik) ---")

        # Oylik tekshirish so'ralsa:
        msg1 = await self._send(bot, "oylik to'lovni tekshirib bering")
        reply1 = msg1.reply.call_args[0][0] if msg1.reply.called else msg1.answer.call_args[0][0]
        self.assertIn("INN", reply1)
        self.assertLess(len(reply1.splitlines()), 6, "Oylik tekshiruv so'rovi juda uzun doston bo'lmasligi kerak!")
        print(f"1. Oylik tekshiruv javobi: lo'nda va 3 qator ✅")

        # Yillik tekshirish so'ralsa:
        msg2 = await self._send(bot, "yillik tekshiruv")
        reply2 = msg2.reply.call_args[0][0] if msg2.reply.called else msg2.answer.call_args[0][0]
        self.assertIn("Fiskal modul", reply2)
        self.assertLess(len(reply2.splitlines()), 10, "Yillik tekshiruv so'rovi juda uzun doston bo'lmasligi kerak!")
        print(f"2. Yillik tekshiruv javobi: lo'nda va tushunarli ✅")

    async def test_scenario_6_operator_and_usta(self):
        """6-STSENARIY: Operator va usta chaqirish"""
        bot = AsyncMock()

        print("\n--- 6-STSENARIY: Operator va Usta intentlari ---")

        msg = await self._send(bot, "operator kerak")
        reply = msg.reply.call_args[0][0] if msg.reply.called else msg.answer.call_args[0][0]
        self.assertIn("operator", reply.lower())
        print(f"1. Operator chaqiruvi muvaffaqiyatli ✅")

        msg_usta = await self._send(bot, "menga usta kerak bog'lanish uchun")
        reply_usta = msg_usta.reply.call_args[0][0] if msg_usta.reply.called else msg_usta.answer.call_args[0][0]
        self.assertTrue(any(w in reply_usta.lower() for w in ["usta", "mutaxassis", "administrator", "bog'lan"]))
        print(f"2. Usta so'rovi muvaffaqiyatli ✅")

    async def test_scenario_7_due_dates_vs_payment_intents(self):
        """7-STSENARIY: Muddat so'rovi va to'lov intenti farqlanishi"""
        bot = AsyncMock()
        bot.copy_message = AsyncMock()

        print("\n--- 7-STSENARIY: Muddat (qachongacha) so'rovi ---")

        # "qachon to'layman" -> Muddat aytilishi kerak (6-sana), shot posti darhol tashlanmasligi kerak
        msg = await self._send(bot, "oylik to'lovni qachongacha to'lash kerak?")
        reply = msg.reply.call_args[0][0] if msg.reply.called else msg.answer.call_args[0][0]
        self.assertTrue(any(w in reply for w in ["6", "sana", "muddat"]))
        print(f"1. 'qachongacha to'lash kerak' -> Muddat (6-sana) to'g'ri tushuntirildi ✅")

    async def test_scenario_8_mxik_questions(self):
        """8-STSENARIY: MXIK va Tasnif savollari"""
        bot = AsyncMock()

        print("\n--- 8-STSENARIY: MXIK va Soliq talabi ---")

        msg = await self._send(bot, "mxik kodni qayerdan olsam bo'ladi?")
        reply = msg.reply.call_args[0][0] if msg.reply.called else msg.answer.call_args[0][0]
        self.assertTrue(any(w in reply.lower() for w in ["mxik", "tasnif", "soliq"]))
        print(f"1. MXIK so'rovi muvaffaqiyatli ✅")

    async def test_scenario_9_multi_inn_tracking(self):
        """9-STSENARIY: Bir nechta INN ketma-ket tekshirilganda adashmaslik"""
        bot = AsyncMock()

        print("\n--- 9-STSENARIY: Bir nechta INN xotirasi ---")

        # 1-korxona (300600431 - qarz 0)
        await self._send(bot, "300600431")
        # 2-korxona (206011507 - qarzli)
        await self._send(bot, "206011507")

        # Qaysi birida qarz borligini so'rash
        msg = await self._send(bot, "qaysi birida qarz bor?")
        reply = msg.reply.call_args[0][0] if msg.reply.called else msg.answer.call_args[0][0]
        self.assertIn("206011507", reply)
        print(f"1. Ko'p korxona taqqoslash javobi to'g'ri berildi ✅")


if __name__ == "__main__":
    unittest.main()
