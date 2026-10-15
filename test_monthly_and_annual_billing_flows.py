import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import types, Bot
from aiogram.enums import ChatType
from user_memory import user_memory
from excel_manager import excel_manager
from handlers.chat import handle_user_chat
from ofd_bridge import ofd_bridge
from payment_accounts import (
    is_annual_check_intent,
    is_monthly_check_intent,
    is_both_check_intent,
    format_ofd_annual_status
)
from handlers.debt import (
    is_debt_inquiry,
    handle_debt_inquiry,
    is_inn_or_phone_query_message,
    handle_inn_query
)


class TestMonthlyAndAnnualBillingFlows(unittest.IsolatedAsyncioTestCase):
    """
    Oylik va Yillik to'lov tekshiruvlarining to'liq va mukammal test to'plami:
    1. Oylik qarz so'rovi (baza bo'yicha)
    2. Yillik to'lov so'rovi (Fiskal modul va INN orqali OFD tekshiruvi)
    3. Ikkala to'lovni birgalikda tekshirish (Dual check)
    4. Ketma-ket suhbat: Oylikdan keyin "yillikdanchi", "yillik to'lovni tekshir"
    5. Turli iboralar va xalqona so'rovlar ("yillikni qayta tekshir", "yillik to'lov haqida")
    6. OFD ko'prigi orqali javob olish va keshdan o'qish
    """

    def setUp(self):
        user_memory.clear()
        ofd_bridge._cache.clear()

    async def _send_msg(self, chat_id: int, user_id: int, text: str, bot_mock: AsyncMock) -> str:
        mock_msg = MagicMock(spec=types.Message)
        mock_msg.chat = MagicMock(id=chat_id, type=ChatType.PRIVATE if chat_id > 0 else ChatType.SUPERGROUP)
        mock_msg.from_user = MagicMock(id=user_id, username=f"user_{user_id}", first_name=f"User_{user_id}")
        mock_msg.text = text
        mock_msg.message_id = 5000 + len(user_memory.get_user_history(chat_id, user_id))

        reply_texts = []
        async def fake_reply(resp_text, *args, **kwargs):
            reply_texts.append(str(resp_text))
        mock_msg.reply = AsyncMock(side_effect=fake_reply)
        mock_msg.answer = AsyncMock(side_effect=fake_reply)
        initial_copy_count = bot_mock.copy_message.call_count

        if is_debt_inquiry(mock_msg):
            await handle_debt_inquiry(mock_msg)
        elif is_inn_or_phone_query_message(mock_msg):
            await handle_inn_query(mock_msg, bot_mock)
        else:
            await handle_user_chat(mock_msg, bot_mock)

        new_copy_calls = bot_mock.copy_message.call_count - initial_copy_count
        if new_copy_calls > 0:
            for call_item in bot_mock.copy_message.call_args_list[-new_copy_calls:]:
                msg_id = call_item.kwargs.get("message_id")
                if not msg_id and len(call_item.args) > 2:
                    msg_id = call_item.args[2]
                reply_texts.append(f"[Video/Post: {msg_id}]")

        return "\n".join(reply_texts)

    # 1. OYLIK QARZ TESTI (Mars abonent to'lovi)
    async def test_monthly_debt_flow(self):
        bot = AsyncMock(spec=Bot)
        chat_id = 1001
        user_id = 1001

        # 1-qadam: Foydalanuvchi "oylik qarzim bormi" deb yozadi (hali INN bermagan)
        r1 = await self._send_msg(chat_id, user_id, "oylik qarzim bormi", bot)
        self.assertTrue(any(w in r1.lower() for w in ["stir", "inn", "9 xonali"]))

        # 2-qadam: INN yuboradi (302568138 - bazada qarzi 0 so'm)
        r2 = await self._send_msg(chat_id, user_id, "302568138", bot)
        self.assertIn("MARS ELEKTRON", r2)
        self.assertTrue("0 so'm" in r2 or "qarzdorlik yo'q" in r2.lower())
        self.assertIn("Smart One", r2)

        # 3-qadam: Yana "oylik to'lovni tekshir" deb so'raydi (xotiradagi INN dan foydalanadi)
        r3 = await self._send_msg(chat_id, user_id, "oylik to'lovni tekshir", bot)
        self.assertIn("MARS ELEKTRON", r3)
        self.assertTrue("0 so'm" in r3 or "qarzdorlik yo'q" in r3.lower())

    # 2. YILLIK TO'LOV TESTI (OFD / Soliq litsenziyasi)
    async def test_annual_debt_flow_with_fm(self):
        bot = AsyncMock(spec=Bot)
        chat_id = 1002
        user_id = 1002

        # 1-qadam: Foydalanuvchi "yillik to'lovni tekshir" deb yozadi
        r1 = await self._send_msg(chat_id, user_id, "yillik to'lovni tekshir", bot)
        self.assertTrue(any(w in r1.lower() for w in ["fiskal modul", "lg", "inn", "stir"]))

        # 2-qadam: Fiskal modul yuboradi (LG420210630789)
        # OFD javobini mock qilamiz
        with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = (
                "🏢 STIR: 302568138\n"
                "📟 Fiskal modul: LG420210630789\n"
                "📅 Faollik muddati: 2026-11-20 gacha\n"
                "✅ Qarzdorlik mavjud emas"
            )
            r2 = await self._send_msg(chat_id, user_id, "LG420210630789", bot)
            self.assertIn("LG420210630789", r2)
            self.assertTrue("qarzdorlik yo'q" in r2.lower() or "mavjud emas" in r2.lower())

        # 3-qadam: "Yillikni qayta tekshir" deb yozsa (xotiradagi FM dan foydalanadi)
        with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = (
                "🏢 STIR: 302568138\n"
                "📟 Fiskal modul: LG420210630789\n"
                "🔴 FMO dan qarzdorlik mavjud: 440 000 so'm"
            )
            r3 = await self._send_msg(chat_id, user_id, "yillikni qayta tekshir", bot)
            self.assertIn("LG420210630789", r3)
            self.assertTrue("qarzdorlik mavjud" in r3.lower() or "440 000" in r3)

    # 3. OYLIK TEKSHIRILGANDAN SO'NG YILLIKNI SO'RASH (OFD faqat Fiskal modul bilan ishlaydi)
    async def test_monthly_then_annual_using_remembered_inn(self):
        bot = AsyncMock(spec=Bot)
        chat_id = 1003
        user_id = 1003

        # 1-qadam: Foydalanuvchi INN beradi
        r1 = await self._send_msg(chat_id, user_id, "302568138", bot)
        self.assertIn("MARS ELEKTRON", r1)

        # 2-qadam: Endi "yillikdanchi" deb so'raydi. OFD bot faqat Fiskal modul bilan ishlagani uchun
        # bot foydalanuvchidan chekdagi FM raqamini (LG..., YG..., UZ...) so'rashi kerak!
        r2 = await self._send_msg(chat_id, user_id, "yillikdanchi", bot)
        self.assertTrue(any(w in r2.lower() for w in ["fiskal modul", "lg", "yg", "uz"]))

        # 3-qadam: Foydalanuvchi Fiskal modul raqamini (LG420210630789) yuboradi
        with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = (
                "🏢 STIR: 302568138\n"
                "📟 Fiskal modul: LG420210630789\n"
                "✅ Yillik to'lovdan qarzdorlik yo'q. Faol holatda."
            )
            r3 = await self._send_msg(chat_id, user_id, "LG420210630789", bot)
            mock_ofd.assert_called_once_with(bot, "LG420210630789")
            self.assertIn("LG420210630789", r3)
            self.assertTrue("qarzdorlik yo'q" in r3.lower() or "faol" in r3.lower())

    # 4. IKKALA TO'LOVNI BIRGALIKDA TEKSHIRISH (Dual Check)
    async def test_dual_check_both_monthly_and_annual(self):
        bot = AsyncMock(spec=Bot)
        chat_id = 1004
        user_id = 1004

        # A) INN va FM birgalikda yuborilganda ikkalasi birdan tekshiriladi
        with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = "Faol holatda, qarzdorlik yo'q"
            r1 = await self._send_msg(chat_id, user_id, "302568138 LG420210630789 ikkala to'lovni tekshir", bot)
            mock_ofd.assert_called_once_with(bot, "LG420210630789")
            self.assertIn("MARS ELEKTRON", r1)
            self.assertIn("LG420210630789", r1)

        # B) Faqat INN berilganda oylik tekshiriladi va yillik uchun FM so'raladi
        user_memory.clear()
        r2 = await self._send_msg(chat_id, user_id, "302568138 ikkala to'lovni tekshir", bot)
        self.assertIn("MARS ELEKTRON", r2)
        self.assertTrue(any(w in r2.lower() for w in ["fiskal modul", "lg", "yg"]))

    # 6. SHOT RAQAMLAR KANALDAN UZATILISHI TESTI (Post 85 va Post 34)
    async def test_06_payment_accounts_forwarded_from_channel(self):
        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()
        chat_id = 1006
        user_id = 1006

        # A) Oylik to'lov hisob raqami so'ralganda (Post 85 va Video 148 uzatiladi)
        r1 = await self._send_msg(chat_id, user_id, "oylik to'lov shotini ber", bot)
        copied_ids = [call.kwargs.get("message_id") or call.args[2] for call in bot.copy_message.call_args_list]
        self.assertIn(85, copied_ids)   # Mars oylik shot posti
        self.assertIn(148, copied_ids)  # Oylik to'lov videosi

        # B) Yillik to'lov hisob raqami so'ralganda (Post 34 va Video 145 uzatiladi)
        bot.copy_message.reset_mock()
        user_memory.clear()
        r2 = await self._send_msg(chat_id, user_id, "yillik to'lov shotini tashla", bot)
        copied_ids = [call.kwargs.get("message_id") or call.args[2] for call in bot.copy_message.call_args_list]
        self.assertIn(34, copied_ids)   # Yangi Texnologiyalar yillik shot posti
        self.assertIn(145, copied_ids)  # Yillik to'lov videosi

        # C) Umumiy / ikkala hisob raqam so'ralganda (Post 85 va Post 34 uzatiladi)
        bot.copy_message.reset_mock()
        user_memory.clear()
        r3 = await self._send_msg(chat_id, user_id, "shot raqamlar kerak", bot)
        copied_ids = [call.kwargs.get("message_id") or call.args[2] for call in bot.copy_message.call_args_list]
        self.assertIn(85, copied_ids)   # Post 85
        self.assertIn(34, copied_ids)   # Post 34

    # 7. YILLIK TO'LOVDA HAR XIL FISKAL RAQAMLAR BILAN TEST
    async def test_07_annual_check_with_various_fiscal_module_inputs(self):
        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()
        chat_id = 1007
        user_id = 1007

        # A) UZ200701040469 kiritilganda OFD dan tekshirish
        with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = "Fiskal modul faol holatda."
            r1 = await self._send_msg(chat_id, user_id, "UZ200701040469", bot)
            mock_ofd.assert_called_once_with(bot, "UZ200701040469")
            self.assertIn("UZ200701040469", r1)
            self.assertTrue("qarzdorlik yo'q" in r1.lower() or "faol" in r1.lower())

        # B) Qarzdorlik mavjud bo'lgan fiskal modul (LG420230615712)
        user_memory.clear()
        with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = "FMO dan qarzdorlik mavjud: 440 000 so'm. Muddati o'tgan."
            r2 = await self._send_msg(chat_id, user_id, "fiskal modul: LG420230615712", bot)
            mock_ofd.assert_called_once_with(bot, "LG420230615712")
            self.assertIn("LG420230615712", r2)
            self.assertIn("QARZDORLIK MAVJUD", r2)

            # Ketidan "to'layman, shotini tashla" desa -> Post 34 uzatilishi kerak!
            r3 = await self._send_msg(chat_id, user_id, "to'layman, shotini tashla", bot)
            copied_ids = [call.kwargs.get("message_id") or call.args[2] for call in bot.copy_message.call_args_list]
            self.assertIn(34, copied_ids)

        # C) Noto'g'ri / topilmagan fiskal modul javobi
        user_memory.clear()
        with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = "Bunday fiskal modul mavjud emas! Qaytadan urinib ko‘ring."
            r4 = await self._send_msg(chat_id, user_id, "LG000000000000", bot)
            self.assertTrue("topilmadi" in r4.lower() or "mavjud emas" in r4.lower())


if __name__ == "__main__":
    unittest.main()
