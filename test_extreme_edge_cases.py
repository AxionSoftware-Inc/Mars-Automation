"""
test_extreme_edge_cases.py
==========================
Mars Telegram Bot — Ekstremal Edge-Case va Stress-Testlar Majmuasi.

Ushbu test quyidagi barcha realistik, qiyin va chekka holatlarni to'liq tekshiradi:
1. Noto'g'ri/iflos formatdagi INN kiritmalari (probellar, nuqtalar, tire, kirill/lotin prefikslar, 14 xonali JSHSHIR).
2. Guruhlarda uzun xabarlar ichida INN kelganda bot jim qolmasligi va to'g'ri qarzni tekshirishi.
3. Noma'lum mijozlar vs Aniqlangan mijozlar davomiy suhbat konteksti (gallyutsinatsiyasiz, ortiqcha INN so'ramasdan).
4. Kvitansiya bo'yicha ortiqcha to'lov (avans), to'liq to'lov va qisman to'lov hisob-kitoblari.
5. Pending kvitansiya zanjiri: Boshqa userlar guruhda 10 ta xabar yozgandan keyin ham o'z kvitansiyasini yo'qotmaslik va adminga rasm/hujjat fayl ID si bilan uzatish.
6. Ekran nosozliklari: Noma'lum INN bilan "qarzdorlik yo'q" deb yolg'on aytmaslik, fatal xatoliklarda esa adminga darhol uzatish.
7. 10 ta konkurrent foydalanuvchining bitta umumiy guruhdagi murakkab, chalkash va parallel harakatlari.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
from aiogram.enums import ChatType
from aiogram import types

from core.models import (
    DeviceFacts, ReceiptFacts, ActionType, extract_clean_inn
)
from core.engine import core_engine
from excel_manager import excel_manager
from user_memory import user_memory
from admin_manager import admin_manager
from handlers.debt import is_inn_query_message, process_and_send_debt_result, handle_debt_inquiry
from handlers.chat import handle_user_chat
from ai_helper import generate_ai_reply

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("extreme_tests")

class MockUser:
    def __init__(self, user_id: int, first_name: str, username: str = ""):
        self.id = user_id
        self.first_name = first_name
        self.full_name = first_name
        self.username = username

class MockChat:
    def __init__(self, chat_id: int, chat_type: str = ChatType.GROUP):
        self.id = chat_id
        self.type = chat_type

class MockMessage:
    def __init__(self, message_id: int, user: MockUser, chat: MockChat, text: str = "", caption: str = ""):
        self.message_id = message_id
        self.from_user = user
        self.chat = chat
        self.text = text
        self.caption = caption
        self.replies = []

    async def reply(self, text: str, parse_mode: str = "HTML", **kwargs):
        self.replies.append(text)
        return self

def create_mock_bot():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_document = AsyncMock()
    bot.copy_message = AsyncMock()
    return bot


# =========================================================================
# TEST 1: IFLOS VA FORMATLANGAN INN LAR TESTI
# =========================================================================
def test_dirty_and_formatted_inns():
    logger.info(">>> TEST 1: Iflos, formatlangan va probelli INN kiritmalari...")
    
    test_cases = [
        ("206011507", "206011507"),
        ("  206011507  ", "206011507"),
        ("206 011 507", "206011507"),
        ("206-011-507", "206011507"),
        ("206.011.507", "206011507"),
        ("INN: 206011507", "206011507"),
        ("INN: 206 011 507.", "206011507"),
        ("STIR 302568138", "302568138"),
        ("СТИР: 302 568 138", "302568138"),
        ("ИНН 302568138", "302568138"),
        ("JSHSHIR: 51234567890123", "51234567890123"),
        ("ЖШШИР: 51234567890123", "51234567890123"),
        ("ПИНФЛ 51234567890123", "51234567890123"),
        ("Assalomu alaykum bizning INN: 206 011 507 tekshiring", "206011507"),
        ("Mening korxonam STIR 302568138 apparat ishlamay qoldi", "302568138"),
        ("Telefon: +998901234567", None),
        ("Kod 204 xatolik", None),
        ("100 000 so'm to'ladim", None)
    ]

    for raw, expected in test_cases:
        extracted = extract_clean_inn(raw)
        assert extracted == expected, f"Xatolik: '{raw}' uchun kutilgan '{expected}', lekin '{extracted}' chiqdi!"
    
    logger.info("✅ Barcha 18 ta qiyin va iflos INN formatlari 100% to'g'ri ajratildi!")


# =========================================================================
# TEST 2: GURUHLARDA UZUN XABARLAR YO'QOLIB KETMASLIGI TESTI
# =========================================================================
async def test_group_chat_routing_never_swallowed():

    logger.info(">>> TEST 2: Guruhlarda uzun xabar kelganda jim qolmaslik (routing) testi...")
    bot = create_mock_bot()
    chat = MockChat(chat_id=-100999888777, chat_type=ChatType.GROUP)
    user = MockUser(user_id=111, first_name="Rustam")

    # Uzun xabar: 68 belgi
    long_msg_text = "Assalomu alaykum bizning INN 206011507 apparat ishlamayapti nima qilaylik?"
    msg = MockMessage(message_id=1, user=user, chat=chat, text=long_msg_text)

    # 1. Filter tekshiruvi: is_inn_query_message True qaytarishi shart!
    assert is_inn_query_message(msg) is True, "Guruhdagi uzun INN so'rovi filtrdan o'tmadi!"

    # 2. Xabarni ijro qilish: bot javob berishi va javobda korxona va qarz bo'lishi shart!
    await process_and_send_debt_result(msg, bot, "206011507")
    assert len(msg.replies) == 1, "Bot javob qaytarmadi!"
    assert "QASHQADARYO SHARQ GAVHARI" in msg.replies[0]
    assert "1,500,400" in msg.replies[0]
    assert bot.copy_message.called, "Click videosi (148) yuborilmadi!"

    # 3. Guruhdagi tasodifiy boshqa uzun xabar (INN yo'q, boshqa maqsad):
    unrelated_msg = MockMessage(
        message_id=2, user=user, chat=chat,
        text="Biz bugun magazinimizga yangi mahsulotlar oldik va soat 14:00 da ochamiz"
    )
    assert is_inn_query_message(unrelated_msg) is False, "INN bo'lmagan xabar qarz filtriga tushib qoldi!"

    logger.info("✅ Guruhdagi uzun xabarlar yo'qolib ketmasligi va xatosiz yo'naltirilishi tasdiqlandi!")


# =========================================================================
# TEST 3: NOMA'LUM VS TANIQLI MIJOZLAR SUHBAT KONTEKSTI TESTI
# =========================================================================
async def test_unknown_vs_identified_context():
    logger.info(">>> TEST 3: Noma'lum va aniqlangan mijozlar suhbat konteksti testi...")
    chat_id = -100555444333

    # A) NOMA'LUM MIJOZ (INN kiritmagan, kvitansiya bermagan)
    unknown_id = 999901
    user_memory.sessions.pop(f"{chat_id}:{unknown_id}", None)

    summary_unknown = user_memory.get_context_summary(chat_id, unknown_id)
    reply, _ = generate_ai_reply("qachon qo'shiladi?", context_history=summary_unknown)
    assert any(w in reply.lower() for w in ["inn", "jshshir", "qaysi korxona", "raqamini"]), (
        f"Noma'lum mijozga INN so'ralmadi: {reply}"
    )

    # B) TANIQLI MIJOZ (Ali, INN 206011507, 1.5M qarzi bor)
    ali_id = 999902
    user_memory.set_last_id(chat_id, ali_id, "206011507", org_name="QASHQADARYO SHARQ GAVHARI MCHJ", debt=1500400.0)
    user_memory.add_user_message(chat_id, ali_id, "206011507")
    user_memory.add_assistant_message(chat_id, ali_id, "Qarzdorlik 1,500,400 so'm")

    summary_ali = user_memory.get_context_summary(chat_id, ali_id)
    reply_ali, _ = generate_ai_reply("nega apparatim o'chib qolgan?", context_history=summary_ali)
    assert "inn" not in reply_ali.lower() or "so'rang" not in reply_ali.lower(), "Taniqli mijozdan qayta INN so'raldi!"
    assert any(w in reply_ali.lower() for w in ["qarz", "to'lov", "click", "1,500,400", "abonent"]), (
        f"Ali ga qarzi haqida tushuntirilmadi: {reply_ali}"
    )

    logger.info("✅ Noma'lum mijozdan INN so'ralishi, taniqliga esa kontekstdan javob berilishi 100% to'g'ri!")


# =========================================================================
# TEST 4: ORTIQCHA TO'LOV (AVANS) VA QISMAN TO'LOV HISOB-KITOBI TESTI
# =========================================================================
def test_receipt_overpayment_and_partial_payment():
    logger.info(">>> TEST 4: Kvitansiya bo'yicha ortiqcha to'lov (avans) va qisman to'lov testi...")
    chat_id = 888111
    user_id = 777222

    # Case 1: Qarz 1,500,400 so'm. Mijoz 2,000,000 so'm to'ladi (Ortiqcha to'lov 499,600 so'm)
    facts_overpaid = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=2000000.0,
        payer_inn="206011507",
        payment_date="2026-10-10 12:00"
    )

    decision_over = core_engine.process_receipt_facts(facts_overpaid, chat_id, user_id)
    assert decision_over.action == ActionType.RECEIPT_PROCESSED
    assert decision_over.remaining_debt == -499600.0, f"Ortiqcha qoldiq xato: {decision_over.remaining_debt}"
    assert "Ortiqcha to'lov (avans)" in decision_over.reply_text, "Ortiqcha to'lov haqida xabar berilmadi!"
    assert "499,600" in decision_over.reply_text, "Avans summasi ko'rsatilmadi!"

    # Case 2: Qarz 1,500,400 so'm. Mijoz 500,000 so'm to'ladi (Qisman to'lov, qoldiq 1,000,400 so'm)
    facts_partial = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=500000.0,
        payer_inn="206011507",
        payment_date="2026-10-10 12:05"
    )

    decision_part = core_engine.process_receipt_facts(facts_partial, chat_id, user_id)
    assert decision_part.action == ActionType.RECEIPT_PROCESSED
    assert decision_part.remaining_debt == 1000400.0, f"Qisman to'lov qoldig'i xato: {decision_part.remaining_debt}"
    assert "qarz to'liq yopilmadi" in decision_part.reply_text
    assert "1,000,400" in decision_part.reply_text

    logger.info("✅ Kvitansiya bo'yicha avans va qisman to'lov hisob-kitoblari 100% to'g'ri!")


# =========================================================================
# TEST 5: ASINXRON PENDING KVITANSIYA VA ADMIN RASM FORWARD TESTI
# =========================================================================
async def test_pending_receipt_with_interleaved_chat_and_file_id():
    logger.info(">>> TEST 5: Guruhdagi xabarlar orasida pending kvitansiya va rasm ID testi...")
    admin_manager.add_admin(999888777)
    bot = create_mock_bot()
    chat_id = -100444333222
    user_a_id = 555001
    user_b_id = 555002

    # 1-qadam: User A kvitansiya tashladi (INN yo'q, rasm file_id mavjud)

    receipt_no_inn = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=1500400.0,
        payer_inn=None,
        payment_date="2026-10-10 13:00"
    )

    dec_step1 = core_engine.process_receipt_facts(
        receipt_no_inn, chat_id, user_a_id, user_comment="", file_id="receipt_photo_file_999", is_photo=True
    )
    assert "korxonangizning INN" in dec_step1.reply_text, "INN so'ralmadi!"
    assert user_memory.get_pending_receipt(chat_id, user_a_id) is not None, "Pending receipt saqlanmadi!"

    # 2-qadam: Guruhda User B kelib bir nechta boshqa mavzularda yozadi
    user_memory.add_user_message(chat_id, user_b_id, "Kassada soat to'g'irlash videosi bormi?")
    user_memory.add_assistant_message(chat_id, user_b_id, "[Video 141 yuborildi]")
    user_memory.set_last_topic(chat_id, user_b_id, "time_fix")

    # User A ning pending kvitansiyasi buzilmaganini tekshiramiz
    pending_a = user_memory.get_pending_receipt(chat_id, user_a_id)
    assert pending_a is not None and pending_a["file_id"] == "receipt_photo_file_999", (
        "User B xabarlari User A ning kvitansiyasini buzdi!"
    )

    # 3-qadam: User A oradan vaqt o'tib INN ni probellar bilan yozadi
    chat = MockChat(chat_id=chat_id, chat_type=ChatType.GROUP)
    user_a = MockUser(user_id=user_a_id, first_name="Ali", username="ali_pos")
    msg_inn = MockMessage(message_id=10, user=user_a, chat=chat, text="Bizning INN: 206 011 507")

    # process_and_send_debt_result pending receiptni topib bog'laydi
    await process_and_send_debt_result(msg_inn, bot, "206011507")
    assert len(msg_inn.replies) == 1
    assert "Qarzdorlik to'liq bartaraf etildi" in msg_inn.replies[0]

    # Adminga rasm (photo_file_id) bilan xabarnoma ketganini tekshirish:
    assert bot.send_photo.called or bot.send_message.called, "Adminga xabarnoma bormadi!"

    # 4-qadam: User A ning keyingi savoli: "qachon qo'shiladi?"
    summary_a = user_memory.get_context_summary(chat_id, user_a_id)
    reply_a, _ = generate_ai_reply("qachon qo'shiladi?", context_history=summary_a)
    assert any(w in reply_a.lower() for w in ["adminga", "operator", "15-30", "yoqiladi", "kvitansiya"]), (
        f"Kvitansiya tasdig'idan keyin AI xato javob berdi: {reply_a}"
    )

    admin_manager.remove_admin(999888777)
    logger.info("✅ Asinxron pending kvitansiya, file_id saqlanishi va adminga uzatilishi 100% muvaffaqiyatli!")



# =========================================================================
# TEST 6: EKRAN NOSOZLIKLARI: NOMA'LUM INN BILAN FALSE CLAIM YO'QLIGI
# =========================================================================
def test_screen_diagnostics_unverified_debt_safeguard():
    logger.info(">>> TEST 6: Ekran nosozliklarida noma'lum INN bilan yolg'on gapirmaslik testi...")
    chat_id = 991122
    unknown_user = 332211
    user_memory.sessions.pop(f"{chat_id}:{unknown_user}", None)

    # 1. Noma'lum userda ekran xatoligi (masalan Smena 24 soat oshgan), internet bor
    facts_screen_unknown = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=True,
        has_internet=True,
        time_mismatch=False,
        error_type="none",
        detected_inn=None, # INN noma'lum!
        raw_facts={"screen_text_summary": "Смена превысила 24 часа. Снимите Z-отчет"}
    )

    decision = core_engine.process_device_facts(facts_screen_unknown, chat_id, unknown_user)
    # INN noma'lum bo'lgani sababli qarzdorlik yo'q deb aytilmasligi va adminga asossiz eskalatsiya bo'lmasligi kerak!
    assert "qarzdorlik yo'q" not in decision.reply_text.lower(), "Tekshirilmagan INN ga 'qarzdorlik yo'q' deb aytildi!"
    assert "INN" in decision.reply_text, "INN so'ralmadi!"
    assert decision.action == ActionType.DIAGNOSE_AND_REPLY, "Asossiz eskalatsiya qilindi!"

    # 2. Fatal xatolik (Tamper) bo'lsa -> INN bo'lmasa ham darhol adminga eskalatsiya qilinishi kerak!
    facts_tamper = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=True,
        has_internet=True,
        time_mismatch=False,
        error_type="none",
        detected_inn=None,
        raw_facts={"screen_text_summary": "Tamper detected! Hardware error"}
    )
    decision_tamper = core_engine.process_device_facts(facts_tamper, chat_id, unknown_user)
    assert decision_tamper.action == ActionType.ESCALATE_TO_ADMIN, "Tamper adminga eskalatsiya qilinmadi!"
    assert decision_tamper.should_notify_admin is True

    # 3. Aniq qarz yo'q bo'lgan taniqli foydalanuvchida oddiy xatolik bo'lsa -> Endi adminga eskalatsiya bo'lishi kerak!
    known_user = 332212
    user_memory.set_last_id(chat_id, known_user, "311790999", org_name="QARZSIZ KORXONA", debt=0.0)
    facts_screen_known = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=True,
        has_internet=True,
        time_mismatch=False,
        error_type="none",
        detected_inn="311790999",
        raw_facts={"screen_text_summary": "Kommutatsiya xatosi (Aloqa yo'q)"}
    )
    decision_known = core_engine.process_device_facts(facts_screen_known, chat_id, known_user)
    assert decision_known.action == ActionType.ESCALATE_TO_ADMIN, "Qarzsiz apparatdagi nosozlik adminga bormadi!"
    assert "qarzdorlik yo'q" in decision_known.reply_text.lower()

    logger.info("✅ Ekran diagnostikasida qarzdorlikni tekshirish va eskalatsiya filtrlari 100% to'g'ri!")


# =========================================================================
# TEST 7: 10 FOYDALANUVCHINING BITTA GURUHDAGI PARALLEL STRESS-TESTI
# =========================================================================
async def test_10_concurrent_users_in_single_group_stress():
    logger.info(">>> TEST 7: 10 ta foydalanuvchining umumiy guruhdagi parallel stress-testi...")
    bot = create_mock_bot()
    shared_chat = MockChat(chat_id=-100777000111, chat_type=ChatType.GROUP)

    users_data = [
        {"id": 101, "name": "User 1 (Ali - Qarzli)", "msg": "206011507", "expected_org": "QASHQADARYO SHARQ GAVHARI"},
        {"id": 102, "name": "User 2 (Vali - Qarzsiz)", "msg": "311790999", "expected_org": "ALISHER BOBO"},
        {"id": 103, "name": "User 3 (Gani - Spaced INN)", "msg": "INN: 206 011 507", "expected_org": "QASHQADARYO SHARQ GAVHARI"},
        {"id": 104, "name": "User 4 (Karim - Operator)", "msg": "operator bilan gaplashmoqchiman", "expected_type": "operator"},
        {"id": 105, "name": "User 5 (Salim - Click)", "msg": "Click orqali qanday to'layman?", "expected_type": "payment_video"},
        {"id": 106, "name": "User 6 (Jasur - Tarix)", "msg": "to'lov tariximni ko'rsat INN 206011507", "expected_type": "history"},
        {"id": 107, "name": "User 7 (Botir - Soat)", "msg": "kassada vaqt xato ko'rsatyapti", "expected_type": "time_video"},
        {"id": 108, "name": "User 8 (Anvar - Noma'lum)", "msg": "qachon qo'shiladi?", "expected_type": "ask_inn"},
        {"id": 109, "name": "User 9 (Zafar - Dotted INN)", "msg": "STIR 302.568.138", "expected_type": "inn_query"},
        {"id": 110, "name": "User 10 (Sardor - Tamper)", "msg": "tamper detected usta chaqir", "expected_type": "operator"}
    ]

    async def execute_user_action(u):
        user_obj = MockUser(user_id=u["id"], first_name=u["name"])
        msg = MockMessage(message_id=u["id"], user=user_obj, chat=shared_chat, text=u["msg"])
        
        # Router orqali chaqirish
        if is_inn_query_message(msg):
            inn_num = extract_clean_inn(u["msg"])
            await process_and_send_debt_result(msg, bot, inn_num)
        else:
            await handle_user_chat(msg, bot)
        return u, msg

    # Barcha 10 ta foydalanuvchini bir vaqtda (parallel) ishga tushirish!
    results = await asyncio.gather(*(execute_user_action(u) for u in users_data))

    # Natijalarni qat'iy tekshirish
    for u, msg in results:
        assert len(msg.replies) >= 1 or bot.copy_message.called, f"{u['name']} ga javob qaytmadi!"
        reply = msg.replies[0] if msg.replies else ""

        if "expected_org" in u:
            assert u["expected_org"] in reply, f"{u['name']} da korxona nomi xato: {reply}"
        elif u.get("expected_type") == "operator":
            assert "adminga" in reply.lower() or "mutaxassis" in reply.lower(), f"{u['name']} eskalatsiya bo'lmadi"
        elif u.get("expected_type") == "payment_video":
            assert bot.copy_message.called
        elif u.get("expected_type") == "history":
            assert "Oylar kesimidagi" in reply or "hisob" in reply.lower()
        elif u.get("expected_type") == "ask_inn":
            assert "inn" in reply.lower() or "jshshir" in reply.lower()

    # Hech bir foydalanuvchi ma'lumoti boshqasiga o'tib ketmaganini tekshirish:
    assert user_memory.get_last_id(shared_chat.id, 101) == "206011507"
    assert user_memory.get_last_id(shared_chat.id, 102) == "311790999"
    assert user_memory.get_last_id(shared_chat.id, 108) is None, "Noma'lum foydalanuvchiga begona INN birikib qoldi!"

    logger.info("✅ 10 ta foydalanuvchining bitta umumiy guruhdagi parallel stress-testi 100% MUVAFFAQIYATLI O'TDI!")


# =========================================================================
# ASOSIY ISHGA TUSHIRUVCHI
# =========================================================================
async def run_all_extreme_tests():
    logger.info("=================================================================")
    logger.info("🚀 MARS BOT — EKSTREMAL EDGE-CASE VA STRESS TESTLARI BOSHLANDI")
    logger.info("=================================================================")

    test_dirty_and_formatted_inns()
    await test_group_chat_routing_never_swallowed()
    await test_unknown_vs_identified_context()
    test_receipt_overpayment_and_partial_payment()
    await test_pending_receipt_with_interleaved_chat_and_file_id()
    test_screen_diagnostics_unverified_debt_safeguard()
    await test_10_concurrent_users_in_single_group_stress()

    logger.info("=================================================================")
    logger.info("🎉 BARCHA EKSTREMAL EDGE-CASE VA STRESS TESTLAR 100% MUVAFFAQIYATLI O'TDI!")
    logger.info("=================================================================")

if __name__ == "__main__":
    asyncio.run(run_all_extreme_tests())
