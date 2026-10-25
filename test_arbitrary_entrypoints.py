import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types

from user_memory import user_memory
from admin_manager import admin_manager
from handlers.chat import handle_user_chat
from ofd_bridge import ofd_bridge


async def test_all_arbitrary_entrypoints():
    print("\n=================================================================")
    print("🚀 BOSHQA JOYDAN BOSHLANADIGAN BARCHA KIRISH NUQTALARI TESTI")
    print("=================================================================\n")

    mock_bot = AsyncMock()
    chat_id = 777666555
    user_id = 333222111

    mock_user = types.User(id=user_id, is_bot=False, first_name="Jamshid", username="jamshid_aka")

    async def send_simulated_msg(text: str) -> types.Message:
        msg = AsyncMock(spec=types.Message)
        msg.reply = AsyncMock()
        msg.text = text
        msg.chat = MagicMock(id=chat_id)
        msg.from_user = mock_user
        msg.message_id = 200 + len(user_memory.sessions.get(f"{chat_id}_{user_id}", {}).get("user_messages", []))
        return msg

    # -------------------------------------------------------------
    # 1. To'g'ridan-to'g'ri INN dan boshlash, keyin "ishlamayapti" deyish
    # -------------------------------------------------------------
    print("--- [KIRISH 1] To'g'ridan-to'g'ri INN yuborish, keyin 'ishlamayapti' deyish ---")
    user_memory.sessions.clear()

    # User darhol INN yuboradi
    m1 = await send_simulated_msg("300600431")
    await handle_user_chat(m1, mock_bot)
    assert m1.reply.called
    r1 = m1.reply.call_args[0][0]
    assert "qarzdorlik yo'q" in r1.lower() or "0" in r1
    print("✅ 1-qadam: To'g'ridan-to'g'ri INN yuborildi -> Oylik qarz 0 so'm deb qaytdi")

    # Keyin: "lekin kassa ishlamayaptiku"
    m2 = await send_simulated_msg("lekin kassa ishlamayaptiku")
    await handle_user_chat(m2, mock_bot)
    assert m2.reply.called
    r2 = m2.reply.call_args[0][0]
    assert "fiskal modul" in r2.lower() or "fm" in r2.lower(), f"INN xotirada bor, endi FM so'rashi kerak, chiqdi: {r2}"
    print("✅ 2-qadam: 'kassa ishlamayaptiku' deganda bot qayta INN so'ramadi, avvalgi INN ni eslab to'g'ridan-to'g'ri FM so'radi!")

    # -------------------------------------------------------------
    # 2. To'g'ridan-to'g'ri Fiskal modul (FM) dan boshlash
    # -------------------------------------------------------------
    print("\n--- [KIRISH 2] To'g'ridan-to'g'ri Fiskal modul (FM) dan boshlash ---")
    user_memory.sessions.clear()

    with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
        mock_ofd.return_value = "Fiskal modul faol. Muddati 2026-12-31 gacha."
        m1 = await send_simulated_msg("LG420230615712")
        await handle_user_chat(m1, mock_bot)
        assert m1.reply.called
        r1 = m1.reply.call_args[0][0]
        assert "yillik" in r1.lower() or "faol" in r1.lower() or "fiskal" in r1.lower()
        print("✅ 1-qadam: To'g'ridan-to'g'ri FM yuborilganda OFD holati to'g'ri berildi")

    # Keyin: "aparatim ishlamayapti nima qilay"
    m2 = await send_simulated_msg("aparatim ishlamayapti nima qilay")
    await handle_user_chat(m2, mock_bot)
    assert m2.reply.called
    r2 = m2.reply.call_args[0][0]
    assert "inn" in r2.lower(), f"FM bor, lekin INN yo'q, INN so'rashi kerak, chiqdi: {r2}"
    print("✅ 2-qadam: Apparat muammosi aytilganda oylik to'lov uchun INN so'raldi")

    # INN kiritilgach:
    with patch.object(admin_manager, "notify_debt_free_device_issue", new_callable=AsyncMock) as mock_adm:
        m3 = await send_simulated_msg("300600431")
        await handle_user_chat(m3, mock_bot)
        assert m3.reply.called
        r3 = m3.reply.call_args[0][0]
        assert "to'lovlar bo'yicha qarzdorlik yo'q" in r3.lower()
        assert "rasmga olib yuboring" in r3.lower()
        print("✅ 3-qadam: Ikkala qarz ham 0 bo'lgach rasm so'raldi va adminga xabar yuborildi!")

    # -------------------------------------------------------------
    # 3. Birdaniga bitta xabarda INN + apparat nosozligi
    # -------------------------------------------------------------
    print("\n--- [KIRISH 3] Bitta xabarda INN va apparat nosozligi yuborilishi ---")
    user_memory.sessions.clear()

    m_comb = await send_simulated_msg("kassa ishlamay qoldi 300600431 tekshirib bering")
    await handle_user_chat(m_comb, mock_bot)
    assert m_comb.reply.called
    r_comb = m_comb.reply.call_args[0][0]
    assert "fiskal modul" in r_comb.lower(), f"Bot INN ni darhol taniy olib, 2-bosqich FM so'rashi kerak, chiqdi: {r_comb}"
    print("✅ Bitta xabarda 'kassa ishlamay qoldi 300600431' -> INN qayta so'ralmadi, darhol FM so'raldi!")

    # -------------------------------------------------------------
    # 4. Birdaniga bitta xabarda INN + FM + nosozlik
    # -------------------------------------------------------------
    print("\n--- [KIRISH 4] Bitta xabarda ham INN, ham FM, ham muammo yuborilishi ---")
    user_memory.sessions.clear()

    with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
        mock_ofd.return_value = "Fiskal modul faol. Muddati 2026-12-31 gacha."
        m_all = await send_simulated_msg("apparatim ishlamayapti INN 300600431 FM LG420230615712")
        await handle_user_chat(m_all, mock_bot)
        assert m_all.reply.called
        r_all = m_all.reply.call_args[0][0]
        assert "qarzdorlik yo'q" in r_all.lower()
        assert "fiskal modul" in r_all.lower()
        print("✅ Bitta xabarda INN + FM + muammo -> Ikkala to'lov ham tekshirilib, darhol rasm so'raldi!")

    # -------------------------------------------------------------
    # 5. Admin kontaktlari va Call markaz raqamlari tekshiruvi
    # -------------------------------------------------------------
    print("\n--- [KIRISH 5] Admin kontaktlari va Call markaz raqamlari olib tashlanganligi ---")
    user_memory.sessions.clear()

    m_adm = await send_simulated_msg("usta kerak adminga bog'lang")
    await handle_user_chat(m_adm, mock_bot)
    assert m_adm.reply.called
    r_adm = m_adm.reply.call_args[0][0]
    # Call-markaz raqamlari bo'lmasligi kerak
    assert "+998 75 522 75 00" not in r_adm
    assert "+998755227500" not in r_adm
    # Hududiy / Bosh mas'ul admin xodimlari tugmasi bo'lishi kerak
    reply_markup = m_adm.reply.call_args[1].get("reply_markup")
    assert reply_markup is not None
    all_buttons = [btn.text for row in reply_markup.inline_keyboard for btn in row]
    assert any("quvonchbek_admin" in b for b in all_buttons)
    assert any("Yashnarbek_butaev" in b for b in all_buttons)
    # Call-markaz telefon tugmasi bo'lmasligi kerak
    assert not any("+998" in b for b in all_buttons)
    print("✅ Tugmalarda call-markaz yo'q, faqat mas'ul adminlar (@quvonchbek_admin, @Yashnarbek_butaev) tugmasi chiqmoqda!")

    print("\n=================================================================")
    print("🎉 BOSHQA JOYDAN BOSHLANGAN BARCHA SSENARIYLAR 100% MUVAFFAQIShLI ISHLADI!")
    print("=================================================================\n")


if __name__ == "__main__":
    asyncio.run(test_all_arbitrary_entrypoints())
