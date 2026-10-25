import logging
from unittest.mock import MagicMock, patch

from core.models import DeviceFacts, ReceiptFacts, ActionType
from core.engine import core_engine, INCOMPLETE_SCREEN_REPLY
from image_analyzer import analyze_media_image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_receipt_routing")

def test_device_facts_auto_redirect_receipt():
    """
    Kvitansiya rasmi qandaydir sabab bilan process_device_facts ga tushib qolganda ham,
    'ekran tepasida soat yo'q' deb javob bermasligi, balki kvitansiya sifatida qabul qilinishi testi.
    """
    logger.info(">>> 1. Kvitansiya matni bo'lganda process_device_facts avto-yo'naltirish testi...")
    
    # Kvitansiya ma'lumotlari bo'lgan fakt (status bar ko'rinmagan)
    fake_device_facts = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False, # Status bar yo'q
        screen_text_summary="Click orqali to'lov amalga oshirildi. Summa 150 000 so'm. Mars Elektron Texnika",
        detected_inn="206011507"
    )

    decision = core_engine.process_device_facts(
        facts=fake_device_facts,
        chat_id=12345,
        user_id=67890,
        user_comment=""
    )

    # Bu holatda ASK_FULL_SCREEN ("ekran tepasida soat yo'q") bo'lmasligi shart!
    assert decision.action != ActionType.ASK_FULL_SCREEN, "XATOLIK: Kvitansiyaga soat yo'q deb javob berildi!"
    assert decision.action == ActionType.RECEIPT_PROCESSED, f"Kvitansiya sifatida qabul qilinmadi: {decision.action}"
    assert "soat va internet belgisi" not in (decision.reply_text or "")
    assert "qabul qilindi" in (decision.reply_text or "").lower()
    logger.info("✅ Kvitansiya avtomatik aniqlanib, qarz solishtirildi va soat so'ralmadi!")


def test_p3_pos_device_screen_error_diagnosed_without_status_bar():
    """P3 model kassa apparatida status bar bo'lmaganda ham ekrandagi xatolik bo'yicha tashxis qo'yilishi testi"""
    logger.info(">>> 2. P3 apparati: status bar yo'q, lekin ekranda xatolik bor -> Ekrandan yechish testi...")
    
    p3_device_facts = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False, # P3 da soat qatori yo'q
        screen_text_summary="Smena 24 soatdan oshgan",
        detected_inn="305758642"
    )

    decision = core_engine.process_device_facts(
        facts=p3_device_facts,
        chat_id=12345,
        user_id=67890
    )

    # Ekrandagi yozuv bo'yicha hal qilinishi kerak, soat so'ralmasligi shart!
    assert decision.action != ActionType.ASK_FULL_SCREEN, "XATOLIK: P3 apparatidagi ekranga soat yo'q deb javob berildi!"
    assert decision.action in [ActionType.DIAGNOSE_AND_REPLY, ActionType.ESCALATE_TO_ADMIN, ActionType.DEBT_INFO]
    assert any(w in (decision.reply_text or "") for w in ["AVTORUM", "Smena", "24 soat", "qarzdorlik yo'q", "Fiskal modul"])
    logger.info("✅ P3 apparatida ekrandagi yozuvdan tashxis qo'yildi va soat qatori so'ralmadi.")


def test_pos_device_without_error_and_without_status_bar_asks_for_clock():
    """Ekrandan muammo topilmaganda va status bar bo'lmaganda soat va tarmoq qatori so'ralishi testi"""
    logger.info(">>> 2b. Ekrandan muammo aniqlanmaganda status bar talab qilinishi testi...")
    
    pos_device_facts = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False,
        screen_text_summary="",
        error_type="none",
        detected_inn=None # Ekrandan INN ham, xatolik ham aniqlanmadi
    )

    decision = core_engine.process_device_facts(
        facts=pos_device_facts,
        chat_id=99999,
        user_id=88888
    )

    assert decision.action == ActionType.ASK_FULL_SCREEN
    assert "INN" in (decision.reply_text or "") or decision.reply_text == INCOMPLETE_SCREEN_REPLY
    logger.info("✅ Ekrandan muammo topilmaganda soat va status bar so'ralishi to'g'ri ishladi.")


def test_analyze_media_image_receipt_mock():
    """Mock qilingan OpenRouter javobi bilan analyze_media_image tahlili"""
    logger.info(">>> 3. analyze_media_image kvitansiyani to'g'ri ajratishi testi...")
    
    mock_ai_json = '''{
        "media_type": "receipt",
        "receipt": {
            "recipient_account": "20208000800208044003",
            "is_mars_recipient": true,
            "amount": 200000.0,
            "payer_inn": "206011507",
            "payer_name": "Test MCHJ",
            "payment_system": "Click",
            "summary": "Mars Elektron Texnika uchun to'lov"
        },
        "device": null
    }'''

    with patch("openrouter_client.openrouter_client.chat_completion", return_value=mock_ai_json):
        m_type, r_facts, d_facts = analyze_media_image(b"fake_image_bytes", user_caption="")
        
        assert m_type == "receipt"
        assert r_facts is not None
        assert r_facts.is_receipt is True
        assert r_facts.amount == 200000.0
        assert r_facts.payer_inn == "206011507"
        assert d_facts is None

    logger.info("✅ analyze_media_image kvitansiyani 100% to'g'ri ajratdi!")

if __name__ == "__main__":
    test_device_facts_auto_redirect_receipt()
    test_p3_pos_device_screen_error_diagnosed_without_status_bar()
    test_pos_device_without_error_and_without_status_bar_asks_for_clock()
    test_analyze_media_image_receipt_mock()
    print("\n🎉 BARCHA ROUTING VA KVITANSIYA TESTLARI MUVAFFAQIYATLI O'TDI!")
