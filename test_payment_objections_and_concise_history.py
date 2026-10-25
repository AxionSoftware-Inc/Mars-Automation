import unittest
from unittest.mock import AsyncMock, MagicMock
from aiogram import types, Bot

from payment_accounts import (
    is_debt_inquiry_or_objection,
    is_payment_claim,
    classify_payment_intent,
    is_monthly_check_intent
)
from excel_manager import excel_manager
from user_memory import user_memory
from core.group_responder import GroupResponseOrchestrator


def create_mock_message(text: str, chat_id: int = -10099887766, user_id: int = 123456789, is_group: bool = True):
    msg = MagicMock(spec=types.Message)
    msg.text = text
    msg.caption = None
    msg.photo = None
    msg.document = None
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


class TestPaymentObjectionsAndConciseHistory(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat_id = -10099887766
        self.user_id = 123456789
        user_memory.clear_context(self.chat_id, self.user_id)

    def test_detection_patterns(self):
        """1. Objection phrases vs payment claim detection"""
        objections = [
            "tulaganmanku",
            "to'lagandimku",
            "nimaga qarzga chiqdi",
            "to'lagandimku nimaga qarzga chiqdi",
            "qarzim yo'qku",
            "qarz yoqku",
            "to'laganmanku",
            "to'laganmizku",
            "pul o'tkazganmanku",
            "to'ladimku",
            "toladimku",
            "to'lov tarixi",
            "tarixni ko'rsat",
            "qachon to'laganman",
            "qaysi oylarga to'langan",
            "qaysi oylar uchun qarz",
            "nega qarz chiqyapti",
            "nimaga qarz",
            "311790999 to'lagandimku",
            "oylik to'lagandimku",
            "тўлаганманку",
            "тўладимку",
            "нега қарзга чиқди"
        ]
        for obj in objections:
            self.assertTrue(
                is_debt_inquiry_or_objection(obj),
                f"Expected is_debt_inquiry_or_objection to be True for: {obj}"
            )
            self.assertFalse(
                is_payment_claim(obj),
                f"Expected is_payment_claim to be False for objection: {obj}"
            )

        claims = [
            "to'ladim",
            "tuladim",
            "toladim",
            "to'lov qildim",
            "pul o'tkazdim",
            "to'lab bo'ldik",
            "to'lab qo'ydim",
            "тўладим",
            "туладим"
        ]
        for cl in claims:
            self.assertTrue(
                is_payment_claim(cl),
                f"Expected is_payment_claim to be True for: {cl}"
            )
            self.assertFalse(
                is_debt_inquiry_or_objection(cl),
                f"Expected is_debt_inquiry_or_objection to be False for: {cl}"
            )

    def test_format_payment_history_concise_output(self):
        """2. Format payment history output is concise and informative"""
        sample_results = [
            {
                "stir": "311790999",
                "jshshir": "-",
                "name": "ALISHER BOBO QURILISH MOLLARI DOKONI",
                "model": "Smart One",
                "terminal_id": "2028081065",
                "debt": 100000.0,
                "old_debt_2026": 0.0,
                "charges_2026": {
                    "Yanvar": 100000.0,
                    "Fevral": 100000.0,
                    "Mart": 100000.0
                },
                "payments_2026": {
                    "Yanvar": 100000.0,
                    "Fevral": 100000.0
                }
            }
        ]

        text = excel_manager.format_payment_history(sample_results)
        self.assertIn("«Mars» oylik abonent to'lovlari tarixi:", text)
        self.assertIn("ALISHER BOBO QURILISH MOLLARI DOKONI", text)
        self.assertIn("311790999", text)
        self.assertIn("Joriy qarzdorlik:", text)
        self.assertIn("100 000 so'm", text)
        self.assertIn("To'langan oylar:", text)
        self.assertIn("Yanvar", text)
        self.assertIn("Fevral", text)
        self.assertIn("To'lanmagan (qarzdor) oylar:", text)
        self.assertIn("Mart", text)
        # Ensure no future December forecasts or huge essays
        self.assertNotIn("Dekabr", text)
        self.assertNotIn("to'langan (0 so'm)", text)

    async def test_end_to_end_orchestrator_objection_routing(self):
        """3. Group responder routes objection to payment history, not receipt or accounts post"""
        user_memory.set_last_id(self.chat_id, self.user_id, "302568138", org_name="MARS TEST", debt=100000.0)

        orchestrator = GroupResponseOrchestrator()
        bot = MagicMock(spec=Bot)
        message = create_mock_message("tulaganmanku nimaga qarzga chiqdi", chat_id=self.chat_id, user_id=self.user_id)

        res = await orchestrator.process_message(message, bot)

        self.assertTrue(res)
        message.reply.assert_called_once()
        replied_text = message.reply.call_args[0][0]
        # Should contain history, NOT asking for receipt and NOT sending payment accounts
        self.assertIn("oylik abonent to'lovlari tarixi", replied_text.lower())
        self.assertNotIn("kvitansiya", replied_text.lower())
        self.assertNotIn("kartadan-kartaga", replied_text.lower())

    async def test_end_to_end_orchestrator_payment_claim_asks_receipt(self):
        """4. Group responder routes payment claim to receipt request"""
        orchestrator = GroupResponseOrchestrator()
        bot = MagicMock(spec=Bot)
        message = create_mock_message("to'ladim", chat_id=self.chat_id, user_id=self.user_id)

        res = await orchestrator.process_message(message, bot)

        self.assertTrue(res)
        message.reply.assert_called_once()
        replied_text = message.reply.call_args[0][0]
        self.assertIn("kvitansiya", replied_text.lower())


if __name__ == "__main__":
    unittest.main()
