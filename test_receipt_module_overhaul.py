import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from core import core_engine
from core.models import ReceiptFacts
from user_memory import user_memory as memory
from transaction_tracker import transaction_tracker as tracker
from image_analyzer import analyze_media_image


async def run_tests():
    print("=" * 70)
    print("🧪 KVITANSIYA MODULI TO'LIQ AVTOMATIK TESTLARI (OVERHAUL)")
    print("=" * 70)

    chat_id = -1003742874507
    uid = 99887766
    memory.sessions.pop(f"{chat_id}:{uid}", None)

    # 1. User checks INN 307314860 first (debt = 2,100,000 so'm)
    print("\n--- TEST 1: User avval INN 307314860 qarzini tekshiradi (2,100,000 so'm) ---")
    memory.set_last_id(chat_id, uid, "307314860", org_name='"MARS SMART SALE" МЧЖ', debt=2100000.0)
    sess = memory._get_or_create_session(chat_id, uid)
    assert sess["debt_info"]["debt"] == 2100000.0
    print("✅ Session INN: 307314860, Qarzdorlik: 2,100,000 so'm")

    # 2. Real receipt from group (/tmp/group_msg_1139.jpg): 08.10.2026, 100,000 so'm, INN 32108755590021
    print("\n--- TEST 2: Guruhga tashlangan haqiqiy kvitansiya (/tmp/group_msg_1139.jpg) Vision + Engine tahlili ---")
    with open("/tmp/group_msg_1139.jpg", "rb") as f:
        img_bytes = f.read()
    m_type, r_facts, d_facts = analyze_media_image(img_bytes, user_caption="", mime_type="image/jpeg")
    print(f"Vision media_type: {m_type}, r_facts: {r_facts}")
    assert m_type == "receipt" and r_facts is not None and r_facts.is_receipt, f"Expected receipt, got {m_type}"

    res1 = core_engine.process_receipt_facts(
        facts=r_facts,
        chat_id=chat_id,
        user_id=uid,
        user_comment="",
        file_id="test_file_1",
        is_photo=True
    )
    print("Userga qaytgan javob:", res1.reply_text)
    print("Admin debt_status_info:", res1.debt_status_info)

    # Verify user reply is simple and does NOT say debt is 0 or apparat yoqiladi
    assert "Kvitansiyangiz qabul qilindi va tekshirish uchun mas'ul adminga yuborildi" in res1.reply_text
    assert "0 so'm" not in res1.reply_text
    assert "bartaraf" not in res1.reply_text
    assert "Oldindan to'lov" not in res1.reply_text

    # Verify session INN and debt were NOT overwritten!
    sess_after = memory._get_or_create_session(chat_id, uid)
    assert sess_after["last_id"] == "307314860", f"Session INN buzildi: {sess_after['last_id']}"
    assert sess_after["debt_info"]["debt"] == 2100000.0, f"Session qarzi 0 bo'lib qoldi: {sess_after['debt_info']['debt']}"
    print("✅ User xotirasidagi INN (307314860) va qarz (2,100,000 so'm) buzilmadi!")

    # Verify admin escalation payload
    dsi1 = res1.debt_status_info
    assert res1.should_notify_admin is True
    assert dsi1["is_old_receipt"] is True, f"08.10.2026 kvitansiyasi ESKI deb belgilanishi shart! Got: {dsi1}"
    assert dsi1["inn_mismatch"] is True
    assert dsi1["session_inn"] == "307314860"
    assert dsi1["prev_debt"] == 2100000.0
    assert dsi1["debt_covered"] is False
    print("✅ Adminga ESKI KVITANSIYA + INN MOS EMAS + 2,100,000 so'm qarz haqida aniq hisobot tayyorlandi!")

    # 3. Test Today's Receipt - Partial Payment (100,000 so'm vs 2,100,000 so'm debt)
    print("\n--- TEST 3: Bugungi kvitansiya (qarzni to'liq yopmaydigan to'lov: 100,000 vs 2,100,000) ---")
    today_str = datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%d.%m.%Y")
    is_old_today, reason_today = tracker.check_old_receipt(today_str)
    assert is_old_today is False, f"Bugungi sana ({today_str}) eski deb topilmasligi kerak!"

    facts_today_partial = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        payment_category="monthly",
        recipient_org_name="«Mars Elektron Texnika» MCHJ",
        amount=100000.0,
        payer_inn="307314860",
        payer_name='"MARS SMART SALE" МЧЖ',
        payment_date=today_str,
        transaction_id="TX_PARTIAL_001",
        payment_system="Bank",
        raw_text="Abonent to'lovi 100000 so'm"
    )
    res2 = core_engine.process_receipt_facts(
        facts=facts_today_partial,
        chat_id=chat_id,
        user_id=uid,
        user_comment="",
        file_id="test_file_2",
        is_photo=True
    )
    assert "Kvitansiyangiz qabul qilindi va tekshirish uchun mas'ul adminga yuborildi" in res2.reply_text
    dsi2 = res2.debt_status_info
    assert dsi2["is_old_receipt"] is False
    assert dsi2["inn_mismatch"] is False
    assert dsi2["prev_debt"] == 2100000.0
    assert dsi2["remaining_debt"] == 2000000.0
    assert dsi2["debt_covered"] is False
    assert memory._get_or_create_session(chat_id, uid)["debt_info"]["debt"] == 2100000.0
    print("✅ Bugungi qisman to'lov: Adminga QARZNI TO'LIQ YOPMAYDI (qoldiq 2,000,000) deb ketdi, userga oddiy javob qaytdi!")

    # 4. Test Today's Receipt - Full Payment (2,100,000 so'm vs 2,100,000 so'm debt)
    print("\n--- TEST 4: Bugungi kvitansiya (qarzni to'liq yopadigan to'lov: 2,100,000 vs 2,100,000) ---")
    facts_today_full = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        payment_category="monthly",
        recipient_org_name="«Mars Elektron Texnika» MCHJ",
        amount=2100000.0,
        payer_inn="307314860",
        payer_name='"MARS SMART SALE" МЧЖ',
        payment_date=today_str,
        transaction_id="TX_FULL_002",
        payment_system="Bank",
        raw_text="Abonent to'lovi 2100000 so'm"
    )
    res3 = core_engine.process_receipt_facts(
        facts=facts_today_full,
        chat_id=chat_id,
        user_id=uid,
        user_comment="",
        file_id="test_file_3",
        is_photo=True
    )
    assert "Kvitansiyangiz qabul qilindi va tekshirish uchun mas'ul adminga yuborildi" in res3.reply_text
    dsi3 = res3.debt_status_info
    assert dsi3["is_old_receipt"] is False
    assert dsi3["inn_mismatch"] is False
    assert dsi3["prev_debt"] == 2100000.0
    assert dsi3["remaining_debt"] == 0.0
    assert dsi3["debt_covered"] is True
    # Kunlik Excel yangilanmaguncha xotiradagi Excel qarzi o'zgarmasligi kerak:
    assert memory._get_or_create_session(chat_id, uid)["debt_info"]["debt"] == 2100000.0
    print("✅ Bugungi to'liq to'lov: Adminga QARZNI TO'LIQ YOPADI deb ketdi, userga oddiy javob qaytdi, kunlik Excel qarzi buzilmadi!")

    # 5. Test Cumulative Receipts (Qismlab to'lash: 1,000,000 + 1,100,000 = 2,100,000)
    print("\n--- TEST 5: Qismlab to'lash (1,000,000 + 1,100,000 = 2,100,000 so'm qarzni yopishi) ---")
    memory.sessions.pop(f"{chat_id}:{uid}", None)
    memory.set_last_id(chat_id, uid, "307314860", org_name='"MARS SMART SALE" МЧЖ', debt=2100000.0)

    # 1-qism: 1,000,000 so'm
    facts_part1 = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        payment_category="monthly",
        recipient_org_name="«Mars Elektron Texnika» MCHJ",
        amount=1000000.0,
        payer_inn="307314860",
        payer_name='"MARS SMART SALE" МЧЖ',
        payment_date=today_str,
        transaction_id="TX_PART_A",
        payment_system="Bank",
        raw_text="1-qism to'lov"
    )
    res_part1 = core_engine.process_receipt_facts(facts_part1, chat_id, uid, file_id="f_p1")
    assert res_part1.debt_status_info["debt_covered"] is False
    assert res_part1.debt_status_info["remaining_debt"] == 1100000.0

    # 2-qism: 1,100,000 so'm
    facts_part2 = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        payment_category="monthly",
        recipient_org_name="«Mars Elektron Texnika» MCHJ",
        amount=1100000.0,
        payer_inn="307314860",
        payer_name='"MARS SMART SALE" МЧЖ',
        payment_date=today_str,
        transaction_id="TX_PART_B",
        payment_system="Bank",
        raw_text="2-qism to'lov"
    )
    res_part2 = core_engine.process_receipt_facts(facts_part2, chat_id, uid, file_id="f_p2")
    assert res_part2.debt_status_info["debt_covered"] is True
    assert res_part2.debt_status_info["remaining_debt"] == 0.0
    print("✅ Qismlab to'lash: 2-kvitansiyadan keyin umumiy summa qarzni to'liq yopgani muvaffaqiyatli aniqlandi!")

    # 6. Test Fast Duplicate Suppression (Spam himoyasi)
    print("\n--- TEST 6: Takroriy kvitansiya spamidan himoya (1 soat ichida bir xil tranzaksiya) ---")
    res_dup = core_engine.process_receipt_facts(facts_part2, chat_id, uid, file_id="f_p2_dup")
    assert "avval qabul qilingan" in res_dup.reply_text
    assert res_dup.should_notify_admin is False
    print("✅ Dublikat kvitansiya: Userga 'avval qabul qilingan' deb javob berildi, adminga spam yuborilmadi!")

    # 7. Test Annual Receipt with Fiscal Module linked
    print("\n--- TEST 7: Yillik to'lov kvitansiyasiga xotiradagi Fiskal Modul ulanishi ---")
    memory.set_last_fm(chat_id, uid, "LG123456789012")
    facts_annual = ReceiptFacts(
        is_receipt=True,
        recipient_account="20210000100431200010",
        is_mars_recipient=False,
        is_annual_fiscal_fee=True,
        payment_category="annual",
        recipient_org_name="«Yangi Texnologiyalar» DUK",
        amount=440000.0,
        payer_inn="307314860",
        payer_name='"MARS SMART SALE" МЧЖ',
        payment_date=today_str,
        transaction_id="TX_ANN_001",
        payment_system="Click",
        raw_text="Yillik soliq tolovi"
    )
    res_ann = core_engine.process_receipt_facts(facts_annual, chat_id, uid, file_id="f_ann")
    assert res_ann.debt_status_info["fiscal_module"] == "LG123456789012"
    print("✅ Yillik kvitansiya: Xotiradagi Fiskal modul (LG123456789012) adminga uzatiladigan hisobotga ulandi!")

    memory.sessions.pop(f"{chat_id}:{uid}", None)
    print("\n🎉 BARCHA YANGI SENARIY VA TESTLAR 100% MUVAFFAQIYATLI O'TDI!")


if __name__ == "__main__":
    asyncio.run(run_tests())
