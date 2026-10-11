import os
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
from aiogram.enums import ChatType

from core.models import (
    ReceiptFacts, ActionType,
    extract_clean_inn, extract_clean_phone
)
from transaction_tracker import TransactionTracker
from excel_manager import excel_manager
from error_manager import error_manager
from admin_manager import admin_manager
from core.engine import CoreEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_v6_8")

def test_extract_clean_phone():
    logger.info(">>> 1. Phone extraction tests...")
    assert extract_clean_phone("+998 93 890 09 90") == "938900990"
    assert extract_clean_phone("998901234567") == "901234567"
    assert extract_clean_phone("tel: 938900990") == "938900990"
    assert extract_clean_phone("Telefon nomerim +998941234567 tekshir") == "941234567"
    assert extract_clean_phone("salom") is None
    logger.info("✅ Telefon raqami to'g'ri ajratib olinmoqda!")

def test_excel_phone_index_and_district():
    logger.info(">>> 2. Excel phone search & district lookup tests...")
    assert len(excel_manager.phone_index) > 0
    first_phone = list(excel_manager.phone_index.keys())[0]
    results = excel_manager.search(first_phone)
    assert len(results) > 0
    record = results[0]
    inn = record.get("stir")
    assert inn is not None

    district = excel_manager.get_district_for_inn(inn)
    assert isinstance(district, str)
    logger.info(f"✅ Excelda telefon ({first_phone}) orqali INN ({inn}) va tuman ({district}) muvaffaqiyatli topildi!")

def test_transaction_tracker_duplicate_and_old_date():
    logger.info(">>> 3. Transaction tracker fraud/duplicate/old date tests...")
    tracker_file = "/tmp/test_tx_v6_8.json"
    if os.path.exists(tracker_file):
        os.remove(tracker_file)
    tracker = TransactionTracker(tracker_file)

    tx_id = "click_tx_998877"
    assert not tracker.is_duplicate(tx_id)

    # 1-marta ro'yxatga olish
    tracker.record_transaction(tx_id, inn="302568138", amount=100000.0, user_id=123)
    assert tracker.is_duplicate(tx_id)

    # O'tgan yilgi chek (2025)
    is_old, warn = tracker.check_old_receipt("2025-05-10 14:00")
    assert is_old is True
    assert "o'tgan yilgi" in warn

    # 60 kun oldingi chek
    is_old_60, warn_60 = tracker.check_old_receipt("2026-01-01")
    assert is_old_60 is True

    # Bugungi chek
    is_fresh, warn_fresh = tracker.check_old_receipt("2026-10-10 12:00")
    assert is_fresh is False
    assert warn_fresh is None
    logger.info("✅ Dublikat va eski kvitansiya tekshiruvi to'liq to'g'ri ishlamoqda!")

def test_payment_purpose_categorization():
    logger.info(">>> 4. Payment purpose categorization tests...")
    tracker = TransactionTracker("/tmp/dummy_tx.json")

    p1, label1 = tracker.detect_payment_purpose("Apparat ta'miri uchun 150000 to'ladim remont")
    assert p1 == "repair"
    assert "ta'miri" in label1

    p2, label2 = tracker.detect_payment_purpose("Yangi apparat sotib olish uchun to'lov")
    assert p2 == "hardware_purchase"
    assert "xaridi" in label2

    p3, label3 = tracker.detect_payment_purpose("pere-registratsiya tolovi")
    assert p3 == "registration"
    assert "ro'yxatdan" in label3

    p4, label4 = tracker.detect_payment_purpose("Abonent tolovi 100 000 som")
    assert p4 == "monthly_subscription"
    assert "abonent" in label4.lower()
    logger.info("✅ To'lov maqsadlari (ta'mir, xarid, registratsiya, abonent) to'g'ri toifalanmoqda!")

def test_new_hardware_rules():
    logger.info(">>> 5. Hardware rules (Pax D210, Printer, Serial) tests...")
    # Pax D210
    rule_d210 = error_manager.match_error({"screen_text_summary": "pax d210 klaviatura smena yopish"})
    assert rule_d210 is not None
    assert rule_d210["id"] == "pax_d210_menu_help"
    assert "Menu" in rule_d210["response_text"]

    # Printer cover open
    rule_cover = error_manager.match_error({"screen_text_summary": "printer qopqoq ochiq cover open"})
    assert rule_cover is not None
    assert rule_cover["id"] == "printer_cover_open"

    # Printer overheat
    rule_heat = error_manager.match_error({"screen_text_summary": "перегрев принтера overheat"})
    assert rule_heat is not None
    assert rule_heat["id"] == "printer_overheat"

    # Paper jam
    rule_jam = error_manager.match_error({"screen_text_summary": "замятие бумаги qog'oz tiqilib qoldi"})
    assert rule_jam is not None
    assert rule_jam["id"] == "paper_jam"

    # Serial number sticker
    rule_sn = error_manager.match_error({"screen_text_summary": "наклейка аппарата s/n: 198273645"})
    assert rule_sn is not None
    assert rule_sn["id"] == "serial_number_sticker"
    logger.info("✅ Barcha yangi texnik qoidalar to'liq ishga tushirildi!")

def test_core_engine_repair_purpose_and_duplicate():
    logger.info(">>> 6. Core engine evaluation with purpose & duplicate tests...")
    engine = CoreEngine()
    facts = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        amount=150000.0,
        payer_inn="302568138",
        payment_date="2026-10-10 10:00",
        transaction_id="tx_unique_repair_001",
        raw_text="kassa apparati ta'miri va remont uchun to'lov"
    )

    decision = engine.process_receipt_facts(
        facts=facts,
        chat_id=999,
        user_id=888,
        user_comment="Usta uchun pul to'ladim"
    )

    assert decision.action == ActionType.RECEIPT_PROCESSED
    assert decision.payment_purpose == "repair"
    assert "ta'miri" in decision.reply_text
    assert decision.tuman is not None

    # Qayta yuborilganda dublikat aniqlanishi kerak
    facts_dup = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        amount=150000.0,
        payer_inn="302568138",
        payment_date="2026-10-10 10:00",
        transaction_id="tx_unique_repair_001",
        raw_text="kassa apparati ta'miri va remont uchun to'lov"
    )
    decision_dup = engine.process_receipt_facts(
        facts=facts_dup,
        chat_id=999,
        user_id=888
    )
    assert decision_dup.is_duplicate is True
    assert "avval ham tizimga yuborilgan" in decision_dup.reply_text
    logger.info("✅ CoreEngine to'lov maqsadi va dublikat ogohlantirishini to'g'ri chiqardi!")

async def test_admin_notification_formatting():
    logger.info(">>> 7. Admin notification formatting (Tuman, purpose, duplicate) tests...")
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    facts = ReceiptFacts(
        is_receipt=True,
        amount=200000.0,
        payer_inn="302568138",
        transaction_id="tx_test_admin_alert",
        payment_date="2026-10-10 10:00",
        payment_purpose="repair",
        purpose_label="Apparat ta'miri / Remont",
        is_duplicate=True
    )

    debt_status = {
        "org_name": "TEST MCHJ",
        "inn": "302568138",
        "tuman": "Shahrisabz",
        "prev_debt": 0.0,
        "remaining_debt": 0.0,
        "debt_covered": True,
        "is_duplicate": True,
        "purpose_label": "Apparat ta'miri / Remont",
        "payment_purpose": "repair"
    }

    admin_manager.admin_ids = [111222333]

    await admin_manager.notify_receipt_escalation(
        bot=mock_bot,
        user=None,
        chat_id=999,
        receipt_facts=facts,
        debt_status_info=debt_status,
        file_id=None,
        is_photo=True
    )

    assert mock_bot.send_message.called
    sent_text = mock_bot.send_message.call_args.kwargs["text"]
    assert "Shahrisabz" in sent_text
    assert "DUBLIKAT TRANZAKSIYA" in sent_text
    assert "Apparat ta'miri" in sent_text
    assert "302568138" in sent_text
    logger.info("✅ Adminga yuborilgan hisobotda tuman, maqsad va dublikat ogohlantirishi aks etdi!")

async def test_excel_security_lockdown():
    logger.info(">>> 9. Excel upload security lockdown tests...")
    from handlers.media import handle_document
    mock_bot = MagicMock()

    # 1. Non-admin user upload attempt
    mock_msg_attacker = MagicMock()
    mock_msg_attacker.document = MagicMock()
    mock_msg_attacker.document.file_name = "malicious_base.xlsx"
    mock_msg_attacker.from_user = MagicMock()
    mock_msg_attacker.from_user.id = 99999999
    mock_msg_attacker.from_user.username = "random_stranger"
    mock_msg_attacker.chat.id = 99999999
    mock_msg_attacker.chat.type = ChatType.PRIVATE
    mock_msg_attacker.reply = AsyncMock()

    await handle_document(mock_msg_attacker, mock_bot)
    assert mock_msg_attacker.reply.called
    reply_text = mock_msg_attacker.reply.call_args[0][0]
    assert "huquqi yo'q" in reply_text
    logger.info("✅ Begona foydalanuvchi Excel yuklashga uringanda bloklandi!")

def test_media_group_debouncer():
    logger.info(">>> 8. Media group debouncer tests...")
    from handlers.media import _check_and_register_media_group
    group_id = "album_12345"
    assert _check_and_register_media_group(group_id) is True
    assert _check_and_register_media_group(group_id) is False
    assert _check_and_register_media_group(None) is True
    logger.info("✅ Media guruh (album) debounceri muvaffaqiyatli ishladi!")

async def run_all():
    test_extract_clean_phone()
    test_excel_phone_index_and_district()
    test_transaction_tracker_duplicate_and_old_date()
    test_payment_purpose_categorization()
    test_new_hardware_rules()
    test_core_engine_repair_purpose_and_duplicate()
    await test_admin_notification_formatting()
    test_media_group_debouncer()
    await test_excel_security_lockdown()
    print("\n🎉 BARCHA V6.8 YANGI IMKONIYATLAR TESTLARI 100% MUVAFFAQISHLI O'TDI! 🎉\n")

if __name__ == "__main__":
    asyncio.run(run_all())
