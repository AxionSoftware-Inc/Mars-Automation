import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import types, Bot
from aiogram.enums import ChatType
from user_memory import user_memory
from excel_manager import excel_manager
from handlers.chat import handle_user_chat
from ofd_bridge import ofd_bridge


class TestLongConversationMultiTurnStress(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        user_memory.clear()

    async def _send_msg(self, chat_id: int, user_id: int, text: str, bot_mock: AsyncMock) -> str:
        """Yordamchi funksiya: Foydalanuvchi xabarini jo'natish va botning qaytargan javob matnini olish"""
        mock_msg = MagicMock(spec=types.Message)
        mock_msg.chat = MagicMock(id=chat_id, type=ChatType.PRIVATE if chat_id > 0 else ChatType.SUPERGROUP)
        mock_msg.from_user = MagicMock(id=user_id, username=f"user_{user_id}", first_name=f"User_{user_id}")
        mock_msg.text = text
        mock_msg.message_id = 1000 + len(user_memory.get_user_history(chat_id, user_id))
        
        reply_texts = []
        async def fake_reply(resp_text, *args, **kwargs):
            reply_texts.append(str(resp_text))
        mock_msg.reply = AsyncMock(side_effect=fake_reply)
        mock_msg.answer = AsyncMock(side_effect=fake_reply)

        from handlers.debt import is_debt_inquiry, handle_debt_inquiry, is_inn_or_phone_query_message, handle_inn_query
        if is_debt_inquiry(mock_msg):
            await handle_debt_inquiry(mock_msg)
        elif is_inn_or_phone_query_message(mock_msg):
            await handle_inn_query(mock_msg, bot_mock)
        else:
            await handle_user_chat(mock_msg, bot_mock)

        combined_reply = "\n".join(reply_texts)
        return combined_reply

    # =========================================================================
    # PERSONA 1: Sobir aka - 10 qadamli to'liq biznes muloqoti
    # =========================================================================
    async def test_persona_1_sobir_aka_full_10_turns(self):
        """Sobir aka: Salom -> Apparat nosozligi -> INN -> Yillik -> FM -> Internet/Vaqt -> Soat videosi -> MXIK -> Muddat -> Rahmat"""
        chat_id = 10001
        user_id = 20001
        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()

        with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = "Litsenziya muddati: 2026-12-31 gacha faol."

            # Turn 1: Salomlashish
            r1 = await self._send_msg(chat_id, user_id, "Assalomu alaykum", bot)
            self.assertTrue(len(r1) > 0)
            self.assertTrue("assalom" in r1.lower() or "salom" in r1.lower() or "xush" in r1.lower())

            # Turn 2: Apparat ishlamayapti
            r2 = await self._send_msg(chat_id, user_id, "Bizda apparat qotib qoldi ishlamayapti", bot)
            self.assertIn("INN", r2)

            # Turn 3: INN kiritish (302568138 - MARS ELEKTRON)
            r3 = await self._send_msg(chat_id, user_id, "302568138", bot)
            self.assertIn("MARS ELEKTRON", r3)
            self.assertIn("qarzdorlik yo'q", r3.lower())

            # Turn 4: Yillikdan qarzim bormi?
            r4 = await self._send_msg(chat_id, user_id, "oylikdan qarzsiz ekanmiz, yillikdanchi qarzim bormi?", bot)
            self.assertIn("Fiskal modul", r4)

            # Turn 5: Fiskal modul seriya raqami
            r5 = await self._send_msg(chat_id, user_id, "LG420210630789", bot)
            self.assertIn("LG420210630789", r5)
            self.assertIn("Litsenziya muddati", r5)

            # Turn 6: Unda nega chek chiqarmayapti?
            r6 = await self._send_msg(chat_id, user_id, "Unda nega apparat chek chiqarmayapti?", bot)
            self.assertTrue(any(w in r6.lower() for w in ["internet", "soat", "sana", "o'chirib yoqing", "reboot", "qarz", "tekshir"]))

            # Turn 7: Soat xato ko'rsatyapti
            r7 = await self._send_msg(chat_id, user_id, "kassada vaqt xato ko'rsatyapti qanday to'g'irlayman", bot)
            # Soat uchun 141-video copy_message orqali yoki matnda yuborilishi kerak
            bot.copy_message.assert_called()

            # Turn 8: MXIK kodi qo'shish
            r8 = await self._send_msg(chat_id, user_id, "endi yangi tovar qo'shmoqchiman mxik kodi qayerdan olinadi", bot)
            self.assertTrue("mxik" in r8.lower() or "tasnif" in r8.lower() or "kod" in r8.lower())

            # Turn 9: To'lov muddati qachongacha?
            r9 = await self._send_msg(chat_id, user_id, "keyingi oylik to'lov har oy qaysi sanagacha to'lanadi", bot)
            self.assertIn("6", r9)

            # Turn 10: Rahmat
            r10 = await self._send_msg(chat_id, user_id, "Katta rahmat sizga!", bot)
            self.assertTrue("arzimaydi" in r10.lower() or "xursandmiz" in r10.lower() or "salomat" in r10.lower())

    # =========================================================================
    # PERSONA 2: Nodirbek - Qarzli mijoz (206011507) 8 qadamli dialog
    # =========================================================================
    async def test_persona_2_nodirbek_debtor_flow_8_turns(self):
        """Nodirbek: Qarz tekshiruvi -> E'tiroz/Tarix -> Shot raqam -> Yillik shot -> Ikkalasini bitta qilish -> Yoqilish vaqti -> Kontaktlar"""
        chat_id = 10002
        user_id = 20002
        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()

        # Turn 1: Qarz bormi 206011507
        r1 = await self._send_msg(chat_id, user_id, "qarzim bormi 206011507", bot)
        self.assertIn("1,500,400", r1)

        # Turn 2: Nega buncha ko'p, to'lov tariximni ko'rsat
        r2 = await self._send_msg(chat_id, user_id, "nega buncha qarzman to'lov tariximni ko'rsating", bot)
        self.assertIn("QASHQADARYO SHARQ GAVHARI", r2)

        # Turn 3: Oylik to'lash uchun shot raqam tashlang
        r3 = await self._send_msg(chat_id, user_id, "oylik to'lash uchun shot raqam tashlang", bot)
        self.assertTrue("MARS ELEKTRON TEXNIKA" in r3 and "100 000" in r3)
        bot.copy_message.assert_called()

        # Turn 4: Yillik uchun ham hisob raqam bering
        r4 = await self._send_msg(chat_id, user_id, "yillik to'lov shot raqamini ham tashlang", bot)
        self.assertTrue("Yangi Texnologiyalar" in r4 and "440 000" in r4)
        bot.copy_message.assert_called()

        # Turn 5: Ikkalasini bitta shotga tashlasam bo'ladimi?
        r5 = await self._send_msg(chat_id, user_id, "ikkalasini bitta shotga tashlasam bo'ladimi", bot)
        self.assertTrue("alohida" in r5.lower() or "boshqa" in r5.lower() or "taqsimlanadi" in r5.lower())

        # Turn 6: To'lov qildim apparat qachon yoqiladi?
        r6 = await self._send_msg(chat_id, user_id, "to'lov qildim apparat qachon yoqiladi", bot)
        self.assertTrue(any(w in r6.lower() for w in ["yoqil", "yoq", "ochil", "aktiv", "kvitansiya", "chek", "tasdiq", "daqiqa"]))

        # Turn 7: Administrator / mutaxassis bilan bog'lanish
        r7 = await self._send_msg(chat_id, user_id, "usta yoki admin bilan qanday bog'lansam bo'ladi", bot)
        self.assertTrue("@" in r7 or "75 522" in r7 or "admin" in r7.lower())

    # =========================================================================
    # PERSONA 3: Bahodir aka - Kirill yozuvidagi 6 qadamli muloqot
    # =========================================================================
    async def test_persona_3_cyrillic_user_flow_6_turns(self):
        """Bahodir aka: Салом -> Аппаратга тўлов қилиш счёти -> ИНН 311790999 -> Йиллик тўлов -> Чекни қайтариш -> Раҳмат"""
        chat_id = 10003
        user_id = 20003
        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()

        # Turn 1: Салом
        r1 = await self._send_msg(chat_id, user_id, "Салом алайкум", bot)
        self.assertTrue("ассалом" in r1.lower() or "салом" in r1.lower() or "хуш" in r1.lower())

        # Turn 2: Тўлов учун счёт
        r2 = await self._send_msg(chat_id, user_id, "аппаратга тўлов қилиш учун счёт беринг", bot)
        self.assertTrue("алоҳида тўлов" in r2.lower() or "марс" in r2.lower())
        bot.copy_message.assert_called()

        # Turn 3: ИНН 311790999
        r3 = await self._send_msg(chat_id, user_id, "311790999", bot)
        self.assertIn("қарздорлик йўқ", r3.lower())

        # Turn 4: Йилликданчи
        r4 = await self._send_msg(chat_id, user_id, "йилликдан қарзим борми", bot)
        self.assertIn("Фискал модул", r4)

        # Turn 5: Чекни бекор қилиш
        r5 = await self._send_msg(chat_id, user_id, "чекни бекор қилиш возврат видеоси", bot)
        bot.copy_message.assert_called()

        # Turn 6: Раҳмат
        r6 = await self._send_msg(chat_id, user_id, "Катта раҳмат сизга", bot)
        self.assertTrue("арзимайди" in r6.lower() or "хурсандмиз" in r6.lower() or "саломат" in r6.lower())

    # =========================================================================
    # PERSONA 4: Qiyin / Beo'xshov savollar bilan adashtiruvchi mijoz
    # =========================================================================
    async def test_persona_4_adversarial_and_awkward_6_turns(self):
        """Qiyin holatlar: Apparat o'lib qoldi -> 123 -> Ism bilan qidirish -> Kartadan pul yechildi chek yo'q -> Usta chaqirish"""
        chat_id = 10004
        user_id = 20004
        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()

        # Turn 1: e xullas apparat o'lib qoldi
        r1 = await self._send_msg(chat_id, user_id, "e xullas apparat o'lib qoldi nega ishlamayapti", bot)
        self.assertIn("INN", r1)

        # Turn 2: 123 (juda qisqa noaniq raqam)
        r2 = await self._send_msg(chat_id, user_id, "123", bot)
        self.assertTrue("inn" in r2.lower() or "raqam" in r2.lower())

        # Turn 3: Ism orqali qarz so'rash
        r3 = await self._send_msg(chat_id, user_id, "mening nomim Jamshid korxonam qarzdorligini ko'rib ber", bot)
        self.assertTrue("9 xonali" in r3 or "inn" in r3.lower())

        # Turn 4: Kartamdan pul yechildi lekin apparat yoqmadi
        r4 = await self._send_msg(chat_id, user_id, "kartamdan 100 ming yechildi lekin apparatim hali ham yonmadi", bot)
        self.assertTrue("kvitansiya" in r4.lower() or "15" in r4 or "daqiqa" in r4 or "bank" in r4.lower())

        # Turn 5: Usta yuboring manzilga kelsin
        r5 = await self._send_msg(chat_id, user_id, "usta yuboring do'konga kelib ko'rsin", bot)
        self.assertTrue("tuman" in r5.lower() or "usta" in r5.lower() or "@" in r5 or "telefon" in r5.lower())


if __name__ == "__main__":
    unittest.main()
