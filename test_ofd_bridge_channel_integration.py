import os
import json
import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch
from aiogram import types

from ofd_bridge import OFDBridgeManager
from handlers import AdminAutoRegisterMiddleware, handle_bot_chat_member_update
from handlers.intents.billing import BillingIntentHandler
from user_memory import user_memory
from payment_accounts import format_ofd_annual_status


class TestOFDBridgeChannelIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.cfg_file = os.path.join(self.tmp_dir.name, "ofd_config.json")
        self.bridge = OFDBridgeManager(config_path=self.cfg_file)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_channel_post_auto_binding_via_admin_list(self):
        """Kanalda @ofd943_bot admin ekanligi aniqlansa, ko'prik avtomatik ulanishi kerak"""
        channel_id = -1001999888777

        class MockBot:
            async def get_chat_administrators(self, chat_id: int):
                return [
                    SimpleNamespace(user=SimpleNamespace(id=111, username="marselektrontexnikamchj_bot", full_name="Mars Bot", is_bot=True)),
                    SimpleNamespace(user=SimpleNamespace(id=222, username="ofd943_bot", full_name="OFD Bot", is_bot=True)),
                    SimpleNamespace(user=SimpleNamespace(id=333, username="boss_admin", full_name="Boss", is_bot=False))
                ]

        mock_bot = MockBot()
        self.assertFalse(self.bridge.is_configured())

        # Kanal posti keldi (kanallarda from_user=None bo'ladi)
        post = SimpleNamespace(
            chat=SimpleNamespace(id=channel_id, type="channel", title="Mars & OFD Bridge"),
            from_user=None,
            text="Kanal ochildi",
            caption=None,
            message_id=1
        )

        res = asyncio.run(self.bridge.handle_incoming_message(post, bot=mock_bot))
        self.assertTrue(self.bridge.is_configured())
        self.assertEqual(self.bridge.ofd_group_id, channel_id)
        self.assertTrue(self.bridge.is_ofd_group(channel_id))

    def test_02_channel_signature_text_auto_binding(self):
        """Kanaldan kelgan post matnida OFD ning xos jumlalari bo'lsa, kanal avtomatik ulanishi kerak"""
        channel_id = -1001888777666
        self.assertFalse(self.bridge.is_configured())

        raw_ofd_text = (
            "Fiskal modul faol holatda.\n"
            "Lekin, VMQ-943 ga ko‘ra FMO dan qarzdorlik mavjud. To‘lov qilish muddati: 15.10.2026 yil."
        )

        post = SimpleNamespace(
            chat=SimpleNamespace(id=channel_id, type="channel", title="OFD Channel"),
            from_user=None,
            text=raw_ofd_text,
            caption=None,
            message_id=5
        )

        mock_bot = MagicMock()
        mock_bot.get_chat_administrators = AsyncMock(side_effect=Exception("No permission"))

        res = asyncio.run(self.bridge.handle_incoming_message(post, bot=mock_bot))
        self.assertTrue(self.bridge.is_configured())
        self.assertEqual(self.bridge.ofd_group_id, channel_id)

    def test_03_query_fiscal_module_channel_flow_with_echo_and_loading_filtering(self):
        """Kanalga FM yuborilganda echo va 'Kuting...' filtrlangan holda haqiqiy javob qaytishi"""
        channel_id = -1001777888999
        self.bridge.set_ofd_group(channel_id)
        fm_code = "LG420230615712"

        sent_messages = []
        bridge_inst = self.bridge

        class MockBot:
            async def send_message(self, chat_id: int, text: str, **kwargs):
                sent_messages.append((chat_id, text))
                sent_obj = SimpleNamespace(message_id=101)

                # 50ms dan keyin Telegram orqali javoblarni simulyatsiya qilish
                async def simulate_telegram_events():
                    await asyncio.sleep(0.02)
                    # 1. Botning o'z xabari channel_post sifatida echo bo'lib qaytdi (message_id=101, text=LG420230615712)
                    echo_msg = SimpleNamespace(
                        chat=SimpleNamespace(id=channel_id, type="channel"),
                        from_user=None,
                        text=text,
                        caption=None,
                        message_id=101
                    )
                    await bridge_inst.handle_incoming_message(echo_msg, bot=self)

                    # 2. OFD botining "Kuting..." placeholder xabari keldi (message_id=102)
                    await asyncio.sleep(0.02)
                    loading_msg = SimpleNamespace(
                        chat=SimpleNamespace(id=channel_id, type="channel"),
                        from_user=None,
                        text="⏳ Tekshirilmoqda, iltimos kuting...",
                        caption=None,
                        message_id=102
                    )
                    await bridge_inst.handle_incoming_message(loading_msg, bot=self)

                    # 3. OFD botining haqiqiy javob xabari keldi (message_id=103)
                    await asyncio.sleep(0.02)
                    real_msg = SimpleNamespace(
                        chat=SimpleNamespace(id=channel_id, type="channel"),
                        from_user=None,
                        text=(
                            f"Fiskal modul faol holatda. Qarzdorlik mavjud emas.\n"
                            f"Fiskal modul: {text}\n"
                            f"Amal qilish muddati: 2027-06-15"
                        ),
                        caption=None,
                        message_id=103
                    )
                    await bridge_inst.handle_incoming_message(real_msg, bot=self)

                asyncio.create_task(simulate_telegram_events())
                return sent_obj

        mock_bot = MockBot()
        reply = asyncio.run(self.bridge.query_fiscal_module(mock_bot, fm_code, timeout=3.0))

        self.assertIsNotNone(reply)
        self.assertIn("Qarzdorlik mavjud emas", reply)
        self.assertIn(fm_code, reply)
        self.assertNotIn("Kuting", reply)  # Placeholder o'tkazib yuborilgan bo'lishi shart

    def test_04_set_ofd_channel_command_with_explicit_id(self):
        """Admin /set_ofd_channel -100123456789 deb boshqa chatda yozsa, ko'prik saqlanishi kerak"""
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        msg = SimpleNamespace(
            chat=SimpleNamespace(id=999888, type="supergroup"),
            from_user=SimpleNamespace(id=1914856786, username="BIM_Project_Manager"),
            text="/set_ofd_channel -1001555444333",
            caption=None,
            message_id=20,
            reply=AsyncMock()
        )

        res = asyncio.run(self.bridge.handle_incoming_message(msg, bot=mock_bot))
        self.assertTrue(res)
        self.assertEqual(self.bridge.ofd_group_id, -1001555444333)

        # Faylga saqlanganligini tekshirish
        with open(self.cfg_file, "r") as f:
            data = json.load(f)
        self.assertEqual(data["ofd_group_id"], -1001555444333)

    def test_05_my_chat_member_event_binds_channel(self):
        """Bot kanalga admin qilinganda my_chat_member hodisasi orqali OFD botini aniqlab avto-ulanish"""
        channel_id = -1001333222111

        mock_bot = MagicMock()
        mock_bot.get_chat_administrators = AsyncMock(return_value=[
            SimpleNamespace(user=SimpleNamespace(id=8682100971, username="marselektrontexnikamchj_bot", is_bot=True)),
            SimpleNamespace(user=SimpleNamespace(id=943943, username="ofd943_bot", is_bot=True))
        ])

        chat_member_event = SimpleNamespace(
            chat=SimpleNamespace(id=channel_id, type="channel", title="OFD Bridge Channel"),
            new_chat_member=SimpleNamespace(status="administrator")
        )

        with patch("handlers.ofd_bridge", self.bridge):
            asyncio.run(handle_bot_chat_member_update(chat_member_event, mock_bot))

        self.assertTrue(self.bridge.is_configured())
        self.assertEqual(self.bridge.ofd_group_id, channel_id)

    def test_06_admin_status_and_test_connection_diagnostics(self):
        """Admin diagnostikasi /ofd va /test_ofd funksiyalari to'g'ri ishlashi"""
        channel_id = -1001444555666
        self.bridge.set_ofd_group(channel_id)

        mock_bot = MagicMock()
        mock_chat = SimpleNamespace(title="OFD Live Channel", type="channel", first_name=None)
        mock_bot.get_chat = AsyncMock(return_value=mock_chat)
        mock_bot.get_me = AsyncMock(return_value=SimpleNamespace(id=8682100971))
        mock_bot.get_chat_administrators = AsyncMock(return_value=[
            SimpleNamespace(user=SimpleNamespace(id=8682100971), can_post_messages=True),
            SimpleNamespace(user=SimpleNamespace(id=943943, username="ofd943_bot", full_name="OFD"))
        ])

        # Status ma'lumotlarini olish
        status = asyncio.run(self.bridge.get_status_info(bot=mock_bot))
        self.assertTrue(status["configured"])
        self.assertEqual(status["chat_id"], channel_id)
        self.assertEqual(status["chat_title"], "OFD Live Channel")
        self.assertTrue(status["our_bot_present"])
        self.assertTrue(status["ofd_bot_present"])
        self.assertTrue(status["can_post_messages"])

        # test_connection simulyatsiyasi
        with patch.object(self.bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = "Fiskal modul faol holatda. Qarzdorlik mavjud emas."
            conn_res = asyncio.run(self.bridge.test_connection(mock_bot, "LG420230615712"))
            self.assertTrue(conn_res["success"])
            self.assertIn("faol", conn_res["reply"])

    def test_07_full_end_to_end_annual_check_with_channel_bridge(self):
        """Mijoz Mars guruhida 'Yillikka qarzim bormi' deganda, kanal ko'prigi orqali tekshirish to'liq ishlashi"""
        chat_id = -1003742874507
        user_id = 1914856786
        fm_code = "LG420230615712"

        user_memory.clear_context(chat_id, user_id)
        user_memory.set_last_fm(chat_id, user_id, fm_code)

        handler = BillingIntentHandler()

        mock_msg = MagicMock()
        mock_msg.text = "Yillikka qarzim bormi"
        mock_msg.chat.id = chat_id
        mock_msg.from_user.id = user_id
        mock_msg.reply = AsyncMock()

        mock_bot = MagicMock()

        with patch("handlers.intents.billing.ofd_bridge", self.bridge):
            with patch.object(self.bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_q:
                mock_q.return_value = "Fiskal modul faol holatda. Qarzdorlik mavjud emas."

                handled = asyncio.run(handler.handle(mock_msg, mock_bot, "latin"))
                self.assertTrue(handled)
                self.assertTrue(mock_msg.reply.called)

                reply_text = mock_msg.reply.call_args[0][0]
                self.assertIn("QARZDORLIK YO'Q", reply_text)
                self.assertIn(fm_code, reply_text)

    def test_08_infinite_loop_prevention_in_bridge_channel(self):
        """OFD ko'prik kanalidagi xabarlar boshqa handlerlarga o'tib ketmasdan to'xtatilishi shart"""
        channel_id = -1001999888777
        self.bridge.set_ofd_group(channel_id)

        middleware = AdminAutoRegisterMiddleware()

        # Kanal posti keldi
        channel_msg = MagicMock(spec=types.Message)
        mock_chat = MagicMock()
        mock_chat.id = channel_id
        mock_chat.type = "channel"
        channel_msg.chat = mock_chat
        channel_msg.from_user = None
        channel_msg.text = "Fiskal modul ma'lumotlari"
        channel_msg.caption = None
        channel_msg.photo = False
        channel_msg.document = False

        dummy_handler = AsyncMock(return_value="SHOULD_NOT_BE_CALLED")

        with patch("handlers.ofd_bridge", self.bridge):
            res = asyncio.run(middleware(dummy_handler, channel_msg, {"bot": MagicMock()}))
            self.assertIsNone(res, "Kanal xabari middleware orqali ushlab qolinishi shart!")
            self.assertFalse(dummy_handler.called)


if __name__ == "__main__":
    unittest.main()
