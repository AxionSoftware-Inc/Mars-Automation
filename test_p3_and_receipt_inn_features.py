import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from core.models import (
    DeviceFacts, ReceiptFacts, ActionType, extract_clean_inn
)
from core import core_engine
from admin_manager import admin_manager
from user_memory import user_memory
from excel_manager import excel_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_p3_receipt_inn")


def test_extract_clean_inn_rejects_dummies():
    """extract_clean_inn dummy qiymatlarni (000, 000000000, null, none) rad etishi kerak"""
    logger.info(">>> 1. extract_clean_inn dummy tekshiruvi...")
    
    assert extract_clean_inn("000") is None
    assert extract_clean_inn("000000000") is None
    assert extract_clean_inn("0") is None
    assert extract_clean_inn("null") is None
    assert extract_clean_inn("none") is None
    assert extract_clean_inn("INN: 000") is None
    assert extract_clean_inn("STIR: 000000000") is None
    assert extract_clean_inn("-") is None
    assert extract_clean_inn("") is None

    # Haqiqiy INNlar esa aniq chiqishi kerak
    assert extract_clean_inn("206011507") == "206011507"
    assert extract_clean_inn("INN 206011507") == "206011507"
    assert extract_clean_inn("STIR: 206 011 507") == "206011507"
    assert extract_clean_inn("JSHSHIR: 12345678901234") == "12345678901234"
    logger.info("✅ extract_clean_inn barcha dummy holatlarni to'g'ri filtrlaydi!")


def test_p3_device_without_status_bar_diagnoses_screen_error():
    """P3 apparatida soat qatori bo'lmaydi: ekrandagi xatolikni o'qib darhol yechim berishi kerak"""
    logger.info(">>> 2. P3 apparati status bar yo'q bo'lganda ekrandan yechish testi...")

    # A) Xatolik 102 (Plata mikrokontroller xatosi -> Adminga eskalatsiya)
    facts_102 = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False, # P3 da soat yo'q
        screen_text_summary="Xatolik 102: Apparat platasi xatosi",
        raw_facts={"screen_text_summary": "Xatolik 102: Apparat platasi xatosi"}
    )
    decision_102 = core_engine.process_device_facts(facts_102, chat_id=111, user_id=222)
    assert decision_102.action != ActionType.ASK_FULL_SCREEN, "P3 xatolik 102 da soat so'ralmasligi shart!"
    assert decision_102.action == ActionType.ESCALATE_TO_ADMIN
    assert "102" in (decision_102.reply_text or "")

    # B) Fiskal modul xatosi (Kod 204) -> Video 134
    facts_fm = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False,
        screen_text_summary="Kod 204: Fiskal modul javob bermayapti",
        raw_facts={"screen_text_summary": "Kod 204: Fiskal modul javob bermayapti"}
    )
    decision_fm = core_engine.process_device_facts(facts_fm, chat_id=111, user_id=222)
    assert decision_fm.action != ActionType.ASK_FULL_SCREEN
    assert decision_fm.action == ActionType.DIAGNOSE_AND_REPLY
    assert decision_fm.video_id == 134

    # C) Smena 24 soatdan oshgan -> Video 2
    facts_smena = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False,
        screen_text_summary="Smena 24 soatdan oshgan, Z-hisobot oling",
        raw_facts={"screen_text_summary": "Smena 24 soatdan oshgan"}
    )
    decision_smena = core_engine.process_device_facts(facts_smena, chat_id=111, user_id=222)
    assert decision_smena.action != ActionType.ASK_FULL_SCREEN
    assert decision_smena.action == ActionType.DIAGNOSE_AND_REPLY
    assert decision_smena.video_id == 2
    assert "smena" in (decision_smena.reply_text or "").lower()

    # C) Qog'oz tugadi
    facts_paper = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False,
        error_type="paper",
        screen_text_summary="Qog'oz lentasi tugagan"
    )
    decision_paper = core_engine.process_device_facts(facts_paper, chat_id=111, user_id=222)
    assert decision_paper.action != ActionType.ASK_FULL_SCREEN
    assert decision_paper.action == ActionType.DIAGNOSE_AND_REPLY
    assert "qog'oz" in (decision_paper.reply_text or "").lower()

    logger.info("✅ P3 apparatidagi har qanday ekran xatosi soat qatorisiz ham to'g'ri tashxislandi!")


def test_pos_device_without_error_and_without_status_bar_asks_for_clock():
    """Ekranda hech qanday muammo topilmaganda va status bar bo'lmaganda soat so'rashi kerak"""
    logger.info(">>> 3. Muammo topilmaganda status bar so'rash testi...")

    facts_empty = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False,
        screen_text_summary="Asosiy oyna",
        error_type="none",
        detected_inn=None
    )
    decision = core_engine.process_device_facts(facts_empty, chat_id=111, user_id=222)
    assert decision.action == ActionType.ASK_FULL_SCREEN
    assert "soat va internet belgisi" in (decision.reply_text or "").lower()
    logger.info("✅ Ekrandan muammo topilmaganda soat qatori so'ralishi tasdiqlandi!")


def test_receipt_with_missing_or_zero_inn_notifies_admin_immediately():
    """Kvitansiyada INN ko'rsatilmagan yoki '000' bo'lsa, adminga darhol xabar borishi va foydalanuvchidan INN so'ralishi testi"""
    logger.info(">>> 4. INN ko'rsatilmagan ('000') kvitansiyani adminga uzatish testi...")

    user_memory.clear_context(chat_id=555, user_id=666)

    # 1. Chekda INN "000" deb ko'rsatilgan kvitansiya
    receipt_zero_inn = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=100000.0,
        payer_inn="000", # Bo'sh/dummy INN
        payer_name="Noma'lum to'lovchi",
        transaction_id="TX-998877",
        payment_system="Click",
        raw_text="Mars Elektron Texnika uchun 100 000 so'm to'lov"
    )

    decision = core_engine.process_receipt_facts(
        facts=receipt_zero_inn,
        chat_id=555,
        user_id=666,
        user_comment=""
    )

    assert decision.action == ActionType.RECEIPT_PROCESSED
    # Foydalanuvchiga INN so'rovi yuborilishi shart
    assert "korxonangizning INN" in (decision.reply_text or "")
    # Adminga xabarnoma chiqishi shart!
    assert decision.should_notify_admin is True
    assert decision.admin_alert_type == "receipt_missing_inn"
    assert decision.debt_status_info.get("inn_missing") is True
    assert decision.debt_status_info.get("inn") is None

    # Pending receipt xotiraga saqlanganini tekshirish
    pending = user_memory.get_pending_receipt(chat_id=555, user_id=666)
    assert pending is not None
    assert pending.get("transaction_id") == "TX-998877"
    assert pending.get("amount") == 100000.0

    logger.info("✅ INN ko'rsatilmagan kvitansiya xotirada saqlandi va adminga uzatish bayrog'i qo'yildi!")


async def test_admin_notification_formatting_for_present_and_missing_inn():
    """Adminga yuboriladigan xabarda pastda alohida <code>{inn}</code> yoki 'INN topilmadi' bo'lishi testi"""
    logger.info(">>> 5. Adminga bildirishnoma matni formatlash testi...")

    bot_mock = MagicMock()
    bot_mock.send_message = AsyncMock()
    bot_mock.send_photo = AsyncMock()

    # Admin ID sini vaqtincha sozlash
    admin_manager.admin_ids = [999999]

    # A) INN mavjud bo'lgan kvitansiya
    receipt_valid = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=200000.0,
        payer_inn="206011507",
        payer_name="Test Korxona",
        transaction_id="TX-1111",
        payment_system="Payme"
    )
    debt_info_valid = {
        "org_name": "Test Korxona",
        "inn": "206011507",
        "inn_missing": False,
        "prev_debt": 200000.0,
        "remaining_debt": 0.0,
        "debt_covered": True
    }

    await admin_manager.notify_receipt_escalation(
        bot=bot_mock,
        user=None,
        chat_id=123,
        receipt_facts=receipt_valid,
        debt_status_info=debt_info_valid,
        file_id="photo_123",
        is_photo=True
    )

    # Adminga yuborilgan xabarni tekshirish
    call_args = bot_mock.send_photo.call_args
    caption = call_args.kwargs.get("caption", "")

    # Pastda alohida nusxa olish bloki bo'lishi shart
    assert "📋 <b>INN (nusxa olish uchun):</b>" in caption
    assert "<code>206011507</code>" in caption
    logger.info("✅ INN mavjud chekda pastda alohida <code>{inn}</code> bloki chiqdi!")

    # B) INN ko'rsatilmagan (topilmagan / 000) kvitansiya
    bot_mock.send_photo.reset_mock()
    debt_info_missing = {
        "org_name": "Noma'lum korxona",
        "inn": None,
        "inn_missing": True,
        "prev_debt": 0.0,
        "remaining_debt": 0.0,
        "debt_covered": False
    }
    receipt_no_inn = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=150000.0,
        payer_inn=None,
        payer_name="Noma'lum",
        transaction_id="TX-2222",
        payment_system="Click"
    )

    await admin_manager.notify_receipt_escalation(
        bot=bot_mock,
        user=None,
        chat_id=123,
        receipt_facts=receipt_no_inn,
        debt_status_info=debt_info_missing,
        file_id="photo_456",
        is_photo=True
    )

    call_args_missing = bot_mock.send_photo.call_args
    caption_missing = call_args_missing.kwargs.get("caption", "")

    assert "⚠️ <b>DIQQAT: Kvitansiyadan INN topilmadi!</b>" in caption_missing
    assert "Chekda INN ko'rsatilmagan yoki '000' bo'sh qoldirilgan" in caption_missing
    logger.info("✅ INN yo'q kvitansiyada adminga 'Kvitansiyadan INN topilmadi' xabari to'g'ri chiqdi!")


def test_pending_receipt_resolution_when_user_subsequently_sends_inn():
    """Mijoz keyinchalik INN yuborganda kvitansiya avtomatik ulanishi va adminga to'liq INN bilan uzatilishi testi"""
    logger.info(">>> 6. Pending kvitansiya mijoz INN yuborganda yechilishi testi...")

    user_memory.clear_context(chat_id=777, user_id=888)

    # 1. INN siz kvitansiya tashladi
    receipt_no_inn = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=1500400.0,
        payer_inn="000", # 000 tashlangan
        payer_name="Qashqadaryo Sharq Gavhari",
        transaction_id="TX-SUCCESS-777",
        payment_system="Click"
    )
    core_engine.process_receipt_facts(receipt_no_inn, chat_id=777, user_id=888)

    # 2. Keyin mijoz "206011507" raqamini yozdi
    decision = core_engine.resolve_pending_receipt_if_any("206011507", chat_id=777, user_id=888)

    assert decision is not None
    assert decision.action == ActionType.RECEIPT_PROCESSED
    assert decision.detected_inn == "206011507"
    assert decision.should_notify_admin is True
    assert decision.debt_status_info.get("inn") == "206011507"
    assert decision.debt_status_info.get("inn_missing") is False
    assert "QASHQADARYO SHARQ GAVHARI" in (decision.reply_text or "")
    logger.info("✅ Pending kvitansiya mijoz INN yozishi bilan 100% muvaffaqiyatli ulandi!")


def test_p3_long_messages_tax_debt_and_freeform():
    """
    1) Excelda P3 apparatlar sariq qator (is_p3=True), SmartPOS apparatlar esa oq qator (is_p3=False) ekanligini tekshirish.
    2) P3 apparatda (sariq qator) ekranda yozilgan aniq xabar qisqa ta'riflab berilishi va soat so'ralmasligi.
    3) SmartPOS apparatda (oq qator) ekrandagi muammoga aloqasiz gaplar HECH QACHON shunchaki o'qib berilmasligi,
       soat ko'rinmasa to'liq ekran so'ralishi, soat/internet xato bo'lsa aniq qoida ishlashi testi.
    """
    from error_manager import error_manager

    error_manager.load_rules()
    logger.info(">>> 7. Excel sariq qator (P3) va oq qator (SmartPOS) qat'iy ajratilishi testi...")

    # A) Excel ranglar tekshiruvi: Sariq qator = P3, Oq qator = SmartPOS
    assert excel_manager.is_p3_for_inn("311481235") is True, "311481235 Excelda sariq qator (P3) bo'lishi shart!"
    assert excel_manager.is_p3_for_inn("305758642") is True, "305758642 Excelda sariq qator (P3) bo'lishi shart!"
    assert excel_manager.is_p3_for_inn("206011507") is False, "206011507 Excelda oq qator (SmartPOS) bo'lishi shart!"
    assert excel_manager.is_p3_for_inn("311790999") is False, "311790999 Excelda oq qator (SmartPOS) bo'lishi shart!"

    # B) P3 apparati (INN: 305758642 - sariq qator): Ekranda erkin uzun xabar yozilgan, tepada soat yo'q
    user_memory.clear_context(chat_id=301, user_id=401)
    facts_p3_custom = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False,
        has_internet=False,  # P3 da status bar yo'qligi sababli false kelsa ham
        time_mismatch=True,
        detected_inn="305758642",  # P3 korxona (sariq qator)
        screen_text_summary="Hurmatli foydalanuvchi, OFD tizimida kassa sertifikati muddati tugaganligi sababli chek urish vaqtincha cheklandi."
    )
    dec_p3 = core_engine.process_device_facts(facts_p3_custom, chat_id=301, user_id=401)
    assert dec_p3.action != ActionType.ASK_FULL_SCREEN, "P3 apparatda soat so'ralmasligi shart!"
    assert "sertifikati muddati tugaganligi" in (dec_p3.reply_text or "").lower()
    assert "internetga ulanmagan" not in (dec_p3.reply_text or "").lower()

    # C) P3 ekranda: "Soliq o'chirdi" (Mars oylik abonent qarzdorligi bilan adashmasligi)
    facts_tax = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False,
        detected_inn="305758642",
        screen_text_summary="Hurmatli soliq to'lovchi, ijara shartnomasi bekor qilinganligi sababli kassa apparati soliq organlari tomonidan vaqtincha o'chirilgan."
    )
    dec_tax = core_engine.process_device_facts(facts_tax, chat_id=301, user_id=401)
    assert dec_tax.action != ActionType.ASK_FULL_SCREEN
    assert "ijara shartnomasi" in (dec_tax.reply_text or "").lower()
    assert "oylik servis xizmati to'lovi amalga oshirilmagan" not in (dec_tax.reply_text or "").lower()

    # D) SmartPOS apparati (INN: 311790999 - oq qator, qarzi 0):
    # Ekranda muammoga aloqasiz yozuv bor va tepada soat ko'rinmayapti ->
    # SmartPOS ekranidagi aloqasiz yozuvni O'QIB BERMASLIGI, balki soat va internet qatorini so'rashi SHART!
    user_memory.clear_context(chat_id=302, user_id=402)
    facts_smart_no_clock = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False,
        detected_inn="311790999",  # SmartPOS korxona (oq qator)
        screen_text_summary="Savdo oynasi versiya 4.2.1: Kassa menyusi ochiq, aloqasiz matn"
    )
    dec_smart_ask = core_engine.process_device_facts(facts_smart_no_clock, chat_id=302, user_id=402)
    assert dec_smart_ask.action == ActionType.ASK_FULL_SCREEN, (
        "SmartPOS da tanish xato kodi bo'lmasa va soat ko'rinmasa, aloqasiz yozuvni o'qimasdan to'liq ekran so'rashi shart!"
    )
    assert "versiya 4.2.1" not in (dec_smart_ask.reply_text or "").lower()

    # E) SmartPOS apparati: Ekranda aloqasiz gap yozilgan, lekin tepada soat xato (time_mismatch=True) ->
    # Aloqasiz gapga chalg'imasdan darhol 'Sana va vaqt noto'g'ri' (Video 141) tashxisini qo'yishi shart!
    facts_smart_time = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=True,
        time_mismatch=True,
        has_internet=True,
        screen_text_summary="Kassa menyusi: Tovarlar ro'yxati bo'sh"
    )
    dec_smart_time = core_engine.process_device_facts(facts_smart_time, chat_id=303, user_id=403)
    assert dec_smart_time.action == ActionType.DIAGNOSE_AND_REPLY
    assert dec_smart_time.video_id == 141
    assert "tovarlar ro'yxati bo'sh" not in (dec_smart_time.reply_text or "").lower()

    logger.info("✅ Excel sariq qator (P3) va oq qator (SmartPOS) 100% bexato ajratildi, SmartPOS aloqasiz yozuvlarni o'qimaydi!")


if __name__ == "__main__":
    test_extract_clean_inn_rejects_dummies()
    test_p3_device_without_status_bar_diagnoses_screen_error()
    test_pos_device_without_error_and_without_status_bar_asks_for_clock()
    test_receipt_with_missing_or_zero_inn_notifies_admin_immediately()
    asyncio.run(test_admin_notification_formatting_for_present_and_missing_inn())
    test_pending_receipt_resolution_when_user_subsequently_sends_inn()
    test_p3_long_messages_tax_debt_and_freeform()
    print("\n🎉 BARCHA P3 VA KVITANSIYA INN TESTLARI 100% MUVAFFAQIYATLI O'TDI!")
