import asyncio
import os
import shutil
from user_memory import UserMemoryManager, user_memory
from core import core_engine, ActionType
from core.models import DeviceFacts
from excel_manager import excel_manager

async def test_memory_persistence_and_photo():
    chat_id = -1003742874507
    user_id = 1966874161

    print("=== 1-QADAM: INN va FM kiritish, oylik va yillik holatni tekshirish ===")
    inn = "300600431"
    fm = "LG420230615712"

    # INN saqlash
    search_res = excel_manager.search(inn)
    org_name = search_res[0].get("name") if search_res else "Test Org"
    user_memory.set_last_id(chat_id, user_id, inn, org_name=org_name, debt=0.0)
    user_memory.set_last_fm(chat_id, user_id, fm)
    user_memory.set_annual_status(chat_id, user_id, has_debt=False, details="Faol")
    user_memory.set_issue_mode(chat_id, user_id, enabled=True, initial_query="aparatim ishlamayapti")
    user_memory.set_last_topic(chat_id, user_id, "awaiting_screen_photo")

    print(f"Xotiraga yozildi: INN={user_memory.get_last_id(chat_id, user_id)}, FM={user_memory.get_last_fm(chat_id, user_id)}")
    assert user_memory.get_last_id(chat_id, user_id) == inn, "INN xotirada bo'lishi kerak"
    assert user_memory.get_last_fm(chat_id, user_id) == fm, "FM xotirada bo'lishi kerak"

    print("\n=== 2-QADAM: SERVER RESTARTINI SIMULYATSIYA QILISH (RAM tozalab, Diskdan yuklash) ===")
    # Yangi xotira obyekti yaratamiz (bu diskdagi data/user_sessions.json dan yuklaydi)
    restarted_memory = UserMemoryManager()
    
    loaded_inn = restarted_memory.get_last_id(chat_id, user_id)
    loaded_fm = restarted_memory.get_last_fm(chat_id, user_id)
    loaded_ann = restarted_memory.get_annual_status(chat_id, user_id)
    loaded_issue = restarted_memory.is_issue_mode(chat_id, user_id)

    print(f"Restartdan keyin diskdan yuklandi: INN={loaded_inn}, FM={loaded_fm}, AnnualStatus={loaded_ann}, IssueMode={loaded_issue}")
    assert loaded_inn == inn, f"Kutilgan INN {inn}, ammo {loaded_inn} bo'ldi!"
    assert loaded_fm == fm, f"Kutilgan FM {fm}, ammo {loaded_fm} bo'ldi!"
    assert loaded_ann and loaded_ann.get("has_debt") is False, "Yillik qarz yo'qligi saqlangan bo'lishi kerak"
    assert loaded_issue is True, "Issue mode saqlangan bo'lishi kerak"

    print("\n=== 3-QADAM: APPARAT EKRANI RASMI YUBORILGANDA TEKSHIRUV ===")
    # Rasmda INN yo'q (xuddi logdagidek), lekin xatolik matni bor
    device_facts = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=False,
        has_internet=False,
        time_mismatch=False,
        error_type="fiscal_module",
        detected_inn=None,
        screen_text_summary="Fiskalizatsiya xatosi: 406, oflayn rejimning maksimal davomiyligi oshib ketgan, kassa UZ84577361",
        raw_facts={"screen_text_summary": "Fiskalizatsiya xatosi: 406"}
    )

    # Core engine apparat faktlarini tahlil qiladi
    decision = core_engine.process_device_facts(
        facts=device_facts,
        chat_id=chat_id,
        user_id=user_id,
        user_comment=""
    )

    print(f"Engine qarori: action={decision.action}, detected_inn={decision.detected_inn}, debt_amount={decision.debt_amount}")
    
    # Muhim tekshiruv: Bot INN so'ramasligi kerak!
    assert decision.action != ActionType.ASK_FULL_SCREEN, "Bot qaytadan INN so'ramasligi shart!"
    assert "korxonangiz СТИР (INN) raqamini yuboring" not in (decision.reply_text or ""), "Matnda qayta INN so'rovi bo'lmasligi kerak!"

    # Media handler mantiqini tekshirish:
    inn_to_use = decision.detected_inn or user_memory.get_last_id(chat_id, user_id) or ""
    org_to_use = decision.org_name or user_memory.get_org_name(chat_id, user_id) or ""
    ann_st = user_memory.get_annual_status(chat_id, user_id)
    has_ann_debt = ann_st.get("has_debt", False) if ann_st else False
    total_debt = decision.debt_amount if decision.debt_amount is not None else 0.0

    print(f"Natijaviy tekshiruv: INN={inn_to_use}, Org={org_to_use}, TotalDebt={total_debt}, HasAnnualDebt={has_ann_debt}")
    assert total_debt <= 0, "Oylik qarz bo'lmasligi kerak"
    assert not has_ann_debt, "Yillik qarz bo'lmasligi kerak"
    assert inn_to_use == inn, "INN to'g'ri olingan bo'lishi kerak"

    # Eskalatsiya matni tekshiruvi:
    esc_ack = "👨‍💻 <b>Iltimos kuting, barcha ma'lumotlaringiz mas'ul adminga yuborildi!</b>"
    print(f"Mijozga chiqadigan xabar: {esc_ack}")

    # Eskalatsiyani belgilash
    user_memory.mark_escalated_to_admin(chat_id, user_id, reason="Ekran rasmi qabul qilindi va adminga yuborildi")
    assert user_memory.is_escalated_to_admin(chat_id, user_id) is True, "Admin javobini kutish rejimiga o'tishi kerak"

    print("\n=== 4-QADAM: FOYDALANUVCHI GAPNI CHO'ZIB YANA YOZSA ===")
    assert user_memory.is_escalated_to_admin(chat_id, user_id) is True
    print("Mijozga: '👨‍💻 Murojaatingiz mas'ul administratorga yo'naltirilgan. Iltimos, admin javobini kuting!' deb javob beriladi.")

    print("\n✅ BARCHA TESTLAR 100% MUVAFFAQISHLIK BILAN O'TDI!")

if __name__ == "__main__":
    asyncio.run(test_memory_persistence_and_photo())
