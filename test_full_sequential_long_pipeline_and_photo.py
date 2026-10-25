import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types

from user_memory import user_memory
from admin_manager import admin_manager
from handlers.chat import handle_user_chat
from handlers.media import _process_image_content
from ofd_bridge import ofd_bridge
from core.models import DeviceFacts


async def test_full_pipeline_flows():
    print("\n=================================================================")
    print("🚀 BOSQICHMA-BOSQICH TO'LIQ PIPELINE VA UZOQ SUHBATLAR TESTI")
    print("=================================================================\n")

    mock_bot = AsyncMock()
    chat_id = 9988776655
    user_id = 1122334455

    mock_user = types.User(id=user_id, is_bot=False, first_name="Akmal", username="akmal_test")

    async def send_msg(text: str) -> types.Message:
        msg = AsyncMock(spec=types.Message)
        msg.reply = AsyncMock()
        msg.text = text
        msg.chat = MagicMock(id=chat_id)
        msg.from_user = mock_user
        msg.message_id = 100 + len(user_memory.sessions.get(f"{chat_id}_{user_id}", {}).get("user_messages", []))
        return msg

    # =========================================================================
    # SSENARIY 1: OYLIKDAN QARZ BOR
    # =========================================================================
    print("--- [SSENARIY 1] Oylikdan qarz bor bo'lgan holat ---")
    user_memory.sessions.clear()

    # 1. User apparat ishlamayotganini aytadi
    m1 = await send_msg("apparatim ishlamayapti")
    await handle_user_chat(m1, mock_bot)
    assert m1.reply.called
    rep1 = m1.reply.call_args[0][0]
    assert "inn" in rep1.lower(), "1-bosqichda INN so'ralishi kerak"
    print("✅ 1-qadam: 'apparatim ishlamayapti' -> INN so'raldi")

    # 2. Qarzli INN (masalan, 206011507 - QASHQADARYO SHARQ GAVHARI MCHJ)
    m2 = await send_msg("206011507")
    await handle_user_chat(m2, mock_bot)
    assert m2.reply.called
    rep2 = m2.reply.call_args[0][0]
    assert "qarzdorlik" in rep2.lower() and ("1 500 400" in rep2 or "1500400" in rep2 or "qashqadaryo" in rep2.lower()), "Oylik qarz summasi chiqishi kerak"
    assert mock_bot.copy_message.called, "Mars hisob raqami kanaldan uzatilishi kerak"
    print("✅ 2-qadam: Oylik qarzdorlik summasi, hisob raqam va Click video yuborildi")

    # =========================================================================
    # SSENARIY 2: OYLIKDAN QARZ YO'Q, YILLIKDAN QARZ BOR
    # =========================================================================
    print("\n--- [SSENARIY 2] Oylikdan qarz yo'q, Yillikdan qarz bor bo'lgan holat ---")
    user_memory.sessions.clear()

    m1 = await send_msg("kassa ishlamayapti")
    await handle_user_chat(m1, mock_bot)
    assert m1.reply.called

    # 300600431 -> Oylik qarz 0 so'm
    m2 = await send_msg("300600431")
    await handle_user_chat(m2, mock_bot)
    assert m2.reply.called
    rep2 = m2.reply.call_args[0][0]
    assert "fiskal modul" in rep2.lower(), "Oylik qarz 0 bo'lgach, Fiskal modul so'ralishi kerak"
    print("✅ 1-qadam: Oylik qarz yo'q (0 so'm) -> Yillik Soliq uchun Fiskal modul so'raldi")

    # OFD qarz qaytargan holat:
    with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
        mock_ofd.return_value = "FMO dan qarzdorlik mavjud. To'lov summasi 440 000 so'm."
        m3 = await send_msg("LG999999999999")
        await handle_user_chat(m3, mock_bot)
        assert m3.reply.called
        rep3 = m3.reply.call_args[0][0]
        assert "yillik soliq" in rep3.lower() or "qarzdorlik mavjud" in rep3.lower()
        assert "440 000" in rep3
        print("✅ 2-qadam: Yillik Soliq (OFD) qarzi (440 000 so'm) va Yangi Texnologiyalar rekviziti berildi")

    # =========================================================================
    # SSENARIY 3: OYLIK VA YILLIK QARZ YO'Q -> RASM SO'RASH VA ADMINGA UZATISH
    # =========================================================================
    print("\n--- [SSENARIY 3] Ikkala to'lov ham 100% to'langan -> Rasm so'rash va Adminga uzatish ---")
    user_memory.sessions.clear()

    m1 = await send_msg("apparatim ishlamayapti negadir")
    await handle_user_chat(m1, mock_bot)

    m2 = await send_msg("300600431")
    await handle_user_chat(m2, mock_bot)

    # LG420230615712 -> Faol, qarzdorlik yo'q
    with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
        mock_ofd.return_value = "Fiskal modul faol. Muddati 2026-12-31 gacha."
        m3 = await send_msg("LG420230615712")
        await handle_user_chat(m3, mock_bot)
        assert m3.reply.called
        rep3 = m3.reply.call_args[0][0]
        assert "to'lovlar bo'yicha hech qanday qarzdorlik yo'q" in rep3.lower()
        assert "rasmga olib yuboring" in rep3.lower(), "Qarzdorlik bo'lmaganda rasm so'ralishi kerak"
        print("✅ 1-qadam: To'lovlardan qarz yo'q -> Ekrandagi xatolikni rasmga olib yuborish so'raldi")

    # Endi user apparat ekran rasmini yuboradi:
    fake_device_facts = DeviceFacts(
        is_real_pos_device=True,
        is_status_bar_visible=True,
        has_internet=True,
        error_type="technical",
        screen_text_summary="Tarmoqqa ulanish xatosi"
    )

    with patch("handlers.media.analyze_media_image") as mock_vision, \
         patch.object(admin_manager, "notify_debt_free_device_issue", new_callable=AsyncMock) as mock_admin_alert:
        mock_vision.return_value = ("pos_device", None, fake_device_facts)

        msg_photo = AsyncMock(spec=types.Message)
        msg_photo.reply = AsyncMock()
        msg_photo.chat = MagicMock(id=chat_id)
        msg_photo.from_user = mock_user
        msg_photo.message_id = 999
        msg_photo.media_group_id = None
        msg_photo.caption = "Mana rasm ko'ringlar"

        await _process_image_content(
            message=msg_photo,
            bot=mock_bot,
            image_bytes=b"fake_image_bytes",
            caption="Mana rasm ko'ringlar",
            file_id="photo_file_12345"
        )

        # Foydalanuvchiga: "Iltimos kuting, barcha ma'lumotlaringiz mas'ul adminga yuborildi!"
        assert msg_photo.reply.called
        photo_reply = msg_photo.reply.call_args[0][0]
        assert "adminga yuborildi" in photo_reply.lower() or "adminga yetkazildi" in photo_reply.lower(), \
            f"Kutilgan javob chiqmadi, chiqdi: {photo_reply}"
        assert "300600431" in photo_reply
        assert "LG420230615712" in photo_reply

        # Adminga barcha ma'lumotlar uzatilganini tekshirish
        assert mock_admin_alert.called
        alert_args = mock_admin_alert.call_args[1]
        assert alert_args["inn"] == "300600431"
        assert alert_args["fiscal_module"] == "LG420230615712"
        assert alert_args["photo_file_id"] == "photo_file_12345"
        print("✅ 2-qadam: Rasm yuborilgach, INN, FM va rasm adminga yetkazildi va userga 'Iltimos kuting, barcha ma'lumotlaringiz mas'ul adminga yuborildi' deyildi!")

    # =========================================================================
    # SSENARIY 4: KETMA-KET UZOQ DAVOM ETGAN SUHBAT (GAP CHO'ZILSA)
    # =========================================================================
    print("\n--- [SSENARIY 4] Ketma-ket uzoq davom etgan suhbat (gap cho'zilishi) ---")
    user_memory.sessions.clear()

    # Foydalanuvchi ketma-ket 4 marta savol berib gapni cho'zadi:
    t1 = await send_msg("salom yaxshimisiz")
    await handle_user_chat(t1, mock_bot)

    t2 = await send_msg("siz qanaqa botsiz")
    await handle_user_chat(t2, mock_bot)

    t3 = await send_msg("kassa apparat qanaqa ishlaydi ozi")
    await handle_user_chat(t3, mock_bot)

    # 4-navbatda gap cho'zilgani va sabrsizlik uchun adminga eskalatsiya qilinishi shart!
    with patch.object(admin_manager, "notify_user_query_escalation", new_callable=AsyncMock) as mock_esc:
        t4 = await send_msg("e javob beringlar alo nega indamaysiz")
        await handle_user_chat(t4, mock_bot)
        assert t4.reply.called
        rep4 = t4.reply.call_args[0][0]
        assert "adminga" in rep4.lower() or "admin javobini kuting" in rep4.lower(), \
            f"Uzoq suhbatda adminga yo'naltirilishi kerak, chiqdi: {rep4}"
        assert mock_esc.called, "Uzoq suhbat adminga xabarnoma yuborishi shart"
        print("✅ 4-navbat: Gap cho'zilgan foydalanuvchi avtomatik mas'ul adminga yo'naltirildi!")

    print("\n=================================================================")
    print("🎉 BARCHA TALABLAR BO'YICHA 4 TA ASOSIY SSENARIY 100% MUVAFFAQIShLI O'TDI!")
    print("=================================================================\n")


if __name__ == "__main__":
    asyncio.run(test_full_pipeline_flows())
