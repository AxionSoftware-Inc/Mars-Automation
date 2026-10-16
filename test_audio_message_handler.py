import asyncio
from unittest.mock import AsyncMock, MagicMock
from aiogram import types

from user_memory import user_memory
from handlers.media import handle_audio_message


async def test_audio_handler():
    print("\n=================================================================")
    print("🚀 AUDIO VA OVOZLI XABARLAR (VOICE/AUDIO) HANDLERI TESTI")
    print("=================================================================\n")

    chat_id = 123456789
    user_id = 987654321
    user_memory.sessions.clear()

    mock_user = types.User(id=user_id, is_bot=False, first_name="Sanjar", username="sanjar_aka")

    # 1. Voice (ovozli xabar) yuborilganda:
    msg_voice = AsyncMock(spec=types.Message)
    msg_voice.reply = AsyncMock()
    msg_voice.chat = MagicMock(id=chat_id)
    msg_voice.from_user = mock_user
    msg_voice.message_id = 11

    await handle_audio_message(msg_voice)
    assert msg_voice.reply.called
    voice_reply = msg_voice.reply.call_args[0][0]
    assert "matn ko'rinishida yozib yuboring" in voice_reply.lower() or "matn bilan" in voice_reply.lower()
    print("✅ 1-test (Voice): Ovozli xabar yuborilganda 'Iltimos, murojaatingizni matn ko'rinishida yozib yuboring' deb so'radi.")

    # 2. Audio (qo'shiq / mp3 / audio fayl) yuborilganda:
    msg_audio = AsyncMock(spec=types.Message)
    msg_audio.reply = AsyncMock()
    msg_audio.chat = MagicMock(id=chat_id)
    msg_audio.from_user = mock_user
    msg_audio.message_id = 12

    await handle_audio_message(msg_audio)
    assert msg_audio.reply.called
    audio_reply = msg_audio.reply.call_args[0][0]
    assert "matn ko'rinishida yozib yuboring" in audio_reply.lower()
    print("✅ 2-test (Audio fayl): Audio fayl yuborilganda ham matn bilan yozish so'raldi.")

    # 3. Video note (dumaloq video xabar) yuborilganda:
    msg_vnote = AsyncMock(spec=types.Message)
    msg_vnote.reply = AsyncMock()
    msg_vnote.chat = MagicMock(id=chat_id)
    msg_vnote.from_user = mock_user
    msg_vnote.message_id = 13

    await handle_audio_message(msg_vnote)
    assert msg_vnote.reply.called
    vnote_reply = msg_vnote.reply.call_args[0][0]
    assert "matn ko'rinishida yozib yuboring" in vnote_reply.lower()
    print("✅ 3-test (Video note): Dumaloq video xabar yuborilganda ham matn bilan yozish so'raldi.")

    print("\n=================================================================")
    print("🎉 AUDIO VA OVOZLI XABARLAR TESTI 100% MUVAFFAQIShLI O'TDI!")
    print("=================================================================\n")


if __name__ == "__main__":
    asyncio.run(test_audio_handler())
