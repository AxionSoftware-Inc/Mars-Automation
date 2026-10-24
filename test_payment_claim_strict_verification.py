import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from user_memory import user_memory
from payment_accounts import is_payment_claim
from core.group_responder import group_responder
from core.models import DeviceFacts
from core import core_engine
from ai_helper import generate_ai_reply_ex

class TestPaymentClaimStrictVerification(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        user_memory.sessions.clear()

    async def _send_chat_msg(self, text: str, chat_id: int = -1001234567, user_id: int = 778899):
        from aiogram import types
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
        msg.text = text
        msg.reply_to_message = None
        msg.message_id = 1234
        msg.reply = AsyncMock()
        msg.answer = AsyncMock()

        handled = await group_responder.process_message(msg, bot)
        reply = msg.reply.call_args[0][0] if msg.reply.called else (msg.answer.call_args[0][0] if msg.answer.called else "")
        return handled, reply

    async def test_01_all_payment_claim_variations_ask_receipt(self):
        """Kvitansiyasiz yozilgan barcha to'lov da'volaridan bot faqat kvitansiya so'rashi shart"""
        phrases = [
            "to'ladim",
            "tuladim",
            "toladim",
            "to'ladimku",
            "to'lov qildim",
            "pul o'tkazdim",
            "to'lab bo'ldik",
            "to'lab qo'ydim",
            "mana to'ladim",
            "clickdan to'ladim",
            "paymedan toladim",
            "shotga pul tashladim",
            "to'ladim ochilmadi",
            "to'ladim lekin hali ham ochilmadi",
            "to'ladim qachon yoqasizlar",
            "to'ladim qachon ochiladi",
            "туладим",
            "тўладим",
            "оплатил"
        ]

        for p in phrases:
            user_memory.sessions.clear()
            handled, reply = await self._send_chat_msg(p)
            self.assertTrue(handled, f"Xabar qayta ishlanmadi: '{p}'")
            rep_low = reply.lower()
            has_receipt_ask = ("to'lov kvitansiyasini" in rep_low or "тўлов квитанциясини" in rep_low or "квитанция" in rep_low or "kvitansiya" in rep_low)
            self.assertTrue(has_receipt_ask, f"Kvitansiya so'ralmadi: '{p}' -> {reply}")
            self.assertNotIn("kvitansiyangiz qabul qilindi", rep_low)
            self.assertNotIn("квитанциянгиз қабул қилинди", rep_low)
            self.assertNotIn("adminga yuborilgan", rep_low)
            self.assertNotIn("админга юборилган", rep_low)

    async def test_02_payment_claim_with_inn_asks_receipt_and_remembers_inn(self):
        """INN bilan birga 'to'ladim' deb yozilganda, INN eslab qolinadi va kvitansiya so'raladi"""
        chat_id = -1005544
        user_id = 223344
        user_memory.sessions.clear()

        handled, reply = await self._send_chat_msg("to'ladim 302568138", chat_id, user_id)
        self.assertTrue(handled)
        self.assertIn("to'lov kvitansiyasini", reply.lower())
        self.assertNotIn("kvitansiyangiz qabul qilindi", reply.lower())
        self.assertEqual(user_memory.get_last_id(chat_id, user_id), "302568138")

    async def test_03_payment_claim_after_actual_receipt_acknowledged(self):
        """Mijoz haqiqatan kvitansiya yuklagandan so'ng 'qachon ochiladi' desa, adminga yuborilgani eslatiladi"""
        chat_id = -1005544
        user_id = 223344
        user_memory.sessions.clear()

        # 1. Kvitansiya yuborildi
        user_memory.set_last_receipt(chat_id, user_id, {
            "inn": "302568138",
            "amount": 100000.0,
            "transaction_id": "TX12345"
        })

        # 2. Keyin mijoz kvitansiyadan so'ng 'qachon ochiladi' deb yozdi
        handled, reply = await self._send_chat_msg("kvitansiya yubordim qachon ochiladi", chat_id, user_id)
        self.assertTrue(handled)
        self.assertIn("adminga yuborilgan", reply.lower())

    def test_04_pos_device_photo_with_tuladim_caption_is_not_receipt(self):
        """POS apparat rasmi bilan captionda 'to'ladim' yozilganda, apparat kvitansiyaga aylanib ketmasligi shart"""
        dev_facts = DeviceFacts(
            is_real_pos_device=True,
            is_status_bar_visible=False,
            time_mismatch=False,
            has_internet=True,
            error_type="debt",
            detected_inn="302568138",
            screen_text_summary="Xatolik: Abonent to'lovidan qarzdorlik"
        )
        decision = core_engine.process_device_facts(
            facts=dev_facts,
            chat_id=123,
            user_id=456,
            user_comment="to'ladim yoqib bering"
        )
        self.assertNotIn("Kvitansiyangiz qabul qilindi", decision.reply_text or "")

    def test_05_ai_helper_guardrail_prevents_false_receipt_acceptance(self):
        """Agar AI kvitansiyasiz odamga 'kvitansiyangiz adminga yuborilgan' deb gallyutsinatsiya qilsa ham guardrail to'g'irlaydi"""
        context = "=== MIJOZNING ANIQLANGAN TIZIMDAGI MA'LUMOTLARI ===\n• INN / JSHSHIR: 302568138"
        # Mock LLM trying to hallucinate that the receipt was received/forwarded:
        with patch("ai_helper.openrouter_client.chat_completion", return_value="To'lov kvitansiyangiz tekshirish uchun mas'ul adminga yuborilgan."):
            text, _, _ = generate_ai_reply_ex(user_message="tuladim", context_history=context, target_script="latin")
            self.assertIn("to'lov kvitansiyasini", text.lower())
            self.assertNotIn("kvitansiyangiz qabul qilindi", text.lower())
            self.assertNotIn("adminga yuborilgan", text.lower())

if __name__ == "__main__":
    unittest.main()
