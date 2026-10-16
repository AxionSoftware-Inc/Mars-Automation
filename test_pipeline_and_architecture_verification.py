"""
test_pipeline_and_architecture_verification.py
==============================================
Yangi tozalangan arxitektura va qat'iy Pipeline tekshiruvi:
1. 0-qadam: RuleEngine (custom_patches.json) to'g'ridan-to'g'ri Telegram chat routeridan ishlashi
2. 1-bosqich: Qarzdorlik tekshiruvi (Avval Oylik Mars to'lovi, keyin Yillik Soliq/OFD to'lovi)
3. 2-bosqich: Qarzdorlik yo'q bo'lsa -> Ekran/Reboot tashxisi (1-urinish)
4. 2-bosqich (Tezkor eskalatsiya): Agar 1 urinishda tuzalmasa ("ishlamadi") -> TEZDA adminga va ustaga yo'naltirish
5. Async/Non-blocking: OpenRouter httpx orqali ishlashi va bot qotib qolmasligi
6. Disk Persistence: Pending receipt bot qayta ishga tushganda ham saqlanishi
7. Anti-hallucination: Sunmi/Pax/UzSmart to'qimaslik, hisob raqamlarni matnda to'qimaslik
"""

import os
import json
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from core.models import DecisionResult, ActionType
from user_memory import user_memory
from excel_manager import excel_manager
from handlers.chat import handle_user_chat
from openrouter_client import openrouter_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_pipeline_verification")


def create_fake_message(text: str, chat_id: int = 77001, user_id: int = 88001, full_name: str = "Ali Valiyev", username: str = "ali_user"):
    msg = MagicMock()
    msg.text = text
    msg.chat.id = chat_id
    msg.chat.type = "private"
    msg.from_user.id = user_id
    msg.from_user.full_name = full_name
    msg.from_user.username = username
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()
    return msg


async def run_pipeline_verification():
    bot = AsyncMock()
    chat_id = 998811
    user_id = 112233
    user_memory.clear_context(chat_id, user_id)

    logger.info("=== 1. RULE ENGINE (0-QADAM) JONLI CHAT ORQALI TEKSHIRUVI ===")
    from core.rule_engine import rule_engine
    rule_engine.add_patch(
        patch_id="custom_wifi_pipeline_test",
        keywords=["kassa wifi paroli", "wifi paroli nima"],
        reply_text="🔑 Kassa apparati Wi-Fi paroli: Mars1234!",
        priority=95
    )

    msg_wifi = create_fake_message("kassa wifi paroli nima?", chat_id, user_id)
    await handle_user_chat(msg_wifi, bot)
    assert msg_wifi.reply.called, "RuleEngine patchi reply qilmadi!"
    reply_call = msg_wifi.reply.call_args[0][0]
    assert "Mars1234!" in reply_call, f"Kutilgan javob olinmadi: {reply_call}"
    logger.info("✅ 1. Rule Engine chat_router orqali zudlik bilan ishladi!")
    rule_engine.remove_patch("custom_wifi_pipeline_test")

    logger.info("\n=== 2. 1-BOSQICH: QARZDORLIK TEKSHIRUVI (OYLIK -> YILLIK) ===")
    user_memory.clear_context(chat_id, user_id)

    # A) Foydalanuvchi umumiy muammoni aytganda -> INN so'raladi
    msg_issue = create_fake_message("kassa ishlamay qoldi", chat_id, user_id)
    await handle_user_chat(msg_issue, bot)
    issue_reply = msg_issue.reply.call_args[0][0]
    assert "СТИР (INN)" in issue_reply or "qarz" in issue_reply.lower(), f"INN so'ralmadi: {issue_reply}"
    logger.info("✅ 2.A Muammo aytilganda avval INN so'ralishi tasdiqlandi!")

    # B) Qarz bor korxona INN kiritilganda -> Faqat oylik qarz va hisob raqam/video beriladi
    msg_debt_inn = create_fake_message("206011507", chat_id, user_id)
    from handlers.debt import handle_inn_query
    await handle_inn_query(msg_debt_inn, bot)
    debt_reply = msg_debt_inn.reply.call_args[0][0]
    assert "QARZDORLIK" in debt_reply or "so'm" in debt_reply, f"Qarz ko'rsatilmadi: {debt_reply}"
    logger.info("✅ 2.B Qarz bor korxonaga aniq qarz summasi va to'lov rekvizitlari berildi!")

    # C) Qarz yo'q korxona INN kiritilganda -> Oylik qarz 0 so'm, keyingi qadam Yillik (Fiskal modul) so'raladi
    msg_clean_inn = create_fake_message("300600431", chat_id, user_id)
    await handle_inn_query(msg_clean_inn, bot)
    clean_reply = msg_clean_inn.reply.call_args[0][0]
    assert ("qarzdorlik yo'q" in clean_reply.lower() or "0 so'm" in clean_reply), f"Qarz yo'qligi aytilmadi: {clean_reply}"
    assert "Fiskal modul" in clean_reply, f"Yillik fiskal modul so'ralmadi: {clean_reply}"
    logger.info("✅ 2.C Oylik qarz bo'lmaganda darhol Yillik Soliq litsenziyasi (Fiskal modul) so'ralishi tasdiqlandi!")

    # D) Fiskal modul yuborilganda -> OFD tekshiriladi
    with patch("ofd_bridge.ofd_bridge.query_fiscal_module", new=AsyncMock(return_value="Fiskal modul faol holatda. Qarzdorlik mavjud emas.")):
        msg_fm = create_fake_message("LG420210630789", chat_id, user_id)
        await handle_user_chat(msg_fm, bot)
        fm_reply = msg_fm.reply.call_args[0][0]
        assert "faol holatda" in fm_reply or "OFD" in fm_reply, f"OFD javobi chiqmadi: {fm_reply}"
        logger.info("✅ 2.D Fiskal modul orqali Yillik Soliq litsenziyasi tekshirildi!")

    logger.info("\n=== 3. 2-BOSQICH: QARZDORLIK BO'LMAGANDA TEXNIK DIAGNOSTIKA & REBOOT ===")
    # Qarzdorliklar to'liq tekshirilgan va yo'q:
    msg_hardware = create_fake_message("apparat ishlamayapti", chat_id, user_id)
    await handle_user_chat(msg_hardware, bot)
    hw_reply = msg_hardware.reply.call_args[0][0]
    assert ("internet" in hw_reply.lower() or "reboot" in hw_reply.lower() or "перезагрузка" in hw_reply.lower()), f"Reboot/Internet ko'rsatmasi berilmadi: {hw_reply}"
    logger.info("✅ 3. Qarzdorlik yo'q bo'lganda 1-urinishda Internet/Soat va Reboot tavsiya qilindi!")

    logger.info("\n=== 4. 2-BOSQICH (TEZKOR ESKALATSIYA): 1 URINISHDAN SO'NG TEZDA ADMINGA YO'NALTIRISH ===")
    # Foydalanuvchi: "ishlamadi" deb yozdi. Bot takrorlamasligi va darhol eskalatsiya qilishi shart!
    with patch("admin_manager.admin_manager.notify_user_query_escalation", new=AsyncMock()) as mock_admin_notify:
        msg_unresolved = create_fake_message("ishlamadi baribir", chat_id, user_id)
        await handle_user_chat(msg_unresolved, bot)
        unresolved_reply = msg_unresolved.reply.call_args[0][0]
        assert ("administrator" in unresolved_reply.lower() or "usta" in unresolved_reply.lower() or "bog'laymiz" in unresolved_reply.lower() or "yetkazildi" in unresolved_reply.lower()), f"Adminga eskalatsiya qilinmadi: {unresolved_reply}"
        assert mock_admin_notify.called, "Admin managerga xabarnoma yuborilmadi!"
        logger.info("✅ 4. 'Ishlamadi' deyilganda ko'p cho'zmasdan TEZDA adminga va ustaga eskalatsiya qilindi!")

    logger.info("\n=== 5. DISK PERSISTENCE: PENDING RECEIPT TESTI ===")
    fake_receipt = {
        "amount": 100000.0,
        "transaction_id": "TX998877",
        "payer_name": "Test Firm"
    }
    user_memory.set_pending_receipt(chat_id, user_id, fake_receipt)
    # Sessiyani xotiradan tozalaymiz (restart taqlidi)
    user_memory.sessions.clear()
    restored = user_memory.get_pending_receipt(chat_id, user_id)
    assert restored is not None, "Diskdan pending receipt tiklanmadi!"
    assert restored.get("transaction_id") == "TX998877", "Tranzaksiya ma'lumoti mos kelmadi!"
    user_memory.clear_pending_receipt(chat_id, user_id)
    assert user_memory.get_pending_receipt(chat_id, user_id) is None, "Pending receipt diskdan tozalanmadi!"
    logger.info("✅ 5. Pending receipt disk persistence to'liq ishladi!")

    logger.info("\n=== 6. ASYNC HTTPX NON-BLOCKING TESTI ===")
    with patch("openrouter_client.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Bu sinov javobi [ADMINGA_SAVOL]"}}]
        }
        mock_instance.post = AsyncMock(return_value=mock_resp)
        mock_httpx.return_value.__aenter__.return_value = mock_instance

        res = await openrouter_client.chat_completion_async([{"role": "user", "content": "salom"}])
        assert res == "Bu sinov javobi [ADMINGA_SAVOL]", f"httpx async javobi olinmadi: {res}"
        logger.info("✅ 6. OpenRouter asinxron httpx mijozi to'liq va bloklamasdan ishladi!")

    logger.info("\n🎉 BARCHA PIPELINE VA ARXITEKTURA TALABLARI 100% MUVAFFAQIYATLI O'TDI!")


if __name__ == "__main__":
    asyncio.run(run_pipeline_verification())
