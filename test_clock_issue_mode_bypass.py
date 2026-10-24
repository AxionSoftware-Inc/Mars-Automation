import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from aiogram import types
from user_memory import user_memory
from handlers.chat import handle_user_chat
from handlers.debt import handle_inn_query
from admin_manager import admin_manager
from catalog_manager import catalog_manager


def create_mock_message(chat_id: int, user_id: int, text: str = ""):
    message = MagicMock(spec=types.Message)
    message.chat = MagicMock(spec=types.Chat)
    message.chat.id = chat_id
    message.chat.type = "group"
    message.from_user = MagicMock(spec=types.User)
    message.from_user.id = user_id
    message.from_user.full_name = "Test User"
    message.from_user.username = "test_user"
    message.text = text
    message.message_id = 12345
    message.reply = AsyncMock()
    message.answer = AsyncMock()
    return message


class TestClockIssueModeBypass(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        user_memory.sessions.clear()
        catalog_manager.load_catalog()
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()
        self.bot.copy_message = AsyncMock()
        self.bot.send_photo = AsyncMock()
        self.orig_notify_admins = admin_manager.notify_admins
        admin_manager.notify_admins = AsyncMock()

    def tearDown(self):
        admin_manager.notify_admins = self.orig_notify_admins

    async def test_user1_in_issue_mode_asks_saotini_gets_clock_video(self):
        """
        User 1 avval 'aparatim ishlamay qoldi' deb yozgan, INN yuborgan (qarz 0),
        va bot 2-bosqichda Fiskal modul so'rab turgan paytda:
        User 1 'saotini qanday tug'irlasa buladi' deb yozganda bot Fiskal modul so'ramasligi,
        balki to'g'ridan-to'g'ri 141-sonli soat videosini yuborishi shart!
        """
        chat_id = -1003742874507
        user1_id = 1966874161

        # 1. User 1: 'aparatim ishlamay qoldi'
        msg1 = create_mock_message(chat_id, user1_id, "aparatim ishlamay qoldi")
        await handle_user_chat(msg1, self.bot)
        self.assertTrue(user_memory.is_issue_mode(chat_id, user1_id))

        # 2. User 1: INN 302568138 (qarz 0) -> Bot Fiskal modul so'raydi
        msg2 = create_mock_message(chat_id, user1_id, "302568138")
        await handle_inn_query(msg2, self.bot)
        rep2 = msg2.reply.call_args[0][0]
        self.assertIn("Fiskal modul", rep2)

        # 3. User 1: 'saotini qanday tug'irlasa buladi' (typo bilan)
        self.bot.copy_message.reset_mock()
        msg3 = create_mock_message(chat_id, user1_id, "saotini qanday tug'irlasa buladi")
        await handle_user_chat(msg3, self.bot)

        # Bot Fiskal modul takrorlamasligi kerak!
        if msg3.reply.called:
            reply_text = msg3.reply.call_args[0][0]
            self.assertNotIn("Fiskal modul raqamini (LG... yoki YG...) yuboring", reply_text)

        # Bot 141-sonli soat videosini yuborishi SHART!
        self.assertTrue(self.bot.copy_message.called, "Bot 141-sonli video xabarini yubormadi!")
        video_id = self.bot.copy_message.call_args[1].get("message_id")
        self.assertEqual(video_id, 141, f"Kutilgan video 141, lekin yuborilgan: {video_id}")

        # Issue mode tozalangan bo'lishi kerak
        self.assertFalse(user_memory.is_issue_mode(chat_id, user1_id))

    async def test_user2_without_issue_mode_gets_clock_video(self):
        """
        User 2 hech qanday muammo rejimida bo'lmagan holda 'saotini qanday tug’irlasa buladi'
        deb yozganda ham 141-sonli soat videosini olishi kerak.
        """
        chat_id = -1003742874507
        user2_id = 1914856786

        msg = create_mock_message(chat_id, user2_id, "saotini qanday tug’irlasa buladi")
        await handle_user_chat(msg, self.bot)

        self.assertTrue(self.bot.copy_message.called)
        video_id = self.bot.copy_message.call_args[1].get("message_id")
        self.assertEqual(video_id, 141)

    async def test_user_in_issue_mode_asks_z_report_gets_video_2(self):
        """
        User issue modeda bo'lsa ham 'z otchet qanday olinadi' desa 2-sonli video berilishi kerak.
        """
        chat_id = -1003742874507
        user3_id = 1999999999

        user_memory.set_issue_mode(chat_id, user3_id, True)
        user_memory.set_last_id(chat_id, user3_id, "302568138")

        msg = create_mock_message(chat_id, user3_id, "z otchet qanday olinadi")
        await handle_user_chat(msg, self.bot)

        self.assertTrue(self.bot.copy_message.called)
        video_id = self.bot.copy_message.call_args[1].get("message_id")
        self.assertEqual(video_id, 2)


if __name__ == "__main__":
    unittest.main()
