import logging
from unittest.mock import patch

from user_memory import user_memory
from core.models import ReceiptFacts, DecisionResult, ActionType
from core.engine import core_engine
from ai_helper import generate_ai_reply
from handlers.debt import format_debt_response
from excel_manager import excel_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_deep_user_context")

def test_single_user_multi_turn_deep_context():
    logger.info("=================================================================")
    logger.info(">>> 1. YAGONA MIJOZNING CHUQUR DAVOMIY KONTEKST TESTI...")
    logger.info("=================================================================")

    chat_id = -100777888
    ali_user_id = 1001
    ali_inn = "206011507"

    # Step 1: Ali INN tekshirdi
    results = excel_manager.search(ali_inn)
    org_name = results[0].get("name", "")
    total_debt = sum(item.get("debt", 0.0) for item in results)
    user_memory.set_last_id(chat_id, ali_user_id, ali_inn, org_name=org_name, debt=total_debt)
    user_memory.add_user_message(chat_id, ali_user_id, f"Mening INN raqamim: {ali_inn}")
    user_memory.add_assistant_message(chat_id, ali_user_id, f"Korxona: {org_name}, Qarz: {total_debt:,.0f} so'm")

    assert user_memory.get_last_id(chat_id, ali_user_id) == ali_inn
    logger.info(f"1-bosqich: Ali INN kiritdi -> {org_name} ({total_debt:,.0f} so'm qarz)")

    # Step 2: Ali kvitansiya tashladi (1 500 400 so'm)
    receipt_facts = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=total_debt,
        payer_inn=ali_inn,
        payer_name=org_name,
        payment_date="2026-10-10 15:00"
    )
    decision = core_engine.process_receipt_facts(
        facts=receipt_facts,
        chat_id=chat_id,
        user_id=ali_user_id,
        user_comment="Mana to'lov cheki"
    )
    user_memory.add_user_message(chat_id, ali_user_id, "[To'lov kvitansiyasi: 1,500,400 so'm]")
    user_memory.add_assistant_message(chat_id, ali_user_id, decision.reply_text or "")

    last_rec = user_memory.get_last_receipt(chat_id, ali_user_id)
    assert last_rec is not None, "Kvitansiya xotiraga saqlanmadi"
    assert last_rec.get("debt_covered") is True, "Qarz yopilmadi deb hisoblandi"
    logger.info("2-bosqich: Kvitansiya qabul qilindi va qarz 100% yopildi!")

    # Step 3: Ali so'raydi: "qachon qo'shiladi?"
    context_ali = user_memory.get_context_summary(chat_id, ali_user_id)
    assert ali_inn in context_ali
    assert "Qayta INN so'rash qat'iyan taqiqlanadi" in context_ali
    assert "To'lov mavjud barcha qarzni TO'LIQ yopdi" in context_ali

    reply_text, video_id = generate_ai_reply("qachon qo'shiladi?", context_history=context_ali)
    logger.info(f"3-bosqich javobi ('qachon qo'shiladi?'):\n-> {reply_text}")

    # TEKSHIRUV: Qaytadan INN so'ramasligi va to'lov yoqilishi haqida tushuntirishi shart!
    lower_rep = reply_text.lower()
    assert "inn" not in lower_rep or "inn raqam" not in lower_rep, "XATO: Qaytadan INN so'raldi!"
    assert any(w in lower_rep for w in ["adminga", "operator", "tasdiq", "yoqiladi", "faollash", "kut"]), "XATO: To'lov aktivlashuvi haqida aytilmadi!"

    user_memory.add_user_message(chat_id, ali_user_id, "qachon qo'shiladi?")
    user_memory.add_assistant_message(chat_id, ali_user_id, reply_text)

    # Step 4: Ali so'raydi: "keyingi to'lovni qachon qilaman?"
    context_ali = user_memory.get_context_summary(chat_id, ali_user_id)
    reply_text_next, _ = generate_ai_reply("keyingi to'lovni qachon qilaman?", context_history=context_ali)
    logger.info(f"4-bosqich javobi ('keyingi to'lovni qachon qilaman?'):\n-> {reply_text_next}")

    lower_rep_next = reply_text_next.lower()
    assert "inn" not in lower_rep_next or "inn raqam" not in lower_rep_next, "XATO: Qaytadan INN so'raldi!"
    assert "6" in lower_rep_next or "oy" in lower_rep_next, "XATO: 6-sana yoki kelgusi oy aytilmadi!"

    logger.info("✅ Yagona mijozning barcha davomiy suhbat savollari xatosiz o'tdi!")


def test_concurrent_users_isolation():
    logger.info("\n=================================================================")
    logger.info(">>> 2. KONKURRENT MIJOZLARNING KONTEKST BO'LINISHI TESTI...")
    logger.info("=================================================================")

    chat_id = -100777888 # Aynan bitta umumiy guruh!
    ali_id = 1001
    vali_id = 2002 # Yangi foydalanuvchi

    # Ali allaqachon ma'lumot kiritgan (Step 1 dan)
    assert user_memory.get_last_id(chat_id, ali_id) == "206011507"

    # Vali esa hech narsa kiritmagan yangi odam
    assert user_memory.get_last_id(chat_id, vali_id) is None
    assert user_memory.get_last_receipt(chat_id, vali_id) is None

    # Vali guruhda yozadi: "qachon qo'shiladi?"
    context_vali = user_memory.get_context_summary(chat_id, vali_id)
    reply_vali, _ = generate_ai_reply("qachon qo'shiladi?", context_history=context_vali)
    logger.info(f"Vali (noma'lum) javobi ('qachon qo'shiladi?'):\n-> {reply_vali}")

    # Valiga begona Ali ning korxonasi yoki to'lovi chiqmasligi, INN so'rashi shart!
    assert "QASHQADARYO" not in reply_vali, "XATO: Alining korxonasi Valiga ko'rinib ketdi!"
    assert "206011507" not in reply_vali, "XATO: Alining INN raqami Valiga ko'rinib ketdi!"

    # Ali esa o'sha paytda yozadi: "rahmat"
    context_ali = user_memory.get_context_summary(chat_id, ali_id)
    reply_ali, _ = generate_ai_reply("rahmat katta", context_history=context_ali)
    logger.info(f"Ali (taniqli) javobi ('rahmat'):\n-> {reply_ali}")

    # Ali ga "arzimaydi" deb samimiy javob berilishi kerak
    assert "arzimaydi" in reply_ali.lower() or "xursand" in reply_ali.lower() or "salomat" in reply_ali.lower()

    logger.info("✅ Konkurrent mijozlar konteksti 100% mustaqil va aralashmadi!")

if __name__ == "__main__":
    test_single_user_multi_turn_deep_context()
    test_concurrent_users_isolation()
    print("\n🎉 BARCHA CHUQUR KONTEKST VA MULTI-TURN TESTLARI MUVAFFAQIYATLI O'TDI!")
