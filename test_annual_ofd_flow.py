import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from payment_accounts import (
    is_annual_check_intent,
    is_annual_pay_intent,
    format_ofd_annual_status,
    get_annual_payment_card
)
from user_memory import user_memory
from handlers.chat import handle_user_chat


class TestAnnualOFDFlow(unittest.TestCase):
    def test_01_annual_check_intent_recognition(self):
        """Yillik to'lov va OFD tekshirish so'rovlari to'g'ri aniqlanishi kerak"""
        positive_cases = [
            "yillik tulovniyam tekshirb ber",
            "yillik to'lovim bormi",
            "yillik tolovni tekshir",
            "yillikni tekshir",
            "yillik qarzim bormi",
            "fiskal modul muddatini tekshirib bering",
            "ofd tekshir",
            "ofd qarz",
            "soliq qarzim bormi",
            "йиллик тўловни текшир",
            "фискал модулни текшир"
        ]
        for phrase in positive_cases:
            with self.subTest(phrase=phrase):
                self.assertTrue(is_annual_check_intent(phrase), f"Failed for: {phrase}")

        negative_cases = [
            "salom",
            "chek qanday uriladi",
            "oylik to'lov qancha",
            "qog'oz qotib qoldi"
        ]
        for phrase in negative_cases:
            with self.subTest(phrase=phrase):
                self.assertFalse(is_annual_check_intent(phrase), f"Should be False for: {phrase}")

    def test_02_annual_pay_intent_recognition(self):
        """To'layman va shot raqam so'rovlari to'g'ri aniqlanishi kerak"""
        # Aniq yillik to'lov so'rovi
        self.assertTrue(is_annual_pay_intent("yillik to'lov uchun shot raqam tashla"))
        self.assertTrue(is_annual_pay_intent("yillik to'layman"))
        self.assertTrue(is_annual_pay_intent("fiskal modul to'lov shotini ber"))

        # Kontekst orqali (oxirgi mavzu annual_debt_exists bo'lganda)
        self.assertTrue(is_annual_pay_intent("to'layman", last_topic="annual_debt_exists"))
        self.assertTrue(is_annual_pay_intent("shot raqam tashla", last_topic="annual_debt_exists"))
        self.assertTrue(is_annual_pay_intent("shotini tashla", last_topic="annual_debt_exists"))
        self.assertTrue(is_annual_pay_intent("rekvizit tashla", last_topic="annual_debt_exists"))

    def test_03_format_ofd_annual_status(self):
        """OFD botidan kelgan xabar bo'yicha to'g'ri status shakllanishi"""
        # Qarzdorlik mavjud holat
        debt_raw = (
            "Fiskal modul faol holatda. \n"
            "Lekin, VMQ-943 ga ko‘ra FMO dan qarzdorlik mavjud. To‘lov qilish muddati: 12.10.2026 yil. "
            "Kassani o‘chirib yoqish hamda internetga ulash tavsiya etiladi."
        )
        debt_status = format_ofd_annual_status("UZ200701040469", debt_raw)
        self.assertIn("QARZDORLIK MAVJUD", debt_status)
        self.assertIn("440 000 so'm", debt_status)
        self.assertIn("UZ200701040469", debt_status)
        self.assertIn("«To'layman»", debt_status)

        # Qarzdorlik yo'q holat
        clear_raw = "Fiskal modul faol holatda. Qarzdorlik mavjud emas."
        clear_status = format_ofd_annual_status("LG420210630789", clear_raw)
        self.assertIn("QARZDORLIK YO'Q", clear_status)
        self.assertIn("LG420210630789", clear_status)

        # Topilmagan holat
        not_found_raw = "Bunday fiskal modul mavjud emas! Qaytadan urinib ko‘ring."
        nf_status = format_ofd_annual_status("XX1234567890", not_found_raw)
        self.assertIn("topilmadi", nf_status.lower())

    async def _async_test_full_chat_flow(self):
        """Mijoz yillik qarz tekshirishdan to'lov shot olishgacha bo'lgan to'liq suhbat oqimi"""
        bot = MagicMock()
        bot.copy_message = AsyncMock()

        chat_id = 998877
        user_id = 998877
        user_memory.clear_context(chat_id, user_id)

        # 1-Qadam: Mijoz "yillik tulovniyam tekshirb ber" dedi
        msg1 = MagicMock()
        msg1.text = "yillik tulovniyam tekshirb ber"
        msg1.chat.id = chat_id
        msg1.chat.type = "supergroup"
        msg1.from_user.id = user_id
        msg1.from_user.username = "test_user"
        msg1.from_user.full_name = "Test User"
        msg1.reply = AsyncMock()

        await handle_user_chat(msg1, bot)
        self.assertTrue(msg1.reply.called)
        reply1_text = msg1.reply.call_args[0][0]
        self.assertIn("Fiskal modul seriya raqamini", reply1_text)

        # 2-Qadam: Mijoz o'z fiskal modulini kiritdi
        msg2 = MagicMock()
        msg2.text = "UZ200701040469"
        msg2.chat.id = chat_id
        msg2.chat.type = "supergroup"
        msg2.from_user.id = user_id
        msg2.reply = AsyncMock()

        mock_ofd_reply = (
            "Fiskal modul faol holatda. \n"
            "Lekin, VMQ-943 ga ko‘ra FMO dan qarzdorlik mavjud. To‘lov qilish muddati: 12.10.2026 yil."
        )
        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", new_callable=AsyncMock, return_value=mock_ofd_reply):
            await handle_user_chat(msg2, bot)
            self.assertTrue(msg2.reply.called)
            reply2_text = msg2.reply.call_args[0][0]
            self.assertIn("QARZDORLIK MAVJUD", reply2_text)
            self.assertIn("440 000 so'm", reply2_text)

        # 3-Qadam: Mijoz to'layman deb shot raqam so'radi
        msg3 = MagicMock()
        msg3.text = "To'layman, shot raqam tashla"
        msg3.chat.id = chat_id
        msg3.chat.type = "supergroup"
        msg3.from_user.id = user_id
        msg3.reply = AsyncMock()

        await handle_user_chat(msg3, bot)
        self.assertTrue(msg3.reply.called)
        reply3_text = msg3.reply.call_args[0][0]
        self.assertIn("20210000100431200010", reply3_text)
        self.assertIn("Yangi Texnologiyalar", reply3_text)
        self.assertTrue(bot.copy_message.called)
        self.assertEqual(bot.copy_message.call_args[1]["message_id"], 145)

    def test_04_full_chat_flow(self):
        asyncio.run(self._async_test_full_chat_flow())


if __name__ == "__main__":
    unittest.main()
