"""
test_all_10_audit_holes_round2.py
=================================
Loyihani qabul qiluvchi (rahbar) va texnik xodim (usta/operator) nuqtai nazaridan
topilgan 10 ta chuqur mantiqiy va texnik teshiklarni (Round 2 Audit) tekshirish.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types

from core.group_responder import group_responder
from core.engine import core_engine
from core.models import ReceiptFacts, DeviceFacts
from handlers.media import _process_fiscal_receipt_content, _process_image_content
from handlers.debt import process_and_send_debt_result
from ofd_bridge import ofd_bridge
from admin_manager import admin_manager
from user_memory import user_memory
from payment_accounts import parse_ofd_reply_status


def make_msg(text: str, user_id: int = 999111, chat_id: int = -100123456, username: str = "mijoz_test", reply_to_user=None):
    msg = MagicMock(spec=types.Message)
    msg.text = text
    msg.caption = None
    msg.message_id = 555
    msg.chat = MagicMock()
    msg.chat.id = chat_id
    msg.chat.type = "supergroup"
    msg.chat.title = "Test Guruh"
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.from_user.full_name = "Test Mijoz"
    msg.from_user.username = username
    msg.from_user.is_bot = False
    if reply_to_user is not None:
        msg.reply_to_message = MagicMock()
        msg.reply_to_message.from_user = reply_to_user
    else:
        msg.reply_to_message = None
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()
    return msg


def make_bot():
    bot = MagicMock()
    bot.copy_message = AsyncMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_document = AsyncMock()
    return bot


async def run_tests():
    user_memory.clear()
    bot = make_bot()
    chat_id = -100999888

    print("\n--- 1. BAZADA YO'Q INN (305123456) XOTIRANI BUZMASLIGI VA 0 SO'M DEMASLIGI ---")
    uid1 = 800001
    user_memory.clear_context(chat_id, uid1)
    # Avval haqiqiy qarzdor INN tekshiradi (206011507 -> 400,000 so'm qarz)
    m1_valid = make_msg("206011507", user_id=uid1, chat_id=chat_id)
    await process_and_send_debt_result(m1_valid, bot, "206011507")
    assert user_memory.get_last_id(chat_id, uid1) == "206011507"
    # Endi bazada yo'q 9 xonali raqam yuboradi (305123456)
    m1_invalid = make_msg("apparat ishlamayapti 305123456", user_id=uid1, chat_id=chat_id)
    await group_responder.process_message(m1_invalid, bot)
    rep1 = m1_invalid.reply.call_args[0][0]
    print("Reply 1 (invalid INN in hardware):", rep1[:140].replace("\n", " "))
    assert "topilmadi" in rep1.lower(), f"Bazada yo'q INN topilmadi deyishi kerak edi: {rep1}"
    assert "0 so'm" not in rep1.lower(), f"Bazada yo'q INN ga 0 so'm demasligi kerak: {rep1}"
    # Va xotiradagi 206011507 o'chib ketmagan bo'lishi shart!
    assert user_memory.get_last_id(chat_id, uid1) == "206011507", f"last_id buzildi: {user_memory.get_last_id(chat_id, uid1)}"
    print("✅ 1-TEST PASS")

    print("\n--- 2. OFD 'BUNDAY FISKAL MODUL MAVJUD EMAS' XATOSI FAOL DEB YUBORILMASLIGI ---")
    uid2 = 800002
    user_memory.clear_context(chat_id, uid2)
    assert parse_ofd_reply_status("❌ Bunday fiskal modul mavjud emas!") == "not_found"
    assert parse_ofd_reply_status("Fiskal modul topilmadi") == "not_found"
    with patch.object(ofd_bridge, "query_fiscal_module", new=AsyncMock(return_value="❌ Bunday fiskal modul mavjud emas!")):
        m2 = make_msg("aparat ishlamayapti 302568138 LG999999999999", user_id=uid2, chat_id=chat_id)
        await group_responder.process_message(m2, bot)
        rep2 = m2.reply.call_args[0][0]
        print("Reply 2 (OFD not_found):", rep2[:140].replace("\n", " "))
        assert "topilmadi" in rep2.lower() or "ro'yxatda yo'q" in rep2.lower(), f"Topilmadi deyishi kerak edi: {rep2}"
        assert "qarzdorlik yo'q" not in rep2.lower() and "litsenziya faol" not in rep2.lower(), f"Yolg'on faol demasligi kerak: {rep2}"
    print("✅ 2-TEST PASS")

    print("\n--- 3. SMART ONE RASMIDA 2-BOSQICH (FISKAL MODUL SO'RASH) SAKRAB KETMASLIGI ---")
    uid3 = 800033
    user_memory.clear_context(chat_id, uid3)
    user_memory.set_last_id(chat_id, uid3, "302568138", org_name="MARS TEST", debt=0.0)
    assert user_memory.get_last_fm(chat_id, uid3) is None, f"last_fm None bo'lishi kerak edi, lekin: {user_memory.get_last_fm(chat_id, uid3)}"
    fake_device_facts = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=True,
        time_mismatch=False,
        has_internet=True,
        error_type="none",
        screen_text_summary="SmartPOS xatolik"
    )
    with patch("handlers.media.analyze_media_image", return_value=("pos_device", None, fake_device_facts)):
        m3 = make_msg("", user_id=uid3, chat_id=chat_id)
        await _process_image_content(m3, bot, b"fake_img", "ishlamayapti", "file_123")
        rep3 = m3.reply.call_args[0][0]
        print("Reply 3 (Smart One photo without FM):", rep3[:140].replace("\n", " "))
        assert "fiskal modul" in rep3.lower() or "2-bosqich" in rep3.lower(), f"2-bosqich FM so'rashi kerak edi: {rep3}"
    print("✅ 3-TEST PASS")

    print("\n--- 4. GURUHDA ADMIN MIJOZGA REPLY QILGANDA BOT JIM TURISHI VA ESKALATSIYANI YOPISHI ---")
    uid4_customer = 800004
    uid4_admin = 1041997926  # Ro'yxatdagi haqiqiy admin ID
    user_memory.clear_context(chat_id, uid4_customer)
    user_memory.set_issue_mode(chat_id, uid4_customer, True, "ishlamayapti")
    user_memory.mark_escalated_to_admin(chat_id, uid4_customer, "test")

    customer_user_mock = MagicMock()
    customer_user_mock.id = uid4_customer
    customer_user_mock.is_bot = False

    m4_admin_reply = make_msg(
        "Hozir apparatingizni yoqib beraman, 5 daqiqada o'chirib yoqing",
        user_id=uid4_admin,
        chat_id=chat_id,
        username="quvonchbek_admin",
        reply_to_user=customer_user_mock
    )
    await group_responder.process_message(m4_admin_reply, bot)
    assert not m4_admin_reply.reply.called, "Admin mijozga javob yozganda bot aralashmasligi kerak!"
    assert not user_memory.is_escalated_to_admin(chat_id, uid4_customer), "Admin javob bergach mijoz eskalatsiyasi yopilishi kerak!"
    assert not user_memory.is_issue_mode(chat_id, uid4_customer), "Admin javob bergach mijoz issue_mode yopilishi kerak!"
    print("✅ 4-TEST PASS")

    print("\n--- 5. 201589463 (YANGI TEXNOLOGIYALAR DUK STIR) YUBORILGANDA ANIQ OGOHLANTIRISH ---")
    uid5 = 800005
    user_memory.clear_context(chat_id, uid5)
    m5 = make_msg("201589463", user_id=uid5, chat_id=chat_id)
    await group_responder.process_message(m5, bot)
    rep5 = m5.reply.call_args[0][0]
    print("Reply 5 (201589463):", rep5[:140].replace("\n", " "))
    assert "yangi texnologiyalar" in rep5.lower() and "201589463" in rep5, f"Yangi Texnologiyalar STIR ekanini tushuntirishi kerak: {rep5}"
    assert user_memory._get_or_create_session(chat_id, uid5).get("last_id") is None, "201589463 mijozning STIRi sifatida saqlanmasligi kerak!"
    print("✅ 5-TEST PASS")

    print("\n--- 6. REGIONAL_ADMINS.JSON VA ADMIN_CONFIG.JSON DA '(Mock)' YOKI SOXTA RAQAMLAR YO'QLIGI ---")
    disp = admin_manager.get_contacts_display(inn="206011507")
    print("Contacts display:", disp.replace("\n", " | "))
    assert "(mock)" not in disp.lower(), f"(Mock) so'zi qolib ketgan: {disp}"
    assert "100 00 0" not in disp, f"Soxta telefon raqam qolib ketgan: {disp}"
    assert 777111222 not in admin_manager.admin_ids, "Soxta test admin ID 777111222 qolib ketgan!"
    print("✅ 6-TEST PASS")

    print("\n--- 7. KVITANSIYADA INN TOPILMAGANDA ADMINGA 'KVITANSIYADA INN TOPILMADI' XABARI BORISHI ---")
    uid7 = 800007
    user_memory.clear_context(chat_id, uid7)
    rf7 = ReceiptFacts(
        is_receipt=True,
        amount=100000.0,
        payer_inn=None,
        payer_name="Noma'lum",
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        transaction_id="TX_NO_INN_777"
    )
    dec7 = core_engine.process_receipt_facts(rf7, chat_id, uid7, "", file_id="f777")
    assert dec7.debt_status_info.get("is_inn_missing") is True, "is_inn_missing True bo'lishi shart!"
    bot.send_photo.reset_mock()
    await admin_manager.notify_receipt_escalation(
        bot=bot,
        user=m5.from_user,
        chat_id=chat_id,
        receipt_facts=rf7,
        debt_status_info=dec7.debt_status_info,
        file_id="f777",
        is_photo=True
    )
    admin_caption = bot.send_photo.call_args.kwargs.get("caption", "")
    print("Admin caption for missing INN:", admin_caption[:140].replace("\n", " "))
    assert "INN TOPILMADI" in admin_caption, f"Adminga INN TOPILMADI deb borishi kerak edi: {admin_caption}"
    assert "AVANS" not in admin_caption, f"Adminga yolg'on AVANS deb bormasligi kerak: {admin_caption}"
    print("✅ 7-TEST PASS")

    print("\n--- 8. 'FISKAL MODULNI BILMAYMAN, QAYERDAN BILAY?' SAVOLIDA ADMINGA LOCK QILMASDAN JAVOB BERISH ---")
    uid8 = 800008
    user_memory.clear_context(chat_id, uid8)
    m8 = make_msg("fiskal modul qayerda yozilgan bilmayman, qayerdan bilay?", user_id=uid8, chat_id=chat_id)
    await group_responder.process_message(m8, bot)
    rep8 = m8.reply.call_args[0][0]
    print("Reply 8 (bilmayman / qayerdan bilay):", rep8[:140].replace("\n", " "))
    assert "fiskal modul" in rep8.lower() and ("chek" in rep8.lower() or "lg" in rep8.lower()), f"FM qayerdaligini tushuntirishi kerak edi: {rep8}"
    assert not user_memory.is_escalated_to_admin(chat_id, uid8), "Mijozni adminga lock qilib qo'ymasligi kerak!"
    print("✅ 8-TEST PASS")

    print("\n--- 9. ACTIVE CONTEXT BOR PAYTDA 'VOZVRAT QANDAY QILINADI?' DEB SO'RASA VIDEO JO'NATISH ---")
    uid9 = 800009
    user_memory.clear_context(chat_id, uid9)
    user_memory.set_last_id(chat_id, uid9, "206011507", org_name="TEST", debt=400000.0)
    bot.copy_message.reset_mock()
    m9 = make_msg("vozvrat qanday qilinadi?", user_id=uid9, chat_id=chat_id)
    await group_responder.process_message(m9, bot)
    assert bot.copy_message.called, "Active context bo'lsa ham aniq texnik savolda kanaldan video post yuborilishi shart!"
    sent_vid_id = bot.copy_message.call_args.kwargs.get("message_id")
    print(f"Sent video post ID for 'vozvrat qanday qilinadi?': {sent_vid_id}")
    print("✅ 9-TEST PASS")

    print("\n--- 10. /set_ofd_channel BEGONA USER TOMONIDAN CHAQIRILGANDA BLOKLANISHI ---")
    old_group_id = ofd_bridge.ofd_group_id
    hacker_msg = make_msg("/set_ofd_channel -100666666666", user_id=999888777, chat_id=chat_id, username="hacker_user")
    await ofd_bridge.handle_incoming_message(hacker_msg, bot=bot)
    assert ofd_bridge.ofd_group_id == old_group_id, "Begona user /set_ofd_channel orqali OFD kanalni o'zgartira olmasligi shart!"
    print("✅ 10-TEST PASS")

    print("\n🎉 BARCHA 10 TA ROUND-2 AUDIT TESTLARI 100% MUVAFFAQIYATLI O'TDI!")


if __name__ == "__main__":
    asyncio.run(run_tests())
