import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from translit_manager import (
    detect_script,
    latin_to_cyrillic,
    cyrillic_to_latin,
    adapt_to_user_script
)
from user_memory import UserMemoryManager
from payment_accounts import (
    classify_payment_intent,
    MARS_POST_ID,
    MARS_VIDEO_ID,
    YANGI_TEXNOLOGIYALAR_POST_ID,
    YANGI_TEXNOLOGIYALAR_VIDEO_ID,
    get_monthly_post_note,
    get_annual_post_note,
    get_both_posts_intro
)


class TestScriptAndChannelAccounts(unittest.IsolatedAsyncioTestCase):

    def test_01_script_detection(self):
        """1. Lotin va Kirill yozuvini aniqlash aniqligi"""
        self.assertEqual(detect_script("Salom, qarzim bormi?"), "latin")
        self.assertEqual(detect_script("Салом, қарзим борми?"), "cyrillic")
        self.assertEqual(detect_script("Аппарат нега ишламаяпти?"), "cyrillic")
        self.assertEqual(detect_script("Apparat nega ishlamayapti?"), "latin")
        self.assertEqual(detect_script("Квитанцияни қачон тасдиқлайсиз?"), "cyrillic")
        self.assertEqual(detect_script("Йиллик шотни беринг"), "cyrillic")
        self.assertEqual(detect_script("Yillik shotni bering"), "latin")
        # Raqamlar va havolalar
        self.assertEqual(detect_script("302568138"), "unknown")
        self.assertEqual(detect_script("https://tasnif.soliq.uz"), "unknown")

    def test_02_transliteration_preservation(self):
        """2. Transliteratsiyada HTML, @, raqamlar va brendlar buzilmasligi"""
        orig_lat = (
            "<b>DIQQAT:</b> Korxona <code>302568138</code> hisobiga 100 000 so'm to'lov qiling. "
            "Click dasturi orqali Pax A930 apparatiga to'lang. Murojaat: @Yashnarbek_butaev"
        )
        cyr = latin_to_cyrillic(orig_lat)
        self.assertIn("<b>", cyr)
        self.assertIn("</b>", cyr)
        self.assertIn("<code>302568138</code>", cyr)
        self.assertIn("Click", cyr)
        self.assertIn("Pax A930", cyr)
        self.assertIn("@Yashnarbek_butaev", cyr)
        self.assertEqual(detect_script(cyr), "cyrillic")

        # Orqaga qaytarish
        back_lat = cyrillic_to_latin(cyr)
        self.assertIn("<code>302568138</code>", back_lat)
        self.assertIn("<b>", back_lat)
        self.assertIn("@Yashnarbek_butaev", back_lat)
        self.assertEqual(detect_script(back_lat), "latin")

    def test_03_adapt_to_user_script(self):
        """3. adapt_to_user_script funksiyasi kutilgan alifboda qaytarishi"""
        text_lat = "Hurmatli mijoz, sizning qarzingiz 100 000 so'm."
        text_cyr = "Ҳурматли мижоз, сизнинг қарзингиз 100 000 сўм."

        self.assertEqual(detect_script(adapt_to_user_script(text_lat, "cyrillic")), "cyrillic")
        self.assertEqual(detect_script(adapt_to_user_script(text_cyr, "latin")), "latin")
        # O'zgarmasdan qolishi
        self.assertEqual(adapt_to_user_script(text_lat, "latin"), text_lat)
        self.assertEqual(adapt_to_user_script(text_cyr, "cyrillic"), text_cyr)

    def test_04_user_memory_script_persistence_and_concurrency(self):
        """4. Foydalanuvchi xotirasida alifboni eslab qolish va parallel userlarda chalkashmaslik"""
        mem = UserMemoryManager()
        user_cyr = (1001, 2001)
        user_lat = (1002, 2002)

        # 1-user kirillcha yozadi
        mem.add_user_message(user_cyr[0], user_cyr[1], "Салом, қарзимни кўриб беринг")
        # 2-user lotincha yozadi
        mem.add_user_message(user_lat[0], user_lat[1], "Salom, qarzimni ko'rib bering")

        self.assertEqual(mem.get_preferred_script(user_cyr[0], user_cyr[1]), "cyrillic")
        self.assertEqual(mem.get_preferred_script(user_lat[0], user_lat[1]), "latin")

        # Keyingi xabarda 1-user faqat INN yuboradi ("302568138")
        sc = mem.detect_and_update_script(user_cyr[0], user_cyr[1], "302568138")
        self.assertEqual(sc, "cyrillic", "Faqat raqam yuborilganda oldingi kirill alifbosi saqlanishi kerak")

        # 2-user ham faqat INN yuboradi
        sc2 = mem.detect_and_update_script(user_lat[0], user_lat[1], "302568138")
        self.assertEqual(sc2, "latin", "Faqat raqam yuborilganda oldingi lotin alifbosi saqlanishi kerak")

    def test_05_payment_intent_cyrillic_and_latin(self):
        """5. To'lov niyatini (monthly, annual, both) Lotin va Kirillda aniqlash"""
        # Yillik
        self.assertEqual(classify_payment_intent("yillik shot raqami"), "annual")
        self.assertEqual(classify_payment_intent("йиллик шот рақами"), "annual")
        self.assertEqual(classify_payment_intent("fiskal modul shot"), "annual")
        self.assertEqual(classify_payment_intent("фискал модул тўлови"), "annual")
        self.assertEqual(classify_payment_intent("янги технологиялар реквизити"), "annual")

        # Oylik
        self.assertEqual(classify_payment_intent("oylik shot raqami"), "monthly")
        self.assertEqual(classify_payment_intent("ойлик шот рақами"), "monthly")
        self.assertEqual(classify_payment_intent("abonent to'lov hisobi"), "monthly")
        self.assertEqual(classify_payment_intent("абонент тўлов ҳисоби"), "monthly")
        self.assertEqual(classify_payment_intent("марс шот"), "monthly")

        # Both / Umumiy
        self.assertEqual(classify_payment_intent("shot raqamlar kerak"), "both")
        self.assertEqual(classify_payment_intent("шот рақамлар керак"), "both")
        self.assertEqual(classify_payment_intent("qayerga to'layman"), "both")
        self.assertEqual(classify_payment_intent("қаерга тўлайман"), "both")
        self.assertEqual(classify_payment_intent("rekvizitlarni bering"), "both")
        self.assertEqual(classify_payment_intent("реквизитларни беринг"), "both")

    async def test_06_channel_post_forwarding_monthly(self):
        """6. Oylik shot so'ralganda 85-post, eslatma va 148-video uzatilishi"""
        from handlers.chat import handle_user_chat
        bot = AsyncMock()
        message = MagicMock()
        message.text = "oylik shot raqamini bering"
        message.from_user.id = 991
        message.chat.id = 991
        message.message_id = 555
        message.reply = AsyncMock()
        message.answer = AsyncMock()

        await handle_user_chat(message, bot)

        # bot.copy_message chaqiruvlari tekshiriladi
        copy_calls = bot.copy_message.call_args_list
        # Birinchi copy_message: Post 85 (Oylik matn posti)
        # Ikkinchi copy_message: Video 148 (Click videosi)
        copied_ids = [c.kwargs.get("message_id") for c in copy_calls]
        self.assertIn(MARS_POST_ID, copied_ids, f"Post {MARS_POST_ID} nusxalanishi shart!")
        self.assertIn(MARS_VIDEO_ID, copied_ids, f"Video {MARS_VIDEO_ID} uzatilishi shart!")

    async def test_07_channel_post_forwarding_annual_cyrillic(self):
        """7. Yillik shot Kirillcha so'ralganda 34-post va 145-video uzatilishi"""
        from handlers.chat import handle_user_chat
        bot = AsyncMock()
        message = MagicMock()
        message.text = "йиллик шот рақамни ташланг"
        message.from_user.id = 992
        message.chat.id = 992
        message.message_id = 777
        message.reply = AsyncMock()
        message.answer = AsyncMock()

        await handle_user_chat(message, bot)

        copy_calls = bot.copy_message.call_args_list
        copied_ids = [c.kwargs.get("message_id") for c in copy_calls]
        self.assertIn(YANGI_TEXNOLOGIYALAR_POST_ID, copied_ids, f"Post {YANGI_TEXNOLOGIYALAR_POST_ID} nusxalanishi shart!")
        self.assertIn(YANGI_TEXNOLOGIYALAR_VIDEO_ID, copied_ids, f"Video {YANGI_TEXNOLOGIYALAR_VIDEO_ID} uzatilishi shart!")

    async def test_08_channel_post_forwarding_both_posts(self):
        """8. Umumiy rekvizit so'ralganda ikkala post (85 va 34) ketma-ket uzatilishi"""
        from handlers.chat import handle_user_chat
        bot = AsyncMock()
        message = MagicMock()
        message.text = "реквизитларни беринг қаерга тўлайман"
        message.from_user.id = 993
        message.chat.id = 993
        message.message_id = 888
        message.reply = AsyncMock()
        message.answer = AsyncMock()

        await handle_user_chat(message, bot)

        copy_calls = bot.copy_message.call_args_list
        copied_ids = [c.kwargs.get("message_id") for c in copy_calls]
        self.assertIn(MARS_POST_ID, copied_ids, "Post 85 nusxalanishi shart")
        self.assertIn(YANGI_TEXNOLOGIYALAR_POST_ID, copied_ids, "Post 34 nusxalanishi shart")

    async def test_09_mxik_guidance_cyrillic(self):
        """9. Kirillcha yozilgan MXIK savoliga Kirillcha javob qaytishi"""
        from handlers.chat import handle_user_chat
        bot = AsyncMock()
        message = MagicMock()
        message.text = "МХИК кодни тасниф сайтидан қандай қидираман?"
        message.from_user.id = 994
        message.chat.id = 994
        message.message_id = 111
        message.reply = AsyncMock()
        message.answer = AsyncMock()

        await handle_user_chat(message, bot)

        self.assertTrue(message.reply.called)
        reply_arg = message.reply.call_args[0][0]
        self.assertEqual(detect_script(reply_arg), "cyrillic", "MXIK javobi Kirill alifbosida bo'lishi shart!")
        self.assertIn("Tasnif.soliq.uz", reply_arg)

        # Video 28 nusxalanishi
        copy_calls = bot.copy_message.call_args_list
        copied_ids = [c.kwargs.get("message_id") for c in copy_calls]
        self.assertIn(28, copied_ids, "Video 28 nusxalanishi shart!")

    async def test_10_debt_response_cyrillic(self):
        """10. Kirillcha so'rov kiritilganda qarz tekshiruvi natijasi Kirillda bo'lishi"""
        from handlers.debt import process_and_send_debt_result
        from user_memory import user_memory
        bot = AsyncMock()
        message = MagicMock()
        message.text = "Қарзимни текшириб беринг: 302568138"
        message.from_user.id = 995
        message.chat.id = 995
        message.message_id = 222
        message.reply = AsyncMock()

        await process_and_send_debt_result(message, bot, "302568138")

        self.assertTrue(message.reply.called)
        resp_text = message.reply.call_args[0][0]
        self.assertEqual(detect_script(resp_text), "cyrillic", "Qarz tekshiruvi Kirill alifbosida bo'lishi shart!")
        self.assertIn("<code>302568138</code>", resp_text)

    async def test_11_commands_cyrillic_adaptation(self):
        """11. /tolov va /help buyruqlari oldingi sessiya alifbosiga moslashishi"""
        from handlers.commands import cmd_help, cmd_start
        from user_memory import user_memory
        user_id = 996
        chat_id = 996
        user_memory.detect_and_update_script(chat_id, user_id, "Салом")

        message = MagicMock()
        message.from_user.id = user_id
        message.chat.id = chat_id
        message.answer = AsyncMock()

        await cmd_help(message)
        help_text = message.answer.call_args[0][0]
        self.assertEqual(detect_script(help_text), "cyrillic")
        self.assertIn("/help", help_text)
        self.assertIn("/tolov", help_text)

    async def test_12_operator_escalation_cyrillic(self):
        """12. Operator talab qilinganda Kirillcha foydalanuvchiga Kirillcha javob qaytishi"""
        from handlers.chat import handle_user_chat
        bot = AsyncMock()
        message = MagicMock()
        message.text = "Оператор билан гаплашмоқчиман уланг"
        message.from_user.id = 997
        message.chat.id = 997
        message.from_user.full_name = "Ali Valiyev"
        message.from_user.username = "alivali"
        message.message_id = 333
        message.reply = AsyncMock()

        await handle_user_chat(message, bot)

        self.assertTrue(message.reply.called)
        reply_arg = message.reply.call_args[0][0]
        self.assertEqual(detect_script(reply_arg), "cyrillic")


if __name__ == "__main__":
    unittest.main()
