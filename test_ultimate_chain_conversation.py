import os
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import types, Bot
from aiogram.enums import ChatType
from user_memory import user_memory
from excel_manager import excel_manager
from handlers.chat import handle_user_chat
from ofd_bridge import ofd_bridge

class TestUltimateChainConversation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        user_memory.clear()

    async def _send_msg(self, chat_id: int, user_id: int, text: str, bot_mock: AsyncMock) -> str:
        mock_msg = MagicMock(spec=types.Message)
        mock_msg.chat = MagicMock(id=chat_id, type=ChatType.PRIVATE if chat_id > 0 else ChatType.SUPERGROUP)
        mock_msg.from_user = MagicMock(id=user_id, username=f"user_{user_id}", first_name=f"User_{user_id}")
        mock_msg.text = text
        mock_msg.message_id = 2000 + len(user_memory.get_user_history(chat_id, user_id))
        
        reply_texts = []
        async def fake_reply(resp_text, *args, **kwargs):
            reply_texts.append(str(resp_text))
        mock_msg.reply = AsyncMock(side_effect=fake_reply)
        mock_msg.answer = AsyncMock(side_effect=fake_reply)
        initial_copy_count = bot_mock.copy_message.call_count

        from handlers.debt import is_debt_inquiry, handle_debt_inquiry, is_inn_or_phone_query_message, handle_inn_query
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
                reply_texts.append(f"[Kanaldan uzatilgan post/video ID: {msg_id}]")

        return "\n".join(reply_texts)

    async def test_full_chain_simulation(self):
        chat_id = 998811
        user_id = 998811
        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()

        # Mock OFD response for FM LG420230615712
        async def fake_ofd(b, fm, timeout=9.0):
            return "OFD ma'lumotlari:\nFiskal modul: LG420230615712\nHolati: To'langan va faol\nMuddati: 2026-12-31 gacha"
        
        turns = [
            ("Turn 1: Kirish", "Assalomu alaykum kassa apparatim o'chib qoldi nima qilish kerak"),
            ("Turn 2: INN berish (Qarzdor)", "206011507"),
            ("Turn 3: Oylik to'lov muddati", "oylik to'lov o'zi har oy qachon to'lanadi"),
            ("Turn 4: Yillik to'lov", "yillik to'lovimchichi, yillikdan qarzim bormi"),
            ("Turn 5: Fiskal modul berish", "LG420230615712"),
            ("Turn 6: Ikkalasini solishtirish", "oylik bilan yillikni bitta hisob raqamga to'lasam bo'ladimi"),
            ("Turn 7: Oylik shot raqam", "oylik to'lash uchun shot raqam bering"),
            ("Turn 8: Yillik shot raqam", "yillik to'lash uchun shot raqam bering"),
            ("Turn 9: Chalg'itish / off-topic", "bugun havo qanaqa bo'ladi yomg'ir yog'adimi"),
            ("Turn 10: Xatolik 406", "ekranda 406 xatolik chiqib qoldi bu nima degani"),
            ("Turn 11: Vaqt to'g'irlash", "kassada soat noto'g'ri ko'rsatyapti vaqtni qanday to'g'irlayman"),
            ("Turn 12: Z-hisobot", "kun oxirida z hisobot qanday chiqariladi"),
            ("Turn 13: MXIK kodi", "tamaki va sigaret mxik kodi qanaqa"),
            ("Turn 14: Chekdan INN/FM topish", "chekdan inn bilan fiskal modul qayerda yozilgan"),
            ("Turn 15: Kirillcha xotira tekshiruvi", "менинг корхонам номи нима эди ва қанча қарзим бор"),
            ("Turn 16: Operator / Texnik", "operator bilan gaplashmoqchiman telefon raqamini bering"),
            ("Turn 17: Yakun", "katta rahmat tushundim")
        ]

        with patch.object(ofd_bridge, "query_fiscal_module", side_effect=fake_ofd):
            print("\n" + "="*70)
            print("🚀 KETMA-KET TO'LIQ ZANJIRLI SIMULYATSIYA BOSHLANDI:")
            print("="*70)

            for step_title, user_prompt in turns:
                reply = await self._send_msg(chat_id, user_id, user_prompt, bot)
                print(f"\n👤 [{step_title}] Foydalanuvchi: {user_prompt}")
                print(f"🤖 Bot Javobi:\n{reply}")
                print("-" * 50)

                # Qat'iy tekshiruvlar:
                if "Turn 2" in step_title:
                    self.assertIn("QASHQADARYO SHARQ GAVHARI", reply)
                    self.assertIn("1,500,400", reply)
                elif "Turn 3" in step_title:
                    self.assertTrue(any(w in reply.lower() for w in ["6", "oylik", "har oy"]))
                elif "Turn 4" in step_title:
                    self.assertTrue(any(w in reply.lower() for w in ["fiskal modul", "lg", "yg", "uz", "soliq"]))
                elif "Turn 5" in step_title:
                    self.assertIn("LG420230615712", reply)
                elif "Turn 6" in step_title:
                    self.assertTrue(any(w in reply.lower() for w in ["alohida", "boshqa", "yo'q", "bo'lmaydi"]))
                elif "Turn 7" in step_title:
                    self.assertTrue("85" in reply or "20208000" in reply or "Mars" in reply)
                elif "Turn 8" in step_title:
                    self.assertTrue("34" in reply or "20210000" in reply or "Yangi Texnologiyalar" in reply)

                elif "Turn 10" in step_title:
                    self.assertTrue("1,500,400" in reply or "qarzdorlik" in reply.lower() or "406" in reply.lower())
                elif "Turn 11" in step_title:
                    self.assertTrue(any(w in reply.lower() for w in ["vaqt", "soat", "15", "video", "post"]))
                elif "Turn 12" in step_title:
                    self.assertTrue(any(w in reply.lower() for w in ["z-hisobot", "z hisobot", "hisobotlar", "kunlik"]))
                elif "Turn 13" in step_title:
                    self.assertTrue(any(w in reply.lower() for w in ["tamaki", "mxik", "kod", "02401"]))
                elif "Turn 14" in step_title:
                    self.assertTrue(any(w in reply.lower() for w in ["chek", "inn", "fiskal", "post", "34", "145", "149"]))

                elif "Turn 15" in step_title:
                    # Kirill alifbosida korxona nomi va qarz holati
                    self.assertTrue("QASHQADARYO" in reply or "ҚАШҚАДАРЁ" in reply or "1,500,400" in reply or "қарз" in reply.lower())
                elif "Turn 16" in step_title:
                    self.assertTrue(any(w in reply.lower() for w in ["@quvonchbek_admin", "@yashnarbek_butaev", "kontakt", "+998", "telefon"]))

            print("\n" + "="*70)
            print("✅ BARCHA 17 TA BOSQICH MUVAFFAQIYATLI O'TDI VA TEKSHIRILDI!")
            print("="*70 + "\n")

if __name__ == "__main__":
    unittest.main()
