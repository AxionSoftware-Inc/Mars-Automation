import unittest
import os
import json
from unittest.mock import AsyncMock, MagicMock, patch
from catalog_manager import catalog_manager
from state_manager import get_last_excel_channel_msg_id, set_last_excel_channel_msg_id
from handlers.media import EXCEL_CHANNEL_ID, DESTINATION_CHANNEL_ID, SOURCE_CHANNEL_ID
from ofd_bridge import ofd_bridge

class TestExcelChannelSyncAndCatalog(unittest.IsolatedAsyncioTestCase):
    def test_post_149_in_catalog(self):
        """149-post (chekdan INN va Fiskal modul topish) katalogda mavjud va qidiruvda chiqishi"""
        post_ids = [p['id'] for p in catalog_manager.posts]
        self.assertIn(149, post_ids)

        match1 = catalog_manager.find_post_by_keywords("chekdan inn topish qanday")
        self.assertEqual(match1, 149)

        match2 = catalog_manager.find_post_by_keywords("fiskal modul raqami qayerda")
        self.assertEqual(match2, 149)

        match3 = catalog_manager.find_post_by_keywords("chekdan jshshir topish")
        self.assertEqual(match3, 149)

    def test_excel_channel_id_configured(self):
        """Excel kanali IDsi to'g'ri sozlanganligi"""
        self.assertEqual(EXCEL_CHANNEL_ID, -1001795471853)
        self.assertEqual(SOURCE_CHANNEL_ID, -1001641871516)

    def test_state_manager_excel_msg_id(self):
        """Excel kanal xabari ID sini saqlash va o'qish"""
        original = get_last_excel_channel_msg_id()
        try:
            set_last_excel_channel_msg_id(99999)
            self.assertEqual(get_last_excel_channel_msg_id(), 99999)
        finally:
            if original is not None:
                set_last_excel_channel_msg_id(original)

    def tearDown(self):
        ofd_bridge._telethon_client = None

    @patch("telethon.TelegramClient")
    async def test_sync_excel_mock_flow(self, mock_client_cls):
        """sync_excel_from_channel muvaffaqiyatli yuklab olish oqimi"""
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.is_user_authorized.return_value = True

        mock_msg = MagicMock()
        mock_msg.id = 12345
        mock_msg.file = MagicMock()
        mock_msg.file.name = "test_2026_abonent.xlsx"

        async def fake_iter(*args, **kwargs):
            yield mock_msg

        mock_client.iter_messages = MagicMock(side_effect=fake_iter)


        async def fake_download(message, file):
            with open(file, "w") as f:
                f.write("dummy")

        mock_client.download_media = AsyncMock(side_effect=fake_download)



        with patch("excel_manager.excel_manager.update_file", return_value=True):
            with patch("state_manager.get_last_excel_channel_msg_id", return_value=12300):
                with patch("state_manager.set_last_excel_channel_msg_id") as mock_set:
                    with patch("state_manager.set_last_forwarded_excel_channel_msg_id"):
                        res = await ofd_bridge.sync_excel_from_channel(channel_id=-1001795471853)
                        self.assertTrue(res)
                        mock_set.assert_called_with(12345)

if __name__ == "__main__":
    unittest.main()
