import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram import types
from payment_accounts import (
    is_annual_check_intent,
    is_monthly_check_intent,
    is_both_check_intent,
    is_annual_pay_intent,
    is_monthly_pay_intent,
    classify_payment_intent
)
from catalog_manager import catalog_manager
from user_memory import user_memory
from handlers.chat import handle_user_chat

def create_mock_message(text: str, chat_id: int = 778899, user_id: int = 112233) -> types.Message:
    msg = MagicMock(spec=types.Message)
    msg.text = text
    msg.caption = None
    msg.photo = None
    msg.document = None
    msg.message_id = 100
    msg.chat = MagicMock(spec=types.Chat)
    msg.chat.id = chat_id
    msg.chat.type = "group"
    msg.from_user = MagicMock(spec=types.User)
    msg.from_user.id = user_id
    msg.from_user.username = "test_merchant"
    msg.from_user.first_name = "Merchant"
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()
    return msg

class TestSequentialDebtFlow(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        user_memory.clear_context(778899, 112233)

    def test_01_intent_classification_sequential_words(self):
        """Davomiy va ketma-ket savollar aniq intentlarga tushishi shart"""
        # Yillik tekshiruvlar
        self.assertTrue(is_annual_check_intent("yilikdan qarzim bormi"))
        self.assertTrue(is_annual_check_intent("yillikdan qarzim bormi"))
        self.assertTrue(is_annual_check_intent("yillikdanchi"))
        self.assertTrue(is_annual_check_intent("yillikchi"))
        self.assertTrue(is_annual_check_intent("fiskaldanchi"))
        self.assertTrue(is_annual_check_intent("soliqdanchi"))
        self.assertTrue(is_annual_check_intent("йилликданчи"))
        self.assertTrue(is_annual_check_intent("фискалданчи"))

        # Oylik tekshiruvlar
        self.assertTrue(is_monthly_check_intent("oylikdanchi"))
        self.assertTrue(is_monthly_check_intent("oylikchi"))
        self.assertTrue(is_monthly_check_intent("oylikdan qarzim bormi"))
        self.assertTrue(is_monthly_check_intent("oylik qarzim bormi"))
        self.assertTrue(is_monthly_check_intent("marsdan qarzim bormi"))
        self.assertTrue(is_monthly_check_intent("oylik qarzdorlik bormi"))
        self.assertTrue(is_monthly_check_intent("ойликданчи"))
        self.assertTrue(is_monthly_check_intent("ойликчи"))
        self.assertTrue(is_monthly_check_intent("марсдан қарзим борми"))

        # Ikkala to'lov tekshiruvi
        self.assertTrue(is_both_check_intent("ikkalasidanchi"))
        self.assertTrue(is_both_check_intent("umumiy qarzim bormi"))
        self.assertTrue(is_both_check_intent("jami qarzim bormi"))
        self.assertTrue(is_both_check_intent("иккаласиданчи"))

        # To'lov intenti qarz so'rovlarini o'zlashtirib olmasligi kerak
        self.assertIsNone(classify_payment_intent("oylikdanchi"))
        self.assertIsNone(classify_payment_intent("oylikdan qarzim bormi"))
        self.assertIsNone(classify_payment_intent("yillikdan qarzim bormi"))

    def test_02_catalog_manager_guards(self):
        """Katalog menejeri qarz/oylik/yillik savollarga video bermasligi shart"""
        self.assertIsNone(catalog_manager.find_matching_post("oylikdanchi"))
        self.assertIsNone(catalog_manager.find_matching_post("oylikchi"))
        self.assertIsNone(catalog_manager.find_matching_post("oylikdan qarzim bormi"))
        self.assertIsNone(catalog_manager.find_matching_post("yillikdanchi"))
        self.assertIsNone(catalog_manager.find_matching_post("fiskaldanchi"))
        self.assertIsNone(catalog_manager.find_matching_post("qarzim bormi"))

        # Faqat aniq video so'ralsa video berilishi mumkin
        vid = catalog_manager.find_matching_post("oylik to'lov qilish videosini tashla")
        self.assertEqual(vid, 148)

    @patch("ofd_bridge.ofd_bridge.query_fiscal_module")
    async def test_03_exact_user_scenario_sequential(self, mock_ofd):
        """
        Foydalanuvchi muammosi:
        1. 'yilikdan qarzim bormi' -> Fiskal modul so'raydi.
        2. 'oylikdanchi' -> Oylik qarz uchun INN so'raydi (video 148 EMAS!).
        3. '302568138' -> Oylik holatini chiqaradi.
        4. 'yillikdanchi' -> Fiskal modul so'raydi.
        5. 'UZ200701040469' -> OFD dan tekshiradi va qarzdorlikni ko'rsatadi.
        6. 'to'layman' -> Yangi Texnologiyalar yillik to'lov kartasini yuboradi.
        """
        mock_ofd.return_value = "Fiskal modul faol holatda. Lekin, VMQ-943 ga ko‘ra FMO dan qarzdorlik mavjud."
        bot = MagicMock()
        bot.copy_message = AsyncMock()

        chat_id = 778899
        user_id = 112233

        # 1-qadam: yilikdan qarzim bormi
        msg1 = create_mock_message("yilikdan qarzim bormi", chat_id, user_id)
        await handle_user_chat(msg1, bot)
        reply1 = msg1.reply.call_args[0][0]
        self.assertIn("Fiskal modul", reply1)
        self.assertIn("seriya raqamini", reply1)
        self.assertEqual(bot.copy_message.call_count, 0)  # Video yuborilmagan!

        # 2-qadam: oylikdanchi
        msg2 = create_mock_message("oylikdanchi", chat_id, user_id)
        await handle_user_chat(msg2, bot)
        reply2 = msg2.reply.call_args[0][0]
        self.assertIn("СТИР (INN)", reply2)
        self.assertIn("yuboring", reply2)
        self.assertIn("Mars", reply2)
        self.assertEqual(bot.copy_message.call_count, 0)  # Hech qanday video 148 yuborilmagan!

        # 3-qadam: 302568138 (INN berildi)
        msg3 = create_mock_message("302568138", chat_id, user_id)
        await handle_user_chat(msg3, bot)
        reply3 = msg3.reply.call_args[0][0]
        self.assertIn("Korxona", reply3)

        # 4-qadam: yillikdanchi (endi yana yillikni so'ramoqda)
        msg4 = create_mock_message("yillikdanchi", chat_id, user_id)
        await handle_user_chat(msg4, bot)
        reply4 = msg4.reply.call_args[0][0]
        self.assertIn("Fiskal modul", reply4)

        # 5-qadam: UZ200701040469 (FM berildi)
        msg5 = create_mock_message("UZ200701040469", chat_id, user_id)
        await handle_user_chat(msg5, bot)
        reply5 = msg5.reply.call_args[0][0]
        self.assertIn("QARZDORLIK MAVJUD", reply5)
        self.assertIn("440 000 so'm", reply5)

        # 6-qadam: to'layman -> Post 34 va Video 145 kanaldan uzatiladi
        msg6 = create_mock_message("to'layman", chat_id, user_id)
        await handle_user_chat(msg6, bot)
        copied_ids = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
        self.assertIn(34, copied_ids)   # Yangi Texnologiyalar post 34
        self.assertIn(145, copied_ids)  # Click yillik video 145

    def test_04_reverse_order_remembered_inn(self):
        """Oldin INN ma'lum bo'lsa, 'oylikdanchi' deb so'raganda qayta INN so'ramay darhol tekshirishi kerak"""
        user_memory.set_last_id(778899, 112233, "302568138", org_name="MARS ELEKTRON TEXNIKA", debt=0.0)
        user_memory.set_last_topic(778899, 112233, "awaiting_fiscal_module")

        # Endi foydalanuvchi "oylikdanchi" desa
        self.assertTrue(is_monthly_check_intent("oylikdanchi"))
        rem_inn = user_memory.get_last_id(778899, 112233)
        self.assertEqual(rem_inn, "302568138")

if __name__ == "__main__":
    unittest.main()
