import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from aiogram import types

from handlers.chat import handle_user_chat
from user_memory import user_memory
from ofd_bridge import ofd_bridge

def create_mock_message(text: str, chat_id: int = 887766, user_id: int = 554433, username: str = "adversary_user") -> types.Message:
    msg = MagicMock(spec=types.Message)
    msg.text = text
    msg.caption = None
    msg.photo = None
    msg.document = None
    msg.message_id = 999
    msg.chat = MagicMock(spec=types.Chat)
    msg.chat.id = chat_id
    msg.chat.type = "group"
    msg.from_user = MagicMock(spec=types.User)
    msg.from_user.id = user_id
    msg.from_user.username = username
    msg.from_user.first_name = "Merchant"
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()
    return msg

class TestAdversarialBreakRound2(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        user_memory.clear_context(887766, 554433)

    @patch("ofd_bridge.ofd_bridge.query_fiscal_module")
    async def test_01_combined_multi_intent_in_single_message(self, mock_ofd):
        """Bitta xabarda qorishiq savollar: yillik + oylik + INN + apparat nosozligi"""
        bot = MagicMock()
        bot.copy_message = AsyncMock()

        msg = create_mock_message("aka yillikdan qarzim bormi oylikdanchi 302568138 apparat chek urmayapti")
        await handle_user_chat(msg, bot)

        self.assertTrue(msg.reply.called)
        reply = msg.reply.call_args[0][0]
        # INN 302568138 topilgani uchun korxona va oylik qarz holati berilishi shart
        self.assertIn("Korxona", reply)
        self.assertIn("302568138", reply)

    @patch("ofd_bridge.ofd_bridge.query_fiscal_module")
    async def test_02_fm_sent_when_asked_for_inn(self, mock_ofd):
        """Foydalanuvchidan INN so'ralganda, u adashib Fiskal modul (LG...) yuborsa"""
        mock_ofd.return_value = "Fiskal modul faol holatda. Qarzdorlik mavjud emas."
        bot = MagicMock()
        bot.copy_message = AsyncMock()

        # 1. Oylik qarzini so'raydi -> bot INN so'raydi
        msg1 = create_mock_message("oylik qarzim bormi")
        await handle_user_chat(msg1, bot)
        reply1 = msg1.reply.call_args[0][0]
        self.assertIn("СТИР (INN)", reply1)

        # 2. Foydalanuvchi adashib FM kodini yuboradi: LG420210630789
        msg2 = create_mock_message("LG420210630789")
        await handle_user_chat(msg2, bot)
        reply2 = msg2.reply.call_args[0][0]
        # Bot xatoga uchramasdan, FM ni tanib, OFD dan tekshirishi kerak
        self.assertIn("LG420210630789", reply2)
        self.assertIn("QARZDORLIK YO'Q", reply2)

    @patch("ofd_bridge.ofd_bridge.query_fiscal_module")
    async def test_03_inn_sent_when_asked_for_fm(self, mock_ofd):
        """Foydalanuvchidan FM so'ralganda, u adashib INN (9 xonali) yuborsa"""
        bot = MagicMock()
        bot.copy_message = AsyncMock()

        # 1. Yillik qarzini so'raydi -> bot FM so'raydi
        msg1 = create_mock_message("yillikdan qarzim bormi")
        await handle_user_chat(msg1, bot)
        reply1 = msg1.reply.call_args[0][0]
        self.assertIn("Fiskal modul", reply1)

        # 2. Foydalanuvchi adashib INN yuboradi: 302568138
        msg2 = create_mock_message("302568138")
        await handle_user_chat(msg2, bot)
        reply2 = msg2.reply.call_args[0][0]
        # Bot bu INN ekanini tushunib, korxona oylik holatini chiqarishi kerak (bunday FM yo'q demasdan!)
        self.assertIn("Korxona", reply2)
        self.assertIn("302568138", reply2)

    @patch("ofd_bridge.ofd_bridge.query_fiscal_module")
    async def test_04_rapid_ping_pong_10_turns(self, mock_ofd):
        """10 bosqichli tezkor mavzu o'zgarishi va kontekst uzluksizligi"""
        mock_ofd.return_value = "Fiskal modul faol holatda. Lekin, VMQ-943 ga ko‘ra FMO dan qarzdorlik mavjud."
        bot = MagicMock()
        bot.copy_message = AsyncMock()

        # Turn 1: Yillik tekshir
        m1 = create_mock_message("yilikdan qarzim bormi")
        await handle_user_chat(m1, bot)
        self.assertIn("Fiskal modul", m1.reply.call_args[0][0])

        # Turn 2: Oylikdanchi
        m2 = create_mock_message("oylikdanchi")
        await handle_user_chat(m2, bot)
        self.assertIn("СТИР (INN)", m2.reply.call_args[0][0])

        # Turn 3: 302568138
        m3 = create_mock_message("302568138")
        await handle_user_chat(m3, bot)
        self.assertIn("Korxona", m3.reply.call_args[0][0])

        # Turn 4: Yillikdanchi
        m4 = create_mock_message("yillikdanchi")
        await handle_user_chat(m4, bot)
        self.assertIn("Fiskal modul", m4.reply.call_args[0][0])

        # Turn 5: FM UZ200701040469 berildi
        m5 = create_mock_message("UZ200701040469")
        await handle_user_chat(m5, bot)
        self.assertIn("QARZDORLIK MAVJUD", m5.reply.call_args[0][0])

        # Turn 6: To'layman shot raqam bering (Yillik qarz kontekstida!)
        m6 = create_mock_message("to'layman shot raqam bering")
        await handle_user_chat(m6, bot)
        # Shot raqam kanaldan copy_message yoki reply orqali uzatiladi
        self.assertTrue(bot.copy_message.called or m6.reply.called)


        # Turn 7: Endi oylik shotniyam bering
        m7 = create_mock_message("endi oylik shotniyam bering")
        await handle_user_chat(m7, bot)
        # Mars oylik shot videosi yoki kartasi uzatilishi kerak
        self.assertTrue(bot.copy_message.called or m7.reply.called)

        # Turn 8: Oylikdanchi (qayta so'rasa, INN xotirada bor, qayta so'ramaydi!)
        m8 = create_mock_message("oylikdanchi")
        await handle_user_chat(m8, bot)
        self.assertIn("Korxona", m8.reply.call_args[0][0])

    @patch("ofd_bridge.ofd_bridge.query_fiscal_module")
    async def test_05_slang_dialects_and_cyrillic(self, mock_ofd):
        """Sheva, xatoliklar va kirill yozuvidagi keskin so'rovlar"""
        mock_ofd.return_value = "Fiskal modul faol holatda. Qarzdorlik mavjud emas."
        bot = MagicMock()
        bot.copy_message = AsyncMock()

        # 1. Sheva: "oylikdan qarzm bormikan oka"
        m1 = create_mock_message("oylikdan qarzm bormikan oka")
        await handle_user_chat(m1, bot)
        self.assertIn("СТИР (INN)", m1.reply.call_args[0][0])

        # 2. Kirill: "йилликданчи карзим"
        m2 = create_mock_message("йилликданчи карзим")
        await handle_user_chat(m2, bot)
        reply2 = m2.reply.call_args[0][0]
        self.assertTrue("Фискал" in reply2 or "Fiskal" in reply2)

        # 3. Kirill qarz so'rovi: "офддан карз борми"
        m3 = create_mock_message("офддан карз борми")
        await handle_user_chat(m3, bot)
        reply3 = m3.reply.call_args[0][0]
        self.assertTrue("Фискал" in reply3 or "Fiskal" in reply3)

    async def test_06_unregistered_inn_inquiry(self):
        """Bazada mavjud bo'lmagan INN (999888777) so'ralganda xatosiz javob berish"""
        bot = MagicMock()
        bot.copy_message = AsyncMock()

        msg = create_mock_message("999888777 oylik qarzim bormi")
        await handle_user_chat(msg, bot)
        self.assertTrue(msg.reply.called)
        reply = msg.reply.call_args[0][0]
        self.assertIn("topilmadi", reply.lower())

    async def test_07_decommissioned_inn_inquiry(self):
        """Hisobdan chiqarilgan (o'chirilgan) INN tekshiruvi"""
        bot = MagicMock()
        bot.copy_message = AsyncMock()

        # Excel bazasida hisobdan chiqarilgan INN
        from excel_manager import excel_manager
        decom_inns = list(excel_manager.decommissioned_stir_index.keys())
        if decom_inns:
            test_inn = decom_inns[0]
            msg = create_mock_message(f"{test_inn} oylikdan qarz bormi")
            await handle_user_chat(msg, bot)
            self.assertTrue(msg.reply.called)
            reply = msg.reply.call_args[0][0]
            self.assertIn("chiqarilgan", reply.lower())
            self.assertIn("0 so'm", reply)

    @patch("ofd_bridge.ofd_bridge.query_fiscal_module")
    async def test_08_gibberish_in_between_debt_turns(self, mock_ofd):
        """Suhbat o'rtasida mutlaqo begona savol kelsa ham bot adashmasligi kerak"""
        bot = MagicMock()
        bot.copy_message = AsyncMock()

        # Turn 1: Oylik qarz
        m1 = create_mock_message("oylik qarzim bormi")
        await handle_user_chat(m1, bot)
        self.assertIn("СТИР (INN)", m1.reply.call_args[0][0])

        # Turn 2: Begona savol: "bugun havo qanaqa" (AI ga boradi)
        with patch("handlers.chat.generate_ai_reply_ex", return_value=("Havo haqida ma'lumotim yo'q, men kassa bo'yicha yordamchiman.", None, False)):
            m2 = create_mock_message("bugun havo qanaqa")
            await handle_user_chat(m2, bot)
            self.assertTrue(m2.reply.called)

        # Turn 3: 302568138 (INN kiritildi)
        m3 = create_mock_message("302568138")
        await handle_user_chat(m3, bot)
        self.assertIn("Korxona", m3.reply.call_args[0][0])

if __name__ == "__main__":
    unittest.main()
