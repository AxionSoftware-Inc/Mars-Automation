import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types

from user_memory import user_memory
from admin_manager import admin_manager, get_admin_contact_keyboard
from handlers.chat import handle_user_chat

async def run_tests():
    print("=== TEST 1: User gapni cho'zganda adminga yo'naltirish ===")
    user_memory.sessions.clear()
    chat_id = 111222333
    user_id = 444555666

    mock_bot = AsyncMock()
    mock_user = types.User(id=user_id, is_bot=False, first_name="Shokir", username="shokir_aka")

    msg1 = AsyncMock(spec=types.Message)
    msg1.reply = AsyncMock()
    msg1.text = "e qachon javob berasizlar kutib qoldimku alo"
    msg1.chat = MagicMock(id=chat_id)
    msg1.from_user = mock_user
    msg1.message_id = 501

    with patch.object(admin_manager, "notify_user_query_escalation", new_callable=AsyncMock) as mock_admin_notify:
        await handle_user_chat(msg1, mock_bot)

        # 1. Bot javob berganini tekshirish
        assert msg1.reply.called
        reply_call = msg1.reply.call_args
        reply_text = reply_call[0][0]
        assert "adminga yo'naltirdik" in reply_text.lower() or "admin javobini kuting" in reply_text.lower()
        
        # 2. Admin inline tugmalari berilganini tekshirish
        assert "reply_markup" in reply_call[1]
        assert reply_call[1]["reply_markup"] is not None
        assert "quvonchbek_admin" in reply_call[1]["reply_markup"].inline_keyboard[0][0].url

        # 3. Adminga xabarnoma borganini tekshirish
        assert mock_admin_notify.called
        assert "gapni cho'zdi" in mock_admin_notify.call_args[1]["reason"].lower()

        # 4. User xotirada eskalatsiya holatiga o'tganini tekshirish
        assert user_memory.is_escalated_to_admin(chat_id, user_id) is True
        print("✅ 1-qadam: Gapni cho'zgan user adminga yo'naltirildi va unga admin javobini kuting deyildi.")

    print("\n=== TEST 2: Aynan shu user yana gapni cho'zganda ===")
    msg2 = AsyncMock(spec=types.Message)
    msg2.reply = AsyncMock()
    msg2.text = "nega indamaysan kim bor u yerda"
    msg2.chat = MagicMock(id=chat_id)
    msg2.from_user = mock_user
    msg2.message_id = 502

    with patch.object(admin_manager, "notify_user_query_escalation", new_callable=AsyncMock) as mock_admin_notify2:
        await handle_user_chat(msg2, mock_bot)

        assert msg2.reply.called
        reply_call2 = msg2.reply.call_args
        reply_text2 = reply_call2[0][0]
        assert "admin javobini kuting" in reply_text2.lower()
        assert "reply_markup" in reply_call2[1]
        print("✅ 2-qadam: Aynan shu user yana yozganda bot chalg'imay yana admin javobini kuting dedi.")

    print("\n=== TEST 3: Boshqa user uchun tizim toza va normal ishlashi ===")
    other_chat_id = 999888
    other_user_id = 777666
    assert user_memory.is_escalated_to_admin(other_chat_id, other_user_id) is False

    msg_other = AsyncMock(spec=types.Message)
    msg_other.reply = AsyncMock()
    msg_other.text = "206011507"
    msg_other.chat = MagicMock(id=other_chat_id)
    msg_other.from_user = types.User(id=other_user_id, is_bot=False, first_name="Boshqa", username="boshqa_user")
    msg_other.message_id = 503

    # Boshqa user INN tekshirishi mumkin
    from excel_manager import excel_manager
    with patch.object(excel_manager, "search", return_value=[{"name": "QASHQADARYO SHARQ GAVHARI MCHJ", "debt": 100000.0, "inn": "206011507"}]):
        await handle_user_chat(msg_other, mock_bot)
        assert msg_other.reply.called
        other_reply = msg_other.reply.call_args[0][0]
        assert "100 000" in other_reply or "qarzdorlik" in other_reply.lower()
        print("✅ 3-qadam: Boshqa userlar uchun normal holatda ishlashda davom etmoqda.")

    print("\n🎉 BARCHA GAPNI CHO'ZISH SINOVLARI 100% MUVAFFAQIShLI O'TDI!")

if __name__ == "__main__":
    asyncio.run(run_tests())
