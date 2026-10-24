import unittest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types, Bot
from handlers.channel import handle_source_channel_post, handle_excel_channel_group_message
from payment_accounts import EXCEL_CHANNEL_ID, EXCEL_FORWARD_CHANNEL_ID
from state_manager import (
    get_last_forwarded_excel_channel_msg_id,
    set_last_forwarded_excel_channel_msg_id
)
from ofd_bridge import ofd_bridge


class TestExcelChannelForwarding(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.bot = AsyncMock(spec=Bot)
        self.orig_fwd = get_last_forwarded_excel_channel_msg_id()

    def tearDown(self):
        ofd_bridge._telethon_client = None
        if self.orig_fwd is not None:
            set_last_forwarded_excel_channel_msg_id(self.orig_fwd)

    async def test_channel_post_forwarding(self):
        """EXCEL_CHANNEL_ID dan yangi channel_post kelganda Oylik abanit guruhiga forward qilinishi"""
        set_last_forwarded_excel_channel_msg_id(1000)

        msg = MagicMock(spec=types.Message)
        msg.chat = MagicMock()
        msg.chat.id = EXCEL_CHANNEL_ID
        msg.message_id = 1005
        msg.text = "Yangi e'lon"
        msg.caption = None
        msg.document = None

        await handle_source_channel_post(msg, self.bot)

        self.bot.forward_message.assert_called_once_with(
            chat_id=EXCEL_FORWARD_CHANNEL_ID,
            from_chat_id=EXCEL_CHANNEL_ID,
            message_id=1005
        )
        self.assertEqual(get_last_forwarded_excel_channel_msg_id(), 1005)

    async def test_duplicate_not_forwarded(self):
        """Eski (allaqachon uzatilgan) xabar takroran uzatilmasligi kerak"""
        set_last_forwarded_excel_channel_msg_id(1010)

        msg = MagicMock(spec=types.Message)
        msg.chat = MagicMock()
        msg.chat.id = EXCEL_CHANNEL_ID
        msg.message_id = 1005

        await handle_source_channel_post(msg, self.bot)
        self.bot.forward_message.assert_not_called()
        self.bot.copy_message.assert_not_called()

    async def test_group_message_forwarding(self):
        """Superguruh sifatida kelgan message xabari ham uzatilishi kerak"""
        set_last_forwarded_excel_channel_msg_id(2000)

        msg = MagicMock(spec=types.Message)
        msg.chat = MagicMock()
        msg.chat.id = EXCEL_CHANNEL_ID
        msg.message_id = 2005

        await handle_excel_channel_group_message(msg, self.bot)

        self.bot.forward_message.assert_called_once_with(
            chat_id=EXCEL_FORWARD_CHANNEL_ID,
            from_chat_id=EXCEL_CHANNEL_ID,
            message_id=2005
        )
        self.assertEqual(get_last_forwarded_excel_channel_msg_id(), 2005)

    @patch("telethon.TelegramClient")
    async def test_ofd_bridge_sync_forwards_all_messages(self, mock_client_cls):
        """ofd_bridge.sync_excel_from_channel har qanday yangi xabarni va excelni uzatishi"""
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.is_user_authorized.return_value = True

        msg1 = MagicMock()
        msg1.id = 5001
        msg1.file = None

        msg2 = MagicMock()
        msg2.id = 5002
        msg2.file = MagicMock()
        msg2.file.name = "yangi_baza.xlsx"

        async def fake_iter(*args, **kwargs):
            yield msg2
            yield msg1

        mock_client.iter_messages = MagicMock(side_effect=fake_iter)

        async def fake_download(message, file):
            with open(file, "w") as f:
                f.write("dummy")

        mock_client.download_media = AsyncMock(side_effect=fake_download)

        with patch("excel_manager.excel_manager.update_file", return_value=True):
            with patch("state_manager.get_last_forwarded_excel_channel_msg_id", return_value=5000):
                with patch("state_manager.set_last_forwarded_excel_channel_msg_id") as mock_set_fwd:
                    with patch("state_manager.set_last_excel_channel_msg_id") as mock_set_excel:
                        res = await ofd_bridge.sync_excel_from_channel(channel_id=EXCEL_CHANNEL_ID)
                        self.assertTrue(res)
                        # Check that forward_messages was called for both
                        self.assertEqual(mock_client.forward_messages.call_count, 2)
                        mock_set_excel.assert_called_with(5002)


if __name__ == "__main__":
    unittest.main()
