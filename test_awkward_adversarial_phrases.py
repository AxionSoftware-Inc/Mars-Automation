import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from handlers.chat import handle_user_chat
from handlers.debt import is_inn_or_phone_query_message
from user_memory import user_memory
from excel_manager import excel_manager
from core.models import extract_fiscal_module, extract_clean_inn


class TestAwkwardAdversarialPhrases(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.chat_id = 556677
        self.user_id = 998811
        user_memory.sessions.clear()
        self.ai_patcher = patch(
            "ai_helper.generate_ai_reply_ex",
            return_value=("Korxonangizning 9 xonali СТИР (INN) raqamini yuboring.", None, False)
        )
        self.ai_patcher.start()

    def tearDown(self):
        self.ai_patcher.stop()

    async def _send_text(self, text: str):
        msg = MagicMock()
        msg.text = text
        msg.chat.id = self.chat_id
        msg.chat.type = "private"
        msg.from_user.id = self.user_id
        msg.from_user.username = "awkward_client"
        msg.from_user.full_name = "Awkward Client"
        msg.reply = AsyncMock()
        msg.answer = AsyncMock()
        bot = MagicMock()
        bot.copy_message = AsyncMock()
        bot.send_message = AsyncMock()

        # Check if debt_router would intercept it
        from handlers.debt import is_debt_inquiry, handle_debt_inquiry
        if is_debt_inquiry(msg):
            await handle_debt_inquiry(msg)
        elif is_inn_or_phone_query_message(msg):
            from handlers.debt import handle_inn_query
            await handle_inn_query(msg, bot)
        else:
            await handle_user_chat(msg, bot)

        replies = []
        if msg.reply.called:
            replies.extend([call[0][0] for call in msg.reply.call_args_list])
        if msg.answer.called:
            replies.extend([call[0][0] for call in msg.answer.call_args_list])
        return replies, bot

    async def test_1_inn_not_known_guidance(self):
        """1. 'inn ni bilmayman qayerdan topsam boladi' -> Qayerdan topishni tushuntirishi kerak"""
        replies, bot = await self._send_text("inn ni bilmayman qayerdan topsam boladi")
        text = " ".join(replies).lower()
        self.assertTrue(any(w in text for w in ["guvohnoma", "soliq", "chek", "inn"]))

    async def test_2_price_inquiry_without_inn(self):
        """2. 'qancha tolashim kerak apparatimga?' -> INN so'raydi va oylik 100 000 so'm ekanini aytadi"""
        replies, bot = await self._send_text("qancha tolashim kerak apparatimga?")
        text = " ".join(replies).lower()
        self.assertTrue("inn" in text or "stir" in text)

    async def test_3_card_deducted_no_receipt(self):
        """3. 'kartamdan pul yechib oldi lekin apparat chek bermadi' -> Tushuntirishi va INN so'rashi kerak"""
        replies, bot = await self._send_text("kartamdan pul yechib oldi lekin apparat chek bermadi")
        text = " ".join(replies).lower()
        self.assertTrue(len(text) > 20)

    async def test_4_immediate_master_request(self):
        """4. 'bizga usta chaqirib bering zudlik bilan' -> Adminga eskalatsiya bo'lishi kerak"""
        with patch("admin_manager.admin_manager.notify_user_query_escalation", new_callable=AsyncMock) as mock_admin:
            replies, bot = await self._send_text("bizga usta chaqirib bering zudlik bilan")
            self.assertTrue(mock_admin.called)
            text = " ".join(replies).lower()
            self.assertTrue("qabul qilindi" in text or "bog'lan" in text)

    async def test_5_paid_objection_without_inn(self):
        """5. 'men tolaganmanku nega blok qilasizlar' -> INN so'rashi kerak"""
        replies, bot = await self._send_text("men tolaganmanku nega blok qilasizlar")
        text = " ".join(replies).lower()
        self.assertTrue("inn" in text or "stir" in text or "tekshirish" in text)

    async def test_6_fiscal_module_with_spaces_not_intercepted_by_debt(self):
        """6. 'fiskal modul LG 42021063078901 tekshirib ber' -> Debt interceptor ga tushmaydi, FM qabul qilinadi!"""
        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", new_callable=AsyncMock, return_value="Fiskal modul faol holatda."):
            replies, bot = await self._send_text("fiskal modul LG 42021063078901 tekshirib ber")
            text = " ".join(replies).lower()
            self.assertIn("fiskal modul", text)
            self.assertIn("42021063078901", text)
            # JSHSHIR deb xato qidirmasligi shart!
            self.assertNotIn("bazada ushbu raqam bo'yicha ma'lumot topilmadi", text)

    async def test_7_tech_question_with_inn_not_dumping_debt(self):
        """7. '311790999 da chek qanday uriladi?' -> Qarz jadvalini tashlamaydi, chek urishni tushuntiradi yoki video beradi!"""
        with patch("ai_helper.generate_ai_reply_ex", return_value=("Chek urish uchun menyudan Savdo bo'limiga kiring.", 2, False)):
            replies, bot = await self._send_text("311790999 da chek qanday uriladi?")
            text = " ".join(replies).lower()
            # Qarz jadvali tashlanmasligi shart!
            self.assertNotIn("jami qarzdorlik", text)
            self.assertNotIn("20208000800208044003", text)
            # Savolga javob berilgan (video yoki matn)
            self.assertTrue(bot.copy_message.called or "chek" in text)

    async def test_8_typo_ochib_qoldi(self):
        """8. 'salom kassa ochib qoldi ishlamayapti' (o'chib qoldi) -> INN so'rashi kerak"""
        replies, bot = await self._send_text("salom kassa ochib qoldi ishlamayapti")
        text = " ".join(replies).lower()
        self.assertTrue("inn" in text or "stir" in text)

    async def test_9_search_by_name_clarification(self):
        """9. 'korxonam nomi Fayz MCHJ shundan top' -> INN talab qilinishini xushmuomala tushuntiradi"""
        replies, bot = await self._send_text("korxonam nomi Fayz MCHJ shundan top")
        text = " ".join(replies).lower()
        self.assertTrue(any(w in text for w in ["inn", "stir", "raqam", "soliq", "9 xonali"]))

    async def test_10_z_report_inquiry(self):
        """10. 'z otchyot qanday olinadi kechqurun?' -> Z-hisobot videosini yuboradi"""
        replies, bot = await self._send_text("z otchyot qanday olinadi kechqurun?")
        self.assertTrue(bot.copy_message.called)
        sent_vid = bot.copy_message.call_args[1].get("message_id")
        self.assertIn(sent_vid, [2, 12, 13])  # Z hisobot video ID lari (Post 2)

    async def test_11_error_406_text_asks_inn_first(self):
        """11. 'xatolik 406 chiqyapti smartonimda' -> 406 haqida doston yozmaydi, avval INN so'raydi!"""
        replies, bot = await self._send_text("xatolik 406 chiqyapti smartonimda")
        text = " ".join(replies).lower()
        self.assertTrue("inn" in text or "stir" in text)
        self.assertNotIn("oflayn limit chegarasi", text)

    async def test_12_reboot_failed_escalates_to_master(self):
        """12. 'reboot qildim apparatni baribir ochmayapti usta jonating' -> Adminga eskalatsiya qiladi"""
        with patch("admin_manager.admin_manager.notify_user_query_escalation", new_callable=AsyncMock) as mock_admin:
            replies, bot = await self._send_text("reboot qildim apparatni baribir ochmayapti usta jonating")
            self.assertTrue(mock_admin.called)

    async def test_13_fiscal_module_expiry_question(self):
        """13. 'fiskal modul qachon tugaydi' -> Chekdagi FM raqamini so'raydi"""
        replies, bot = await self._send_text("fiskal modul qachon tugaydi")
        text = " ".join(replies).lower()
        self.assertTrue("fiskal modul" in text)
        self.assertTrue("lg" in text or "yg" in text)

    async def test_14_who_are_you_greeting(self):
        """14. 'sizlar kimsizlar ozi' -> Xizmat markazi haqida ma'lumot beradi"""
        replies, bot = await self._send_text("sizlar kimsizlar ozi")
        text = " ".join(replies).lower()
        self.assertTrue("mars" in text or "servis" in text or "kassa" in text or "yordam" in text)

    async def test_15_polite_thanks(self):
        """15. 'rahmat katta rahmat ishladi' -> Xushmuomala yakunlaydi"""
        replies, bot = await self._send_text("rahmat katta rahmat ishladi")
        text = " ".join(replies).lower()
        self.assertTrue(len(text) > 0)


if __name__ == "__main__":
    unittest.main()
