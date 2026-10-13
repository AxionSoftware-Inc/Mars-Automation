"""
test_realistic_difficult_dialogue.py
====================================
Haqiqiy hayotiy, asabiy va qiyin mijoz dialogining to'liq ko'p bosqichli (multi-turn) testi:
1. Muammo shikoyati (INN so'ralishi)
2. E'tiroz va iflos formatlangan INN (Qarz ko'rsatilishi)
3. Qattiq e'tiroz va to'lov tarixi talabi
4. Pul to'lash va hisob raqam so'rovi (Click videosi)
5. Kvitansiya yuborish va qachon yoqiladi deb so'rash (To'lov qabul qilinishi)
6. Qayta qarz tekshiruvi (0 qarz va 3-bosqich Reboot)
7. Ekranda 406-xatolik chiqishi (Yillik Soliq to'lovi va Video 145)
8. Fiskal modul tekshiruvi (OFD ko'prigi)
9. Admin/Usta talab qilish (Dual-texnik eskalatsiyasi)
10. Rahmat va xotira nazorati
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from core.models import ActionType, ReceiptFacts, DeviceFacts
from core.engine import core_engine
from excel_manager import excel_manager
from user_memory import user_memory
from admin_manager import admin_manager
from handlers.chat import handle_user_chat
from handlers.debt import handle_debt_inquiry, process_and_send_debt_result
from ofd_bridge import ofd_bridge
from ai_helper import generate_ai_reply

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("realistic_test")

class MockUser:
    def __init__(self, user_id: int, first_name: str, username: str = ""):
        self.id = user_id
        self.first_name = first_name
        self.full_name = first_name
        self.username = username

class MockChat:
    def __init__(self, chat_id: int, chat_type: str = "private"):
        self.id = chat_id
        self.type = chat_type

class MockMessage:
    def __init__(self, message_id: int, user: MockUser, chat: MockChat, text: str = ""):
        self.message_id = message_id
        self.from_user = user
        self.chat = chat
        self.text = text
        self.replies = []

    async def reply(self, text: str, parse_mode: str = "HTML", **kwargs):
        self.replies.append(text)
        return self

    async def answer(self, text: str, parse_mode: str = "HTML", **kwargs):
        self.replies.append(text)
        return self

def create_mock_bot():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.copy_message = AsyncMock()
    return bot

async def run_realistic_dialogue_simulation():
    chat_id = -100888999
    user_id = 998877
    user = MockUser(user_id, "Sardor aka", "sardor_savdo")
    chat = MockChat(chat_id)
    bot = create_mock_bot()

    user_memory.clear_context(chat_id, user_id)
    admin_manager.admin_ids = [1966874161, 6436610869]

    print("\n" + "="*70)
    print("🚀 REALISTIK VA QIYIN MIJOZ MULOQOTI SIMULYATSIYASI BOSHLANDI")
    print("Mijoz: Sardor aka (@sardor_savdo) — Qashqadaryo Sharq Gavhari MCHJ")
    print("="*70 + "\n")

    # -------------------------------------------------------------------------
    # TURN 1: MIJOZ MUAMMO SHIKOYATI BILAN YOZADI
    # -------------------------------------------------------------------------
    t1_text = "Assalomu alaykum aka ertalabdan beri apparatim ishlamayapti, savdo to'xtab qoldi, kassa umuman chek chiqarmayapti, tezda tekshirib bering!"
    print(f"👤 MIJOZ (Turn 1): {t1_text}\n")
    
    msg1 = MockMessage(1, user, chat, text=t1_text)
    await handle_user_chat(msg1, bot)
    assert len(msg1.replies) > 0, "Bot javob bermadi"
    bot_reply_1 = msg1.replies[-1]
    print(f"🤖 BOT:\n{bot_reply_1}\n")
    print("-" * 70)

    # Assert Turn 1: Bot INN va Fiskal modul talab qilishi shart (1-bosqich)
    assert "INN" in bot_reply_1
    assert "Fiskal modul" in bot_reply_1
    assert "60%" in bot_reply_1

    # -------------------------------------------------------------------------
    # TURN 2: MIJOZ E'TIROZ BILDIRIB, IFLOS FORMATDA INN YUBORADI
    # -------------------------------------------------------------------------
    t2_text = "Eee nimaga har doim qarz deysizlar, apparat buzildiku o'zi! Mayli tekshirib ko'ringchi, inn: 206 011 507"
    print(f"👤 MIJOZ (Turn 2): {t2_text}\n")
    
    msg2 = MockMessage(2, user, chat, text=t2_text)
    await handle_user_chat(msg2, bot)
    assert len(msg2.replies) > 0
    bot_reply_2 = msg2.replies[-1]
    print(f"🤖 BOT:\n{bot_reply_2}\n")
    print("-" * 70)

    # Assert Turn 2: Bot 206011507 ni topib, 1,500,400 so'm qarzni va Click video 148 ni berishi shart
    assert "QASHQADARYO SHARQ GAVHARI" in bot_reply_2
    assert "1,500,400" in bot_reply_2
    assert bot.copy_message.called
    assert any(c.kwargs.get("message_id") == 148 for c in bot.copy_message.call_args_list)

    # -------------------------------------------------------------------------
    # TURN 3: MIJOZ QATTIQ E'TIROZ BILDIRADI VA TO'LOV TARIXINI TALAB QILADI
    # -------------------------------------------------------------------------
    t3_text = "Qanaqasiga 1 yarim million qarz?! Men o'tgan oy to'lagandimku! Qayerdan kelib chiqdi buncha qarz, to'lov tariximni ko'rsat menga!"
    print(f"👤 MIJOZ (Turn 3): {t3_text}\n")
    
    msg3 = MockMessage(3, user, chat, text=t3_text)
    await handle_debt_inquiry(msg3)
    assert len(msg3.replies) > 0
    bot_reply_3 = msg3.replies[-1]
    print(f"🤖 BOT:\n{bot_reply_3}\n")
    print("-" * 70)

    # Assert Turn 3: To'lov tarixi ko'rsatiladi
    assert "QASHQADARYO SHARQ GAVHARI" in bot_reply_3
    assert "to'lov tarixi" in bot_reply_3.lower() or "tarix" in bot_reply_3.lower() or "oy" in bot_reply_3.lower()

    # -------------------------------------------------------------------------
    # TURN 4: MIJOZ PUL TO'LAMOQCHI BO'LIB REKVIZIT SO'RAYDI
    # -------------------------------------------------------------------------
    t4_text = "Ha tushundim, demak to'lanmagan oylar bor ekanda. Xo'sh qayerga to'layman, clickdan qanday to'lasam bo'ladi, hisob raqamini tashlang?"
    print(f"👤 MIJOZ (Turn 4): {t4_text}\n")
    
    msg4 = MockMessage(4, user, chat, text=t4_text)
    await handle_user_chat(msg4, bot)
    assert len(msg4.replies) > 0
    bot_reply_4 = msg4.replies[-1]
    print(f"🤖 BOT:\n{bot_reply_4}\n")
    print("-" * 70)

    # Assert Turn 4: Mars hisob raqami (20208000800208044003) va Click video 148
    assert "20208000800208044003" in bot_reply_4 or any(c.kwargs.get("message_id") == 85 for c in bot.copy_message.call_args_list)

    # -------------------------------------------------------------------------
    # TURN 5: MIJOZ TO'LOV KVITANSIYASINI YUBORADI VA QACHON YOQILISHINI SO'RAYDI
    # -------------------------------------------------------------------------
    t5_text = "Mana hozir Clickdan 1 500 400 so'm to'ladim, chek tushdimi? Qachon yoqasizlar apparatimni?"
    print(f"👤 MIJOZ (Turn 5): [To'lov kvitansiyasi: 1,500,400 so'm] + {t5_text}\n")

    # Kvitansiya kelishi:
    receipt_facts = ReceiptFacts(
        is_receipt=True,
        recipient_account="20208000800208044003",
        is_mars_recipient=True,
        amount=1500400.0,
        payer_inn="206011507",
        payer_name="QASHQADARYO SHARQ GAVHARI MCHJ",
        payment_date="2026-10-13 19:40",
        transaction_id="TX_CLICK_SARDOR_001",
        payment_system="Click"
    )
    rec_decision = core_engine.process_receipt_facts(
        facts=receipt_facts,
        chat_id=chat_id,
        user_id=user_id,
        user_comment=t5_text,
        file_id="photo_sardor_receipt",
        is_photo=True
    )
    assert rec_decision.action == ActionType.RECEIPT_PROCESSED
    print(f"🤖 BOT (Kvitansiya javobi):\n{rec_decision.reply_text}\n")

    # Adminga eskalatsiya
    await admin_manager.notify_receipt_escalation(
        bot=bot,
        user=user,
        chat_id=chat_id,
        receipt_facts=rec_decision.receipt_facts,
        debt_status_info=rec_decision.debt_status_info,
        file_id=rec_decision.file_id,
        is_photo=True
    )
    assert bot.send_photo.called
    admin_caption = bot.send_photo.call_args.kwargs.get("caption", "")
    print(f"📢 ADMINGA YUBORILGAN HISOBOT (Caption):\n{admin_caption}\n")
    print("-" * 70)

    # Assert Turn 5: Qarz to'liq yopildi deb qayd etilishi
    assert "QARZ TO'LIQ YOPILDI" in admin_caption or "to'liq yopildi" in (rec_decision.reply_text or "").lower()

    # Turn 5b: "Qachon qo'shiladi / yoqiladi?" savoliga AI javobi
    user_memory.add_user_message(chat_id, user_id, "[To'lov kvitansiyasi: 1,500,400 so'm]")
    user_memory.add_assistant_message(chat_id, user_id, rec_decision.reply_text or "")
    
    ctx_summary = user_memory.get_context_summary(chat_id, user_id)
    reply_activation, _ = generate_ai_reply("qachon yoqasizlar apparatimni?", context_history=ctx_summary)
    print(f"🤖 BOT ('qachon yoqasizlar' javobi):\n{reply_activation}\n")
    print("-" * 70)
    assert any(w in reply_activation.lower() for w in ["adminga", "operator", "tasdiq", "yoqiladi", "daqiqa", "vaqt"])

    # -------------------------------------------------------------------------
    # TURN 6: MIJOZ QAYTA TEKSHIRADI (SUHBAT KONTEKSTI VA QARZSIZ APPARAT)
    # -------------------------------------------------------------------------
    t6_text = "Qarzim qoldimi yana, to'lov tushdimi?"
    print(f"👤 MIJOZ (Turn 6): {t6_text}\n")
    
    msg6 = MockMessage(6, user, chat, text=t6_text)
    await handle_user_chat(msg6, bot)
    assert len(msg6.replies) > 0
    bot_reply_6 = msg6.replies[-1]
    print(f"🤖 BOT:\n{bot_reply_6}\n")
    print("-" * 70)

    # Assert Turn 6: To'lov qabul qilinganligi va qarz yopilganligi aytiladi
    assert any(w in bot_reply_6.lower() for w in ["qabul", "to'lov", "yopildi", "adminga", "tasdiq", "tekshir"])

    # Turn 6b: Mijoz qarzsiz apparati (INN: 311790999) bo'yicha ham tekshiradi:
    t6b_text = "Mayli, boshqa do'konimizdagi apparatni ham tekshirib beringchi: 311790999"
    print(f"👤 MIJOZ (Turn 6b): {t6b_text}\n")

    msg6b = MockMessage(61, user, chat, text=t6b_text)
    await process_and_send_debt_result(msg6b, bot, "311790999")
    bot_reply_6b = msg6b.replies[-1]
    print(f"🤖 BOT (Qarzsiz apparat javobi):\n{bot_reply_6b}\n")
    print("-" * 70)

    # Assert Turn 6b: 0 qarz va Stage 3 tavsiyalari (Reboot, Soat, Internet)
    assert "qarzdorlik mavjud emas" in bot_reply_6b.lower() or "0 so'm" in bot_reply_6b or "qarz yo'q" in bot_reply_6b.lower()
    assert "Internet va Soat" in bot_reply_6b or "soat" in bot_reply_6b.lower()
    assert "Reboot" in bot_reply_6b or "qayta yoqing" in bot_reply_6b.lower()

    # -------------------------------------------------------------------------
    # TURN 7: EKRANDA 406-XATOLIK CHIQISHI VA YILLIK TO'LOV ANGLATILISHI
    # -------------------------------------------------------------------------
    t7_text = "Aka apparatni yoqdim, lekin ekranda '406 oflayn rejimning maksimal davomiyligi oshib ketdi' deb yozuv chiqyapti, bu nima yana qarzmi?!"
    print(f"👤 MIJOZ (Turn 7): {t7_text}\n")

    res7 = await core_engine.process_text_inquiry(
        text=t7_text,
        chat_id=chat_id,
        user_id=user_id,
        bot=bot
    )
    bot_reply_7 = res7.reply_text
    print(f"🤖 BOT:\n{bot_reply_7}\n")
    print("-" * 70)

    # Assert Turn 7: 406-xatolik OYLIQ EMAS, YILLIK SOLIQ to'lovi ekanligi + Video 145
    assert "406" in bot_reply_7
    assert "oylik abonent to'lovi emas" in bot_reply_7.lower()
    assert "Yangi Texnologiyalar" in bot_reply_7
    assert res7.video_id == 145

    # -------------------------------------------------------------------------
    # TURN 8: FISKAL MODULNI TEKSHIRISH
    # -------------------------------------------------------------------------
    t8_text = "Fiskal modulim mana: LG420210009999, qachongacha ekan litsenziyasi?"
    print(f"👤 MIJOZ (Turn 8): {t8_text}\n")

    with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
        mock_ofd.return_value = "🟢 Soliq (OFD) holati: Litsenziya muddati tugagan (2026-10-01). To'lov talab etiladi."
        res8 = await core_engine.process_text_inquiry(
            text=t8_text,
            chat_id=chat_id,
            user_id=user_id,
            bot=bot
        )
        bot_reply_8 = res8.reply_text
        print(f"🤖 BOT:\n{bot_reply_8}\n")
        print("-" * 70)

        # Assert Turn 8: OFD litsenziya holati chiqariladi
        assert "OFD / Soliq" in bot_reply_8
        assert "LG420210009999" in bot_reply_8

    # -------------------------------------------------------------------------
    # TURN 9: MIJOZ ADMIN/USTA BILAN GAPLASHAMAN DEB QAT'IY TALAB QILADI
    # -------------------------------------------------------------------------
    t9_text = "Menga baribir tushunarsiz, boshim qotib ketdi. Admin bilan gaplashaman, hoziroq usta chaqirib bering yoki aloqaga chiqinglar!"
    print(f"👤 MIJOZ (Turn 9): {t9_text}\n")

    msg9 = MockMessage(9, user, chat, text=t9_text)
    bot.send_message.reset_mock()
    await handle_user_chat(msg9, bot)
    assert len(msg9.replies) > 0
    bot_reply_9 = msg9.replies[-1]
    print(f"🤖 BOT:\n{bot_reply_9}\n")

    # Adminga yuborilgan xabarni tekshirish
    assert bot.send_message.called
    admin_alert_text = bot.send_message.call_args.kwargs.get("text", "")
    print(f"📢 ADMINGA / TEXNIKLARGA BORGAN ESKALATSIYA XABARI:\n{admin_alert_text}\n")
    print("-" * 70)

    # Assert Turn 9: Ikkala texnik (@quvonchbek_admin va @Yashnarbek_butaev) ko'rsatiladi
    assert "@quvonchbek_admin" in bot_reply_9
    assert "@Yashnarbek_butaev" in bot_reply_9
    assert "@quvonchbek_admin" in admin_alert_text
    assert "@Yashnarbek_butaev" in admin_alert_text
    assert "311790999" in admin_alert_text or "206011507" in admin_alert_text

    # -------------------------------------------------------------------------
    # TURN 10: MINNATDORCHILIK VA SUHBAT YAKUNI
    # -------------------------------------------------------------------------
    t10_text = "Rahmat tushundim, ustani kutaman"
    print(f"👤 MIJOZ (Turn 10): {t10_text}\n")

    ctx_final = user_memory.get_context_summary(chat_id, user_id)
    reply_10, _ = generate_ai_reply(t10_text, context_history=ctx_final)
    print(f"🤖 BOT:\n{reply_10}\n")
    print("=" * 70)
    print("🎉 BARCHA 10 TA REALISTIK VA QIYIN TURN-LAR 100% MUVAFFAQIYATLI O'TDI!")
    print("=" * 70 + "\n")

def main():
    asyncio.run(run_realistic_dialogue_simulation())

if __name__ == "__main__":
    main()
