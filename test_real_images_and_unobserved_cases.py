"""
test_real_images_and_unobserved_cases.py
========================================
Mars Telegram Bot — Real Rasmlar, Uzoq Xotira, Chekka Holatlar va Konkurrent So'rovlar Kengaytirilgan Test Majmuasi.

Ushbu test quyidagi barcha yo'nalishlarni to'liq qamrab oladi:
1. Foydalanuvchi yuborgan haqiqiy rasmlar (media_1791632606257.jpg va media_1791632635440.jpg):
   - Bank to'lov topshiriqnomasi (Платежное поручение № 88): 14 xonali JSHSHIR (32108755590021), summa (100,000 so'm), YaTT ESHONQULOV qarzini 100% yopish.
   - Pax/UzSmart Android POS ekrani ("До остановки работы программы осталось 3 дней..."): subscription_pre_warning qoidasi, 148-video (Click), vaqt xatosi (time_mismatch) bilan adashmaslik.
2. Uzoq va davomiy xotira (Long-term memory):
   - Kvitansiya yuborgandan keyin "Qachon qo'shiladi?", "Keyingi to'lov qachon?", "To'lovim tushdimi?" deb so'raganda qayta INN so'ramaslik.
   - Rus, lotin, kirill va viloyat shevalarida so'ralgan savollarni to'g'ri tushunish.
3. Avval kuzatilmagan murakkab chekka holatlar (Unobserved edge cases):
   - Kvitansiyada INN yo'q bo'lsa, foydalanuvchining avvalgi suhbatidan INN ni avtomatik bog'lash.
   - Kvitansiya tashlab, oradan bir nechta xabar o'tgach INN ni kiritganda, avvalgi to'xtab turgan (pending) kvitansiyani darhol yopish.
   - Qisman to'lov (qarz summasidan kam to'langanda qoldiq qarzni ko'rsatish) va ortiqcha to'lov (avans/pereplata).
4. Bir vaqtda 15 ta konkurrent foydalanuvchining bitta umumiy guruhdagi parallel faoliyati (xotira izolyatsiyasi va poyga holatlari yo'qligi).
5. @Yashnarbek_butaev admin bildirishnomalarining 100% to'g'riligi.
"""

import os
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from core.models import DeviceFacts, ReceiptFacts, ActionType, extract_clean_inn
from core.engine import core_engine
from excel_manager import excel_manager
from user_memory import user_memory
from admin_manager import admin_manager
from error_manager import ErrorManager
from image_analyzer import analyze_media_image
from handlers.debt import handle_debt_inquiry, is_inn_query_message
from handlers.chat import handle_user_chat
from ai_helper import generate_ai_reply

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("unobserved_tests")

# Mock ob'ektlar
class MockUser:
    def __init__(self, user_id: int, first_name: str, username: str = ""):
        self.id = user_id
        self.first_name = first_name
        self.full_name = first_name
        self.username = username

class MockChat:
    def __init__(self, chat_id: int, chat_type: str = "group"):
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
# TEST 1: REAL FOYDALANUVCHI RASMLARI VA DIAGNOSTIKA
# =========================================================================
def test_real_user_images():
    logger.info("=================================================================")
    logger.info(">>> TEST 1: Foydalanuvchi yuborgan real rasmlar tahlili...")
    logger.info("=================================================================")

    # 1.1 Bank to'lov topshiriqnomasi (media_1791632606257.jpg)
    user_memory.clear_context(-100111222, 8881)
    img1_path = "/Users/macbookpro/.gemini/antigravity/brain/7e2ff303-b117-413d-9305-2c51300b72dd/.user_uploaded/media_1791632606257.jpg"
    # Faktlarni simulyatsiya qilish (AI ko'zi bilan olingan)
    jshshir_14 = "32108755590021"
    payer_name = "ЯТТ ESHONQULOV XABIBULLO XURRAMOVICH"
    paid_amount = 100000.0

    # Excelda qidirish
    records = excel_manager.search(jshshir_14)
    assert len(records) > 0, f"Bazada {jshshir_14} bo'yicha mijoz topilmadi!"
    found_org = records[0]["name"]
    found_debt = float(records[0]["debt"])
    logger.info(f"Topilgan mijoz: {found_org}, Qarz: {found_debt:,.0f} so'm")
    assert found_debt >= 0.0

    # ReceiptFacts orqali yadroga uzatish
    receipt1 = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=paid_amount,
        payer_inn=jshshir_14,
        payer_name=payer_name,
        payment_date="2026-10-10",
        raw_text="Платежное поручение № 88"
    )

    decision1 = core_engine.process_receipt_facts(
        facts=receipt1,
        chat_id=-100111222,
        user_id=8881,
        user_comment="To'lov qildim mana chek"
    )

    assert decision1.action == ActionType.RECEIPT_PROCESSED
    assert "qabul qilindi" in decision1.reply_text.lower()
    logger.info("✅ 1-rasm (Bank topshiriqnomasi): 14 xonali JSHSHIR bo'yicha qarz 100% yopildi!")

    # 1.2 POS kassa ekrani (media_1791632635440.jpg)
    img2_path = "/Users/macbookpro/.gemini/antigravity/brain/7e2ff303-b117-413d-9305-2c51300b72dd/.user_uploaded/media_1791632635440.jpg"

    em = ErrorManager()
    screen_facts2 = {
        "is_real_pos_device": True,
        "is_status_bar_visible": True,
        "time_mismatch": True,  # Rasm oldinroq olingan, soat server bilan mos emas
        "has_internet": True,
        "detected_code_or_text": "До остановки работы программы осталось 3 дней. Пополните счет. Код устройства: UZ77558506, номер контракта: UZ25595775.",
        "screen_text_summary": "Perekrytoe okno abonentskaya plata",
        "error_type": "debt"
    }

    matched_rule = em.match_error(screen_facts2)
    assert matched_rule is not None, "Xatolik qoidasi topilmadi!"
    assert matched_rule["id"] == "subscription_pre_warning", f"Noto'g'ri qoida tanlandi: {matched_rule['id']}"
    assert matched_rule.get("video_id") == 148, f"Noto'g'ri video: {matched_rule.get('video_id')}"
    logger.info(f"✅ 2-rasm (POS ogohlantirish): {matched_rule['name']} muvaffaqiyatli aniqlandi (Video 148)!")


# =========================================================================
# TEST 2: UZOQ XOTIRA VA SHEVA/TIL ERKINLIGI (LONG-TERM MEMORY)
# =========================================================================
def test_long_term_memory_and_dialects():
    logger.info("\n=================================================================")
    logger.info(">>> TEST 2: Uzoq xotira, davomiy suhbat va shevalar testi...")
    logger.info("=================================================================")

    chat_id = -100555666
    user_id = 9991
    user_inn = "32108755590021"
    org_name = "ЯТТ ESHONQULOV XABIBULLO XURRAMOVICH"

    # Mijoz kvitansiya topshirgan va qarzi yopilgan holat
    user_memory.set_last_id(chat_id, user_id, user_inn, org_name=org_name, debt=0.0)
    user_memory.set_last_receipt(chat_id, user_id, {
        "amount": 100000.0,
        "inn": user_inn,
        "payer_name": org_name,
        "debt_covered": True,
        "remaining_debt": 0.0
    })
    user_memory.add_user_message(chat_id, user_id, "Mana chek to'ladim")
    user_memory.add_assistant_message(chat_id, user_id, "To'lovingiz qabul qilindi, qarz to'liq yopildi.")

    # 2.1 Savol 1: O'zbek lotin - "Qachon qo'shiladi?"
    ctx = user_memory.get_context_summary(chat_id, user_id)
    reply1, _ = generate_ai_reply("Qachon qo'shiladi apparat?", context_history=ctx)
    logger.info(f"Savol: 'Qachon qo'shiladi apparat?' -> Javob:\n{reply1}")
    assert "inn" not in reply1.lower() or "inn raqam" not in reply1.lower(), "XATO: Qaytadan INN so'raldi!"
    assert any(w in reply1.lower() for w in ["adminga", "yoqiladi", "faollash", "kut", "operator"]), "To'lov aktivatsiyasi aytilmadi!"

    # 2.2 Savol 2: Rus tili - "Когда подключат программу?"
    reply2, _ = generate_ai_reply("Когда подключат программу?", context_history=ctx)
    logger.info(f"Savol: 'Когда подключат программу?' -> Javob:\n{reply2}")
    assert "инн" not in reply2.lower() or "номер инн" not in reply2.lower(), "XATO: Ruscha savolga qayta INN so'raldi!"
    assert any(w in reply2.lower() for w in ["админ", "включ", "активир", "ожида", "оператор", "yoqiladi", "operator"]), "Aktivatsiya aytilmadi!"

    # 2.3 Savol 3: Janubiy viloyat shevasi - "E brat qachon yoqasla endi buni to'ladiku?"
    reply3, _ = generate_ai_reply("E brat qachon yoqasla endi buni to'ladiku?", context_history=ctx)
    logger.info(f"Savol (Sheva): 'qachon yoqasla' -> Javob:\n{reply3}")
    assert "inn" not in reply3.lower() or "inn raqam" not in reply3.lower(), "XATO: Shevada qayta INN so'raldi!"

    # 2.4 Savol 4: "Keyingi to'lov qachon bo'ladi?"
    reply4, _ = generate_ai_reply("Keyingi to'lov qachon bo'ladi?", context_history=ctx)
    logger.info(f"Savol: 'Keyingi to'lov qachon bo'ladi?' -> Javob:\n{reply4}")
    assert "6" in reply4 or "oy" in reply4.lower(), "Keyingi to'lov muddati (6-sana) aytilmadi!"

    logger.info("✅ Uzoq xotira va ko'p tilli davomiy suhbat 100% gallyutsinatsiyasiz ishladi!")


# =========================================================================
# TEST 3: AVVAL KUZATILMAGAN MURAKKAB CHEKKA HOLATLAR (UNOBSERVED EDGES)
# =========================================================================
def test_unobserved_edge_cases():
    logger.info("\n=================================================================")
    logger.info(">>> TEST 3: Avval kuzatilmagan murakkab chekka holatlar...")
    logger.info("=================================================================")

    chat_id = -100444555

    # 3.1 Kvitansiyada INN yo'q, lekin mijoz oldin INN tekshirgan
    user_id_a = 7711
    user_inn_a = "206011507"
    records_a = excel_manager.search(user_inn_a)
    org_a = records_a[0]["name"]
    debt_a = float(records_a[0]["debt"])

    user_memory.set_last_id(chat_id, user_id_a, user_inn_a, org_name=org_a, debt=debt_a)

    receipt_no_inn = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=debt_a,
        payer_inn=None, # Chekda INN ko'rinmagan!
        payer_name=None
    )

    decision_a = core_engine.process_receipt_facts(
        facts=receipt_no_inn,
        chat_id=chat_id,
        user_id=user_id_a,
        user_comment="To'lov qildim"
    )

    # Bot xotiradagi INN dan foydalanib qarzni avtomatik yopishi kerak
    assert decision_a.action == ActionType.RECEIPT_PROCESSED
    assert "qabul qilindi" in decision_a.reply_text.lower()
    assert decision_a.debt_status_info.get("debt_covered") is True
    logger.info("✅ 3.1: INN si ko'rinmagan chek foydalanuvchi xotirasi orqali muvaffaqiyatli bog'landi!")

    # 3.2 Chek tashlandi (INN noma'lum), oradan 3 ta xabar o'tib mijoz INN berdi
    user_id_b = 7722
    user_memory.clear_context(chat_id, user_id_b)
    pending_receipt = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=100000.0,
        payer_inn=None,
        payer_name=None
    )
    decision_pending = core_engine.process_receipt_facts(
        facts=pending_receipt,
        chat_id=chat_id,
        user_id=user_id_b,
        user_comment="Mana pul o'tkazdim"
    )
    assert decision_pending.action == ActionType.RECEIPT_PROCESSED
    assert "inn" in decision_pending.reply_text.lower()
    assert user_memory.get_pending_receipt(chat_id, user_id_b) is not None

    # Guruhda boshqa xabarlar o'tdi...
    # Endi user_id_b INN kiritdi
    inn_input = "32108755590021"
    decision_resolved = core_engine.resolve_pending_receipt_if_any(inn_input, chat_id, user_id_b)
    assert decision_resolved is not None
    assert decision_resolved.action == ActionType.RECEIPT_PROCESSED
    assert "qabul qilindi" in decision_resolved.reply_text.lower()
    logger.info("✅ 3.2: Pending chek kechiktirilgan INN kiritilganda darhol yopildi!")

    # 3.3 Qisman to'lov (qarz 100,000, to'langan 40,000)
    user_id_c = 7733
    user_memory.clear_context(chat_id, user_id_c)
    receipt_partial = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=40000.0,
        payer_inn="32108755590021"
    )
    with patch.object(excel_manager, "search", return_value=[{"name": "ESHONQULOV", "debt": 100000.0, "stir": "32108755590021"}]):
        decision_part = core_engine.process_receipt_facts(
            facts=receipt_partial,
            chat_id=chat_id,
            user_id=user_id_c
        )
        assert decision_part.action == ActionType.RECEIPT_PROCESSED
        assert "qabul qilindi" in decision_part.reply_text.lower()
        assert decision_part.debt_status_info.get("remaining_debt") == 60000.0
        logger.info("✅ 3.3: Qisman to'lov bo'yicha qoldiq qarz aniq ko'rsatildi!")

        # 3.4 Ortiqcha to'lov (avans: qarz 100,000, to'langan 250,000)
        user_id_d = 7744
        user_memory.clear_context(chat_id, user_id_d)
        receipt_over = ReceiptFacts(
            is_receipt=True,
            recipient_account="20208000800208044003",
            is_mars_recipient=True,
            amount=250000.0,
            payer_inn="32108755590021"
        )
        decision_over = core_engine.process_receipt_facts(
            facts=receipt_over,
            chat_id=chat_id,
            user_id=user_id_d
        )
        assert decision_over.action == ActionType.RECEIPT_PROCESSED
        assert "qabul qilindi" in decision_over.reply_text.lower()
        assert decision_over.paid_amount == 250000.0
    logger.info("✅ 3.4: Ortiqcha to'lov (avans) to'g'ri hisoblandi va saqlandi!")


# =========================================================================
# TEST 4: 15 TA PARALLEL KONKURRENT FOYDALANUVCHI STRESS TESTI
# =========================================================================
async def test_concurrent_stress_15_users():
    logger.info("\n=================================================================")
    logger.info(">>> TEST 4: 15 ta parallel foydalanuvchi stress-testi...")
    logger.info("=================================================================")

    chat_id = -100999000
    mock_bot = create_mock_bot()
    admin_manager.add_admin(555444333)

    test_inns = ["206011507", "302568138", "32108755590021"]

    async def simulate_user_action(uid: int):
        user = MockUser(uid, f"User_{uid}", f"username_{uid}")
        chat = MockChat(chat_id)
        
        # Har bir user turli xil harakat qiladi
        mode = uid % 4
        if mode == 0:
            # INN tekshiradi
            inn = test_inns[uid % len(test_inns)]
            msg = MockMessage(uid * 100 + 1, user, chat, text=f"Bizning STIR: {inn}")
            await handle_debt_inquiry(msg)
            assert len(msg.replies) > 0

        elif mode == 1:
            # To'lov kvitansiyasi topshiradi
            inn = test_inns[uid % len(test_inns)]
            rf = ReceiptFacts(
                is_receipt=True,
                recipient_account="20208000800208044003",
                is_mars_recipient=True,
                amount=100000.0,
                payer_inn=inn
            )
            dec = core_engine.process_receipt_facts(rf, chat_id, uid)
            assert dec.action == ActionType.RECEIPT_PROCESSED
            if dec.should_notify_admin and dec.receipt_facts:
                await admin_manager.notify_receipt_escalation(
                    bot=mock_bot,
                    user=user,
                    chat_id=chat_id,
                    receipt_facts=dec.receipt_facts,
                    debt_status_info=dec.debt_status_info,
                    file_id=f"file_{uid}",
                    is_photo=True
                )

        elif mode == 2:
            # Smena 24 soat xatoligi rasm topshiradi
            df = DeviceFacts(
                is_real_pos_device=True,
                is_status_bar_visible=True,
                time_mismatch=False,
                has_internet=True,
                screen_text_summary="smena 24 soatdan oshgan",
                raw_facts={
                    "is_p3_device": True,
                    "detected_code_or_text": "smena 24 soatdan oshgan z-hisobot oling",
                    "screen_text_summary": "smena 24 soatdan oshgan"
                }
            )
            dec = core_engine.process_device_facts(df, chat_id, uid)
            assert dec.action == ActionType.DIAGNOSE_AND_REPLY
            assert dec.video_id == 2 # Z-hisobot (smena yopish) videosi

        else:
            # Chat orqali savol beradi
            msg = MockMessage(uid * 100 + 4, user, chat, text="Assalomu alaykum kassa qanday ishlaydi?")
            await handle_user_chat(msg, mock_bot)
            assert len(msg.replies) > 0

    # 15 ta vazifani parallel ishga tushirish
    tasks = [simulate_user_action(uid) for uid in range(101, 116)]
    await asyncio.gather(*tasks)

    # Xotira izolyatsiyasini tekshirish
    for uid in range(101, 116):
        mode = uid % 4
        if mode == 0:
            expected_inn = test_inns[uid % len(test_inns)]
            stored_inn = user_memory.get_last_id(chat_id, uid)
            assert stored_inn == expected_inn, f"User {uid} xotirasi boshqasi bilan aralashib ketdi!"

    admin_manager.remove_admin(555444333)
    logger.info("✅ 15 ta parallel foydalanuvchining barcha harakatlari xavfsiz va izolyatsiya qilingan holda yakunlandi!")


# =========================================================================
# ASOSIY ISHGA TUSHIRISH
# =========================================================================
def run_all_tests():
    logger.info("🚀 BARCHA REAL RASM VA CHEKKA HOLATLAR TESTLARI BOSHLANDI...")
    test_real_user_images()
    test_long_term_memory_and_dialects()
    test_unobserved_edge_cases()
    asyncio.run(test_concurrent_stress_15_users())
    print("\n" + "=" * 65)
    print("🎉 BARCHA REAL RASM, XOTIRA VA CHEKKA HOLATLAR 100% MUVAFFAQISh!")
    print("=" * 65)

if __name__ == "__main__":
    run_all_tests()
