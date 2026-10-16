import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types

from user_memory import user_memory
from admin_manager import admin_manager
from handlers.chat import handle_user_chat


async def test_telegram_group_real_conversations():
    """
    Telegram guruhidan (-1003742874507) olingan real foydalanuvchilar va adminlar
    yozishmalarining to'liq simulyatsiyasi:
    1. Soat va vaqt bo'yicha savol: 'soatinii qanday tug'irlasa buladi'
    2. MXIK / Tasnif bo'yicha savol: 'mixni qayerdan topaman', 'shu mixikni qayerdan topsam buladi'
    3. Internet tarmog'i: 'internetga ulanmaganaka'
    4. Kassa apparat nosozligi (Aparatim ishlamayapti -> INN 300600431 -> FM LG420230615712 -> Rasm/Admin)
    5. Gapni cho'zish / sabrsizlik ('tashladimku boya', 'hudoga soldim', 'Gap qaytarma')
    """
    print("\n=================================================================")
    print("🚀 TELEGRAM GURUHDAGI REAL YOZISHMALAR SIMULYATSIYA TESTI BOSHLANDI")
    print("=================================================================\n")

    mock_bot = AsyncMock()
    chat_id = -1003742874507  # Real guruh ID
    user_id = 1966874161      # Quvonchbek admin / user ID
    user_memory.sessions.clear()

    mock_user = types.User(id=user_id, is_bot=False, first_name="Quvonchbek", username="Quvonchbek_admin")

    async def send_simulated_msg(text: str) -> types.Message:
        msg = AsyncMock(spec=types.Message)
        msg.reply = AsyncMock()
        msg.text = text
        msg.chat = MagicMock(id=chat_id)
        msg.from_user = mock_user
        msg.message_id = 1000 + len(user_memory.sessions.get(f"{chat_id}_{user_id}", {}).get("user_messages", []))
        return msg

    # -------------------------------------------------------------
    # 1-SSENARIY: Soat va sana noto'g'riligi bo'yicha real xabarlar
    # -------------------------------------------------------------
    print("--- [1-SSENARIY] Soat va sana bo'yicha savollar ---")
    msg_soat1 = await send_simulated_msg("soatinii qanday tug'irlasa buladi")
    await handle_user_chat(msg_soat1, mock_bot)
    assert msg_soat1.reply.called or mock_bot.copy_message.called, "Soat bo'yicha bot javob berishi kerak"
    print("✅ 'soatinii qanday tug'irlasa buladi' -> Muvaffaqiyatli yo'riqnoma berildi.")

    msg_soat2 = await send_simulated_msg("soati noturiykan")
    await handle_user_chat(msg_soat2, mock_bot)
    assert msg_soat2.reply.called or mock_bot.copy_message.called
    print("✅ 'soati noturiykan' -> Muvaffaqiyatli javob qaytarildi.")

    # -------------------------------------------------------------
    # 2-SSENARIY: MXIK / Mixik / Tasnif bo'yicha real xabarlar
    # -------------------------------------------------------------
    print("\n--- [2-SSENARIY] MXIK / Mixik bo'yicha real xabarlar ---")
    user_memory.sessions.clear()
    msg_mix1 = await send_simulated_msg("mixni qayerdan topaman")
    await handle_user_chat(msg_mix1, mock_bot)
    assert msg_mix1.reply.called
    reply_mix1 = msg_mix1.reply.call_args[0][0]
    assert "tasnif.soliq.uz" in reply_mix1.lower() or "mxik" in reply_mix1.lower(), "MXIK/Tasnif havolasi bo'lishi kerak"
    print("✅ 'mixni qayerdan topaman' -> MXIK/Tasnif.soliq.uz tushuntirildi.")

    msg_mix2 = await send_simulated_msg("shu mixikni qayerdan topsam buladi")
    await handle_user_chat(msg_mix2, mock_bot)
    assert msg_mix2.reply.called
    print("✅ 'shu mixikni qayerdan topsam buladi' -> MXIK yo'riqnomasi berildi.")

    # -------------------------------------------------------------
    # 3-SSENARIY: Tarmoq / Internet bo'yicha real xabar
    # -------------------------------------------------------------
    print("\n--- [3-SSENARIY] Internet tarmog'i bo'yicha real xabar ---")
    user_memory.sessions.clear()
    msg_net = await send_simulated_msg("internetga ulanmaganaka")
    await handle_user_chat(msg_net, mock_bot)
    assert msg_net.reply.called or mock_bot.copy_message.called
    print("✅ 'internetga ulanmaganaka' -> Internet qo'llanmasi berildi.")

    # -------------------------------------------------------------
    # 4-SSENARIY: To'liq Kassa nosozligi dialogi (Guruhdagi zanjir)
    # -------------------------------------------------------------
    print("\n--- [4-SSENARIY] Guruhdagi to'liq Kassa nosozligi zanjiri ---")
    user_memory.sessions.clear()

    # Qadam 1: Aparatim ishlamayapti
    msg_app1 = await send_simulated_msg("Aparatim ishlamayapti")
    await handle_user_chat(msg_app1, mock_bot)
    assert msg_app1.reply.called
    reply1 = msg_app1.reply.call_args[0][0]
    assert "inn" in reply1.lower(), "1-bosqichda INN so'ralishi kerak"
    print("✅ Qadam 1: 'Aparatim ishlamayapti' -> INN so'raldi (1-bosqich)")

    # Qadam 2: INN yuborish (300600431 - SEROX-SHERBEK BAXTI MCHJ)
    msg_inn = await send_simulated_msg("300600431")
    await handle_user_chat(msg_inn, mock_bot)
    assert msg_inn.reply.called
    reply_inn = msg_inn.reply.call_args[0][0]
    assert "fiskal modul" in reply_inn.lower() or "fm" in reply_inn.lower(), "Oylik qarz 0 so'm bo'lgach, FM so'ralishi kerak"
    print("✅ Qadam 2: '300600431' -> Oylik qarz yo'q (0 so'm), Fiskal modul so'raldi (2-bosqich)")

    # Qadam 3: User FM raqamini bilmaydi va so'raydi
    msg_fm_ask = await send_simulated_msg("fm raqamini qayerdan olaman")
    await handle_user_chat(msg_fm_ask, mock_bot)
    assert msg_fm_ask.reply.called or mock_bot.copy_message.called
    print("✅ Qadam 3: 'fm raqamini qayerdan olaman' -> FM haqida ma'lumot berildi")

    # Qadam 4: Fiskal modul raqamini kiritish (LG420230615712)
    with patch.object(admin_manager, "notify_debt_free_device_issue", new_callable=AsyncMock) as mock_notify_admin:
        msg_fm = await send_simulated_msg("LG420230615712")
        await handle_user_chat(msg_fm, mock_bot)
        assert msg_fm.reply.called
        reply_fm = msg_fm.reply.call_args[0][0]
        assert "to'lovlar bo'yicha hech qanday qarzdorlik yo'q" in reply_fm.lower()
        assert "adminga" in reply_fm.lower() or "mas'ul mutaxassislarga" in reply_fm.lower()
        assert mock_notify_admin.called, "To'lovlar to'langan apparat muammosi zudlik bilan adminga uzatilishi shart"
        print("✅ Qadam 4: 'LG420230615712' -> Yillik litsenziya faol, internet/soat/reboot ko'rsatildi va adminga uzatildi (3-bosqich)")

    # Qadam 5: Userning sabrsizlik / noo'rin guruhdagi real xabarlari:
    # 'tashladimku boya', 'hudoga soldim', 'Gap qaytarma'
    print("\n--- [5-SSENARIY] Sabrsizlik va eskalatsiya qilingan foydalanuvchi xabarlari ---")

    msg_rep1 = await send_simulated_msg("tashladimku boya")
    await handle_user_chat(msg_rep1, mock_bot)
    assert msg_rep1.reply.called
    rep1_text = msg_rep1.reply.call_args[0][0]
    assert "admin javobini kuting" in rep1_text.lower(), f"Bot aljiramasdan admin javobini kuting deyishi kerak, chiqdi: {rep1_text}"
    print("✅ 'tashladimku boya' -> 'Murojaatingiz mas'ul administratorga yo'naltirilgan. Iltimos, admin javobini kuting!'")

    msg_rep2 = await send_simulated_msg("hudoga soldim")
    await handle_user_chat(msg_rep2, mock_bot)
    assert msg_rep2.reply.called
    rep2_text = msg_rep2.reply.call_args[0][0]
    assert "admin javobini kuting" in rep2_text.lower()
    print("✅ 'hudoga soldim' -> 'Murojaatingiz mas'ul administratorga yo'naltirilgan. Iltimos, admin javobini kuting!'")

    msg_rep3 = await send_simulated_msg("Gap qaytarma")
    await handle_user_chat(msg_rep3, mock_bot)
    assert msg_rep3.reply.called
    rep3_text = msg_rep3.reply.call_args[0][0]
    assert "admin javobini kuting" in rep3_text.lower()
    print("✅ 'Gap qaytarma' -> 'Murojaatingiz mas'ul administratorga yo'naltirilgan. Iltimos, admin javobini kuting!'")

    print("\n=================================================================")
    print("🎉 BARCHA GURUH REAL YOZISHMALARI BO'YICHA TESTLAR 100% MUVAFFAQ QATLANDI!")
    print("=================================================================\n")


if __name__ == "__main__":
    asyncio.run(test_telegram_group_real_conversations())
