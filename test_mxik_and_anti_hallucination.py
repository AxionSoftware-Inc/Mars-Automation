import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from payment_accounts import (
    classify_payment_intent,
    is_mxik_intent,
    get_mxik_guidance,
    MARS_POST_ID,
    MARS_VIDEO_ID,
    YANGI_TEXNOLOGIYALAR_POST_ID,
    YANGI_TEXNOLOGIYALAR_VIDEO_ID
)
from handlers.intents.billing import billing_intent_handler
from handlers.intents.mxik import mxik_intent_handler
from user_memory import user_memory
from ai_helper import generate_ai_reply_ex, _UNKNOWN_PHRASES


class TestMxikAndAntiHallucination(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        user_memory.clear()

    def test_01_debt_vs_payment_intent_differentiation(self):
        """'qarzim qancha' bilan 'oylikchi' / 'yillikchi' qat'iy ajratilishi shart"""
        # 1. Qarzdorlik so'rovlari -> None (rekvizit emas)
        self.assertIsNone(classify_payment_intent("qarzim qancha"))
        self.assertIsNone(classify_payment_intent("qancha qarzim bor"))
        self.assertIsNone(classify_payment_intent("qarzim bormi"))
        self.assertIsNone(classify_payment_intent("qancha qarzdorman"))
        self.assertIsNone(classify_payment_intent("қарзим қанча"))
        self.assertIsNone(classify_payment_intent("қанча қарзим бор"))

        # 2. Oylik hisob raqam so'rovlari -> 'monthly'
        self.assertEqual(classify_payment_intent("oylikchi"), "monthly")
        self.assertEqual(classify_payment_intent("oylik shot"), "monthly")
        self.assertEqual(classify_payment_intent("marsga to'lov"), "monthly")
        self.assertEqual(classify_payment_intent("oylik rekvizit"), "monthly")
        self.assertEqual(classify_payment_intent("ойликчи"), "monthly")
        self.assertEqual(classify_payment_intent("ойлик шот"), "monthly")

        # 3. Yillik hisob raqam so'rovlari -> 'annual'
        self.assertEqual(classify_payment_intent("yillikchi"), "annual")
        self.assertEqual(classify_payment_intent("yillik shot"), "annual")
        self.assertEqual(classify_payment_intent("fiskal modul shot"), "annual")
        self.assertEqual(classify_payment_intent("yangi texnologiyalar shot"), "annual")
        self.assertEqual(classify_payment_intent("йилликчи"), "annual")
        self.assertEqual(classify_payment_intent("йиллик шот"), "annual")

    def test_02_mxik_intent_recognition(self):
        """MXIK va soliq sayti so'rovlari to'g'ri tanilishi kerak"""
        self.assertTrue(is_mxik_intent("mxik kod nima"))
        self.assertTrue(is_mxik_intent("soliq saytidan kod qanday olinadi"))
        self.assertTrue(is_mxik_intent("tovar kodi qayerdan olinadi"))
        self.assertTrue(is_mxik_intent("tasnifdan kod olish"))
        self.assertTrue(is_mxik_intent("tovarlar bazasi yuklash"))
        self.assertTrue(is_mxik_intent("chekni bekor qilish otkaz"))
        self.assertTrue(is_mxik_intent("qqs stavkasi 12%"))
        self.assertTrue(is_mxik_intent("солиқ сайтидан код"))
        self.assertTrue(is_mxik_intent("база юклаш"))

    def test_03_mxik_guidance_and_video_mapping(self):
        """MXIK bo'yicha har bir mavzuga mos rasmiy video biriktirilishi va soxta kod to'qilmasligi"""
        # Soliq saytidan qidirish (Post 28)
        text_28, vid_28 = get_mxik_guidance("soliq saytidan kod qayerdan olinadi")
        self.assertEqual(vid_28, 28)
        self.assertIn("tasnif.soliq.uz", text_28)

        # Aniq tovar kodi so'ralsa ham tasnif saytiga yo'naltirishi shart (Post 28)
        text_bread, vid_bread = get_mxik_guidance("nonning mxik kodi qanaqa")
        self.assertEqual(vid_bread, 28)
        self.assertIn("tasnif.soliq.uz", text_bread)
        # Soxta kod to'qilmagan bo'lishi kerak
        self.assertNotIn("1234567890", text_bread)

        # Tovar qo'shish (Post 15)
        text_15, vid_15 = get_mxik_guidance("tovar qo'shish tartibi")
        self.assertEqual(vid_15, 15)

        # Soliq jarimasi va xato kod (Post 17)
        text_17, vid_17 = get_mxik_guidance("xato kod soliq jarima")
        self.assertEqual(vid_17, 17)

        # Zapravka / naqd cheklovi (Post 133)
        text_133, vid_133 = get_mxik_guidance("zapravkada naqdga chek urish")
        self.assertEqual(vid_133, 133)

        # Otkaz / bekor qilish (Post 53)
        text_53, vid_53 = get_mxik_guidance("tovarni otkaz qilish qaytadan urish")
        self.assertEqual(vid_53, 53)

        # QQS stavkasi (Post 89)
        text_89, vid_89 = get_mxik_guidance("qqs stavka 12%")
        self.assertEqual(vid_89, 89)

        # Tovarlar bazasini yuklash (Post 138)
        text_138, vid_138 = get_mxik_guidance("exceldan tovarlar bazasini yuklash")
        self.assertEqual(vid_138, 138)

    async def test_04_mxik_handler_execution(self):
        """mxik_intent_handler xabar kelganda to'g'ri javob va videoni uzatishi kerak"""
        bot = AsyncMock()
        bot.copy_message = AsyncMock()

        msg = MagicMock()
        msg.text = "soliq saytidan kod qayerdan olinadi"
        msg.chat.id = 12345
        msg.from_user.id = 12345
        msg.message_id = 999
        msg.reply = AsyncMock()

        handled = await mxik_intent_handler.handle(msg, bot, user_script="latin")
        self.assertTrue(handled)
        msg.reply.assert_called_once()
        self.assertIn("tasnif.soliq.uz", msg.reply.call_args[0][0])
        # Video 28 nusxalanishi kerak
        bot.copy_message.assert_called_once_with(
            chat_id=12345,
            from_chat_id=-1001641871516,
            message_id=28,
            reply_to_message_id=999
        )

    async def test_05_billing_flow_oylikchi_and_yillikchi(self):
        """'oylikchi' va 'yillikchi' alohida kanaldan post va video uzatishi kerak"""
        bot = AsyncMock()
        bot.copy_message = AsyncMock()

        # 1. "oylikchi"
        msg_oylik = MagicMock()
        msg_oylik.text = "oylikchi"
        msg_oylik.chat.id = 12345
        msg_oylik.from_user.id = 12345
        msg_oylik.message_id = 101

        handled = await billing_intent_handler.handle(msg_oylik, bot, user_script="latin")
        self.assertTrue(handled)
        self.assertEqual(bot.copy_message.call_count, 2)
        call_ids = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
        self.assertIn(MARS_POST_ID, call_ids)
        self.assertIn(MARS_VIDEO_ID, call_ids)

        # 2. "yillikchi"
        bot.copy_message.reset_mock()
        msg_yillik = MagicMock()
        msg_yillik.text = "yillikchi"
        msg_yillik.chat.id = 12345
        msg_yillik.from_user.id = 12345
        msg_yillik.message_id = 102

        handled = await billing_intent_handler.handle(msg_yillik, bot, user_script="latin")
        self.assertTrue(handled)
        self.assertEqual(bot.copy_message.call_count, 2)
        call_ids_ann = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
        self.assertIn(YANGI_TEXNOLOGIYALAR_POST_ID, call_ids_ann)
        self.assertIn(YANGI_TEXNOLOGIYALAR_VIDEO_ID, call_ids_ann)

    async def test_06_billing_handler_ignores_qarzim_qancha(self):
        """'qarzim qancha' BillingIntentHandler da to'lov posti bo'lib ketmasligi shart"""
        bot = AsyncMock()
        bot.copy_message = AsyncMock()

        msg_debt = MagicMock()
        msg_debt.text = "qarzim qancha"
        msg_debt.chat.id = 12345
        msg_debt.from_user.id = 12345
        msg_debt.message_id = 103

        # Foydalanuvchida hali INN yo'q, shuning uchun BillingIntentHandler False qaytarib, ConversationHandler ga o'tishi kerak
        handled = await billing_intent_handler.handle(msg_debt, bot, user_script="latin")
        self.assertFalse(handled)
        bot.copy_message.assert_not_called()

    def test_07_anti_hallucination_unknown_phrases(self):
        """AI noma'lum savolda needs_admin=True qaytarishi kafolatlanishi kerak"""
        # Test 1: [ADMINGA_SAVOL] tegi bilan
        with patch("ai_helper.openrouter_client.chat_completion", return_value="Bu savol bo'yicha menda ma'lumot yo'q. [ADMINGA_SAVOL]"):
            reply, vid, needs_admin = generate_ai_reply_ex("Kassirni qanday ishga olaman?")
            self.assertTrue(needs_admin)
            self.assertNotIn("[ADMINGA_SAVOL]", reply)

        # Test 2: AI teg qo'yishni unutgan taqdirda ham _UNKNOWN_PHRASES ishlashi
        with patch("ai_helper.openrouter_client.chat_completion", return_value="Bu masala bo'yicha menda aniq ma'lumot yo'q, mutaxassisimizga yubordim"):
            reply, vid, needs_admin = generate_ai_reply_ex("Soliq tekshiruvi qachon keladi?")
            self.assertTrue(needs_admin)


if __name__ == "__main__":
    unittest.main()
