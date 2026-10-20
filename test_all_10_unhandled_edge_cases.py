import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram import types, Bot

from user_memory import user_memory
from handlers.intents.billing import billing_intent_handler
from handlers.intents.hardware import hardware_intent_handler
from handlers.media import _process_fiscal_receipt_content
from core.models import extract_bank_card_number, extract_bank_account_number, is_invalid_digit_length, is_incomplete_inn_text


def create_mock_message(text: str, chat_id: int = -1001234567890, user_id: int = 12345, is_group: bool = True):
    msg = MagicMock(spec=types.Message)
    msg.text = text
    msg.message_id = 999
    msg.chat = MagicMock()
    msg.chat.id = chat_id
    msg.chat.type = "supergroup" if is_group else "private"
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.from_user.first_name = "TestUser"
    msg.from_user.username = "testuser"
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()
    return msg


class TestAll10EdgeCases(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        user_memory.clear()
        self.bot = MagicMock(spec=Bot)
        self.bot.copy_message = AsyncMock()

    async def test_01_ofd_timeout_failsafe_billing_annual_check(self):
        """Case 1: When OFD times out (returns None), NEVER falsely declare 'Qarzdorlik yo'q'"""
        msg = create_mock_message("yillikchi LG420210630789")
        with patch("handlers.intents.billing.ofd_bridge.query_fiscal_module", new=AsyncMock(return_value=None)):
            handled = await billing_intent_handler.handle(msg, self.bot, "latin")
            self.assertTrue(handled)
            reply_text = msg.reply.call_args[0][0]
            self.assertIn("vaqtincha javob bermayapti", reply_text.lower())
            self.assertNotIn("qarzdorlik yo'q", reply_text.lower())
            self.assertNotIn("litsenziya faol", reply_text.lower())

    async def test_01b_ofd_timeout_failsafe_direct_fm(self):
        """Case 1b: Direct FM submission with OFD timeout"""
        msg = create_mock_message("LG420210630789")
        with patch("handlers.intents.billing.ofd_bridge.query_fiscal_module", new=AsyncMock(return_value=None)):
            handled = await billing_intent_handler.handle(msg, self.bot, "latin")
            self.assertTrue(handled)
            reply_text = msg.reply.call_args[0][0]
            self.assertIn("vaqtincha javob bermayapti", reply_text.lower())
            self.assertNotIn("to'langan va faol", reply_text.lower())

    async def test_01c_ofd_timeout_failsafe_media_chek(self):
        """Case 1c: When kassa cheki is submitted and OFD times out"""
        chat_id = -100999888
        user_id = 777
        msg = create_mock_message("Kassa cheki", chat_id=chat_id, user_id=user_id)
        from core.models import ReceiptFacts, FiscalChekFacts
        fisc = FiscalChekFacts(inn="302568138", fiscal_module="LG420210630789", org_name="TEST MCHJ", terminal_id="12345")
        facts = ReceiptFacts(is_fiscal_chek=True, payer_inn="302568138", fiscal_module="LG420210630789", fiscal_facts=fisc)
        with patch("handlers.media.ofd_bridge.query_fiscal_module", new=AsyncMock(return_value=None)), \
             patch("handlers.media.excel_manager.check_debt", return_value={"record": {"org_name": "TEST", "debt_amount": 0.0, "status": "qarzi yo'q"}}):
            await _process_fiscal_receipt_content(
                message=msg,
                bot=self.bot,
                receipt_facts=facts,
                user_script="latin",
                caption="",
                file_id="file_abc"
            )
            msg.reply.assert_called()
            sent_text = msg.reply.call_args[0][0]
            self.assertIn("vaqtincha javob bermayapti", sent_text.lower())
            self.assertNotIn("litsenziya muddati faol", sent_text.lower())

    async def test_02_group_chat_multi_user_context_fallback(self):
        """Case 2: User A inputs INN in group, User B asks oylikchi -> correctly falls back to group context"""
        group_id = -100555444
        user_a = 111
        user_b = 222

        # User A sets INN (NARZILLO BOBO MALLAYEV MCHJ: 311756421 with 300,000 debt)
        user_memory.set_last_id(group_id, user_a, "311756421", org_name="NARZILLO BOBO MALLAYEV MCHJ", debt=300000.0)

        # User B asks "oylikchi"
        msg_b = create_mock_message("oylikchi", chat_id=group_id, user_id=user_b)
        handled = await billing_intent_handler.handle(msg_b, self.bot, "latin")
        self.assertTrue(handled)
        msg_b.reply.assert_called()
        reply_b = msg_b.reply.call_args[0][0]
        self.assertTrue("300 000 so'm" in reply_b or "300,000 so'm" in reply_b)
        self.assertIn("NARZILLO BOBO", reply_b)

    async def test_03_bank_card_16_digits(self):
        """Case 3: Intercept 16-digit card numbers (8600, 9860, etc.)"""
        self.assertEqual(extract_bank_card_number("8600 1234 5678 9012"), "8600123456789012")
        msg = create_mock_message("8600 1234 5678 9012")
        handled = await billing_intent_handler.handle(msg, self.bot, "latin")
        self.assertTrue(handled)
        reply = msg.reply.call_args[0][0]
        self.assertIn("kartadan-kartaga (p2p) qabul qilinmaydi", reply.lower())
        self.assertIn("20 xonali", reply.lower())

    async def test_04_bank_account_20_digits(self):
        """Case 4: Recognize 20-digit bank account numbers (20208... vs 20210...)"""
        msg_mars = create_mock_message("20208000800208044003")
        handled = await billing_intent_handler.handle(msg_mars, self.bot, "latin")
        self.assertTrue(handled)
        reply_mars = msg_mars.reply.call_args[0][0]
        self.assertIn("«mars» oylik abonent to'lovi hisob raqami", reply_mars.lower())

        msg_yangi = create_mock_message("20210000000000000001")
        handled2 = await billing_intent_handler.handle(msg_yangi, self.bot, "latin")
        self.assertTrue(handled2)
        reply_yangi = msg_yangi.reply.call_args[0][0]
        self.assertIn("yangi texnologiyalar", reply_yangi.lower())

    async def test_05_invalid_digit_lengths_and_spaced_inns(self):
        """Case 5: Handle spaced INNs and catch 10-13 digit length mismatches"""
        # Spaced incomplete INN
        self.assertTrue(is_incomplete_inn_text("302 568 13"))
        msg_short = create_mock_message("302 568 13")
        handled = await billing_intent_handler.handle(msg_short, self.bot, "latin")
        self.assertTrue(handled)
        self.assertIn("to'liq emas", msg_short.reply.call_args[0][0].lower())

        # 11 digits
        self.assertEqual(is_invalid_digit_length("12345678901"), 11)
        msg_11 = create_mock_message("12345678901")
        handled_11 = await billing_intent_handler.handle(msg_11, self.bot, "latin")
        self.assertTrue(handled_11)
        self.assertIn("11 xonali", msg_11.reply.call_args[0][0].lower())

    async def test_06_tolaganman_prompts_receipt(self):
        """Case 6: 'Ertalab to'laganman' prompts user to upload receipt"""
        msg = create_mock_message("Ertalab to'lagandik")
        handled = await billing_intent_handler.handle(msg, self.bot, "latin")
        self.assertTrue(handled)
        reply = msg.reply.call_args[0][0]
        self.assertIn("to'lov kvitansiyasini", reply.lower())

    async def test_07_pul_yechildi_lekin_yonmadi(self):
        """Case 7: 'Pul yechildi lekin apparat ochilmadi' gives 3-step diagnostic"""
        msg = create_mock_message("pul yechildi lekin apparat ochilmadi hali")
        handled = await billing_intent_handler.handle(msg, self.bot, "latin")
        self.assertTrue(handled)
        reply = msg.reply.call_args[0][0]
        self.assertIn("«mars» oylik to'lovi", reply.lower())
        self.assertIn("yangi texnologiyalar", reply.lower())
        self.assertIn("2 soatdan 24 soatgacha", reply.lower())
        self.assertIn("reboot", reply.lower())

    async def test_08_multi_device_inquiry(self):
        """Case 8: 'Bizda 2 ta apparat bor' explains multi-device policy"""
        msg = create_mock_message("Bizda 2 ta apparat bor")
        handled = await billing_intent_handler.handle(msg, self.bot, "latin")
        self.assertTrue(handled)
        reply = msg.reply.call_args[0][0]
        self.assertIn("har bir kassa apparati uchun alohida oylik to'lov", reply.lower())
        self.assertIn("440 000 so'm", reply.lower())

    async def test_09_repeat_oylikchi_yillikchi_cycle_persistent_debt(self):
        """Case 9: Repetitive 'oylikchi' -> 'yillikchi' -> 'oylikchi' keeps debt persistent"""
        chat_id = -100444333
        user_id = 888

        # Step 1: Set INN 311756421 (300,000 debt)
        user_memory.set_last_id(chat_id, user_id, "311756421", org_name="NARZILLO BOBO MALLAYEV MCHJ", debt=300000.0)

        # Step 2: "oylikchi"
        msg1 = create_mock_message("oylikchi", chat_id, user_id)
        await billing_intent_handler.handle(msg1, self.bot, "latin")
        r1 = msg1.reply.call_args[0][0]
        self.assertTrue("300 000 so'm" in r1 or "300,000 so'm" in r1)

        # Step 3: "yillikchi LG420210630789" (OFD clean)
        msg2 = create_mock_message("yillikchi LG420210630789", chat_id, user_id)
        with patch("handlers.intents.billing.ofd_bridge.query_fiscal_module", new=AsyncMock(return_value="Fiskal modul faol. Qarzdorlik mavjud emas.")):
            await billing_intent_handler.handle(msg2, self.bot, "latin")
            r2 = msg2.reply.call_args[0][0]
            # Shows annual clean BUT still shows monthly 300,000 debt!
            self.assertTrue("300 000 so'm" in r2 or "300,000 so'm" in r2)

        # Step 4: "oylikchi" again -> MUST NOT BE ZERO!
        msg3 = create_mock_message("oylikchi", chat_id, user_id)
        await billing_intent_handler.handle(msg3, self.bot, "latin")
        r3 = msg3.reply.call_args[0][0]
        self.assertTrue("300 000 so'm" in r3 or "300,000 so'm" in r3)
        self.assertNotIn("qarzdorlik yo'q (to'langan)", r3.lower())


if __name__ == "__main__":
    unittest.main()
