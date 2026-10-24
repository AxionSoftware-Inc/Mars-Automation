import unittest
from unittest.mock import AsyncMock, MagicMock
from aiogram import types
from user_memory import user_memory
from admin_manager import admin_manager


def create_mock_user(user_id: int = 123456, full_name: str = "Ali Valiyev", username: str = "ali_valiyev"):
    user = MagicMock(spec=types.User)
    user.id = user_id
    user.full_name = full_name
    user.first_name = full_name.split()[0]
    user.username = username
    return user


class TestAdminEscalationEnrichment(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        user_memory.sessions.clear()
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()
        self.bot.send_photo = AsyncMock()
        self.bot.send_document = AsyncMock()
        self.orig_notify_admins = admin_manager.notify_admins

    def tearDown(self):
        admin_manager.notify_admins = self.orig_notify_admins

    async def test_escalation_card_contains_all_required_sections(self):
        """
        Adminga yuboriladigan eskalatsiya xabarida quyidagilar bo'lishi shart:
        1. Mijoz bilan suhbat qisqacha mazmuni
        2. Aniqlangan ma'lumotlar
        3. Qarzdorligi
        4. Aniqlanmagan ma'lumotlar
        5. Mijoz username va tg:// havolasi
        6. Bir nechta rasm yuborilgan bo'lsa barchasini uzatish
        """
        chat_id = -100999888
        user_id = 777888
        user = create_mock_user(user_id=user_id, full_name="Botir Zokirov", username="botir_z")

        # 1. Suhbat tarixi
        user_memory.add_user_message(chat_id, user_id, "Salom, apparat ishlamay qoldi")
        user_memory.add_assistant_message(chat_id, user_id, "INN raqamingizni yuboring")
        user_memory.add_user_message(chat_id, user_id, "302568138")
        user_memory.add_assistant_message(chat_id, user_id, "Oylik to'lov joyida, kassa chekidan Fiskal modulni yuboring")

        # 2. Aniqlangan ma'lumotlar
        user_memory.set_last_id(chat_id, user_id, "302568138", org_name="MARS ELEKTRON TEXNIKA", debt=0.0)
        user_memory.set_last_fm(chat_id, user_id, "LG420210630789")

        # 3. Foydalanuvchi 2 ta rasm tashlagan
        user_memory.add_photo(chat_id, user_id, "photo_file_id_1")
        user_memory.add_photo(chat_id, user_id, "photo_file_id_2")

        # Eskalatsiya yuborish
        await admin_manager.notify_user_query_escalation(
            bot=self.bot,
            user=user,
            chat_id=chat_id,
            query_text="Usta bormi tezroq bog'lansin iltimos",
            reason="Mijoz mutaxassis bilan bog'lanishni so'radi",
            inn="302568138",
            org_name="MARS ELEKTRON TEXNIKA",
            photo_file_id="photo_file_id_2"
        )

        # send_photo kamida 2 marta chaqirilgan bo'lishi kerak (har ikkala rasm uzatiladi!)
        self.assertGreaterEqual(self.bot.send_photo.call_count, 2)

        # 1-rasm caption tekshiruvi
        first_call = self.bot.send_photo.call_args_list[0]
        caption = first_call[1].get("caption") or ""
        self.assertIn("botir_z", caption)

        # 2-rasm uzatilganini tekshirish
        second_call = self.bot.send_photo.call_args_list[1]
        self.assertEqual(second_call[1].get("photo"), "photo_file_id_2")
        self.assertIn("qo'shimcha", second_call[1].get("caption", "").lower())

        # Matn strukturasini to'liq tekshirish
        card_text, short_caption, eff_inn, tuman, all_photos, admin_kb = admin_manager._build_escalation_card(
            title="🔔 <b>YANGI HUDUDIY ESKALATSIYA!</b>",
            reason="Mijoz mutaxassis bilan bog'lanishni so'radi",
            user=user,
            chat_id=chat_id,
            inn="302568138",
            org_name="MARS ELEKTRON TEXNIKA",
            query_text="Usta bormi tezroq bog'lansin iltimos"
        )

        # 1. Mijoz bilan suhbat qisqacha mazmuni
        self.assertIn("Suhbat mazmuni", card_text)
        self.assertIn("Salom, apparat ishlamay qoldi", card_text)

        # 2. Aniqlangan ma'lumotlar
        self.assertIn("Aniqlangan ma'lumotlar", card_text)
        self.assertIn("302568138", card_text)
        self.assertIn("LG420210630789", card_text)

        # 3. Qarzdorligi
        self.assertIn("Qarzdorlik holati", card_text)
        self.assertIn("0 so'm", card_text)

        # 4. Aniqlanmagan ma'lumotlar
        self.assertIn("Aniqlanmagan ma'lumotlar", card_text)

        # 5. Mijoz akkaunt havolasi
        self.assertIn("tg://user?id=777888", card_text)
        self.assertIn("@botir_z", card_text)

    async def test_escalation_when_inn_not_provided_shows_missing_alert(self):
        """Agar INN kiritilmagan bo'lsa, 'Aniqlanmagan ma'lumotlar' bo'limida INN yo'qligi aniq ko'rsatiladi."""
        chat_id = -100999888
        user_id = 555444
        user = create_mock_user(user_id=user_id, full_name="Noma'lum Mijoz", username=None)

        card_text, short_caption, eff_inn, tuman, all_photos, admin_kb = admin_manager._build_escalation_card(
            title="🔔 <b>YANGI HUDUDIY ESKALATSIYA!</b>",
            reason="Mijoz operator so'radi",
            user=user,
            chat_id=chat_id,
            query_text="Operatorga ulang"
        )

        self.assertIn("Aniqlanmagan ma'lumotlar", card_text)
        self.assertIn("STIR (INN) kiritilmagan", card_text)
        self.assertIn("Fiskal moduli", card_text)
        self.assertIn("tg://user?id=555444", card_text)


if __name__ == "__main__":
    unittest.main()
