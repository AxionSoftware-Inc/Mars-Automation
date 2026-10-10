import logging
from error_manager import error_manager
from core.engine import core_engine
from core.models import DeviceFacts, ActionType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_errors")

def test_all_22_errors_loaded():
    logger.info(">>> 1. 22 TA XATOLIKNING BAZAGA YUKLANISHI TESTI...")
    rules = error_manager.get_all_rules()
    logger.info(f"Bazada jami {len(rules)} ta xatolik qoidasi mavjud.")
    assert len(rules) >= 22, f"Kamida 22 ta qoida bo'lishi kerak, hozir: {len(rules)}"
    
    # Muhim qoidalar mavjudligini tekshirish
    expected_ids = [
        "time_error", "shift_exceeded_24h", "no_internet", "fiscal_module_error",
        "annual_fm_expired", "debt_blocked", "paper_out", "update_required",
        "cancel_check_error", "mxik_code_error", "battery_low", "unsent_checks_limit",
        "card_read_error", "password_blocked", "app_crash_freeze", "gps_location_error",
        "scanner_barcode_error", "markirovka_error", "code_102_hardware",
        "code_201_tax_server", "code_300_storage", "fatal_hardware_damage"
    ]
    for eid in expected_ids:
        rule = error_manager.get_rule_by_id(eid)
        assert rule is not None, f"Qoida topilmadi: {eid}"
        assert len(rule.get("screen_keywords", [])) > 0, f"Kalit so'zlar bo'sh: {eid}"
        assert rule.get("response_text") != "", f"Yechim matni bo'sh: {eid}"
    logger.info("✅ Barcha 22 ta asosiy xatolik qoidalari to'liq yuklangan va soz!")

def test_screen_error_matching():
    logger.info(">>> 2. HAR XIL EKRAN XATOLIKLARI MOSLIGI (MATCHING) TESTI...")
    
    test_cases = [
        # (ekrandagi yozuv/kod, kutilgan qoida ID si)
        ("Ekranda yozuv: Смена превысила 24 часа. Сделайте Z-отчет", "shift_exceeded_24h"),
        ("Xatolik kodi: Kod 204. FM javob bermayapti", "fiscal_module_error"),
        ("Bosh menyuda: Yillik to'lov muddati tugagan (Yangi texnologiyalar)", "annual_fm_expired"),
        ("Ekranda: Qog'oz tugadi (Нет бумаги). Lentani tekshiring", "paper_out"),
        ("Chek urishda: Vozvrat чека / chekni bekor qilish", "cancel_check_error"),
        ("Diqqat: Kod 102 ichki mikrokontroller xatosi", "code_102_hardware"),
        ("Xavfsizlik: Tamper detected! Apparat bloklandi", "fatal_hardware_damage"),
        ("Tovar qo'shishda: MXIK topilmadi / Tasnif kod xato", "mxik_code_error"),
        ("Batareya: Low battery / Quvvat kam qoldi", "battery_low"),
        ("Skanerlashda: 2D shtrix kod skaner ishlamayapti", "scanner_barcode_error"),
        ("Markirovka: Asllik belgisi DataMatrix o'qilmadi", "markirovka_error"),
        ("Offline rejim: Jo'natilmagan cheklar yig'ilib qolgan", "unsent_checks_limit")
    ]

    for screen_text, expected_id in test_cases:
        facts_dict = {"screen_text_summary": screen_text}
        matched = error_manager.match_error(facts_dict)
        assert matched is not None, f"Mos qoida topilmadi: '{screen_text}'"
        assert matched.get("id") == expected_id, f"Kutilgan {expected_id}, lekin {matched.get('id')} topildi ('{screen_text}')"
        logger.info(f"   [OK] '{screen_text[:35]}...' -> {matched.get('name')}")

    logger.info("✅ Barcha turli xatoliklar kalit so'zlari bo'yicha 100% to'g'ri tanildi!")

def test_fatal_hardware_escalation():
    logger.info(">>> 3. JIDDIY APPARAT NOSOZLIGIDA AVTOMATIK ADMINGA ESKALATSIYA TESTI...")
    # Apparat zarba yeb tamper datchigi tushgan
    facts = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=True,
        time_mismatch=False,
        has_internet=True,
        error_type="hardware_tamper",
        screen_text_summary="Tamper detected! Xavfsizlik bloklandi",
        raw_facts={"screen_text_summary": "Tamper detected! Xavfsizlik bloklandi"}
    )
    decision = core_engine.process_device_facts(facts, chat_id=-1001, user_id=99)
    assert decision.action == ActionType.ESCALATE_TO_ADMIN
    assert decision.should_notify_admin is True
    assert decision.admin_alert_type == "tech_issue"
    assert "TAMPER DETECTED" in decision.reply_text
    assert "bosh administratorimizga (@Yashnarbek_butaev) hamda ustalariga yetkazildi" in decision.reply_text
    logger.info("✅ Jiddiy texnik nosozlik (Tamper) adminga to'g'ri eskalatsiya qilindi!")

def test_add_and_delete_rule():
    logger.info(">>> 4. YANGI QOIDA QO'SHISH VA O'CHIRISH TESTI...")
    test_id = "test_custom_err_99"
    error_manager.add_or_update_rule(
        rule_id=test_id,
        name="Test xatoligi 99",
        screen_keywords=["xato 99", "custom error 99"],
        response_text="Bu maxsus sinov xatoligi matni",
        video_id=2
    )
    assert error_manager.get_rule_by_id(test_id) is not None
    
    # Match test
    matched = error_manager.match_error({"screen_text_summary": "Ekranda xato 99 chiqdi"})
    assert matched is not None and matched.get("id") == test_id
    
    # Delete test
    error_manager.delete_rule(test_id)
    assert error_manager.get_rule_by_id(test_id) is None
    logger.info("✅ Yangi qoida qo'shish va o'chirish muvaffaqiyatli ishladi!")

def main():
    logger.info("=================================================================")
    logger.info("🚀 KASSA EKRAN NOSOZLIKLARI: 22 TA XATOLIK TEST SUITE")
    logger.info("=================================================================")
    test_all_22_errors_loaded()
    test_screen_error_matching()
    test_fatal_hardware_escalation()
    test_add_and_delete_rule()
    logger.info("=================================================================")
    logger.info("🎉 BARCHA EKRAN XATOLIKLARI TESTLARI 100% MUVAFFAQIYATLI O'TDI!")
    logger.info("=================================================================")

if __name__ == "__main__":
    main()
