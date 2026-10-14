import unittest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from core.models import (
    ReceiptFacts,
    FiscalChekFacts,
    extract_clean_inn,
    extract_fiscal_module
)
from image_analyzer import analyze_media_image
from user_memory import user_memory
from excel_manager import excel_manager
from ofd_bridge import ofd_bridge
from handlers.media import _process_fiscal_receipt_content
from handlers.intents.billing import BillingIntentHandler

class TestFiscalChekVsKvitansiya(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        user_memory.clear()

    def tearDown(self):
        user_memory.clear()

    # =========================================================================
    # 1. VISION CLASSIFICATION & EXTRACTION TESTS
    # =========================================================================

    def test_01_classify_click_payment_receipt_as_receipt(self):
        """To'lov kvitansiyasi (Click/Payme) to'g'ri 'receipt' deb aniqlanishi va fiscal_chek EMASLIGI"""
        mock_response = json.dumps({
            "media_type": "receipt",
            "receipt": {
                "recipient_account": "20208000800208044003",
                "is_mars_recipient": True,
                "amount": 100000.0,
                "payer_inn": "302568138",
                "payer_name": "BARAKA MCHJ",
                "payment_date": "2026-10-10 11:30",
                "transaction_id": "TX998877",
                "payment_system": "Click",
                "summary": "Mars Elektron Texnika uchun 100 000 so'm abonent to'lovi"
            }
        })

        with patch("openrouter_client.openrouter_client.chat_completion", return_value=mock_response):
            m_type, r_facts, d_facts = analyze_media_image(b"fake_bytes", user_caption="to'lov qildim")

            self.assertEqual(m_type, "receipt")
            self.assertIsNotNone(r_facts)
            self.assertTrue(r_facts.is_receipt)
            self.assertFalse(r_facts.is_fiscal_chek)
            self.assertEqual(r_facts.amount, 100000.0)
            self.assertEqual(r_facts.payer_inn, "302568138")
            self.assertTrue(r_facts.is_mars_recipient)

    def test_02_classify_thermal_kassa_chek_as_fiscal_receipt(self):
        """Kassa apparatidan chiqqan savdo cheki 'fiscal_receipt' deb aniqlanishi va INN + FM olinishi"""
        mock_response = json.dumps({
            "media_type": "fiscal_receipt",
            "fiscal_receipt": {
                "inn": "308123456",
                "fiscal_module": "LG420210630789",
                "org_name": "OMADLI SAVDO MCHJ",
                "terminal_id": "01234567",
                "check_number": "45",
                "total_amount": 25000.0,
                "date_time": "2026-10-14 12:40",
                "receipt_type": "sale",
                "summary": "Savdo cheki, STIR: 308123456, Fiskal modul: LG420210630789, Jami: 25 000 so'm"
            }
        })

        with patch("openrouter_client.openrouter_client.chat_completion", return_value=mock_response):
            m_type, r_facts, d_facts = analyze_media_image(b"fake_bytes", user_caption="")

            self.assertEqual(m_type, "fiscal_receipt")
            self.assertIsNotNone(r_facts)
            self.assertTrue(r_facts.is_fiscal_chek)
            self.assertFalse(r_facts.is_receipt)
            self.assertEqual(r_facts.payer_inn, "308123456")
            self.assertEqual(r_facts.fiscal_module, "LG420210630789")
            self.assertEqual(r_facts.payer_name, "OMADLI SAVDO MCHJ")
            self.assertIsNotNone(r_facts.fiscal_facts)
            self.assertEqual(r_facts.fiscal_facts.inn, "308123456")
            self.assertEqual(r_facts.fiscal_facts.fiscal_module, "LG420210630789")

    def test_03_thermal_receipt_with_sales_amount_not_flipped_to_payment_receipt(self):
        """Chekda 25 000 so'm xarid summasi bo'lsa ham, u to'lov kvitansiyasiga aylanib ketmasligi shart!"""
        mock_response = json.dumps({
            "media_type": "fiscal_receipt",
            "fiscal_receipt": {
                "inn": "200112233",
                "fiscal_module": "YG202106307890",
                "org_name": "BARAKA NON XK",
                "total_amount": 15000.0,
                "summary": "Fiskal kassa cheki, STIR: 200112233, FM: YG202106307890"
            },
            "receipt": {
                "amount": 15000.0,
                "summary": "Non xaridi 15000 som"
            }
        })

        with patch("openrouter_client.openrouter_client.chat_completion", return_value=mock_response):
            m_type, r_facts, d_facts = analyze_media_image(b"fake_bytes", user_caption="chek urdim")

            self.assertEqual(m_type, "fiscal_receipt")
            self.assertTrue(r_facts.is_fiscal_chek)
            self.assertFalse(r_facts.is_receipt)
            self.assertEqual(r_facts.payer_inn, "200112233")
            self.assertEqual(r_facts.fiscal_module, "YG202106307890")

    # =========================================================================
    # 2. PROCESSING FISCAL RECEIPT IN HANDLER (DUAL DEBT CHECK & NO ADMIN ALERT)
    # =========================================================================

    async def test_04_process_fiscal_receipt_checks_excel_and_ofd(self):
        """Kassa cheki kelganda bot ham Excel (oylik), ham OFD (yillik) qarzni tekshirishi va javob berishi"""
        bot = AsyncMock()
        message = AsyncMock()
        message.chat.id = 1111
        message.from_user.id = 2222
        message.reply = AsyncMock()

        # Excelda qarz bor qilib belgilaymiz
        excel_manager.stir_index["308123456"] = [{
            "stir": "308123456",
            "name": "OMADLI SAVDO MCHJ",
            "debt": 100000.0,
            "paid_date": "2026-09-06",
            "tuman": "Shahrisabz",
            "terminal": "01234567"
        }]

        # OFD botida yillik qarzdorlik bor deb qaytaramiz
        ofd_mock_reply = "Fiskal modul faol holatda. Lekin, VMQ-943 ga ko‘ra FMO dan qarzdorlik mavjud."

        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = ofd_mock_reply

            fiscal_facts = FiscalChekFacts(
                is_fiscal_chek=True,
                inn="308123456",
                fiscal_module="LG420210630789",
                org_name="OMADLI SAVDO MCHJ"
            )
            receipt_facts = ReceiptFacts(
                is_receipt=False,
                is_fiscal_chek=True,
                payer_inn="308123456",
                fiscal_module="LG420210630789",
                payer_name="OMADLI SAVDO MCHJ",
                fiscal_facts=fiscal_facts
            )

            await _process_fiscal_receipt_content(
                message=message,
                bot=bot,
                receipt_facts=receipt_facts,
                user_script="latin",
                caption="",
                file_id="photo_123"
            )

            # 1. Reply yuborilganini tekshiramiz
            self.assertTrue(message.reply.called)
            reply_call_args = message.reply.call_args[0][0]

            # 2. Xabarda INN va Fiskal modul aks etgan bo'lishi kerak
            self.assertIn("308123456", reply_call_args)
            self.assertIn("LG420210630789", reply_call_args)

            # 3. «Mars» oylik qarzdorligi ko'rsatilgan
            self.assertIn("100 000", reply_call_args)
            self.assertIn("Mars", reply_call_args)

            # 4. Soliq (OFD) yillik qarzdorligi ko'rsatilgan
            self.assertTrue("Soliq" in reply_call_args or "OFD" in reply_call_args)

            # 5. user_memory ga INN va FM saqlangan bo'lishi kerak!
            self.assertEqual(user_memory.get_last_id(1111, 2222), "308123456")
            self.assertEqual(user_memory.get_last_fm(1111, 2222), "LG420210630789")

    async def test_05_subsequent_question_remembers_inn_and_fm_from_chek(self):
        """Chek tashlangandan so'ng mijoz 'oylikdanchi?' yoki 'yillikdanchi?' desa xotiradan to'g'ri topishi"""
        bot = AsyncMock()
        message = AsyncMock()
        message.chat.id = 5555
        message.from_user.id = 6666
        message.reply = AsyncMock()
        message.answer = AsyncMock()

        # Chekdan xotiraga yozib qo'yilgan holat
        user_memory.set_last_id(5555, 6666, "308123456")
        user_memory.set_last_fm(5555, 6666, "LG420210630789")
        user_memory.set_last_topic(5555, 6666, "fiscal_receipt_checked")

        excel_manager.stir_index["308123456"] = [{
            "stir": "308123456",
            "name": "OMADLI SAVDO MCHJ",
            "debt": 0.0,
            "paid_date": "2026-11-06",
            "tuman": "Shahrisabz",
            "terminal": "01234567"
        }]

        billing_handler = BillingIntentHandler()

        # 1. Foydalanuvchi "oylikdanchi?" deb so'raydi
        message.text = "oylikdanchi?"
        with patch("handlers.debt.process_and_send_debt_result", new_callable=AsyncMock) as mock_debt:
            res = await billing_handler.handle(message, bot, "latin")
            self.assertTrue(res)
            self.assertTrue(mock_debt.called)
            self.assertEqual(mock_debt.call_args[0][2], "308123456")

        # 2. Foydalanuvchi "yillikdanchi?" deb so'raydi
        message.text = "yillikdanchi?"
        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = "Fiskal modul faol holatda. Qarzdorlik mavjud emas."
            res = await billing_handler.handle(message, bot, "latin")
            self.assertTrue(res)
            self.assertTrue(mock_ofd.called)
            self.assertEqual(mock_ofd.call_args[0][1], "LG420210630789")

    async def test_06_chek_with_only_inn_prompts_for_fm(self):
        """Agar chekning faqat yuqori qismi tushgan bo'lsa (faqat INN bor, FM yo'q)"""
        bot = AsyncMock()
        message = AsyncMock()
        message.chat.id = 7777
        message.from_user.id = 8888
        message.reply = AsyncMock()

        excel_manager.stir_index["308123456"] = [{
            "stir": "308123456",
            "name": "TEST SAVDO",
            "debt": 0.0,
            "paid_date": "2026-11-06",
            "tuman": "Shahrisabz",
            "terminal": "01234567"
        }]

        fiscal_facts = FiscalChekFacts(
            is_fiscal_chek=True,
            inn="308123456",
            fiscal_module=None,
            org_name="TEST SAVDO"
        )
        receipt_facts = ReceiptFacts(
            is_receipt=False,
            is_fiscal_chek=True,
            payer_inn="308123456",
            fiscal_module=None,
            payer_name="TEST SAVDO",
            fiscal_facts=fiscal_facts
        )

        await _process_fiscal_receipt_content(
            message=message,
            bot=bot,
            receipt_facts=receipt_facts,
            user_script="latin",
            caption="",
            file_id="photo_only_inn"
        )

        self.assertTrue(message.reply.called)
        text = message.reply.call_args[0][0]
        self.assertIn("308123456", text)
        self.assertIn("Qarzdorlik yo'q", text)
        self.assertIn("Fiskal modul seriya raqamini", text)

    async def test_07_chek_with_unreadable_inn_and_fm_prompts_clearer_photo(self):
        """Agar chek juda xira bo'lib na INN na FM o'qilmasa, tushunarli yo'l-yo'riq berilishi"""
        bot = AsyncMock()
        message = AsyncMock()
        message.chat.id = 9999
        message.from_user.id = 1010
        message.reply = AsyncMock()

        fiscal_facts = FiscalChekFacts(
            is_fiscal_chek=True,
            inn=None,
            fiscal_module=None
        )
        receipt_facts = ReceiptFacts(
            is_receipt=False,
            is_fiscal_chek=True,
            payer_inn=None,
            fiscal_module=None,
            fiscal_facts=fiscal_facts
        )

        await _process_fiscal_receipt_content(
            message=message,
            bot=bot,
            receipt_facts=receipt_facts,
            user_script="latin",
            caption="",
            file_id="photo_blurry"
        )

        self.assertTrue(message.reply.called)
        text = message.reply.call_args[0][0]
        self.assertTrue("aniq o'qib bo'lmadi" in text or "aniq rasmga" in text)

    async def test_08_core_engine_does_not_escalate_fiscal_receipt_to_admin(self):
        """core_engine ga agar fiscal_receipt tushib qolsa, adminga soxta to'lov eskalatsiyasi yubormasligi"""
        from core import core_engine, ActionType

        fiscal_facts = FiscalChekFacts(
            is_fiscal_chek=True,
            inn="308123456",
            fiscal_module="LG420210630789"
        )
        receipt_facts = ReceiptFacts(
            is_receipt=False,
            is_fiscal_chek=True,
            payer_inn="308123456",
            fiscal_module="LG420210630789",
            amount=15000.0,
            fiscal_facts=fiscal_facts
        )

        decision = core_engine.process_receipt_facts(
            facts=receipt_facts,
            chat_id=111,
            user_id=222
        )

        self.assertEqual(decision.action, ActionType.IGNORE)
        self.assertFalse(decision.should_notify_admin)

if __name__ == "__main__":
    unittest.main()
