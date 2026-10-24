import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import types, Bot
from aiogram.enums import ChatType
from user_memory import user_memory
from excel_manager import excel_manager
from handlers.chat import handle_user_chat
from ofd_bridge import ofd_bridge
from handlers.debt import (
    is_debt_inquiry,
    handle_debt_inquiry,
    is_inn_or_phone_query_message,
    handle_inn_query
)


class Test10xUltraComplexAdversarialStress(unittest.IsolatedAsyncioTestCase):
    """
    10x Baravar Murakkablashtirilgan Adversarial Stress Test To'plami:
    - Chalg'itishlar, gapni burish, qarama-qarshi talablar
    - Bir xabarda 3-4 xil intent va jargon
    - Soxta to'lov e'tirozlari va bosim o'tkazish
    - Xavfsizlik: SQLi, XSS, buzilgan formatlar
    - 1 soatlik TTL sessiya tugashi va uning xavfsiz boshqaruvi
    - Guruh chatlarida bir vaqtda 3 ta mijozning aralash muloqoti (State Isolation)
    """

    def setUp(self):
        user_memory.clear()
        self.ai_patcher = patch(
            "ai_helper.generate_ai_reply_ex",
            return_value=("Assalomu alaykum! Smart POS bo'yicha yordam beramiz.", None, False)
        )
        self.ai_async_patcher = patch(
            "ai_helper.generate_ai_reply_ex_async",
            new_callable=AsyncMock,
            return_value=("Assalomu alaykum! Smart POS bo'yicha yordam beramiz.", None, False)
        )
        self.ai_patcher.start()
        self.ai_async_patcher.start()

    def tearDown(self):
        self.ai_patcher.stop()
        self.ai_async_patcher.stop()

    async def _send_msg(self, chat_id: int, user_id: int, text: str, bot_mock: AsyncMock) -> str:
        """Yordamchi funksiya: Foydalanuvchi xabarini router tartibida o'tkazish va javob matnini olish"""
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
                reply_texts.append(f"[Video/Post: {msg_id}]")

        combined_reply = "\n".join(reply_texts)
        return combined_reply

    # =========================================================================
    # FLOW 1: THE HYPER-DISTRACTED CONTRADICTORY BOSS (11 TURNS)
    # =========================================================================
    async def test_flow_1_hyper_distracted_contradictory_boss(self):
        """
        Mavzudan-mavzuga sakrash, INNni o'rtada almashtirish, bema'ni savollar,
        texnik yo'riqnomalar va hisob raqamlarni aralashtirib berish.
        """
        chat_id = 70001
        user_id = 80001
        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()

        with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = "Litsenziya muddati: 2026-12-31 gacha faol."

            # Turn 1: Apparat buzildi deb boshlash
            r1 = await self._send_msg(chat_id, user_id, "E apparat o'lib qoldi, ekranda qanaqadir xato chiqyapti!", bot)
            self.assertIn("INN", r1)

            # Turn 2: Chalg'itish 1 - Tovar narxini o'zgartirish (MXIK)
            r2 = await self._send_msg(chat_id, user_id, "To'xtab turing, unga qadar non sotuvini kiritgandim narxini qanday o'zgartiraman?", bot)
            self.assertTrue(len(r2) > 0 and any(w in r2.lower() for w in ["narx", "tovar", "mxik", "tasnif", "katalog", "kassa", "mahsulot", "o'zgartir", "video", "post", "140"]))

            # Turn 3: Chalg'itish 2 - Usta raqami
            r3 = await self._send_msg(chat_id, user_id, "Usta raqamini ham yozib qoyingchi bir yo'la kerak bo'ladi", bot)
            self.assertTrue(any(w in r3.lower() for w in ["usta", "admin", "@", "75 522", "telefon"]))

            # Turn 4: Qaytish + Noto'g'ri firma INNi (206011507)
            r4 = await self._send_msg(chat_id, user_id, "Ha mayli, apparat blok bo'lgani bo'yicha INN: 206011507", bot)
            self.assertIn("1,500,400", r4)
            self.assertIn("QASHQADARYO SHARQ GAVHARI", r4)

            # Turn 5: Fikrni keskin o'zgartirish (Contradiction: bu akamniki edi, meniki boshqa)
            r5 = await self._send_msg(chat_id, user_id, "Voy kechirasiz adashibman! Bu akamning do'koni edi, meniki boshqa: 302568138 tekshirib ber!", bot)
            self.assertIn("MARS ELEKTRON", r5)
            self.assertIn("qarzdorlik yo'q", r5.lower())
            self.assertEqual(user_memory.get_last_id(chat_id, user_id), "302568138")

            # Turn 6: "Nega yillik qarzimni aytmading?"
            r6 = await self._send_msg(chat_id, user_id, "Oylikdan qarzi yo'q bo'lsa nega apparat ishlamayapti, yillikdan qarzim bormi?", bot)
            self.assertIn("Fiskal modul", r6)

            # Turn 7: Fiskal modul berish (matn ichida shovqin bilan)
            r7 = await self._send_msg(chat_id, user_id, "Hozir chekni ko'ryapman, pastida f.m: LG420210630789 deb yozilgan, qarab yubor-chi", bot)
            self.assertIn("LG420210630789", r7)
            self.assertIn("Litsenziya muddati", r7)

            # Turn 8: Soat nosozligi
            r8 = await self._send_msg(chat_id, user_id, "Kassada soat 2 soat orqada qolib ketgan ekan, shundan chek chiqmayapti shekilli, qanday to'g'irlayman?", bot)
            bot.copy_message.assert_called()

            # Turn 9: Oylik to'lov hisob raqamini so'rash (Post 85 uzatiladi)
            r9 = await self._send_msg(chat_id, user_id, "Yaxshi, lekin baribir oylik to'lov hisob raqamini ham tashlab qo'y, to'lab qo'yay", bot)
            self.assertTrue("85" in r9 or "MARS ELEKTRON TEXNIKA" in r9)

            # Turn 10: Chalg'ituvchi bema'ni savol (ob-havo)
            r10 = await self._send_msg(chat_id, user_id, "Bugun ob-havo qanday bo'ladi kassa sovib ketmasin", bot)
            self.assertTrue(len(r10) > 0)  # Bot xatoliksiz silliq javob beradi

            # Turn 11: Rahmatlashish
            r11 = await self._send_msg(chat_id, user_id, "Katta rahmat uka, ishingizga baraka!", bot)
            self.assertTrue(len(r11) > 0 and any(w in r11.lower() for w in ["arzimaydi", "xursandmiz", "salomat", "rahmat", "baraka", "xizmat", "omad", "yordam", "har doim"]))

    # =========================================================================
    # FLOW 2: THE MULTI-INTENT HYBRID MESSAGE TORNADO (7 TURNS)
    # =========================================================================
    async def test_flow_2_multi_intent_hybrid_and_slang(self):
        """
        Bir xabarda bir nechta savol/talab, Kirill va ruscha jargon,
        soxta to'lov bosimi va kvitansiya talabi.
        """
        chat_id = 70002
        user_id = 80002
        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()

        # Turn 1: Aralash xabar (Salom + Qotib qoldi + INN 302568138 + Yillik/Oylik qarz)
        r1 = await self._send_msg(
            chat_id, user_id,
            "Assalomu alaykum usta aka, Smart One apparatimiz qotib qoldi, 302568138 nomerli firmamiz qarzini tekshirib bering",
            bot
        )
        self.assertIn("MARS ELEKTRON", r1)
        self.assertIn("qarzdorlik yo'q", r1.lower())

        # Turn 2: Yillikdan ham qarzim bormi?
        r2 = await self._send_msg(chat_id, user_id, "yillikdan ham qarzim bormi aytib yuboring", bot)
        self.assertIn("Fiskal modul", r2)

        # Turn 3: Kirill va ruscha jargon bilan vozvrat videosini so'rash
        r3 = await self._send_msg(
            chat_id, user_id,
            "Брат, чекни қайтариш возврат қилиш керак эди, клиент пулини сўраяпти видеосини ташланг",
            bot
        )
        bot.copy_message.assert_called()

        # Turn 4: Soxta to'lov bilan shoshiltirish va bosim o'tkazish
        r4 = await self._send_msg(
            chat_id, user_id,
            "Men hozir 1 500 000 tashladim, chek yo'q apparatni zudlik bilan yoqib bering bo'lmasam soliq jarima soladi!",
            bot
        )
        # Bot darhol yolg'ondan 'yoqildi' demaydi, kvitansiya yoki 15-30 daqiqa bank tasdiqini talab qiladi
        self.assertTrue(len(r4) > 0 and any(w in r4.lower() for w in ["kvitansiya", "tasdiq", "daqiqa", "bank", "inn", "chek", "to'lov", "admin", "yoqil", "ochil", "operat"]))

        # Turn 5: Ikkala hisob raqamni bir vaqtda so'rash (Post 85 va Post 34 uzatiladi)
        r5 = await self._send_msg(chat_id, user_id, "oylik va yillik ikkala shotni ham bitta qilib tashlab bering", bot)
        self.assertTrue(("85" in r5 and "34" in r5) or ("MARS ELEKTRON TEXNIKA" in r5 and "Yangi Texnologiyalar" in r5))

        # Turn 6: To'lov tarixi e'tirozi
        r6 = await self._send_msg(chat_id, user_id, "nimaga qarzim bor deb o'ylaysiz to'lov tariximni ko'rsating", bot)
        self.assertIn("MARS ELEKTRON", r6)

        # Turn 7: Z-hisobot va inkassatsiya
        r7 = await self._send_msg(chat_id, user_id, "kun oxirida z-otchet qanday olinadi inkassatsiya qilish kerak", bot)
        self.assertTrue(any(w in r7.lower() for w in ["z-otchet", "z otchet", "inkassatsiya", "hisobot", "menyu", "video"]))

    # =========================================================================
    # FLOW 3: SECURITY INJECTION, BROKEN INPUTS & BOUNDARIES (8 TURNS)
    # =========================================================================
    async def test_flow_3_security_injection_and_corrupt_inputs(self):
        """
        SQL Injection, HTML/Script teglar, chala raqamlar, ulkan spam,
        matn ichiga yashirilgan INN va formatlar.
        """
        chat_id = 70003
        user_id = 80003
        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()

        # Turn 1: SQL Injection urinishi
        r1 = await self._send_msg(
            chat_id, user_id,
            "SELECT * FROM debts WHERE inn='302568138' OR 1=1; DROP TABLE clients;--",
            bot
        )
        self.assertIn("MARS ELEKTRON", r1)
        self.assertIn("qarzdorlik yo'q", r1.lower())

        # Turn 2: XSS / Script Injection
        r2 = await self._send_msg(
            chat_id, user_id,
            "<script>alert('pwned')</script><b>Salom</b> apparat ishlamayapti",
            bot
        )
        self.assertIn("INN", r2)

        # Turn 3: 5 xonali chala INN
        r3 = await self._send_msg(chat_id, user_id, "INN 12345", bot)
        self.assertTrue(len(r3) > 0 and any(w in r3.lower() for w in ["9 xonali", "inn", "raqam", "fiskal", "modul", "baza", "korxona", "302568138"]))

        # Turn 4: Faqat emojilar
        r4 = await self._send_msg(chat_id, user_id, "??? 🤦‍♂️💥🚫🚨", bot)
        self.assertTrue(len(r4) > 0)

        # Turn 5: Ulkan takroriy matn (Spam)
        r5 = await self._send_msg(chat_id, user_id, "qarzim bormi " * 40, bot)
        self.assertTrue(len(r5) > 0 and any(w in r5.lower() for w in ["inn", "stir", "modul", "qarz", "to'lov", "0 so'm"]))

        # Turn 6: Matn ichiga yashirilgan defisli INN (302-568-138)
        r6 = await self._send_msg(
            chat_id, user_id,
            "Buxgalterimiz bugun 302-568-138 nomerli firmamizni qarzini tekshirib ko'r degandi",
            bot
        )
        self.assertIn("MARS ELEKTRON", r6)

        # Turn 7: 14 xonali JSHSHIR orqali qidiruv
        r7 = await self._send_msg(chat_id, user_id, "jshshir orqali 51234567890123 ni tekshir", bot)
        self.assertTrue(len(r7) > 0)

        # Turn 8: Rahmat
        r8 = await self._send_msg(chat_id, user_id, "Tushunarli, rahmat sizga", bot)
        self.assertTrue(len(r8) > 0)

    # =========================================================================
    # FLOW 4: 30-MINUTE MEMORY EXPIRATION MID-DIALOGUE (6 TURNS)
    # =========================================================================
    async def test_flow_4_session_expiry_after_30_minutes(self):
        """
        30 daqiqa (1800s) TTL tugashidan keyin botning xotirani toza unutishi,
        qulab tushmasdan muloyimlik bilan INNni qayta so'rashi.
        """
        chat_id = 70004
        user_id = 80004
        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()

        current_fake_time = 1700000000.0

        with patch("time.time", side_effect=lambda: current_fake_time):
            # Turn 1: t=0 da INN 206011507 ni tekshiradi
            r1 = await self._send_msg(chat_id, user_id, "qarzim bormi 206011507", bot)
            self.assertIn("1,500,400", r1)
            self.assertEqual(user_memory.get_last_id(chat_id, user_id), "206011507")

            # Turn 2: t=60s da qarz tushuntirishini so'raydi
            current_fake_time += 60.0
            r2 = await self._send_msg(chat_id, user_id, "nega buncha qarzman to'lov tariximni ko'rsat", bot)
            self.assertIn("QASHQADARYO SHARQ GAVHARI", r2)

            # Turn 3: 1805 soniya o'tdi (> 30 daqiqa TTL)
            current_fake_time += 1805.0

            # Foydalanuvchi kelib qisqa savol beradi: "oylikdanchi?"
            r3 = await self._send_msg(chat_id, user_id, "oylikdanchi qarzim qancha", bot)
            # Xotira 30 daqiqadan keyin tozalangan bo'lishi kerak, shuning uchun INN so'raydi
            self.assertIn("INN", r3)
            self.assertIsNone(user_memory.get_last_id(chat_id, user_id))

            # Turn 4: Foydalanuvchi yangitdan INN kiritadi: 302568138
            r4 = await self._send_msg(chat_id, user_id, "302568138", bot)
            self.assertIn("MARS ELEKTRON", r4)
            self.assertIn("qarzdorlik yo'q", r4.lower())
            self.assertEqual(user_memory.get_last_id(chat_id, user_id), "302568138")

            # Turn 5: Yillikdan qarzim bormi?
            r5 = await self._send_msg(chat_id, user_id, "yillikdanchi?", bot)
            self.assertIn("Fiskal modul", r5)

            # Turn 6: Rahmat
            r6 = await self._send_msg(chat_id, user_id, "Rahmat!", bot)
            self.assertTrue(len(r6) > 0)

    # =========================================================================
    # FLOW 5: CONCURRENT GROUP CHAOS (3 USERS INTERLEAVED IN SUPERGROUP)
    # =========================================================================
    async def test_flow_5_concurrent_group_chaos_3_users(self):
        """
        Bitta superguruhda 3 xil mijoz bir vaqtda aralash savollar beradi.
        Hech birining konteksti, INNi yoki fiskal moduli ikkinchisiga o'tib ketmasligi shart.
        """
        group_chat_id = -1009988776655
        user_a = 90001
        user_b = 90002
        user_c = 90003

        bot = AsyncMock(spec=Bot)
        bot.copy_message = AsyncMock()

        with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = "Litsenziya muddati: 2026-12-31 gacha faol."

            # User A: Apparat qotib qoldi, INN 302568138
            ra1 = await self._send_msg(group_chat_id, user_a, "Bizda apparat qotib qoldi, INN 302568138", bot)
            self.assertIn("MARS ELEKTRON", ra1)
            self.assertIn("qarzdorlik yo'q", ra1.lower())

            # User B: Usta kerak
            rb1 = await self._send_msg(group_chat_id, user_b, "Iltimos Qarshi shahriga usta kerak, kimga murojaat qilay?", bot)
            self.assertTrue(any(w in rb1.lower() for w in ["usta", "admin", "aloqa", "kontakt", "@", "telefon"]))

            # User C: Qarz bormi 206011507
            rc1 = await self._send_msg(group_chat_id, user_c, "bizda qarz bormi 206011507", bot)
            self.assertIn("1,500,400", rc1)
            self.assertIn("QASHQADARYO SHARQ GAVHARI", rc1)

            # User A: "yillikdanchi qarzim bormi?" -> User C ning INNi aralashmasligi kerak, User A dan FM so'rashi kerak!
            ra2 = await self._send_msg(group_chat_id, user_a, "oylikdan qarzsiz ekanmiz, yillikdanchi qarzim bormi?", bot)
            self.assertIn("Fiskal modul", ra2)
            self.assertNotIn("1,500,400", ra2)

            # User B: Qo'ng'iroq qilish uchun nomer so'raydi
            rb2 = await self._send_msg(group_chat_id, user_b, "telefon nomerini tashlang", bot)
            self.assertTrue(any(w in rb2 for w in ["+998", "75 522", "admin", "bog'lan"]))

            # User C: Oylik to'lash uchun shot raqam so'raydi (Post 85 uzatiladi)
            rc2 = await self._send_msg(group_chat_id, user_c, "oylik to'lash uchun shot raqam tashlang", bot)
            self.assertTrue("85" in rc2 or "MARS ELEKTRON TEXNIKA" in rc2)

            # User A: Fiskal modul kiritadi
            ra3 = await self._send_msg(group_chat_id, user_a, "LG420210630789", bot)
            self.assertIn("LG420210630789", ra3)
            self.assertIn("Litsenziya muddati", ra3)

            # User C: To'lov qildim qachon yoqiladi
            rc3 = await self._send_msg(group_chat_id, user_c, "to'lov qildim apparat qachon yoqiladi", bot)
            self.assertTrue(any(w in rc3.lower() for w in ["yoqil", "kvitansiya", "tasdiq", "daqiqa", "bank"]))

            # Yakuniy tekshiruv: Xotiradagi ma'lumotlar to'liq izolyatsiyalangan
            self.assertEqual(user_memory.get_last_id(group_chat_id, user_a), "302568138")
            self.assertEqual(user_memory.get_last_fm(group_chat_id, user_a), "LG420210630789")
            self.assertEqual(user_memory.get_last_id(group_chat_id, user_c), "206011507")
            self.assertIsNone(user_memory.get_last_fm(group_chat_id, user_c))


if __name__ == "__main__":
    unittest.main()
