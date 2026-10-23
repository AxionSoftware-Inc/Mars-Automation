import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from aiogram import types

from core import core_engine, ActionType
from core.models import ReceiptFacts, DeviceFacts
from user_memory import UserMemoryManager, user_memory
from excel_manager import excel_manager
from transaction_tracker import TransactionTracker
from handlers.debt import format_debt_response
from admin_manager import AdminManager


class TestAdvancedProductionScenarios(unittest.TestCase):
    def setUp(self):
        self.memory = UserMemoryManager()

    # =========================================================================
    # 1. USER MEMORY ISOLATION & CONCURRENCY
    # =========================================================================
    def test_01_user_memory_isolation_between_private_users(self):
        """User A va User B ning xotirasi (INN, qarz, kontekst) bir-biriga aslo aralashmasligi kerak"""
        user_a_chat = 1001
        user_a_id = 1001

        user_b_chat = 1002
        user_b_id = 1002

        user_c_chat = 1003
        user_c_id = 1003

        # User A o'z INN sini kiritdi va qarzini ko'rdi
        self.memory.set_last_id(user_a_chat, user_a_id, "302568138", org_name="Fayz Savdo", debt=100000.0)
        self.memory.add_user_message(user_a_chat, user_a_id, "Qarzim qancha?")
        self.memory.add_assistant_message(user_a_chat, user_a_id, "Qarzingiz 100 000 so'm.")

        # User B o'z INN sini kiritdi
        self.memory.set_last_id(user_b_chat, user_b_id, "311790999", org_name="Baraka Baraka", debt=0.0)

        # User C hali hech narsa kiritmadi
        self.memory.add_user_message(user_c_chat, user_c_id, "Salom")

        # Tekshiruvlar:
        # User A faqat o'zinikini ko'radi
        self.assertEqual(self.memory.get_last_id(user_a_chat, user_a_id), "302568138")
        self.assertEqual(self.memory.get_org_name(user_a_chat, user_a_id), "Fayz Savdo")
        self.assertEqual(self.memory.get_debt_info(user_a_chat, user_a_id)["debt"], 100000.0)

        # User B faqat o'zinikini ko'radi
        self.assertEqual(self.memory.get_last_id(user_b_chat, user_b_id), "311790999")
        self.assertEqual(self.memory.get_org_name(user_b_chat, user_b_id), "Baraka Baraka")
        self.assertEqual(self.memory.get_debt_info(user_b_chat, user_b_id)["debt"], 0.0)

        # User C da boshqalarning ma'lumotlari umuman yo'q
        self.assertIsNone(self.memory.get_last_id(user_c_chat, user_c_id))
        self.assertIsNone(self.memory.get_org_name(user_c_chat, user_c_id))
        self.assertIsNone(self.memory.get_debt_info(user_c_chat, user_c_id))

    def test_02_group_chat_multi_user_isolation(self):
        """Bitta Telegram guruh ichida turli foydalanuvchilar yozganda ham ularning xotirasi ajralishi kerak"""
        group_chat_id = -10099887766
        user_1 = 5001
        user_2 = 5002

        self.memory.set_last_id(group_chat_id, user_1, "123456789", org_name="Korxona 1")
        self.memory.set_last_id(group_chat_id, user_2, "987654321", org_name="Korxona 2")

        self.assertEqual(self.memory.get_last_id(group_chat_id, user_1), "123456789")
        self.assertEqual(self.memory.get_last_id(group_chat_id, user_2), "987654321")

    # =========================================================================
    # 2. TO'LOV KVITANSIYALARI VA MANTIQ (EXACT, PARTIAL, OVERPAY, DUPLICATE)
    # =========================================================================
    def test_03_receipt_exact_debt_settlement(self):
        """Kvitansiya qarzni to'liq qoplagan holat (100,000 qarz, 100,000 to'lov)"""
        facts = ReceiptFacts(
            is_receipt=True,
            recipient_account="20208000800208044003",
            is_mars_recipient=True,
            amount=100000.0,
            payer_inn="302568138",
            payer_name="Mars Elektron Texnika",
            transaction_id="TX_EXACT_001",
            payment_system="Click",
            payment_purpose="subscription",
            is_duplicate=False
        )

        with patch.object(excel_manager, "search", return_value=[{"name": "Mars MChJ", "debt": 100000.0, "stir": "302568138", "tuman": "Shahrisabz"}]):
            res = core_engine.process_receipt_facts(facts, chat_id=101, user_id=101)
            self.assertEqual(res.action, ActionType.RECEIPT_PROCESSED)
            self.assertIn("Kvitansiyangiz qabul qilindi", res.reply_text)
            self.assertTrue(res.debt_status_info.get("debt_covered"))
            self.assertEqual(res.debt_status_info.get("remaining_debt"), 0.0)

    def test_04_receipt_partial_payment(self):
        """Kvitansiya qarzni qisman to'lagan holat (200,000 qarz, 80,000 to'lov -> 120,000 qoldiq)"""
        facts = ReceiptFacts(
            is_receipt=True,
            recipient_account="20208000800208044003",
            is_mars_recipient=True,
            amount=80000.0,
            payer_inn="302568138",
            payer_name="Mars Elektron Texnika",
            transaction_id="TX_PARTIAL_002",
            payment_system="Payme",
            payment_purpose="subscription",
            is_duplicate=False
        )

        with patch.object(excel_manager, "search", return_value=[{"name": "Mars MChJ", "debt": 200000.0, "stir": "302568138", "tuman": "Shahrisabz"}]):
            res = core_engine.process_receipt_facts(facts, chat_id=102, user_id=102)
            self.assertEqual(res.action, ActionType.RECEIPT_PROCESSED)
            self.assertIn("Kvitansiyangiz qabul qilindi", res.reply_text)
            self.assertFalse(res.debt_status_info.get("debt_covered"))
            self.assertEqual(res.debt_status_info.get("remaining_debt"), 120000.0)

    def test_05_receipt_overpayment_advance(self):
        """Qarzdan ko'p to'langan holat (100,000 qarz, 200,000 to'lov -> 100,000 avans)"""
        facts = ReceiptFacts(
            is_receipt=True,
            recipient_account="20208000800208044003",
            is_mars_recipient=True,
            amount=200000.0,
            payer_inn="302568138",
            payer_name="Mars Elektron Texnika",
            transaction_id="TX_OVERPAY_003",
            payment_system="Click",
            payment_purpose="subscription",
            is_duplicate=False
        )

        with patch.object(excel_manager, "search", return_value=[{"name": "Mars MChJ", "debt": 100000.0, "stir": "302568138", "tuman": "Shahrisabz"}]):
            res = core_engine.process_receipt_facts(facts, chat_id=103, user_id=103)
            self.assertEqual(res.action, ActionType.RECEIPT_PROCESSED)
            self.assertIn("Kvitansiyangiz qabul qilindi", res.reply_text)
            self.assertTrue(res.debt_status_info.get("debt_covered"))
            self.assertEqual(res.debt_status_info.get("remaining_debt"), 0.0)

    def test_06_receipt_duplicate_detection(self):
        """Bitta kvitansiya tranzaksiyasi 2 marta yuborilganda dublikat deb belgilanishi va ogohlantirish berishi"""
        tracker = TransactionTracker(filepath="/tmp/test_transactions.json")
        tracker.transactions = {}
        tracker.record_transaction("TX_DUP_999", "302568138", 100000.0, 104)

        # 2-marta tekshirganda True qaytishi kerak
        self.assertTrue(tracker.is_duplicate("TX_DUP_999"))
        self.assertFalse(tracker.is_duplicate("TX_FRESH_111"))

        facts = ReceiptFacts(
            is_receipt=True,
            recipient_account="20208000800208044003",
            is_mars_recipient=True,
            amount=100000.0,
            payer_inn="302568138",
            transaction_id="TX_DUP_999",
            is_duplicate=True
        )

        with patch("transaction_tracker.transaction_tracker.is_duplicate", return_value=True), \
             patch.object(excel_manager, "search", return_value=[{"name": "Mars MChJ", "debt": 0.0, "stir": "302568138", "tuman": "Shahrisabz"}]):
            res = core_engine.process_receipt_facts(facts, chat_id=104, user_id=104)
            self.assertIn("Kvitansiyangiz qabul qilindi", res.reply_text)
            self.assertTrue(res.is_duplicate)

    def test_07_receipt_soliq_annual_fiscal_fee(self):
        """Yillik Soliq («Yangi Texnologiyalar» DUK) to'lovi qabul qilinganda foydalanuvchiga 2-24 soat vaqt va Mars to'lovi alohidaligi tushuntirilishi"""
        facts = ReceiptFacts(
            is_receipt=True,
            recipient_account="23402000300100001010",
            is_mars_recipient=False,
            is_annual_fiscal_fee=True,
            payment_category="annual",
            amount=440000.0,
            payer_inn="302568138",
            transaction_id="TX_SOLIQ_888",
            payment_system="Click",
            is_duplicate=False
        )

        res = core_engine.process_receipt_facts(facts, chat_id=105, user_id=105)
        self.assertEqual(res.action, ActionType.RECEIPT_PROCESSED)
        self.assertIn("Kvitansiyangiz qabul qilindi", res.reply_text)
        self.assertTrue(res.debt_status_info.get("is_annual"))
        self.assertIn("Yangi Texnologiyalar", res.debt_status_info.get("recipient"))

    def test_08_receipt_unknown_third_party_recipient(self):
        """Marsga ham, Soliqqa ham tegishli bo'lmagan begona to'lov cheki yuborilganda ogohlantirish berishi"""
        facts = ReceiptFacts(
            is_receipt=True,
            recipient_account="20208000999999999999",
            is_mars_recipient=False,
            is_annual_fiscal_fee=False,
            payment_category="other",
            amount=50000.0,
            payer_inn="302568138",
            transaction_id="TX_OTHER_777"
        )

        res = core_engine.process_receipt_facts(facts, chat_id=106, user_id=106)
        self.assertIn("tegishli emasdek ko'rinmoqda", res.reply_text.lower())
        self.assertIn("20208000800208044003", res.reply_text)

    # =========================================================================
    # 3. MULTI-TERMINAL PER INN & DECOMMISSIONED (RED) COMBINATION
    # =========================================================================
    def test_09_multi_terminal_active_calculation(self):
        """Bitta INN da 2 ta apparat (1 Smart One, 1 P3) bo'lsa, apparatlar va oylik stavka to'g'ri ko'rsatilishi"""
        mock_results = [
            {"stir": "123456789", "name": "Mega Savdo", "debt": 100000.0, "is_p3": False, "terminal": "SMART01", "tuman": "Kitob"},
            {"stir": "123456789", "name": "Mega Savdo", "debt": 100000.0, "is_p3": True, "terminal": "P3HUMO02", "tuman": "Kitob"}
        ]

        with patch.object(excel_manager, "get_decommissioned", return_value=[]):
            resp = format_debt_response(mock_results)
            self.assertIn("Biriktirilgan apparatlar soni:</b> 2 ta", resp)
            self.assertIn("P3 Humo:</b> 1 ta", resp)
            self.assertIn("Smart One:</b> 1 ta", resp)
            self.assertIn("JAMI QARZDORLIK: 200,000 so'm", resp)

    def test_10_multi_terminal_active_plus_decommissioned(self):
        """Bitta INN da 1 ta faol apparat va 1 ta avval hisobdan chiqarilgan (qizil) apparat bo'lsa, eslatma berilishi"""
        mock_active = [
            {"stir": "123456789", "name": "Mega Savdo", "debt": 100000.0, "is_p3": False, "terminal": "SMART01", "tuman": "Kitob"}
        ]
        mock_decom = [
            {"stir": "123456789", "name": "Mega Savdo", "debt": 0.0, "is_p3": False, "terminal": "OLD_TERM", "is_decommissioned": True}
        ]

        with patch.object(excel_manager, "get_decommissioned", return_value=mock_decom):
            resp = format_debt_response(mock_active)
            self.assertIn("Apparat modeli:</b> Smart One", resp)
            self.assertIn("Terminal ID:</b> <code>SMART01</code>", resp)
            self.assertIn("Korxonaning 1 ta apparati avval hisobdan chiqarilgan", resp)
            # Faqat faol apparat qarzi hisoblangan
            self.assertIn("JAMI QARZDORLIK: 100,000 so'm", resp)

    # =========================================================================
    # 4. MEDIA GROUP (ALBUM) AND PDF BATCHING
    # =========================================================================
    def test_11_media_group_album_deduplication(self):
        """Bir vaqtda 3 ta rasm (album) yuborilganda birinchisi o'tib, keyingilari spam bo'lmasligi"""
        from handlers.media import _check_and_register_media_group, _PROCESSED_MEDIA_GROUPS
        _PROCESSED_MEDIA_GROUPS.clear()

        group_id = "album_test_12345"

        # 1-rasm o'tishi kerak
        is_first = _check_and_register_media_group(group_id)
        self.assertTrue(is_first)

        # 2-rasm rad etilishi kerak
        is_second = _check_and_register_media_group(group_id)
        self.assertFalse(is_second)

        # 3-rasm ham rad etilishi kerak
        is_third = _check_and_register_media_group(group_id)
        self.assertFalse(is_third)

        # Alohida yuborilgan (media_group_id bo'lmagan) rasm doim True qaytishi kerak
        self.assertTrue(_check_and_register_media_group(None))

    # =========================================================================
    # 5. ADMIN ESCALATION COMPLETENESS
    # =========================================================================
    async def _async_test_admin_escalation_details(self):
        """Adminga boradigan xabarda mijoz profili, INN, tuman, oxirgi rasm va xabar matni to'liq bo'lishi"""
        admin_mgr = AdminManager()
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        bot_mock.send_photo = AsyncMock()

        user_mock = MagicMock()
        user_mock.id = 778899
        user_mock.full_name = "Ali Valiyev"
        user_mock.username = "alivali"

        with patch.object(excel_manager, "get_district_for_inn", return_value="Kitob tumani"):
            await admin_mgr.notify_user_query_escalation(
                bot=bot_mock,
                user=user_mock,
                chat_id=778899,
                query_text="Apparatim o'chib qoldi, usta kerak",
                reason="Mijoz usta talab qilmoqda",
                inn="302568138",
                org_name="Fayz MChJ",
                photo_file_id="photo_file_12345"
            )

            # notify_admins orqali send_photo yoki send_message chaqirilganini tekshirish
            self.assertTrue(bot_mock.send_photo.called or bot_mock.send_message.called)
            call_kwargs = bot_mock.send_photo.call_args[1] if bot_mock.send_photo.called else bot_mock.send_message.call_args[1]
            content = call_kwargs.get("caption") or call_kwargs.get("text") or ""

            self.assertIn("Ali Valiyev", content)
            self.assertIn("@alivali", content)
            self.assertIn("302568138", content)
            self.assertIn("Fayz MChJ", content)
            self.assertIn("Kitob tumani", content)
            self.assertIn("Apparatim o'chib qoldi, usta kerak", content)

    def test_12_admin_escalation_details(self):
        asyncio.run(self._async_test_admin_escalation_details())


if __name__ == "__main__":
    unittest.main()
