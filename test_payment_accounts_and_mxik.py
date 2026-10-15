"""
test_payment_accounts_and_mxik.py
=================================
Yillik va Oylik hisob raqamlar, ularning qat'iy ajratilishi,
MXIK (IKPU / Tasnif / Soliq) bilimlari va kvitansiya tahlili test majmuasi.
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from payment_accounts import (
    MARS_ACCOUNT, MARS_INN, MARS_ORG_NAME, MARS_MONTHLY_FEE, MARS_VIDEO_ID, MARS_POST_ID,
    YANGI_TEXNOLOGIYALAR_ACCOUNT, YANGI_TEXNOLOGIYALAR_INN, YANGI_TEXNOLOGIYALAR_ORG_NAME,
    YANGI_TEXNOLOGIYALAR_ANNUAL_FEE, YANGI_TEXNOLOGIYALAR_VIDEO_ID, YANGI_TEXNOLOGIYALAR_POST_ID,
    get_monthly_payment_card, get_annual_payment_card, get_all_payment_accounts_card,
    get_mxik_guidance, classify_payment_intent, is_mxik_intent, classify_receipt_target
)
from core.models import ReceiptFacts, ActionType
from core.engine import core_engine
from excel_manager import excel_manager
from user_memory import user_memory
from admin_manager import admin_manager
from handlers.chat import handle_user_chat
from handlers.commands import cmd_tolov

class MockUser:
    def __init__(self, user_id: int, first_name: str, username: str = ""):
        self.id = user_id
        self.first_name = first_name
        self.full_name = first_name
        self.username = username

class MockChat:
    def __init__(self, chat_id: int, chat_type: str = "private"):
        self.id = chat_id
        self.type = chat_type

class MockMessage:
    def __init__(self, message_id: int, user: MockUser, chat: MockChat, text: str = "", caption: str = ""):
        self.message_id = message_id
        self.from_user = user
        self.chat = chat
        self.text = text
        self.caption = caption
        self.replies = []

    async def reply(self, text: str, parse_mode: str = "HTML", **kwargs):
        self.replies.append(text)
        return self

    async def answer(self, text: str, parse_mode: str = "HTML", **kwargs):
        self.replies.append(text)
        return self

def create_mock_bot():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_document = AsyncMock()
    bot.copy_message = AsyncMock()
    return bot


class TestPaymentAccountsAndMxik(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        user_memory.clear_context(12345, 11111)

    # =========================================================================
    # 1. YILLIK VA OYLIK SHOT SO'ROVLARINING QAT'IY AJRATILISHI
    # =========================================================================
    def test_payment_intent_classification(self):
        # Yillik to'lov so'rovlari
        self.assertEqual(classify_payment_intent("yillik shot qayerga to'lanadi?"), "annual")
        self.assertEqual(classify_payment_intent("yillik to'lov hisob raqami nima?"), "annual")
        self.assertEqual(classify_payment_intent("fiskal modul shotini tashlang"), "annual")
        self.assertEqual(classify_payment_intent("yangi texnologiyalar rekviziti"), "annual")
        self.assertEqual(classify_payment_intent("440000 to'lash uchun shot"), "annual")

        # Oylik to'lov so'rovlari
        self.assertEqual(classify_payment_intent("oylik shot qanaqa?"), "monthly")
        self.assertEqual(classify_payment_intent("mars hisob raqamini bering"), "monthly")
        self.assertEqual(classify_payment_intent("abonent to'lov qayerga to'lanadi?"), "monthly")
        self.assertEqual(classify_payment_intent("100 000 so'm oylik to'lov hisobi"), "monthly")

        # Ikkala to'lov / umumiy rekvizitlar
        self.assertEqual(classify_payment_intent("/tolov"), "both")
        self.assertEqual(classify_payment_intent("to'lov rekvizitlari"), "both")
        self.assertEqual(classify_payment_intent("shot raqamlar"), "both")
        self.assertEqual(classify_payment_intent("qayerga to'layman?"), "both")

        # Begona matn
        self.assertIsNone(classify_payment_intent("assalomu alaykum"))
        self.assertIsNone(classify_payment_intent("apparat ishlamayapti"))

    def test_payment_cards_content(self):
        # Oylik karta
        monthly_card = get_monthly_payment_card()
        self.assertIn("20208000800208044003", monthly_card)
        self.assertIn("«MARS ELEKTRON TEXNIKA» MCHJ", monthly_card)
        self.assertIn("100 000 so'm", monthly_card)
        self.assertIn("6-sanasigacha", monthly_card)

        # Yillik karta
        annual_card = get_annual_payment_card()
        self.assertIn("20210000100431200010", annual_card)
        self.assertIn("«Yangi Texnologiyalar» DUK", annual_card)
        self.assertIn("440 000 so'm", annual_card)
        self.assertIn("00668", annual_card)
        self.assertIn("mutlaqo alohidadir", annual_card)

        # To'liq umumiy karta
        all_card = get_all_payment_accounts_card()
        self.assertIn("20208000800208044003", all_card)
        self.assertIn("20210000100431200010", all_card)
        self.assertIn("adashtirmaslik lozim", all_card)

    # =========================================================================
    # 2. KVITANSIYA TURLARINING QAT'IY AJRATILISHI (ANNUAL VS MONTHLY)
    # =========================================================================
    def test_receipt_classification(self):
        # Yillik to'lov kvitansiyasi («Yangi Texnologiyalar» DUK)
        self.assertEqual(
            classify_receipt_target("20210000100431200010", 440000.0, "fiskal modul yillik"),
            "annual"
        )
        self.assertEqual(
            classify_receipt_target("Yangi Texnologiyalar DUK", 440000.0),
            "annual"
        )

        # Oylik to'lov kvitansiyasi («Mars Elektron Texnika»)
        self.assertEqual(
            classify_receipt_target("20208000800208044003", 100000.0, "abonent tolov"),
            "monthly"
        )
        self.assertEqual(
            classify_receipt_target("Mars Elektron Texnika MCHJ", 200000.0),
            "monthly"
        )

        # Begona kvitansiya
        self.assertEqual(
            classify_receipt_target("20208000999999999999", 50000.0, "kommunal"),
            "other"
        )

    def test_annual_fiscal_receipt_core_processing(self):
        # Yillik kvitansiya kelganda
        facts = ReceiptFacts(
            is_receipt=True,
            recipient_account="20210000100431200010",
            is_mars_recipient=False,
            is_annual_fiscal_fee=True,
            payment_category="annual",
            recipient_org_name=YANGI_TEXNOLOGIYALAR_ORG_NAME,
            amount=440000.0,
            payer_inn="206011507",
            payer_name="Test MCHJ",
            transaction_id="TX998877",
            payment_system="Click",
            raw_text="fiskal modulning yillik to'lovi"
        )

        decision = core_engine.process_receipt_facts(
            facts=facts,
            chat_id=12345,
            user_id=11111,
            user_comment=""
        )

        self.assertEqual(decision.action, ActionType.RECEIPT_PROCESSED)
        self.assertTrue(decision.should_notify_admin)
        self.assertEqual(decision.admin_alert_type, "annual_receipt")
        self.assertIn("Fiskal modulning yillik to'lov kvitansiyasi", decision.reply_text)
        self.assertIn("«Yangi Texnologiyalar» DUK", decision.reply_text)
        self.assertTrue("440,000" in decision.reply_text or "440 000" in decision.reply_text)
        self.assertIn("2 soatdan 24 soatgacha", decision.reply_text)
        # Mars abonent qarzi bilan aralashmaslik
        self.assertTrue(decision.debt_status_info.get("is_annual"))

    # =========================================================================
    # 3. MXIK (IKPU / TASNIF / SOLIQ) BILIMLAR BAZASI TESTI
    # =========================================================================
    def test_mxik_intent_detection(self):
        self.assertTrue(is_mxik_intent("mxik kod nima?"))
        self.assertTrue(is_mxik_intent("mixk kodni qanday qo'yaman?"))
        self.assertTrue(is_mxik_intent("ikpu kodi haqida ma'lumot bering"))
        self.assertTrue(is_mxik_intent("tasnif.soliq.uz saytidan kod qidirish"))
        self.assertTrue(is_mxik_intent("tovar qo'shish tartibi"))
        self.assertTrue(is_mxik_intent("mxik xatosi chiqdi"))
        self.assertTrue(is_mxik_intent("soliq jarimasi mxik sababli"))
        self.assertFalse(is_mxik_intent("soatni qanday to'g'irlayman?"))

    def test_mxik_guidance_routing(self):
        # Tasnif / qidirish
        t1, v1 = get_mxik_guidance("tasnif saytidan qidirish")
        self.assertEqual(v1, 28)
        self.assertIn("tasnif.soliq.uz", t1)

        # Tekshirish / jarima
        t2, v2 = get_mxik_guidance("mxik tekshirish va jarima")
        self.assertEqual(v2, 17)
        self.assertIn("jarima", t2)

        # Naqd cheklov / zapravka
        t3, v3 = get_mxik_guidance("zapravkada naqd pulga urib bo'lmayapti")
        self.assertEqual(v3, 133)
        self.assertIn("Naqd pulga savdo qilib bo'lmaydigan", t3)

        # Umumiy tovar qo'shish
        t4, v4 = get_mxik_guidance("mxik kod nima, qanday kiritaman?")
        self.assertEqual(v4, 15)
        self.assertIn("Tovar qo'shish", t4)

    # =========================================================================
    # 4. CHAT HANDLER INTEGRATSIYASI (YILLIK, OYLIK, MXIK)
    # =========================================================================
    async def test_chat_handler_yillik_shot_query(self):
        bot = create_mock_bot()
        user = MockUser(11111, "Farrux")
        chat = MockChat(12345)
        msg = MockMessage(101, user, chat, text="yillik to'lov hisob raqamini tashlang")

        await handle_user_chat(msg, bot)

        # Kanaldan Post 34 va Video 145 nusxalanganini tekshirish
        copied_ids = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
        self.assertIn(YANGI_TEXNOLOGIYALAR_POST_ID, copied_ids, "34-post kanaldan uzatilishi kerak")
        self.assertIn(YANGI_TEXNOLOGIYALAR_VIDEO_ID, copied_ids, "145-video kanaldan uzatilishi kerak")

    async def test_chat_handler_oylik_shot_query(self):
        bot = create_mock_bot()
        user = MockUser(22222, "Olim")
        chat = MockChat(23456)
        msg = MockMessage(102, user, chat, text="oylik to'lov shot raqamini bering")

        await handle_user_chat(msg, bot)

        # Kanaldan Post 85 va Video 148 nusxalanganini tekshirish
        copied_ids = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
        self.assertIn(MARS_POST_ID, copied_ids, "85-post kanaldan uzatilishi kerak")
        self.assertIn(MARS_VIDEO_ID, copied_ids, "148-video kanaldan uzatilishi kerak")

    async def test_chat_handler_mxik_query(self):
        bot = create_mock_bot()
        user = MockUser(33333, "Sardor")
        chat = MockChat(34567)
        msg = MockMessage(103, user, chat, text="mxik kod nima va qanday qo'yiladi?")

        await handle_user_chat(msg, bot)

        self.assertTrue(len(msg.replies) > 0)
        reply = msg.replies[0]
        self.assertIn("MXIK (ИКПУ)", reply)
        self.assertIn("Tovar qo'shish", reply)
        bot.copy_message.assert_called_with(
            chat_id=34567,
            from_chat_id=-1001641871516,
            message_id=15,
            reply_to_message_id=103
        )

    async def test_command_tolov(self):
        bot = create_mock_bot()
        user = MockUser(44444, "Jamshid")
        chat = MockChat(45678)
        msg = MockMessage(104, user, chat, text="/tolov")

        await cmd_tolov(msg, bot)

        self.assertTrue(len(msg.replies) > 0)
        reply = msg.replies[0]
        self.assertIn("adashtirmaslik lozim", reply)
        copied_ids = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
        self.assertIn(MARS_POST_ID, copied_ids)
        self.assertIn(YANGI_TEXNOLOGIYALAR_POST_ID, copied_ids)
        self.assertIn(MARS_VIDEO_ID, copied_ids)

    async def test_admin_annual_notification(self):
        bot = create_mock_bot()
        user = MockUser(55555, "Javlon", "javlon_user")
        receipt_facts = ReceiptFacts(
            is_receipt=True,
            recipient_account="20210000100431200010",
            amount=440000.0,
            transaction_id="TX776655",
            payment_system="Click",
            payment_date="2026-10-10 16:30"
        )
        debt_status_info = {
            "is_annual": True,
            "org_name": "TEST SAVDO MCHJ",
            "inn": "302568138",
            "paid_amount": 440000.0
        }

        # Vaqtincha test admin qo'shish
        orig_admins = list(admin_manager.admin_ids)
        admin_manager.admin_ids = [999111222]
        try:
            await admin_manager.notify_receipt_escalation(
                bot=bot,
                user=user,
                chat_id=56789,
                receipt_facts=receipt_facts,
                debt_status_info=debt_status_info,
                file_id="photo_123",
                is_photo=True
            )
            bot.send_photo.assert_called_once()
            call_args = bot.send_photo.call_args[1]
            self.assertIn("YILLIK FISKAL MODUL TO'LOVI", call_args["caption"])
            self.assertTrue("440,000" in call_args["caption"] or "440 000" in call_args["caption"])
            self.assertIn("«Yangi Texnologiyalar» DUK", call_args["caption"])
        finally:
            admin_manager.admin_ids = orig_admins


if __name__ == "__main__":
    unittest.main()
