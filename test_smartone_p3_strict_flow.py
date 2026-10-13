import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from core.models import DeviceFacts, ActionType
from core.engine import core_engine
from user_memory import user_memory
from excel_manager import excel_manager
from admin_manager import admin_manager
from handlers.debt import format_debt_response


class TestStrictDiagnosticFlow(unittest.TestCase):
    def setUp(self):
        self.chat_id = 99887766
        self.user_id = 11223344
        user_memory.sessions.clear()

    def test_smartone_photo_no_inn_asks_inn(self):
        """Smart One rasm kelganda va INN bo'lmaganda, AI ekrandagi xatoni taxmin qilmaydi, avval INN so'raydi!"""
        facts = DeviceFacts(
            is_real_pos_device=True,
            detected_inn=None,
            screen_text_summary="Xatolik 406. Chek urib bo'lmadi",
            raw_facts={"is_p3_device": False, "screen_error_code": "406"}
        )
        # Rasm file_id saqlanadi
        user_memory.set_last_photo(self.chat_id, self.user_id, "photo_smartone_123")

        decision = core_engine.process_device_facts(
            facts=facts,
            chat_id=self.chat_id,
            user_id=self.user_id,
            user_comment="apparat ishlamayapti"
        )

        self.assertEqual(decision.action, ActionType.ASK_FULL_SCREEN)
        self.assertIn("СТИР (INN)", decision.reply_text)
        # Ekran xatosi bo'yicha uzun taxminlar yoki 406 haqida doston bo'lmasligi kerak
        self.assertNotIn("406", decision.reply_text)
        self.assertNotIn("oflayn limit", decision.reply_text.lower())
        self.assertEqual(user_memory.get_last_photo(self.chat_id, self.user_id), "photo_smartone_123")

    def test_smartone_photo_with_debt_returns_monthly_debt(self):
        """Smart One apparatida qarzdorlik bo'lsa, faqat oylik qarz va video 148 chiqadi, ekran xatosi taxmin qilinmaydi!"""
        # Bazada qarzli korxona topamiz
        debt_inn = None
        for inn, items in excel_manager.stir_index.items():
            if sum(it.get("debt", 0.0) for it in items) > 0:
                debt_inn = inn
                break
        self.assertIsNotNone(debt_inn, "Bazada qarzli korxona topilmadi")

        facts = DeviceFacts(
            is_real_pos_device=True,
            detected_inn=debt_inn,
            screen_text_summary="Bloklangan",
            raw_facts={"is_p3_device": False}
        )

        decision = core_engine.process_device_facts(
            facts=facts,
            chat_id=self.chat_id,
            user_id=self.user_id,
            user_comment=""
        )

        self.assertEqual(decision.action, ActionType.DIAGNOSE_AND_REPLY)
        self.assertEqual(decision.video_id, 148)
        self.assertGreater(decision.debt_amount, 0)
        self.assertIn("JAMI QARZDORLIK", decision.reply_text)
        self.assertIn("20208000800208044003", decision.reply_text)

    def test_smartone_photo_with_zero_debt_asks_fiscal_module(self):
        """Smart One apparatida Mars qarzi 0 bo'lsa, Step 2: Fiskal modul so'raydi!"""
        # Bazada qarzi 0 yoki ortiqcha to'lovli korxona topamiz
        clear_inn = None
        for inn, items in excel_manager.stir_index.items():
            if sum(it.get("debt", 0.0) for it in items) <= 0:
                clear_inn = inn
                break
        self.assertIsNotNone(clear_inn, "Bazada qarzi 0 korxona topilmadi")

        facts = DeviceFacts(
            is_real_pos_device=True,
            detected_inn=clear_inn,
            screen_text_summary="Tarmoq xatosi",
            raw_facts={"is_p3_device": False}
        )

        decision = core_engine.process_device_facts(
            facts=facts,
            chat_id=self.chat_id,
            user_id=self.user_id,
            user_comment=""
        )

        self.assertEqual(decision.action, ActionType.DEBT_INFO)
        self.assertIn("qarzdorlik yo'q (0 so'm)", decision.reply_text)
        self.assertIn("Fiskal modul raqamini (LG... yoki YG...)", decision.reply_text)

    def test_smartone_photo_with_both_debts_clear_advises_reboot(self):
        """Smart One apparatida oylik qarz 0 bo'lsa va Fiskal modul ham tekshirilgan bo'lsa, Step 3: Internet/Reboot maslahati!"""
        clear_inn = None
        for inn, items in excel_manager.stir_index.items():
            if sum(it.get("debt", 0.0) for it in items) <= 0:
                clear_inn = inn
                break

        user_memory.set_last_fm(self.chat_id, self.user_id, "LG420210009999")

        facts = DeviceFacts(
            is_real_pos_device=True,
            detected_inn=clear_inn,
            raw_facts={"is_p3_device": False}
        )

        decision = core_engine.process_device_facts(
            facts=facts,
            chat_id=self.chat_id,
            user_id=self.user_id,
            user_comment=""
        )

        self.assertEqual(decision.action, ActionType.DIAGNOSE_AND_REPLY)
        self.assertIn("qarzdorlik yo'q", decision.reply_text)
        self.assertIn("Перезагрузка / Reboot", decision.reply_text)
        self.assertIn("Usta kerak", decision.reply_text)

    def test_p3_humo_reports_screen_text(self):
        """P3 Humo apparati bo'lsa (sariq qator), ekrandagi matn tahlil qilinadi va chiqariladi!"""
        facts = DeviceFacts(
            is_real_pos_device=True,
            detected_inn=None,
            screen_text_summary="Karta bloklangan",
            raw_facts={"is_p3_device": True}
        )

        decision = core_engine.process_device_facts(
            facts=facts,
            chat_id=self.chat_id,
            user_id=self.user_id,
            user_comment=""
        )

        self.assertEqual(decision.action, ActionType.DIAGNOSE_AND_REPLY)
        self.assertIn("P3 Humo apparat ekranidagi xabar", decision.reply_text)
        self.assertIn("Karta bloklangan", decision.reply_text)


class TestChatHandlerStrictFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.chat_id = 99887766
        self.user_id = 11223344
        user_memory.sessions.clear()

    async def test_device_issue_text_asks_inn_when_unknown(self):
        """Foydalanuvchi 'apparat ishlamayapti' deb yozsa va INN bo'lmasa, INN so'raydi"""
        from handlers.chat import handle_user_chat

        msg = MagicMock()
        msg.chat.id = self.chat_id
        msg.from_user.id = self.user_id
        msg.from_user.username = "test_user"
        msg.from_user.full_name = "Test User"
        msg.text = "Apparat ishlamayapti nima qilsam bo'ladi?"
        msg.reply = AsyncMock()

        bot = MagicMock()

        await handle_user_chat(msg, bot)

        msg.reply.assert_called_once()
        sent_text = msg.reply.call_args[0][0]
        self.assertIn("СТИР (INN) raqamini yuboring", sent_text)

    async def test_reboot_failed_escalates_to_master_with_saved_photo(self):
        """Rebootdan keyin 'ishlamadi baribir usta kerak' deyilsa, adminga avval saqlangan rasm bilan eskalatsiya qilinadi!"""
        from handlers.chat import handle_user_chat

        user_memory.set_last_photo(self.chat_id, self.user_id, "device_screen_photo_xyz")
        user_memory.set_last_id(self.chat_id, self.user_id, "123456789")

        msg = MagicMock()
        msg.chat.id = self.chat_id
        msg.from_user.id = self.user_id
        msg.from_user.username = "client_biz"
        msg.from_user.full_name = "Client Biz"
        msg.text = "O'chirib yoqdim baribir ishlamadi, usta kerak"
        msg.reply = AsyncMock()

        bot = MagicMock()

        with patch("admin_manager.admin_manager.notify_user_query_escalation", new_callable=AsyncMock) as mock_escalate:
            await handle_user_chat(msg, bot)

            mock_escalate.assert_called_once()
            call_kwargs = mock_escalate.call_args[1]
            self.assertEqual(call_kwargs.get("photo_file_id"), "device_screen_photo_xyz")
            self.assertIn("ishlamadi", call_kwargs.get("query_text", "").lower())

            sent_text = msg.reply.call_args[0][0]
            self.assertIn("Murojaatingiz qabul qilindi", sent_text)


if __name__ == "__main__":
    unittest.main()
