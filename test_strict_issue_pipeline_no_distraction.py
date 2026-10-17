import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from aiogram import types
from user_memory import user_memory
from excel_manager import excel_manager
from handlers.chat import handle_user_chat
from handlers.debt import handle_inn_query
from admin_manager import admin_manager


def create_mock_message(chat_id: int, user_id: int, text: str = ""):
    message = MagicMock(spec=types.Message)
    message.chat = MagicMock(spec=types.Chat)
    message.chat.id = chat_id
    message.chat.type = "private"
    message.from_user = MagicMock(spec=types.User)
    message.from_user.id = user_id
    message.from_user.full_name = "Sinov Foydalanuvchi"
    message.from_user.username = "sinov_user"
    message.text = text
    message.message_id = 999
    message.reply = AsyncMock()
    message.answer = AsyncMock()
    return message


class TestStrictIssuePipelineNoDistraction(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        user_memory.sessions.clear()
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()
        self.bot.copy_message = AsyncMock()
        self.bot.send_photo = AsyncMock()
        admin_manager.notify_admins = AsyncMock()

    async def test_1_full_issue_pipeline_with_questions(self):
        """Mijoz muammo bilan yozganda oraliqda qanday savol bermasin, bot pipeline dan chalg'imasligi shart."""
        chat_id = 7001
        user_id = 8001

        # 1-qadam: Mijoz muammo bilan yozadi
        msg1 = create_mock_message(chat_id, user_id, text="kassada muammo bulyapti ishlamayapdi")
        await handle_user_chat(msg1, self.bot)

        # Bot INN so'rashi kerak
        self.assertTrue(user_memory.is_issue_mode(chat_id, user_id))
        reply1 = msg1.reply.call_args[0][0]
        self.assertIn("INN", reply1)

        # 2-qadam: Mijoz INN kiritadi (300600431 -> qarz 0)
        msg2 = create_mock_message(chat_id, user_id, text="300600431")
        await handle_inn_query(msg2, self.bot)

        # Bot oylik qarz yo'qligini aytib, 2-bosqich: Fiskal modul so'rashi va Post 149 yuborishi shart!
        reply2 = msg2.reply.call_args[0][0]
        self.assertIn("2-bosqich: Davlat Soliq (OFD) yillik litsenziyasini tekshirish", reply2)
        self.assertEqual(self.bot.copy_message.call_args[1]["message_id"], 149)

        # 3-qadam: Mijoz chalg'ituvchi savol beradi: "fiskal modul nima u"
        self.bot.copy_message.reset_mock()
        msg3 = create_mock_message(chat_id, user_id, text="fiskal modul nima u")
        await handle_user_chat(msg3, self.bot)

        # Bot chalg'imasdan Fiskal modul nima ekanini tushuntirib, yana chek namunasi yuborishi shart!
        reply3 = msg3.reply.call_args[0][0]
        self.assertIn("Fiskal modul", reply3)
        self.assertIn("LG420210630789", reply3)
        self.assertEqual(self.bot.copy_message.call_args[1]["message_id"], 149)

        # 4-qadam: Mijoz yana chalg'ituvchi savol beradi: "chek chiqmayaptiku qayerdan olaman"
        self.bot.copy_message.reset_mock()
        msg4 = create_mock_message(chat_id, user_id, text="chek chiqmayaptiku qayerdan olaman")
        await handle_user_chat(msg4, self.bot)

        # Bot apparat orqasidagi nakleyka yoki ekranni rasmga olishni aytishi kerak
        reply4 = msg4.reply.call_args[0][0]
        self.assertIn("nakleyka", reply4.lower())

        # 5-qadam: Mijoz Fiskal modulni topib yuboradi: LG420210630789 (OFD da qarz yo'q)
        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", new=AsyncMock(return_value="Holati: Faol. Muddati: 2026-12-31")):
            msg5 = create_mock_message(chat_id, user_id, text="LG420210630789")
            await handle_user_chat(msg5, self.bot)

            # 3-bosqich: Internet, soat, reboot tekshirish, rasm so'rash
            reply5 = msg5.reply.call_args[0][0]
            self.assertIn("To'lovlar bo'yicha hech qanday qarzdorlik yo'q", reply5)
            self.assertIn("Internet aloqasi", reply5)
            self.assertIn("Soat va sana", reply5)
            self.assertIn("Qayta yoqish", reply5)
            self.assertIn("adminga", reply5.lower())

            # VA ADMINGA ZUDLIK BILAN ESKALATSIYA QILINGAN BO'LISHI SHART!
            admin_manager.notify_admins.assert_called_once()
            call_text = admin_manager.notify_admins.call_args[1]["text"]
            self.assertIn("300600431", call_text)
            self.assertIn("LG420210630789", call_text)
            self.assertIn("to'langan", call_text.lower())

    async def test_2_single_message_inn_and_issue(self):
        """Mijoz bir vaqtning o'zida ham INN, ham nosozlikni yozsa ('300600431 apparatim ishlamayapti')."""
        chat_id = 7002
        user_id = 8002

        msg = create_mock_message(chat_id, user_id, text="300600431 apparatim ishlamayapti")
        await handle_inn_query(msg, self.bot)

        # Bot oylik qarz 0 bo'lgani uchun to'xtab qolmasdan darhol 2-bosqich: Fiskal modul so'rashi kerak!
        self.assertTrue(user_memory.is_issue_mode(chat_id, user_id))
        reply = msg.reply.call_args[0][0]
        self.assertIn("2-bosqich: Davlat Soliq (OFD) yillik litsenziyasini tekshirish", reply)
        self.assertEqual(self.bot.copy_message.call_args[1]["message_id"], 149)

    async def test_3_reboot_failed_immediate_escalation(self):
        """Mijoz 'reboot qildim baribir ishlamadi' desa darhol adminga eskalatsiya ketishi shart."""
        chat_id = 7003
        user_id = 8003

        # Muammo rejimi
        user_memory.set_issue_mode(chat_id, user_id, True, initial_query="kassa ishlamayapti")
        user_memory.set_last_id(chat_id, user_id, "300600431", org_name="TEST SERVIS MCHJ", debt=0.0)

        msg = create_mock_message(chat_id, user_id, text="reboot qildim baribir ishlamadi bolmadi")
        await handle_user_chat(msg, self.bot)

        reply = msg.reply.call_args[0][0]
        self.assertIn("mas'ul xodimlarimizga", reply.lower())

        # Adminga eskalatsiya
        admin_manager.notify_admins.assert_called_once()
        call_text = admin_manager.notify_admins.call_args[1]["text"]
        self.assertIn("300600431", call_text)
        self.assertIn("qayta yoqilgandan keyin ham ishlamadi", call_text.lower())


if __name__ == "__main__":
    unittest.main()
