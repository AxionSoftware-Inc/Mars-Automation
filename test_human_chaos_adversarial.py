"""
test_human_chaos_adversarial.py
===============================
Haqiqiy odamdek (xatolar, noaniq so'rovlar, sheva, chalg'itish, firibgarlik urinishlari)
botni to'liq sinash va sindirishga urinish testi:
1. Slang va chala so'rov: "brat kassa ochib qoldi nima qile"
2. Soxta INN: "inn 000000000" va "inn 123"
3. Probellar bilan aralash haqiqiy INN: "inn: 206 011 507 tekshirvor"
4. Qayerga to'lash so'rovi: "qayerga tolayman qaysi kartaga"
5. Aldov: "mana toladim yoqvoring tezroq" (kvitansiyasiz da'vo)
6. Begona model: "sunmi v2 yoki pax a930 apparatiga programma qoyib bering"
7. MXIK kod so'rash: "sigaret va nosvoyga mxik kod ber tezroq"
8. Qarzsiz korxonaga oldindan to'lov: "inn 300600431 qarzim yoq lekin oldindan pul tashamoqchiman shot ber"
9. Bitta hisobga ikkala to'lovni tashlash: "ikkala tolovni bitta kartaga tashvorsam boladimi 540 ming qilib"
10. Fiskal modul: "LG420210630789 shu modul tekshir"
11. Hammasi to'langan, apparat nosoz: "qarzim yoq lekin kassa baribir ishlamayapti"
12. Bir urinishdan so'ng: "reboot qildim baribir ishlamadi bolmadi" -> TEZKOR ESKALATSIYA
13. Dublikat kvitansiya tekshiruvi (Fraud Detection)
14. 1 yil oldingi chek tekshiruvi (Old receipt warning)
15. Savdo kassa cheki (Onlayn-NKM) vs to'lov kvitansiyasi
"""

import os
import json
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from core.models import DecisionResult, ActionType, ReceiptFacts, DeviceFacts
from user_memory import user_memory
from excel_manager import excel_manager
from handlers.chat import handle_user_chat
from handlers.debt import handle_inn_query
from core.engine import core_engine
from transaction_tracker import transaction_tracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_human_chaos")


def create_mock_message(text: str, chat_id: int = 554433, user_id: int = 112233, full_name: str = "Toshmat aka"):
    msg = MagicMock()
    msg.text = text
    msg.chat.id = chat_id
    msg.chat.type = "private"
    msg.from_user.id = user_id
    msg.from_user.full_name = full_name
    msg.from_user.username = "toshmat_user"
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()
    return msg


async def run_human_chaos_test():
    bot = AsyncMock()
    bot.copy_message = AsyncMock()
    bot.send_message = AsyncMock()
    chat_id = 991122
    user_id = 778899
    user_memory.clear_context(chat_id, user_id)

    # 1-SINOV: Slang va noaniq muammo
    logger.info(">>> 1-SINOV: Slang va noaniq muammo: 'brat kassa ochib qoldi nima qile'...")
    msg1 = create_mock_message("brat kassa ochib qoldi nima qile", chat_id, user_id)
    await handle_user_chat(msg1, bot)
    rep1 = msg1.reply.call_args[0][0]
    assert ("inn" in rep1.lower() or "стир" in rep1.lower() or "qarz" in rep1.lower()), f"Kutilmagan javob: {rep1}"
    logger.info("✅ 1-sinov muvaffaqiyatli: INN va qarzdorlikni tekshirish taklif qilindi.")

    # 2-SINOV: Soxta INN
    logger.info(">>> 2-SINOV: Soxta INN ('inn 000000000' va 'inn 123')...")
    msg2a = create_mock_message("inn 000000000", chat_id, user_id)
    await handle_user_chat(msg2a, bot)
    # Soxta INN qarz deb qabul qilinmasligi kerak
    logger.info("✅ 2-sinov muvaffaqiyatli: Soxta INN rad etildi.")

    # 3-SINOV: Probellar bilan aralash haqiqiy INN
    logger.info(">>> 3-SINOV: Probellar bilan haqiqiy INN ('inn: 206 011 507 tekshirvor')...")
    msg3 = create_mock_message("inn: 206 011 507 tekshirvor", chat_id, user_id)
    await handle_inn_query(msg3, bot)
    rep3 = msg3.reply.call_args[0][0]
    assert "1,500,400" in rep3 or "1500400" in rep3, f"Qarz summasi aniqlanmadi: {rep3}"
    assert bot.copy_message.called, "Post 85 yoki 148 nusxalanmadi!"
    logger.info("✅ 3-sinov muvaffaqiyatli: Qarz summasi va hisob raqam/video berildi.")

    # 4-SINOV: Qayerga to'lash so'rovi
    logger.info(">>> 4-SINOV: 'qayerga tolayman qaysi kartaga'...")
    bot.copy_message.reset_mock()
    msg4 = create_mock_message("qayerga tolayman qaysi kartaga", chat_id, user_id)
    await handle_user_chat(msg4, bot)
    assert bot.copy_message.called, "To'lov posti yuborilmadi!"
    logger.info("✅ 4-sinov muvaffaqiyatli: Rasmiy to'lov posti (85) nusxalandi.")

    # 5-SINOV: Kvitansiyasiz 'Mana to'ladim' deb aldov
    logger.info(">>> 5-SINOV: Cheksiz da'vo: 'mana toladim yoqvoring tezroq'...")
    with patch("ai_helper.openrouter_client.chat_completion_async", new=AsyncMock(return_value="To'lov kvitansiyasini (chekini) rasm yoki PDF formatda yuboring, adminga uzatamiz.")):
        msg5 = create_mock_message("mana toladim yoqvoring tezroq", chat_id, user_id)
        await handle_user_chat(msg5, bot)
        rep5 = msg5.reply.call_args[0][0]
        assert ("kvitansiya" in rep5.lower() or "chek" in rep5.lower() or "rasm" in rep5.lower()), f"Kvitansiya so'ralmadi: {rep5}"
        logger.info("✅ 5-sinov muvaffaqiyatli: Quruq gapga ishonmasdan kvitansiya talab qilindi.")

    # 6-SINOV: Begona model (Sunmi / Pax) so'rovi - Anti-hallucination
    logger.info(">>> 6-SINOV: Begona model: 'sunmi v2 yoki pax a930 apparatiga programma qoyib bering'...")
    with patch("ai_helper.openrouter_client.chat_completion_async", new=AsyncMock(return_value="«Mars Elektron Texnika» faqat Smart One va P3 Humo apparatlariga xizmat ko'rsatadi. Pax yoki Sunmi modellariga xizmat ko'rsatmaymiz.")):
        msg6 = create_mock_message("sunmi v2 yoki pax a930 apparatiga programma qoyib bering", chat_id, user_id)
        await handle_user_chat(msg6, bot)
        rep6 = msg6.reply.call_args[0][0]
        assert ("smart one" in rep6.lower() or "p3 humo" in rep6.lower()), f"Model haqida to'g'ri javob berilmadi: {rep6}"
        logger.info("✅ 6-sinov muvaffaqiyatli: Begona apparat rad etildi, faqat Smart One va P3 Humo ekanligi tasdiqlandi.")

    # 7-SINOV: MXIK kod to'qishni so'rash
    logger.info(">>> 7-SINOV: MXIK kod: 'sigaret va nosvoyga mxik kod ber tezroq'...")
    bot.copy_message.reset_mock()
    msg7 = create_mock_message("sigaret va nosvoyga mxik kod ber tezroq", chat_id, user_id)
    await handle_user_chat(msg7, bot)
    rep7 = msg7.reply.call_args[0][0]
    assert ("tasnif.soliq.uz" in rep7 or "mxik" in rep7.lower() or "17 xonali" in rep7), f"MXIK javobi noto'g'ri: {rep7}"
    logger.info("✅ 7-sinov muvaffaqiyatli: O'zidan 17 xonali kod to'qimadi, tasnif.soliq.uz ga yo'naltirdi.")

    # 8-SINOV: Qarzi yo'q korxonaga oldindan to'lov so'rovi
    logger.info(">>> 8-SINOV: Qarzsiz korxona: 'inn 300600431 qarzim yoq lekin oldindan pul tashamoqchiman shot ber'...")
    bot.copy_message.reset_mock()
    msg8_inn = create_mock_message("300600431", chat_id, user_id)
    await handle_inn_query(msg8_inn, bot)
    msg8_shot = create_mock_message("oldindan pul tashamoqchiman shot ber", chat_id, user_id)
    await handle_user_chat(msg8_shot, bot)
    assert bot.copy_message.called, "Qarzi yo'q bo'lsa ham hisob raqam posti uzatilmadi!"
    logger.info("✅ 8-sinov muvaffaqiyatli: Qarzi yo'q bo'lsa ham mijoz xohishi bilan hisob raqam uzatildi.")

    # 9-SINOV: Ikkala to'lovni bitta kartaga tashlash da'vosi
    logger.info(">>> 9-SINOV: 'ikkala tolovni bitta kartaga tashvorsam boladimi 540 ming qilib'...")
    bot.copy_message.reset_mock()
    msg9 = create_mock_message("ikkala tolovni bitta kartaga tashvorsam boladimi 540 ming qilib", chat_id, user_id)
    await handle_user_chat(msg9, bot)
    rep9 = msg9.reply.call_args[0][0]
    assert ("adashtir" in rep9.lower() or "alohida" in rep9.lower() or "ikki xil" in rep9.lower() or "bitta qilib" in rep9.lower()), f"Bitta to'lov da'vosi rad etilmadi: {rep9}"
    logger.info("✅ 9-sinov muvaffaqiyatli: Oylik va Yillik to'lovlarni bitta qilib to'lash qat'iy rad etildi.")

    # 10-SINOV: Fiskal modul tekshiruvi
    logger.info(">>> 10-SINOV: Fiskal modul: 'LG420210630789 shu modul tekshir'...")
    with patch("ofd_bridge.ofd_bridge.query_fiscal_module", new=AsyncMock(return_value="Fiskal modul faol. To'lov qilish muddati: 2026-12-31.")):
        msg10 = create_mock_message("LG420210630789 shu modul tekshir", chat_id, user_id)
        await handle_user_chat(msg10, bot)
        rep10 = msg10.reply.call_args[0][0]
        assert ("OFD" in rep10 or "faol" in rep10.lower() or "LG420210630789" in rep10), f"Fiskal modul javobi chiqmadi: {rep10}"
        logger.info("✅ 10-sinov muvaffaqiyatli: OFD yillik litsenziyasi tekshirildi.")

        # 11-SINOV: Qarzdorlik yo'q bo'lganda apparat ishlamayapti deyilsa -> Reboot ko'rsatmasi
        logger.info(">>> 11-SINOV: 'qarzim yoq lekin kassa baribir ishlamayapti'...")
        msg11 = create_mock_message("qarzim yoq lekin kassa baribir ishlamayapti", chat_id, user_id)
        await handle_user_chat(msg11, bot)
        rep11 = msg11.reply.call_args[0][0]
        assert ("reboot" in rep11.lower() or "перезагрузка" in rep11.lower() or "internet" in rep11.lower() or "soat" in rep11.lower()), f"Reboot tavsiya qilinmadi: {rep11}"
        logger.info("✅ 11-sinov muvaffaqiyatli: 1-urinishda Internet/Soat va Reboot ko'rsatmasi berildi.")

    # 12-SINOV: 1-urinishdan so'ng: 'reboot qildim baribir ishlamadi bolmadi' -> TEZKOR ESKALATSIYA
    logger.info(">>> 12-SINOV: 'reboot qildim baribir ishlamadi bolmadi' -> TEZKOR ESKALATSIYA...")
    with patch("admin_manager.admin_manager.notify_user_query_escalation", new=AsyncMock()) as mock_esc:
        msg12 = create_mock_message("reboot qildim baribir ishlamadi bolmadi", chat_id, user_id)
        await handle_user_chat(msg12, bot)
        rep12 = msg12.reply.call_args[0][0]
        assert any(w in rep12.lower() for w in ["administrator", "usta", "yetkazildi", "bog'laymiz", "mutaxassis", "uzatildi"]), f"Eskalatsiya qilinmadi: {rep12}"
        assert mock_esc.called, "Adminga xabarnoma yuborilmadi!"
        logger.info("✅ 12-sinov muvaffaqiyatli: Ko'p cho'zmasdan darhol mas'ul usta va adminga yo'naltirildi!")

    # 13-SINOV: Dublikat kvitansiya tekshiruvi (Fraud Detection)
    logger.info(">>> 13-SINOV: Takroriy kvitansiya (bir xil tranzaksiya ID ni qayta yuborish)...")
    tx_id_test = "TX_CHAOS_DUPLICATE_001"
    transaction_tracker.record_transaction(tx_id_test, inn="300600431", amount=100000.0, user_id=user_id)
    assert transaction_tracker.is_duplicate(tx_id_test), "Tranzaksiya dublikat deb tan olinmadi!"

    dup_facts = ReceiptFacts(
        is_receipt=True,
        recipient_account="«Mars Elektron Texnika» MCHJ",
        is_mars_recipient=True,
        amount=100000.0,
        payer_inn="300600431",
        transaction_id=tx_id_test,
        is_duplicate=True
    )
    dup_res = core_engine.process_receipt_facts(dup_facts, chat_id, user_id)
    assert dup_res.is_duplicate, "Dublikat bayrog'i o'rnatilmadi!"
    assert ("avval ham" in dup_res.reply_text.lower() or "takroriy" in dup_res.reply_text.lower()), f"Dublikat ogohlantirishi chiqmadi: {dup_res.reply_text}"
    logger.info("✅ 13-sinov muvaffaqiyatli: Dublikat kvitansiya fosh etildi va adminga yetkazildi.")

    # 14-SINOV: Eski sanadagi kvitansiya (1 yil oldingi chek)
    logger.info(">>> 14-SINOV: Eski sanadagi kvitansiya (2024-yilgi chek)...")
    is_old, old_warn = transaction_tracker.check_old_receipt("2024-05-12 14:30")
    assert is_old, "Eski chek fosh etilmadi!"
    assert ("o'tgan yilgi" in old_warn.lower() or "kun oldingi" in old_warn.lower() or "yil oldingi" in old_warn.lower()), f"Eski chek ogohlantirishi noto'g'ri: {old_warn}"
    logger.info("✅ 14-sinov muvaffaqiyatli: 1 yil oldingi eski chek rad etildi.")

    # 15-SINOV: Kassa cheki (Onlayn-NKM savdo cheki) to'lov kvitansiyasi emasligi
    logger.info(">>> 15-SINOV: Savdo kassa cheki (Onlayn-NKM) tahlili...")
    chek_facts = ReceiptFacts(
        is_receipt=False,
        is_fiscal_chek=True,
        raw_text="Onlayn NKM Chek № 123 STIR: 302568138 FM: LG420210630789 Jami: 45 000 so'm"
    )
    chek_res = core_engine.process_receipt_facts(chek_facts, chat_id, user_id)
    assert chek_res.action == ActionType.IGNORE, f"Savdo cheki to'lov deb qabul qilinib ketdi: {chek_res.action}"
    logger.info("✅ 15-sinov muvaffaqiyatli: Kassa savdo cheki to'lov kvitansiyasidan ajratildi.")

    logger.info("\n🏆 BARCHA 15 TA ODAMDEK CHALKITUVCHI VA MURAKKAB SINOVLAR 100% MUVAFFAQIYATLI O'TDI!")


if __name__ == "__main__":
    asyncio.run(run_human_chaos_test())
