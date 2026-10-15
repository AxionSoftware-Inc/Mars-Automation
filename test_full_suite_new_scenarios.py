import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import types
from handlers.chat import handle_user_chat
from user_memory import user_memory
from payment_accounts import (
    MARS_POST_ID,
    MARS_VIDEO_ID,
    YANGI_TEXNOLOGIYALAR_POST_ID,
    YANGI_TEXNOLOGIYALAR_VIDEO_ID
)


class TestFullSuiteNewScenarios(unittest.IsolatedAsyncioTestCase):
    """
    Yangi to'liq test:
    Barcha yangi talablar (qarzim qancha vs oylikchi/yillikchi, MXIK kodlar va soliq videolari,
    bitta shotga to'lash taqiqi, anti-hallucination va adminga eskalatsiya)
    haqiqiy foydalanuvchi muloqoti zanjirida to'liq sinovdan o'tkaziladi.
    """

    def setUp(self):
        user_memory.clear()
        self.chat_id = 778899
        self.user_id = 778899

    async def _send_msg(self, bot, text: str) -> MagicMock:
        msg = MagicMock(spec=types.Message)
        msg.text = text
        msg.chat = MagicMock(id=self.chat_id)
        msg.from_user = MagicMock(id=self.user_id, full_name="Valisher", username="valisher_biz")
        self._msg_counter = getattr(self, "_msg_counter", 1000) + 1
        msg.message_id = self._msg_counter
        msg.reply = AsyncMock()
        msg.answer = AsyncMock()

        await handle_user_chat(msg, bot)
        return msg

    async def test_complete_new_lifecycle(self):
        bot = AsyncMock()
        bot.copy_message = AsyncMock()
        bot.send_message = AsyncMock()

        print("\n" + "=" * 60)
        print("🚀 YANGI TO'LIQ TEST: 15 BOSQICHLI KOMPLEKS FOYDALANUVCHI OQIMI")
        print("=" * 60)

        # -------------------------------------------------------------
        # 1-QADAM: "Salom, qarzim qancha?"
        # -------------------------------------------------------------
        print("\n🔹 [Turn 1] Mijoz: 'Salom, qarzim qancha?'")
        with patch("ai_helper.openrouter_client.chat_completion", return_value="Assalomu alaykum! Qarzdorlikni bilish uchun korxonangiz INN raqamini yuboring."):
            msg1 = await self._send_msg(bot, "Salom, qarzim qancha?")
            # Tekshirish: Shot postlari (85 yoki 34) USHLANMAGAN bo'lishi shart
            bot.copy_message.assert_not_called()
            reply1 = msg1.reply.call_args[0][0]
            print(f"🤖 Bot: {reply1}")
            self.assertIn("INN", reply1)

        # -------------------------------------------------------------
        # 2-QADAM: Mijoz INN yuboradi ("302568138")
        # -------------------------------------------------------------
        print("\n🔹 [Turn 2] Mijoz: '302568138'")
        msg2 = await self._send_msg(bot, "302568138")
        reply2 = msg2.reply.call_args[0][0]
        print(f"🤖 Bot: {reply2[:140]}...")
        self.assertIn("MARS ELEKTRON TEXNIKA", reply2)
        self.assertIn("0 so'm", reply2)  # 302568138 da qarz 0

        # -------------------------------------------------------------
        # 3-QADAM: Mijoz endi "qarzim qancha" deb qayta so'raydi
        # (Kontekst bor, lekin shot postlari tashlanmasligi kerak!)
        # -------------------------------------------------------------
        print("\n🔹 [Turn 3] Mijoz yana: 'qarzim qancha'")
        bot.copy_message.reset_mock()
        with patch("ai_helper.openrouter_client.chat_completion", return_value="Abonent to'lovidan qarzingiz yo'q (0 so'm)."):
            msg3 = await self._send_msg(bot, "qarzim qancha")
            bot.copy_message.assert_not_called()
            reply3 = msg3.reply.call_args[0][0]
            print(f"🤖 Bot: {reply3}")
            self.assertTrue("qarzdorlik yo'q" in reply3.lower() or "qarzingiz yo'q" in reply3.lower())

        # -------------------------------------------------------------
        # 4-QADAM: Mijoz oylik hisob raqamini so'raydi: "oylikchi"
        # -------------------------------------------------------------
        print("\n🔹 [Turn 4] Mijoz: 'oylikchi'")
        bot.copy_message.reset_mock()
        await self._send_msg(bot, "oylikchi")
        self.assertEqual(bot.copy_message.call_count, 2)
        copied_ids = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
        print(f"🤖 Bot kanaldan uzatdi: Post {copied_ids}")
        self.assertIn(MARS_POST_ID, copied_ids)      # 85
        self.assertIn(MARS_VIDEO_ID, copied_ids)     # 148

        # -------------------------------------------------------------
        # 5-QADAM: Mijoz yillik hisob raqamini so'raydi: "yillikchi"
        # -------------------------------------------------------------
        print("\n🔹 [Turn 5] Mijoz: 'yillikchi'")
        bot.copy_message.reset_mock()
        await self._send_msg(bot, "yillikchi")
        self.assertEqual(bot.copy_message.call_count, 2)
        copied_ann = [c.kwargs.get("message_id") for c in bot.copy_message.call_args_list]
        print(f"🤖 Bot kanaldan uzatdi: Post {copied_ann}")
        self.assertIn(YANGI_TEXNOLOGIYALAR_POST_ID, copied_ann)  # 34
        self.assertIn(YANGI_TEXNOLOGIYALAR_VIDEO_ID, copied_ann) # 145

        # -------------------------------------------------------------
        # 6-QADAM: "Ikkalasini bitta hisob raqamga to'lasam bo'ladimi?"
        # -------------------------------------------------------------
        print("\n🔹 [Turn 6] Mijoz: 'oylik bilan yillikni bitta shotga qoshib tolasam boladimi'")
        bot.copy_message.reset_mock()
        msg6 = await self._send_msg(bot, "oylik bilan yillikni bitta shotga qoshib tolasam boladimi")
        reply6 = msg6.reply.call_args[0][0]
        print(f"🤖 Bot: {reply6[:130]}...")
        self.assertIn("Yo'q, mutlaqo bo'lmaydi", reply6)
        # Ikkala rekvizit uzatilishi kerak (Post 85 va 34)
        self.assertEqual(bot.copy_message.call_count, 2)

        # -------------------------------------------------------------
        # 7-QADAM: MXIK - Soliq saytidan kod qayerdan olinadi (Video 28)
        # -------------------------------------------------------------
        print("\n🔹 [Turn 7] Mijoz: 'soliq saytidan kod qanday olinadi'")
        bot.copy_message.reset_mock()
        msg7 = await self._send_msg(bot, "soliq saytidan kod qanday olinadi")
        reply7 = msg7.reply.call_args[0][0]
        print(f"🤖 Bot: {reply7[:120]}...")
        self.assertIn("tasnif.soliq.uz", reply7)
        bot.copy_message.assert_called_once()
        self.assertEqual(bot.copy_message.call_args[1]["message_id"], 28)

        # -------------------------------------------------------------
        # 8-QADAM: MXIK - Aniq tovar kodi so'ralsa (Soxta kod to'qilmaydi!)
        # -------------------------------------------------------------
        print("\n🔹 [Turn 8] Mijoz: 'nonning mxik kodi qanaqa'")
        bot.copy_message.reset_mock()
        msg8 = await self._send_msg(bot, "nonning mxik kodi qanaqa")
        reply8 = msg8.reply.call_args[0][0]
        print(f"🤖 Bot: {reply8[:120]}...")
        self.assertIn("tasnif.soliq.uz", reply8)
        self.assertEqual(bot.copy_message.call_args[1]["message_id"], 28)

        # -------------------------------------------------------------
        # 9-QADAM: MXIK - Tovar qo'shish tartibi (Video 15)
        # -------------------------------------------------------------
        print("\n🔹 [Turn 9] Mijoz: 'kassaga tovar qo'shish qanday boladi'")
        bot.copy_message.reset_mock()
        msg9 = await self._send_msg(bot, "kassaga tovar qo'shish qanday boladi")
        reply9 = msg9.reply.call_args[0][0]
        print(f"🤖 Bot: {reply9[:120]}...")
        self.assertIn("Tovar qo'shish", reply9)
        self.assertEqual(bot.copy_message.call_args[1]["message_id"], 15)

        # -------------------------------------------------------------
        # 10-QADAM: MXIK - Naqdga savdo cheklovi (Video 133)
        # -------------------------------------------------------------
        print("\n🔹 [Turn 10] Mijoz: 'tamaki va sigaret naqdga urib bolmayapti'")
        bot.copy_message.reset_mock()
        msg10 = await self._send_msg(bot, "tamaki va sigaret naqdga urib bolmayapti")
        reply10 = msg10.reply.call_args[0][0]
        print(f"🤖 Bot: {reply10[:120]}...")
        self.assertIn("Naqd pulga savdo qilib bo'lmaydigan", reply10)
        self.assertEqual(bot.copy_message.call_args[1]["message_id"], 133)

        # -------------------------------------------------------------
        # 11-QADAM: MXIK - Chekni bekor qilish / otkaz (Video 53)
        # -------------------------------------------------------------
        print("\n🔹 [Turn 11] Mijoz: 'tovarni chekdan otkaz qilish va qaytadan urish'")
        bot.copy_message.reset_mock()
        msg11 = await self._send_msg(bot, "tovarni chekdan otkaz qilish va qaytadan urish")
        reply11 = msg11.reply.call_args[0][0]
        print(f"🤖 Bot: {reply11[:120]}...")
        self.assertIn("bekor", reply11.lower())
        self.assertEqual(bot.copy_message.call_args[1]["message_id"], 53)

        # -------------------------------------------------------------
        # 12-QADAM: MXIK - Exceldan baza yuklash (Video 138)
        # -------------------------------------------------------------
        print("\n🔹 [Turn 12] Mijoz: 'exceldan tovarlar bazasi yuklash'")
        bot.copy_message.reset_mock()
        msg12 = await self._send_msg(bot, "exceldan tovarlar bazasi yuklash")
        reply12 = msg12.reply.call_args[0][0]
        print(f"🤖 Bot: {reply12[:120]}...")
        self.assertIn("bazasini yuklash", reply12)
        self.assertEqual(bot.copy_message.call_args[1]["message_id"], 138)

        # -------------------------------------------------------------
        # 13-QADAM: MXIK - Soliq jarimasi va xato kodlar (Video 17)
        # -------------------------------------------------------------
        print("\n🔹 [Turn 13] Mijoz: 'xato kod uchun soliq jarima qollaydimi'")
        bot.copy_message.reset_mock()
        msg13 = await self._send_msg(bot, "xato kod uchun soliq jarima qollaydimi")
        reply13 = msg13.reply.call_args[0][0]
        print(f"🤖 Bot: {reply13[:120]}...")
        self.assertIn("jarima", reply13.lower())
        self.assertEqual(bot.copy_message.call_args[1]["message_id"], 17)

        # -------------------------------------------------------------
        # 14-QADAM: Yillik to'lovni tekshirish (Fiskal modul so'rash)
        # -------------------------------------------------------------
        print("\n🔹 [Turn 14] Mijoz: 'yillik tolovimni tekshirib ber'")
        bot.copy_message.reset_mock()
        msg14 = await self._send_msg(bot, "yillik tolovimni tekshirib ber")
        reply14 = msg14.reply.call_args[0][0]
        print(f"🤖 Bot: {reply14[:120]}...")
        self.assertIn("Fiskal modul", reply14)

        # -------------------------------------------------------------
        # 15-QADAM: Noma'lum / begona savol (Anti-Hallucination & Eskalatsiya)
        # -------------------------------------------------------------
        print("\n🔹 [Turn 15] Mijoz: 'buxgalteriya hisobotini qanday topshiraman'")
        with patch("ai_helper.openrouter_client.chat_completion", return_value="Bu savol bo'yicha menda aniq ma'lumot yo'q. Savolingizni mas'ul mutaxassisimizga yubordim. [ADMINGA_SAVOL]"), \
             patch("admin_manager.admin_manager.notify_user_query_escalation") as mock_escalate:
            msg15 = await self._send_msg(bot, "buxgalteriya hisobotini qanday topshiraman")
            reply15 = msg15.reply.call_args[0][0]
            print(f"🤖 Bot: {reply15}")
            self.assertIn("menda aniq ma'lumot yo'q", reply15)
            self.assertNotIn("[ADMINGA_SAVOL]", reply15)  # Mijozga ko'rinmaydi
            # Adminga eskalatsiya qilinganini tekshirish:
            mock_escalate.assert_called_once()
            call_kwargs = mock_escalate.call_args[1]
            print(f"📢 Adminga eskalatsiya yuborildi: sabab='{call_kwargs['reason']}'")
            self.assertEqual(call_kwargs["chat_id"], self.chat_id)

        print("\n" + "=" * 60)
        print("✅ YANGI 15 BOSQICHLI TEST MUVAFFAQIYATLI O'TDI!")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    unittest.main()
