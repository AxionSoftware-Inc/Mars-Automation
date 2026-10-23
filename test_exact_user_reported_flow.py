import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import types
from handlers.chat import handle_user_chat
from handlers.media import _process_fiscal_receipt_content
from core.models import ReceiptFacts, FiscalChekFacts
from user_memory import user_memory
from excel_manager import excel_manager
from payment_accounts import (
    MARS_POST_ID,
    MARS_VIDEO_ID,
    classify_payment_intent,
    is_annual_check_intent
)


class TestExactUserReportedFlow(unittest.IsolatedAsyncioTestCase):
    """
    Foydalanuvchi bildirgan real stsenariy testi:
    1. Chek tashlandi -> Oylikda 2 100 000 so'm qarz, Yillikda qarz yo'q (faol).
    2. 'qancha tolay' -> Oylik qarz 2 100 000 so'm ekani aytiladi.
    3. 'yillikkachi' -> Yillikdan qarz yo'q (faol) ekani aytiladi (shot tashlanmaydi yoki qarz yo'qligi tushuntiriladi).
    4. 'oylikchi' -> Aslo 'qarz yo'q 0' deyilmaydi! 2 100 000 qarz saqlanib qoladi va rekvizitlar uzatiladi.
    """

    def setUp(self):
        user_memory.clear()
        self.chat_id = 991122
        self.user_id = 991122

    async def _send_msg(self, bot, text: str) -> MagicMock:
        msg = MagicMock(spec=types.Message)
        msg.text = text
        msg.chat = MagicMock(id=self.chat_id)
        msg.from_user = MagicMock(id=self.user_id, full_name="Sardor", username="sardor_pos")
        self._counter = getattr(self, "_counter", 100) + 1
        msg.message_id = self._counter
        msg.reply = AsyncMock()
        msg.answer = AsyncMock()

        await handle_user_chat(msg, bot)
        return msg

    async def test_reported_turn_by_turn(self):
        bot = AsyncMock()
        bot.copy_message = AsyncMock()
        bot.send_message = AsyncMock()

        print("\n" + "=" * 60)
        print("🎯 REAL STSENARIY TESTI: CHEK -> QANCHA TO'LAY -> YILLIKKACHI -> OYLIKCHI")
        print("=" * 60)

        # 0. Test uchun bazaga 2 100 000 qarzli korxona kiritish yoki mavjudidan foydalanish
        test_inn = "206011507"
        # Baza tekshiruvi
        rec = excel_manager.search(test_inn)
        self.assertTrue(len(rec) > 0, "Test INN bazada topilmadi")
        print(f"Baza tekshirildi: INN={test_inn}, Qarz={sum(r.get('debt', 0.0) for r in rec):,.0f} so'm")

        # 1-QADAM: Kassa cheki tahlili
        print("\n🔹 [Turn 1: Chek yuborildi]")
        receipt_facts = ReceiptFacts(
            payer_inn=test_inn,
            fiscal_module="LG420210630789",
            is_fiscal_chek=True,
            fiscal_facts=FiscalChekFacts(
                inn=test_inn,
                fiscal_module="LG420210630789",
                org_name="QASHQADARYO SHARQ GAVHARI MCHJ",
                total_amount=50000.0
            )
        )

        msg_chek = MagicMock(spec=types.Message)
        msg_chek.chat = MagicMock(id=self.chat_id)
        msg_chek.from_user = MagicMock(id=self.user_id, full_name="Sardor", username="sardor_pos")
        msg_chek.message_id = 101
        msg_chek.reply = AsyncMock()

        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", return_value="Fiskal modul: LG420210630789\nHolati: To'langan va faol\nMuddati: 2026-12-31 gacha"):
            await _process_fiscal_receipt_content(
                message=msg_chek,
                bot=bot,
                receipt_facts=receipt_facts,
                user_script="latin",
                caption="",
                file_id="photo_123"
            )

        chek_reply = msg_chek.reply.call_args[0][0]
        print(f"🤖 Bot (Chek javobi): {chek_reply[:140]}...")
        self.assertIn("Qarzdorlik", chek_reply)
        self.assertIn("OFD", chek_reply)

        # Xotira tekshiruvi: Qarz 0 bo'lib qolmagan, aynan bazadagi qarz yozilgan!
        debt_in_mem = user_memory.get_debt_info(self.chat_id, self.user_id)
        self.assertIsNotNone(debt_in_mem)
        self.assertGreater(debt_in_mem["debt"], 0, "Qarz xotirada 0 bo'lib qolmasligi shart!")
        print(f"✅ Xotiradagi qarz saqlandi: {debt_in_mem['debt']:,.0f} so'm")

        # Yillik holat xotirasi tekshiruvi
        ann_status = user_memory.get_annual_status(self.chat_id, self.user_id)
        self.assertIsNotNone(ann_status)
        self.assertFalse(ann_status["has_debt"])
        print(f"✅ Xotiradagi yillik holat saqlandi: has_debt={ann_status['has_debt']}")

        # 2-QADAM: "qancha tolay"
        print("\n🔹 [Turn 2] Mijoz: 'qancha tolay'")
        context_str = user_memory.get_context_summary(self.chat_id, self.user_id)
        self.assertIn("«Mars» oylik abonent to'lovidan joriy qarzdorlik", context_str)
        self.assertIn("Davlat Soliq (OFD) yillik to'lovi: QARZDORLIK YO'Q", context_str)

        msg2 = await self._send_msg(bot, "qancha tolay")
        reply2 = msg2.reply.call_args[0][0]
        print(f"🤖 Bot: {reply2}")
        # Bot qarz borligini aytishi kerak, 0 so'm deb aldamasligi shart
        self.assertNotIn("qarzingiz yo'q (0 so'm)", reply2.lower())
        self.assertIn("qarz", reply2.lower())

        # 3-QADAM: "yillikkachi"
        print("\n🔹 [Turn 3] Mijoz: 'yillikkachi'")
        self.assertTrue(is_annual_check_intent("yillikkachi"))
        self.assertIsNone(classify_payment_intent("yillikkachi"))

        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", return_value="Fiskal modul: LG420210630789\nHolati: To'langan va faol\nMuddati: 2026-12-31 gacha"):
            msg3 = await self._send_msg(bot, "yillikkachi")
            reply3 = msg3.reply.call_args[0][0]
            print(f"🤖 Bot: {reply3[:140]}...")
            self.assertIn("QARZDORLIK YO'Q", reply3.upper())

            # 3.1-QADAM: "yillikchi" -> Yillikdan qarz yo'q bo'lsa, XR uzatilmaydi! Faqat qarz yo'q deyiladi!
            print("\n🔹 [Turn 3.1] Mijoz: 'yillikchi'")
            bot.copy_message.reset_mock()
            self.assertEqual(classify_payment_intent("yillikchi"), "annual")
            msg3_1 = await self._send_msg(bot, "yillikchi")
            reply3_1 = msg3_1.reply.call_args[0][0]
            print(f"🤖 Bot: {reply3_1}")
            self.assertIn("QARZDORLIK YO'Q", reply3_1.upper())
            self.assertEqual(bot.copy_message.call_count, 0, "Yillikdan qarz yo'q bo'lsa, aslo XR posti uzatilmasligi shart!")

        # 4-QADAM: "oylikchi"
        print("\n🔹 [Turn 4] Mijoz: 'oylikchi'")
        bot.copy_message.reset_mock()
        await self._send_msg(bot, "oylikchi")
        
        # Oylik hisob raqami kanaldan uzatiladi (video esa avtomatik uzatilmaydi)
        self.assertEqual(bot.copy_message.call_count, 1)
        copied_ids = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
        print(f"🤖 Bot kanaldan uzatdi: {copied_ids}")
        self.assertIn(MARS_POST_ID, copied_ids)
        self.assertNotIn(MARS_VIDEO_ID, copied_ids)

        # Eng muhimi: Qarz hali ham xotirada 2 100 000 bo'lib turibdi, 0 ga aylanmagan!
        debt_after_oylikchi = user_memory.get_debt_info(self.chat_id, self.user_id)
        self.assertGreater(debt_after_oylikchi["debt"], 0, "Oylikchi so'rovidan keyin ham qarz saqlanishi shart!")
        print(f"✅ Xotiradagi qarz o'zgarmadi: {debt_after_oylikchi['debt']:,.0f} so'm")

        print("\n" + "=" * 60)
        print("✅ REAL STSENARIY TESTI 100% MUVAFFAQIYATLI O'TDI!")
        print("=" * 60 + "\n")

    async def test_annual_debt_exists_flow(self):
        """Yillik to'lovdan haqiqatan qarz bo'lsa, qarz summasi aytiladi va post 34 uzatiladi"""
        bot = AsyncMock()
        bot.copy_message = AsyncMock()
        bot.send_message = AsyncMock()

        test_inn = "206011507"
        receipt_facts = ReceiptFacts(
            payer_inn=test_inn,
            fiscal_module="LG420210630789",
            is_fiscal_chek=True,
            fiscal_facts=FiscalChekFacts(
                inn=test_inn,
                fiscal_module="LG420210630789",
                org_name="QASHQADARYO SHARQ GAVHARI MCHJ",
                total_amount=50000.0
            )
        )

        msg_chek = MagicMock(spec=types.Message)
        msg_chek.chat = MagicMock(id=self.chat_id)
        msg_chek.from_user = MagicMock(id=self.user_id, full_name="Sardor", username="sardor_pos")
        msg_chek.message_id = 201
        msg_chek.reply = AsyncMock()

        from payment_accounts import YANGI_TEXNOLOGIYALAR_POST_ID, YANGI_TEXNOLOGIYALAR_VIDEO_ID

        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", return_value="FMO dan qarzdorlik mavjud (440 000 so'm)"):
            await _process_fiscal_receipt_content(
                message=msg_chek,
                bot=bot,
                receipt_facts=receipt_facts,
                user_script="latin",
                caption="",
                file_id="photo_123"
            )

        chek_reply = msg_chek.reply.call_args[0][0]
        self.assertIn("Qarzdorlik", chek_reply)
        self.assertIn("440 000", chek_reply)
        # Chekda ham oylik, ham yillik qarz bo'lgani uchun postlar uzatiladi
        copied_ids = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
        self.assertIn(YANGI_TEXNOLOGIYALAR_POST_ID, copied_ids)

        # Endi mijoz: 'yillikchi' desa, qarz borligi va post 34 uzatilishi kerak
        bot.copy_message.reset_mock()
        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", return_value="FMO dan qarzdorlik mavjud (440 000 so'm)"):
            msg_yillik = await self._send_msg(bot, "yillikchi")
            rep_yillik = msg_yillik.reply.call_args[0][0]
            self.assertIn("QARZDORLIK MAVJUD", rep_yillik.upper())
            copied_ids2 = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
            self.assertIn(YANGI_TEXNOLOGIYALAR_POST_ID, copied_ids2)

    async def test_multi_inn_alternating_questions_and_payment(self):
        """
        Foydalanuvchi bildirgan kasha stsenariy:
        1. 1-INN yuborildi (qarz 0)
        2. 2-INN yuborildi (qarz bor)
        3. 'oylikdan qarzim bormi' -> qarz borligi chiqishi shart (0 emas)
        4. 'qarzim qancha' -> qarz borligi chiqishi shart (0 emas)
        5. 'qayerga tolashim kerak' -> Post 85 / 148 uzatilishi shart, o'zi doston yozmasligi kerak
        6. 'qarzdorligim bormi' -> qarz borligi chiqishi shart (0 emas)
        7. 'oylikdan qancha qarzman' -> qarz borligi chiqishi shart (0 emas)
        8. 'qaysi inn boyicha qarz bor' -> ikkala INN holatini aniq ajratib berishi kerak
        """
        bot = AsyncMock()
        bot.copy_message = AsyncMock()
        bot.send_message = AsyncMock()

        inn_zero = "302568138"
        inn_with_debt = "206011507"

        # 1. 1-INN (qarz 0)
        m1 = await self._send_msg(bot, inn_zero)
        r1 = m1.reply.call_args[0][0]
        self.assertIn("0 so'm", r1)

        # 2. 2-INN (qarz bor)
        m2 = await self._send_msg(bot, inn_with_debt)
        r2 = m2.reply.call_args[0][0]
        self.assertIn("qarzdorlik", r2.lower())
        self.assertNotIn("qarzdorlik yo'q", r2.lower())

        # 3. 'oylikdan qarzim bormi'
        m3 = await self._send_msg(bot, "oylikdan qarzim bormi")
        r3 = m3.reply.call_args[0][0]
        self.assertIn("qarzdorlik", r3.lower())
        self.assertNotIn("qarzdorlik yo'q", r3.lower())

        # 4. 'qarzim qancha'
        m4 = await self._send_msg(bot, "qarzim qancha")
        r4 = m4.reply.call_args[0][0]
        self.assertIn("qarzdorlik", r4.lower())
        self.assertNotIn("qarzdorlik yo'q", r4.lower())

        # 5. 'qayerga tolashim kerak'
        bot.copy_message.reset_mock()
        m5 = await self._send_msg(bot, "qayerga tolashim kerak")
        self.assertEqual(bot.copy_message.call_count, 1, "Qayerga tolashim kerak so'roviga kanal posti 85 uzatilishi shart!")
        copied_ids = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
        self.assertIn(MARS_POST_ID, copied_ids)
        self.assertNotIn(MARS_VIDEO_ID, copied_ids)

        # 6. 'qarzdorligim bormi'
        m6 = await self._send_msg(bot, "qarzdorligim bormi")
        r6 = m6.reply.call_args[0][0]
        self.assertIn("qarzdorlik", r6.lower())
        self.assertNotIn("qarzdorlik yo'q", r6.lower())

        # 7. 'oylikdan qancha qarzman'
        m7 = await self._send_msg(bot, "oylikdan qancha qarzman")
        r7 = m7.reply.call_args[0][0]
        self.assertIn("qarzdorlik", r7.lower())
        self.assertNotIn("qarzdorlik yo'q", r7.lower())

        # 8. 'qaysi inn boyicha qarz bor'
        m8 = await self._send_msg(bot, "qaysi inn boyicha qarz bor")
        r8 = m8.reply.call_args[0][0]
        self.assertIn(inn_zero, r8)
        self.assertIn(inn_with_debt, r8)


if __name__ == "__main__":
    unittest.main()
