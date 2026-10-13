"""
test_adversarial_break_attempt.py
=================================
Haqiqiy mijoz rolida botni "buzishga" va chalg'itishga urinuvchi 10 bosqichli
keskin (adversarial) stress-test:
1. Turn 1: Noaniq asabiy e'tiroz ("apparat yana o'chib qoldi, ishlamayapti")
2. Turn 2: Xato/chala INN (6 xonali: "123456 tekshir")
3. Turn 3: Probellar bilan aralash haqiqiy INN ("311 481 235 inn bu") -> P3 Humo sariq model aniqlanishi
4. Turn 4: To'qima apparat haqida savol ("Pax A930 apparat bor dediku...") -> Hallucination yo'qligi
5. Turn 5: Kichik harfda kiritilgan fiskal modul ("fm lg420210008888") -> OFD tekshiruvi
6. Turn 6: Bot bilmaydigan tashqi xizmat ("elektron tarozi va skaner narxi qancha") -> Adminga eskalatsiya
7. Turn 7: To'lov rekviziti va video so'rovi ("Click raqam va hisob raqamni tashla") -> Rekvizitlar
8. Turn 8: Chek yubormasdan turib da'vo qilish ("To'ladim mana 200 ming tushdimi?") -> Kontekst tahlili
9. Turn 9: Kirill alifbosida asabiy so'rov ("Нега ёқилмади ҳали ҳам, қачон ёқасизлар?") -> Kirillda javob
10. Turn 10: Usta talab qilish va janjal ("Bo'ldi usta chaqir, telefon nomeringni ber") -> Eskalatsiya
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.chat import handle_user_chat
from user_memory import user_memory
from excel_manager import excel_manager
from admin_manager import admin_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
logger = logging.getLogger("adversarial_test")

class MockUser:
    def __init__(self, user_id: int, first_name: str, username: str = ""):
        self.id = user_id
        self.first_name = first_name
        self.full_name = first_name
        self.username = username

class MockChat:
    def __init__(self, chat_id: int, chat_type: str = "private"):
        self.id = chat_id
        self.type = chat_type

class MockMessage:
    def __init__(self, message_id: int, user: MockUser, chat: MockChat, text: str = ""):
        self.message_id = message_id
        self.from_user = user
        self.chat = chat
        self.text = text
        self.replies = []

    async def reply(self, text: str, parse_mode: str = "HTML", **kwargs):
        self.replies.append(text)
        return self

    async def answer(self, text: str, parse_mode: str = "HTML", **kwargs):
        self.replies.append(text)
        return self

async def run_adversarial_test():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.copy_message = AsyncMock()

    user = MockUser(778899, "Shavkat aka", "shavkat_savdo")
    chat = MockChat(-100998877)
    chat_id = chat.id
    user_id = user.id

    # Sessiyani tozalash
    user_memory.clear_context(chat_id, user_id)

    print("\n" + "="*70)
    print("🔥 BOTNI BUZISHGA VA CHALG'ITISHGA URINUVCHI 10 BOSQICHLI ADVERSARIAL TEST")
    print("="*70 + "\n")

    # -------------------------------------------------------------------------
    # TURN 1: Noaniq asabiy e'tiroz (INN va FM so'ralishi shart)
    # -------------------------------------------------------------------------
    t1_text = "Uff apparat yana o'chib qoldi, hech narsa ishlamayapti, bu qanaqa xizmat?!"
    print(f"👤 MIJOZ (Turn 1): {t1_text}")
    msg1 = MockMessage(1, user, chat, t1_text)
    await handle_user_chat(msg1, bot)
    r1 = msg1.replies[-1]
    print(f"🤖 BOT:\n{r1}\n" + "-"*70)
    assert any(w in r1.lower() for w in ["inn", "стир"]), "Turn 1 da INN so'ralmadi!"
    assert any(w in r1.lower() for w in ["fiskal", "lg", "yg"]), "Turn 1 da Fiskal modul so'ralmadi!"

    # -------------------------------------------------------------------------
    # TURN 2: Chala / xato INN (6 xonali son, dastur buzilmasligi kerak)
    # -------------------------------------------------------------------------
    t2_text = "INN raqamim 123456 mana tekshir tezroq"
    print(f"👤 MIJOZ (Turn 2): {t2_text}")
    msg2 = MockMessage(2, user, chat, t2_text)
    await handle_user_chat(msg2, bot)
    r2 = msg2.replies[-1]
    print(f"🤖 BOT:\n{r2}\n" + "-"*70)
    # 6 xonali son haqiqiy INN emas, shuning uchun bazadan qarz tekshiruvi xato bermay,
    # foydalanuvchiga 9 xonali INN so'rashi yoki tushuntirishi kerak.
    assert "Traceback" not in r2 and "xatolik yuz berdi" not in r2.lower()

    # -------------------------------------------------------------------------
    # TURN 3: Probellar bilan aralash haqiqiy INN ("311 481 235" - Jaloliddin Panjiyev XK, P3 Humo)
    # -------------------------------------------------------------------------
    t3_text = "Ey qara 311 481 235 inn bu, qarzim bormi o'zi?"
    print(f"👤 MIJOZ (Turn 3): {t3_text}")
    msg3 = MockMessage(3, user, chat, t3_text)
    await handle_user_chat(msg3, bot)
    r3 = msg3.replies[-1]
    print(f"🤖 BOT:\n{r3}\n" + "-"*70)
    assert "JALOLIDDIN PANJIYEV" in r3, "Korxona nomi topilmadi!"
    assert "P3 Humo" in r3, "Exceldagi sariq rang (P3 Humo) aniqlanmadi!"
    assert user_memory.get_last_id(chat_id, user_id) == "311481235", "INN xotirada saqlanmadi!"

    # -------------------------------------------------------------------------
    # TURN 4: To'qima apparat modeli bo'yicha chalg'itish (Pax A930) -> Anti-hallucination
    # -------------------------------------------------------------------------
    t4_text = "Menda Pax A930 apparat bor dediku boshqa usta, sizlar Pax apparatiga ham qaraysizlarmi?"
    print(f"👤 MIJOZ (Turn 4): {t4_text}")
    msg4 = MockMessage(4, user, chat, t4_text)
    await handle_user_chat(msg4, bot)
    r4 = msg4.replies[-1]
    print(f"🤖 BOT:\n{r4}\n" + "-"*70)
    # AI mutlaqo Pax apparatiga qaraymiz deb aldamasligi, faqat P3 Humo va Smart One ga xizmat ko'rsatishini aytishi shart!
    assert "pax a930 ga qaraymiz" not in r4.lower()
    assert any(m in r4 for m in ["P3 Humo", "Smart One", "faqat"]), "To'g'ri model cheklovi aytilmadi!"

    # -------------------------------------------------------------------------
    # TURN 5: Kichik harfda kiritilgan fiskal modul ("fm lg420210008888") -> OFD tekshiruvi
    # -------------------------------------------------------------------------
    t5_text = "Mayli fiskal modulim mana: lg420210008888, qachongacha ekan litsenziyasi?"
    print(f"👤 MIJOZ (Turn 5): {t5_text}")
    msg5 = MockMessage(5, user, chat, t5_text)
    await handle_user_chat(msg5, bot)
    r5 = msg5.replies[-1]
    print(f"🤖 BOT:\n{r5}\n" + "-"*70)
    assert any(w in r5.lower() for w in ["ofd", "soliq", "yangi texnologiyalar", "fiskal"]), "Fiskal modul tekshirilmadi!"

    # -------------------------------------------------------------------------
    # TURN 6: Bot bilmaydigan / bazada yo'q tashqi savol -> Adminga eskalatsiya
    # -------------------------------------------------------------------------
    t6_text = "Bizga kassa uchun shtrix-kod skaner va elektron tarozi ham yetkazib berasizlarmi, narxi qancha?"
    print(f"👤 MIJOZ (Turn 6): {t6_text}")
    msg6 = MockMessage(6, user, chat, t6_text)
    with patch("admin_manager.admin_manager.notify_user_query_escalation", new_callable=AsyncMock) as mock_admin_alert:
        await handle_user_chat(msg6, bot)
        r6 = msg6.replies[-1]
        print(f"🤖 BOT:\n{r6}\n" + "-"*70)
        # Bot bilmagan narsasiga narx to'qimasligi, mutaxassisga yo'naltirilganini bildirishi kerak
        assert any(w in r6.lower() for w in ["aniq ma'lumot yo'q", "mutaxassis", "yubordim", "bog'lan"]), "AI yolg'on to'qidi yoki eskalatsiya qilmadi!"
        print(f"📢 Adminga xabar ketishi holati: {mock_admin_alert.called}")

    # -------------------------------------------------------------------------
    # TURN 7: To'lov qilish niyati va rekvizitlar so'rovi
    # -------------------------------------------------------------------------
    t7_text = "Mayli to'layman, Click raqam va hisob raqamni tashla"
    print(f"👤 MIJOZ (Turn 7): {t7_text}")
    msg7 = MockMessage(7, user, chat, t7_text)
    await handle_user_chat(msg7, bot)
    r7 = msg7.replies[-1]
    print(f"🤖 BOT:\n{r7}\n" + "-"*70)
    assert "MARS ELEKTRON TEXNIKA" in r7, "Mars MCHJ nomi chiqmadi!"
    assert "Yangi Texnologiyalar" in r7, "Yangi Texnologiyalar nomi chiqmadi!"
    assert bot.copy_message.called, "Postlar kanaldan uzatilmadi!"

    # -------------------------------------------------------------------------
    # TURN 8: Chek yubormasdan turib da'vo qilish ("To'ladim mana 200 ming tushdimi?")
    # -------------------------------------------------------------------------
    t8_text = "To'ladim mana 200 ming tushdimi chek?"
    print(f"👤 MIJOZ (Turn 8): {t8_text}")
    msg8 = MockMessage(8, user, chat, t8_text)
    await handle_user_chat(msg8, bot)
    r8 = msg8.replies[-1]
    print(f"🤖 BOT:\n{r8}\n" + "-"*70)
    # Chek yuborilmaganligi sababli bot kvitansiya rasmini yoki PDF faylini tashlashni so'rashi kerak
    assert any(w in r8.lower() for w in ["kvitansiya", "chek", "rasm", "to'lov"]), "Kvitansiya tekshiruvi konteksti buzuldi!"

    # -------------------------------------------------------------------------
    # TURN 9: Kirill alifbosida asabiy so'rov ("Нега ёқилмади ҳали ҳам, қачон ёқасизлар?")
    # -------------------------------------------------------------------------
    t9_text = "Нега ёқилмади ҳали ҳам, қачон ёқасизлар аппратни?!"
    print(f"👤 MIJOZ (Turn 9): {t9_text}")
    msg9 = MockMessage(9, user, chat, t9_text)
    await handle_user_chat(msg9, bot)
    r9 = msg9.replies[-1]
    print(f"🤖 BOT:\n{r9}\n" + "-"*70)
    # Kirill alifbosiga kirill alifbosida javob qaytarilishi kerak
    cyrillic_chars = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяўқғҳ")
    has_cyrillic = any(c in cyrillic_chars for c in r9.lower())
    assert has_cyrillic, f"Kirill alifbosida javob qaytmadi: {r9}"

    # -------------------------------------------------------------------------
    # TURN 10: Usta talab qilish va janjal ("Bo'ldi usta chaqir, telefon nomeringni ber")
    # -------------------------------------------------------------------------
    t10_text = "Bo'ldi asabim tugadi, hoziroq usta chaqirib beringlar yoki telefon raqamingizni bering!"
    print(f"👤 MIJOZ (Turn 10): {t10_text}")
    msg10 = MockMessage(10, user, chat, t10_text)
    with patch("admin_manager.admin_manager.notify_user_query_escalation", new_callable=AsyncMock) as mock_tech_call:
        await handle_user_chat(msg10, bot)
        r10 = msg10.replies[-1]
        print(f"🤖 BOT:\n{r10}\n" + "-"*70)
        assert mock_tech_call.called, "Texniklarga eskalatsiya xabarnomasi yuborilmadi!"
        assert any(num in r10 for num in ["+998", "@quvonchbek_admin", "@Yashnarbek_butaev"]), "Mas'ul xodimlar kontaktlari berilmadi!"

    print("\n" + "="*70)
    print("🎉 BARCHA 10 TA ADVERSARIAL STRESS TURN-LARI 100% MUVAFFAQIYATLI O'TDI!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(run_adversarial_test())
