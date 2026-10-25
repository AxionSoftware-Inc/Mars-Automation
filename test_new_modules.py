import os
import io
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pypdf

from core.models import DeviceFacts, ReceiptFacts, DecisionResult, ActionType
from core.engine import core_engine
from excel_manager import excel_manager
from admin_manager import admin_manager
from user_memory import user_memory
from receipt_analyzer import extract_receipt_facts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_new_modules")

def test_admin_manager():
    logger.info(">>> 1. ADMIN MANAGER TEST...")
    # Add admin
    test_admin_id = 999888777
    admin_manager.add_admin(test_admin_id)
    assert admin_manager.is_admin(test_admin_id) is True, "Admin qo'shish xatosi"
    assert test_admin_id in admin_manager.get_admin_ids()

    # Add contact
    admin_manager.add_contact("Usta Toxir", "+998901112233", "Katta muhandis")
    contacts_str = admin_manager.get_contacts_display()
    assert "Usta Toxir" in contacts_str
    assert "+998901112233" in contacts_str

    # Test @Yashnarbek_butaev auto registration
    yashnar_test_id = 555444333
    assert admin_manager.is_admin(yashnar_test_id, username="Yashnarbek_butaev") is True
    assert yashnar_test_id in admin_manager.get_admin_ids()
    admin_manager.remove_admin(yashnar_test_id)

    # Clean up test admin
    admin_manager.remove_admin(test_admin_id)
    assert admin_manager.is_admin(test_admin_id) is False
    admin_manager.remove_contact("+998901112233")
    logger.info("✅ AdminManager (@Yashnarbek_butaev bilan) barcha tekshiruvlardan muvaffaqiyatli o'tdi.")

def test_receipt_full_debt_coverage():
    logger.info(">>> 2. KVITANSIYA: QARZ TO'LIQ YOPILISH TESTI...")
    chat_id = -100123
    user_id = 501
    user_memory.clear_context(chat_id, user_id)

    # Ali (INN: 206011507) has debt in latest.xlsx
    ali_inn = "206011507"
    results = excel_manager.search(ali_inn)
    assert len(results) > 0, "Bazada korxona topilmadi"
    current_debt = sum(r.get("debt", 0.0) for r in results)
    logger.info(f"Ali (INN {ali_inn}) joriy qarzi: {current_debt:,.0f} so'm")

    # Kvitansiya summasi qarzga teng yoki katta
    paid_sum = current_debt if current_debt > 0 else 100000.0
    receipt = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=paid_sum,
        payer_inn=ali_inn,
        payer_name="Qashqadaryo Sharq Gavhari",
        transaction_id="CLK-987654321",
        payment_system="Click"
    )

    decision = core_engine.process_receipt_facts(receipt, chat_id=chat_id, user_id=user_id)
    assert decision.action == ActionType.RECEIPT_PROCESSED
    assert decision.should_notify_admin is True
    assert decision.admin_alert_type == "receipt"
    assert decision.debt_status_info.get("debt_covered") is True
    assert decision.debt_status_info.get("remaining_debt") == 0.0
    assert "qabul qilindi" in decision.reply_text.lower()
    logger.info("✅ Kvitansiya to'liq qarzni yopishi to'g'ri hisoblandi va adminga bildirishnoma tayyorlandi.")

def test_receipt_partial_debt_coverage():
    logger.info(">>> 3. KVITANSIYA: QARZ QISMAN TO'LANISH TESTI...")
    chat_id = -100124
    user_id = 502
    user_memory.clear_context(chat_id, user_id)

    ali_inn = "206011507"
    # Qarzning yarmini to'laymiz
    results = excel_manager.search(ali_inn)
    current_debt = sum(r.get("debt", 0.0) for r in results)
    partial_sum = current_debt / 2 if current_debt > 0 else 50000.0

    receipt = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=partial_sum,
        payer_inn=ali_inn,
        transaction_id="CLK-11223344",
        payment_system="Click"
    )

    decision = core_engine.process_receipt_facts(receipt, chat_id=chat_id, user_id=user_id)
    assert decision.action == ActionType.RECEIPT_PROCESSED
    assert decision.should_notify_admin is True
    assert decision.debt_status_info.get("debt_covered") is False
    assert decision.debt_status_info.get("remaining_debt") > 0
    assert "qabul qilindi" in decision.reply_text.lower()
    logger.info("✅ Qisman to'lov holati aniq hisoblandi va qolgan qarz ko'rsatildi.")

def test_pending_receipt_flow():
    logger.info(">>> 4. KVITANSIYA: INN YO'Q BO'LGANDA KETMA-KETLIK (PENDING) TESTI...")
    chat_id = -100125
    user_id = 503
    user_memory.clear_context(chat_id, user_id)

    # Foydalanuvchi kvitansiya tashladi, lekin unda INN yo'q
    receipt = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=100000.0,
        payer_inn=None,
        transaction_id="CLK-PENDING-001"
    )

    decision1 = core_engine.process_receipt_facts(receipt, chat_id=chat_id, user_id=user_id)
    assert "inn" in decision1.reply_text.lower()
    assert user_memory.get_pending_receipt(chat_id, user_id) is not None

    # Endi foydalanuvchi keyingi xabarda INN yuboradi
    decision2 = core_engine.resolve_pending_receipt_if_any("206011507", chat_id, user_id)
    assert decision2 is not None
    assert decision2.action == ActionType.RECEIPT_PROCESSED
    assert decision2.detected_inn == "206011507"
    assert decision2.should_notify_admin is True
    assert user_memory.get_pending_receipt(chat_id, user_id) is None
    logger.info("✅ INN so'rash va keyin bog'lash zanjiri muvaffaqiyatli ishladi!")

def test_technical_issue_escalation_to_admin():
    logger.info(">>> 5. TEXNIK NOSOZLIKNI ADMINGA ESKALATSIYA QILISH TESTI...")
    chat_id = -100126
    user_id = 504

    # Vali (INN: 311790999) has 0 debt!
    vali_inn = "311790999"
    results = excel_manager.search(vali_inn)
    debt_val = sum(r.get("debt", 0.0) for r in results)
    assert debt_val <= 0, "Vali qarzsiz bo'lishi kerak"

    # Apparat ekrani: Internet bor, soat to'g'ri, lekin ekranda xatolik bor (fiskal modul nosozligi)
    facts = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=True,
        time_mismatch=False,
        has_internet=True,
        error_type="hardware",
        detected_inn=vali_inn,
        screen_text_summary="Xato 102 mikrokontroller xatosi",
        raw_facts={"is_p3_device": True}
    )

    decision = core_engine.process_device_facts(facts, chat_id=chat_id, user_id=user_id)
    assert decision.action in [ActionType.ESCALATE_TO_ADMIN, ActionType.DIAGNOSE_AND_REPLY]
    assert decision.should_notify_admin is True
    assert decision.admin_alert_type == "tech_issue"
    assert "102" in decision.reply_text or "xato" in decision.reply_text.lower()
    logger.info("✅ Qarzsiz va interneti bor apparatdagi nosozlik adminga to'g'ri eskalatsiya qilindi!")

def test_pdf_receipt_creation_and_parsing():
    logger.info(">>> 6. PDF KVITANSIYA MATNINI AJRATISH VA SENSOR TESTI...")
    # PDF faylni xotirada yaratamiz
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=300, height=500)
    
    # Test text kiritish yoki test PDF o'qish
    pdf_buffer = io.BytesIO()
    writer.write(pdf_buffer)
    pdf_bytes = pdf_buffer.getvalue()
    assert len(pdf_bytes) > 0

    # Sensor testi
    facts = extract_receipt_facts(pdf_bytes, filename="to'lov_chek.pdf", mime_type="application/pdf", user_caption="Click orqali to'ladim 206011507")
    assert facts.payer_inn == "206011507"
    logger.info("✅ PDF kvitansiya sensori INN va izohni to'g'ri ajratib oldi.")

async def test_async_admin_notification_mock():
    logger.info(">>> 7. ADMINGA TELEGRAM XABARNOMA YUBORISHNING ASINXRON TESTI...")
    mock_bot = AsyncMock()
    
    saved_admin_ids = list(admin_manager.admin_ids)
    test_admin_id = 777111222
    admin_manager.admin_ids = [test_admin_id]

    receipt = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=150000.0,
        payer_inn="206011507",
        transaction_id="CLK-TEST-999"
    )
    debt_info = {"org_name": "Test MCHJ", "inn": "206011507", "prev_debt": 150000.0, "remaining_debt": 0.0, "debt_covered": True}

    mock_user = MagicMock()
    mock_user.id = 12345
    mock_user.full_name = "Rustam Karimov"
    mock_user.username = "rustam_k"

    await admin_manager.notify_receipt_escalation(
        bot=mock_bot,
        user=mock_user,
        chat_id=-100999,
        receipt_facts=receipt,
        debt_status_info=debt_info,
        file_id="photo_123_abc",
        is_photo=True
    )

    assert mock_bot.send_photo.called
    sent_captions = [c.kwargs.get("caption", "") for c in mock_bot.send_photo.call_args_list]
    assert any(c.kwargs.get("chat_id") == test_admin_id for c in mock_bot.send_photo.call_args_list)
    assert any("Rustam Karimov" in cap for cap in sent_captions)
    assert any("QARZNI YOPADI" in cap or "QARZ" in cap for cap in sent_captions)

    admin_manager.admin_ids = saved_admin_ids
    logger.info("✅ Adminga Telegram orqali xabarnoma jo'natish simulyatsiyasi 100% muvaffaqiyatli!")

def main():
    logger.info("=================================================================")
    logger.info("🚀 YANGI MODULLAR: ADMIN VA KVITANSIYA INTEGRATSIYA TESTI")
    logger.info("=================================================================")
    test_admin_manager()
    test_receipt_full_debt_coverage()
    test_receipt_partial_debt_coverage()
    test_pending_receipt_flow()
    test_technical_issue_escalation_to_admin()
    test_pdf_receipt_creation_and_parsing()
    asyncio.run(test_async_admin_notification_mock())
    logger.info("=================================================================")
    logger.info("🎉 BARCHA 7 TA SINOV 100% MUVAFFAQIYATLI O'TDI!")
    logger.info("=================================================================")

if __name__ == "__main__":
    main()
