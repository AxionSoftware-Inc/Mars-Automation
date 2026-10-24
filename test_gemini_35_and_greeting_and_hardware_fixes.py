import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from core.group_responder import group_responder
from handlers.intents.hardware import is_device_issue, hardware_intent_handler
from user_memory import user_memory
from openrouter_client import DEFAULT_MODEL

class TestGemini35AndFixes(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()

    def test_default_model_is_gemini_35_flash_lite(self):
        """1. Model Gemini 3.5 Flash Lite ga o'tkazilganligini tekshirish"""
        self.assertEqual(DEFAULT_MODEL, "google/gemini-3.5-flash-lite")

    def test_hardware_issue_detection_with_typos_and_dialects(self):
        """2. 'meni aparatim islamay qolopti' va 'aparatimni tekshirib beriyla...' apparat nosozligi sifatida aniqlanishi"""
        t1 = "meni aparatim islamay qolopti"
        t2 = "aparatimni tekshirib beriyla ettalabdan beri ishlamayabdida tulov qilligam ishlamayabdi"
        t3 = "aparat ishklamayapdi"
        self.assertTrue(is_device_issue(t1))
        self.assertTrue(is_device_issue(t2))
        self.assertTrue(is_device_issue(t3))

    async def test_greeting_variants_and_escalation_reset(self):
        """3. 'assalomalaykum' va '/salombot' salomlashish sifatida olinishi va eskalatsiyani tozalashi"""
        chat_id = 99881
        user_id = 77112
        # Avval userni adminga eskalatsiya qilib qo'yamiz
        user_memory.mark_escalated_to_admin(chat_id, user_id, reason="Old test")
        self.assertTrue(user_memory.is_escalated_to_admin(chat_id, user_id))

        # 3.1 'assalomalaykum'
        m1 = MagicMock()
        m1.text = "assalomalaykum"
        m1.chat.id = chat_id
        m1.chat.type = "supergroup"
        m1.from_user.id = user_id
        m1.from_user.username = "test_user"
        m1.reply = AsyncMock()

        handled1 = await group_responder.process_message(m1, self.bot)
        self.assertTrue(handled1)
        self.assertEqual(m1.reply.call_count, 1)
        self.assertIn("Assalomu alaykum", m1.reply.call_args[0][0])
        # Eskalatsiya tozalangan bo'lishi shart!
        self.assertFalse(user_memory.is_escalated_to_admin(chat_id, user_id))

        # 3.2 '/salombot'
        user_memory.mark_escalated_to_admin(chat_id, user_id, reason="Old test 2")
        m2 = MagicMock()
        m2.text = "/salombot"
        m2.chat.id = chat_id
        m2.chat.type = "supergroup"
        m2.from_user.id = user_id
        m2.from_user.username = "test_user"
        m2.reply = AsyncMock()

        handled2 = await group_responder.process_message(m2, self.bot)
        self.assertTrue(handled2)
        self.assertEqual(m2.reply.call_count, 1)
        self.assertIn("Assalomu alaykum", m2.reply.call_args[0][0])
        self.assertFalse(user_memory.is_escalated_to_admin(chat_id, user_id))

    async def test_hardware_intent_handler_handles_stem_device_issue(self):
        """4. hardware_intent_handler moslashuvchan o'zakli xabarlarda ham to'g'ridan-to'g'ri javob berishi (False qaytarmasligi)"""
        chat_id = 99882
        user_id = 77113
        user_memory.clear_issue_mode(chat_id, user_id)
        user_memory.set_last_id(chat_id, user_id, "311481235") # 0 qarzli INN

        m = MagicMock()
        m.text = "aparatimni tekshirib beriyla ettalabdan beri ishlamayabdida tulov qilligam ishlamayabdi"
        m.chat.id = chat_id
        m.chat.type = "supergroup"
        m.from_user.id = user_id
        m.from_user.username = "test_user"
        m.reply = AsyncMock()

        handled = await group_responder.process_message(m, self.bot)
        self.assertTrue(handled)
        self.assertEqual(m.reply.call_count, 1)
        reply_text = m.reply.call_args[0][0]
        # Oylik abonent to'lovidan qarzdorlik yo'q (0 so'm) va 2-bosqich Fiskal modul so'rashi
        self.assertIn("qarzdorlik yo'q", reply_text)
        self.assertIn("Fiskal modul", reply_text)

if __name__ == "__main__":
    unittest.main()
