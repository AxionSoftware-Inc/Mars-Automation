import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

from aiogram import types
from user_memory import user_memory
from excel_manager import excel_manager
from handlers.intents.hardware import hardware_intent_handler
from handlers.debt import handle_inn_query
from handlers.intents.billing import billing_intent_handler
from handlers.media import _process_image_content
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
    return message


class TestIssuePipelineAndSimpleQuery(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        user_memory.sessions.clear()
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()
        self.bot.copy_message = AsyncMock()
        self.bot.send_photo = AsyncMock()
        self.orig_notify_admins = admin_manager.notify_admins
        admin_manager.notify_admins = AsyncMock()

    def tearDown(self):
        admin_manager.notify_admins = self.orig_notify_admins

    async def test_1_simple_query_no_issue_mode(self):
        """Oddiy so'rov: mijoz faqat INN yuboradi. Bot faqat qarzni aytadi, majburiy 2-bosqich yuklanmaydi."""
        chat_id = 1001
        user_id = 2001
        msg = create_mock_message(chat_id, user_id, text="300600431")

        # INN orqali qarz so'rovi
        await handle_inn_query(msg, self.bot)

        self.assertFalse(user_memory.is_issue_mode(chat_id, user_id))
        msg.reply.assert_called_once()
        reply_call = msg.reply.call_args[0][0]

        # Javobda qarz ma'lumoti bo'lishi kerak
        self.assertIn("qarzdorlik yo'q", reply_call.lower())
        # Lekin majburiy 2-bosqich (OFD fiskal modul so'rash) va Post 149 bo'lmasligi kerak!
        self.assertNotIn("2-bosqich: Davlat Soliq (OFD)", reply_call)
        self.bot.copy_message.assert_not_called()
        admin_manager.notify_admins.assert_not_called()

    async def test_2_issue_mode_with_monthly_debt(self):
        """Muammo rejimi: apparat ishlamayapti -> INN kiritganda oylik qarz bor bo'lsa -> Post 85 va 148 nusxalanadi."""
        chat_id = 1002
        user_id = 2002

        # 1-qadam: mijoz muammodan shikoyat qiladi
        msg1 = create_mock_message(chat_id, user_id, text="apparatim ishlamayapti nima qilsam boladi")
        handled = await hardware_intent_handler.handle(msg1, self.bot, "latin")
        self.assertTrue(handled)
        self.assertTrue(user_memory.is_issue_mode(chat_id, user_id))

        # 2-qadam: mijoz qarzga ega korxona INN sini yuboradi
        # Excel bazadagi qarzdor INN ni topamiz yoki mock qilamiz
        with patch.object(excel_manager, "search", return_value=[{"name": "TEST QARZ MCHJ", "stir": "999888777", "debt": 100000.0, "is_p3": False}]):
            msg2 = create_mock_message(chat_id, user_id, text="999888777")
            await handle_inn_query(msg2, self.bot)

            # Javobda apparat to'xtashining sababi oylik qarz ekani aytilishi kerak
            reply_call = msg2.reply.call_args[0][0]
            self.assertIn("sababi: «Mars» oylik abonent to'lovidan qarzdorlik", reply_call)
            # Faqat rasmiy hisob raqam posti (Post 85) nusxalanadi (video faqat qanday to'lanadi deb so'ralganda uzatiladi)
            self.assertEqual(self.bot.copy_message.call_count, 1)
            copy_msg_ids = [c[1]["message_id"] for c in self.bot.copy_message.call_args_list]
            self.assertIn(85, copy_msg_ids)
            self.assertNotIn(148, copy_msg_ids)

    async def test_3_issue_mode_with_annual_debt(self):
        """Muammo rejimi: apparat ishlamayapti -> Oylik 0 -> 2-bosqich FM so'raydi -> Yillik qarz bo'lsa -> Post 34 va 145."""
        chat_id = 1003
        user_id = 2003

        # 1-qadam: Muammo bildirish
        msg1 = create_mock_message(chat_id, user_id, text="kassa ishlamay qoldi")
        await hardware_intent_handler.handle(msg1, self.bot, "latin")
        self.assertTrue(user_memory.is_issue_mode(chat_id, user_id))

        # 2-qadam: INN yuborish (oylik qarz 0 bo'lgan INN: 300600431)
        msg2 = create_mock_message(chat_id, user_id, text="300600431")
        await handle_inn_query(msg2, self.bot)

        reply2 = msg2.reply.call_args[0][0]
        self.assertIn("2-bosqich: Davlat Soliq (OFD) yillik litsenziyasini tekshirish", reply2)
        # Post 149 (fiskal modul namunasi) nusxalangan bo'lishi kerak!
        self.bot.copy_message.assert_called_once()
        self.assertEqual(self.bot.copy_message.call_args[1]["message_id"], 149)

        # 3-qadam: Fiskal modul raqamini yuborish (Soliq OFD tizimida qarzdorlik mavjud)
        self.bot.copy_message.reset_mock()
        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", new=AsyncMock(return_value="Qarzdorlik mavjud: 440 000 so'm")):
            msg3 = create_mock_message(chat_id, user_id, text="LG420210630789")
            handled3 = await billing_intent_handler.handle(msg3, self.bot, "latin")
            self.assertTrue(handled3)

            reply3 = msg3.reply.call_args[0][0]
            self.assertIn("qarzdorlik mavjud", reply3.lower())
            self.assertIn("davlat soliq qo'mitasi (ofd) yillik litsenziya", reply3.lower())
            # Faqat rasmiy hisob raqam posti (Post 34) nusxalanadi (video faqat qanday to'lanadi deb so'ralganda uzatiladi)
            self.assertEqual(self.bot.copy_message.call_count, 1)
            copy_msg_ids = [c[1]["message_id"] for c in self.bot.copy_message.call_args_list]
            self.assertIn(34, copy_msg_ids)
            self.assertNotIn(145, copy_msg_ids)

    async def test_4_issue_mode_both_clear_escalates_to_admin(self):
        """Muammo rejimi: apparat ishlamayapti -> Oylik 0 -> Yillik 0 -> 3-bosqich ko'rsatiladi va ADMINGA ESKALATSIYA qilinadi!"""
        chat_id = 1004
        user_id = 2004

        # 1-qadam: Muammo bildirish
        msg1 = create_mock_message(chat_id, user_id, text="apparatim o'chib qoldi chek chiqmayapti")
        await hardware_intent_handler.handle(msg1, self.bot, "latin")
        self.assertTrue(user_memory.is_issue_mode(chat_id, user_id))

        # 2-qadam: INN yuborish (300600431 -> qarz 0)
        msg2 = create_mock_message(chat_id, user_id, text="300600431")
        await handle_inn_query(msg2, self.bot)

        # 3-qadam: Fiskal modul yuborish (Soliq OFD tizimida FAOL / qarz yo'q)
        with patch("ofd_bridge.ofd_bridge.query_fiscal_module", new=AsyncMock(return_value="Holati: Faol. Muddati: 2026-12-31")):
            msg3 = create_mock_message(chat_id, user_id, text="LG420210630789")
            handled3 = await billing_intent_handler.handle(msg3, self.bot, "latin")
            self.assertTrue(handled3)

            reply3 = msg3.reply.call_args[0][0]
            # 3-bosqich matni foydalanuvchiga chiqishi kerak:
            self.assertIn("To'lovlar bo'yicha hech qanday qarzdorlik yo'q", reply3)
            self.assertIn("Internet aloqasi", reply3)
            self.assertIn("Soat va sana", reply3)
            self.assertIn("Qayta yoqish", reply3)
            self.assertIn("Rasm yuborish", reply3)
            self.assertIn("mutaxassislarga", reply3)

            # VA ADMINGA ESKALATSIYA QILINISHI SHART!
            admin_manager.notify_admins.assert_called_once()
            admin_text = admin_manager.notify_admins.call_args[1]["text"]
            self.assertIn("300600431", admin_text)
            self.assertIn("LG420210630789", admin_text)
            self.assertIn("to'langan", admin_text.lower())
            self.assertIn("ishlamayapti", admin_text.lower())

    async def test_5_issue_mode_photo_escalation(self):
        """Muammo rejimida foydalanuvchi ekrandagi xatolik rasmini yuborganda adminga rasm bilan eskalatsiya ketishi kerak."""
        chat_id = 1005
        user_id = 2005

        # 1-qadam: Muammo boshlash
        msg1 = create_mock_message(chat_id, user_id, text="kassa ishlamayapti xato chiqyapti")
        await hardware_intent_handler.handle(msg1, self.bot, "latin")
        user_memory.set_last_id(chat_id, user_id, "300600431", org_name="YANGI TEST MCHJ", debt=0.0)

        # 2-qadam: Rasm yuborish (Smart POS apparati ekrani)
        msg_photo = create_mock_message(chat_id, user_id, text="")
        msg_photo.caption = "Mana rasm"

        from core.models import DeviceFacts
        mock_facts = DeviceFacts(
            is_real_pos_device=True,
            is_status_bar_visible=True,
            screen_text_summary="Tarmoq ulanmadi (Internet xatosi)",
            detected_inn="300600431"
        )

        with patch("handlers.media.analyze_media_image", return_value=("pos_device", None, mock_facts)):
            await _process_image_content(
                message=msg_photo,
                bot=self.bot,
                image_bytes=b"dummy_bytes",
                caption="Mana rasm",
                file_id="photo_123456"
            )

            # Adminga foto bilan eskalatsiya ketgan bo'lishi kerak!
            admin_manager.notify_admins.assert_called_once()
            call_args = admin_manager.notify_admins.call_args[1]
            self.assertEqual(call_args["photo_file_id"], "photo_123456")
            admin_text = call_args["text"]
            self.assertIn("300600431", admin_text)
            self.assertIn("Tarmoq ulanmadi", admin_text)


if __name__ == "__main__":
    unittest.main()
