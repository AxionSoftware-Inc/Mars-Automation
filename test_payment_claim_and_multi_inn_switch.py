import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from user_memory import user_memory
from payment_accounts import is_payment_claim
from core.group_responder import group_responder
from modules.admin_module import regional_admin_service

class TestPaymentClaimAndMultiINNSwitch(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        user_memory.sessions.clear()

    def test_01_is_payment_claim_detection(self):
        """'tuladim', 'to'ladim', 'to'lov qildim' kabi to'lov da'volari aniqlanishi"""
        # Ijobiy holatlar (to'lov qilindi)
        self.assertTrue(is_payment_claim("tuladim"))
        self.assertTrue(is_payment_claim("to'ladim"))
        self.assertTrue(is_payment_claim("toladim"))
        self.assertTrue(is_payment_claim("туладим"))
        self.assertTrue(is_payment_claim("to'lov qildim"))
        self.assertTrue(is_payment_claim("pul o'tkazdim"))
        self.assertTrue(is_payment_claim("to'lab bo'ldik"))
        self.assertTrue(is_payment_claim("to'lab qo'ydim"))
        self.assertTrue(is_payment_claim("clickdan to'ladim"))
        self.assertTrue(is_payment_claim("302568138 ga to'ladim"))
        self.assertTrue(is_payment_claim("oylikni to'ladim"))

        # Salbiy holatlar (savol yoki kelgusi niyat)
        self.assertFalse(is_payment_claim("to'lamoqchiman"))
        self.assertFalse(is_payment_claim("tulamoqchiman"))
        self.assertFalse(is_payment_claim("qanday to'lanadi"))
        self.assertFalse(is_payment_claim("qayerga to'layman"))
        self.assertFalse(is_payment_claim("to'lash kerakmi"))
        self.assertFalse(is_payment_claim("to'lasam bo'ladimi"))

    async def test_02_tuladim_asks_receipt_not_accepts(self):
        """'tuladim' yoki 'to'ladim' yozilganda kvitansiya so'rashi va yolg'on 'qabul qilindi' demasligi"""
        from aiogram import types
        chat_id = -100123456789
        user_id = 998877

        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.copy_message = AsyncMock()

        msg = MagicMock(spec=types.Message)
        msg.chat = MagicMock(spec=types.Chat)
        msg.chat.id = chat_id
        msg.chat.type = "supergroup"
        msg.from_user = MagicMock(spec=types.User)
        msg.from_user.id = user_id
        msg.from_user.username = "test_payer"
        msg.from_user.first_name = "Payer"
        msg.text = "tuladim"
        msg.reply_to_message = None
        msg.message_id = 9999
        msg.reply = AsyncMock()
        msg.answer = AsyncMock()

        mock_ai = AsyncMock(return_value="AI JAVOBI")
        handled = await group_responder.process_message(msg, bot, ai_func=mock_ai)
        self.assertTrue(handled)
        mock_ai.assert_not_called()
        msg.reply.assert_called_once()
        reply_text = msg.reply.call_args[0][0]

        # Javob kvitansiyani so'rashi kerak
        self.assertIn("to'lov kvitansiyasini", reply_text.lower())

        # Kvitansiya qabul qilindi yoki adminga yuborildi degan xato bo'lmasligi kerak
        self.assertNotIn("kvitansiyangiz qabul qilindi", reply_text.lower())
        self.assertNotIn("adminga yuborilgan", reply_text.lower())

    def test_03_multi_inn_switch_resets_previous_context_and_photos(self):
        """Bir kishi 2-3 ta INN tekshirganda, har yangi INN eskisi bo'yicha rasm va so'rovlarni unutishi"""
        chat_id = -100999
        user_id = 112233

        # 1-bosqich: Foydalanuvchi INN 1 (302568138) ni tekshirdi va unga rasm/kvitansiya tashladi
        user_memory.set_last_id(chat_id, user_id, "302568138", org_name="KORXONA 1", debt=200000.0)
        user_memory.set_last_photo(chat_id, user_id, "file_photo_inn_1")
        user_memory.set_last_receipt(chat_id, user_id, {"amount": 200000.0})
        user_memory.set_issue_mode(chat_id, user_id, True, initial_query="Ekran qotib qoldi")
        user_memory.add_user_message(chat_id, user_id, "Eski korxonam bo'yicha savol")

        # Tekshiramiz: INN 1 ma'lumotlari xotirada bor
        self.assertEqual(user_memory.get_last_id(chat_id, user_id), "302568138")
        self.assertEqual(user_memory.get_last_photo(chat_id, user_id), "file_photo_inn_1")
        self.assertEqual(len(user_memory.get_all_photos(chat_id, user_id)), 1)
        self.assertTrue(user_memory.is_issue_mode(chat_id, user_id))

        # 2-bosqich: Foydalanuvchi endi yangi INN 2 (311790999) ni kiritdi!
        user_memory.set_last_id(chat_id, user_id, "311790999", org_name="KORXONA 2", debt=0.0)

        # Qat'iy tekshiruv: Yangi INN kiritilgach, eski INN 1 bo'yicha rasm, kvitansiya va muammolar UNUTILISHI SHART!
        self.assertEqual(user_memory.get_last_id(chat_id, user_id), "311790999")
        self.assertEqual(user_memory.get_org_name(chat_id, user_id), "KORXONA 2")
        self.assertIsNone(user_memory.get_last_photo(chat_id, user_id), "Eski INN 1 ning rasmi o'chirilishi shart!")
        self.assertEqual(user_memory.get_all_photos(chat_id, user_id), [], "Eski rasmlar ro'yxati bo'sh bo'lishi shart!")
        self.assertIsNone(user_memory.get_last_receipt(chat_id, user_id), "Eski kvitansiya o'chirilishi shart!")
        self.assertFalse(user_memory.is_issue_mode(chat_id, user_id), "Eski INN muammo rejimi o'chirilishi shart!")

    def test_04_admin_keyboard_has_no_invalid_tel_urls(self):
        """Telegram Bot API 'tel:' URL larga ruxsat bermaydi (Bad Request beradi). Keyboard tekshiruvi."""
        user_mock = MagicMock()
        user_mock.username = "testuser"
        user_mock.id = 12345

        kb = regional_admin_service.build_user_contact_keyboard_for_admin(user=user_mock, phone="+998938900990")
        self.assertIsNotNone(kb)

        # Barcha inline buttonlarni tekshiramiz
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.url:
                    self.assertFalse(btn.url.startswith("tel:"), f"Bad Request xatosi beruvchi 'tel:' URL topildi: {btn.url}")
                    self.assertTrue(btn.url.startswith("https://") or btn.url.startswith("tg://"), f"Yaroqsiz URL: {btn.url}")

    async def test_05_multi_inn_escalation_does_not_send_old_photo(self):
        """INN 1 tashlab rasm yuborilgan bo'lsa, keyin INN 2 tekshirilib adminga eskalatsiya qilinganda eski rasm ketmasligi kerak"""
        from admin_manager import admin_manager
        from aiogram import types
        chat_id = -100778899
        user_id = 554433

        # INN 1 va uning rasmi
        user_memory.set_last_id(chat_id, user_id, "302568138", org_name="ESKI KORXONA 1", debt=100000.0)
        user_memory.set_last_photo(chat_id, user_id, "file_id_inn_1_old")

        # Keyin INN 2 tekshirildi (qarz 0)
        user_memory.set_last_id(chat_id, user_id, "311790999", org_name="YANGI KORXONA 2", debt=0.0)

        # Endi foydalanuvchi "usta kerak" deb yozdi
        bot = MagicMock()
        bot.send_message = AsyncMock()
        bot.copy_message = AsyncMock()
        bot.send_photo = AsyncMock()

        orig_notify = admin_manager.notify_user_query_escalation
        admin_manager.notify_user_query_escalation = AsyncMock()

        try:
            msg = MagicMock(spec=types.Message)
            msg.chat = MagicMock(spec=types.Chat)
            msg.chat.id = chat_id
            msg.chat.type = "supergroup"
            msg.from_user = MagicMock(spec=types.User)
            msg.from_user.id = user_id
            msg.from_user.username = "multi_inn_user"
            msg.from_user.first_name = "User"
            msg.text = "usta kerak"
            msg.reply_to_message = None
            msg.message_id = 8888
            msg.reply = AsyncMock()
            msg.answer = AsyncMock()

            handled = await group_responder.process_message(msg, bot)
            self.assertTrue(handled)

            # Eskalatsiya chaqirilganini tekshiramiz
            admin_manager.notify_user_query_escalation.assert_called_once()
            call_kwargs = admin_manager.notify_user_query_escalation.call_args[1]

            # Eskalatsiyadagi INN yangi INN 2 (311790999) bo'lishi shart!
            self.assertEqual(call_kwargs.get("inn"), "311790999")
            # Eski INN 1 ning rasmi yuborilmasligi (None bo'lishi) shart!
            self.assertIsNone(call_kwargs.get("photo_file_id"))
        finally:
            admin_manager.notify_user_query_escalation = orig_notify

if __name__ == "__main__":
    unittest.main()
