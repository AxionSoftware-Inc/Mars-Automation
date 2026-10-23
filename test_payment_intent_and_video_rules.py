import asyncio
from unittest.mock import AsyncMock, MagicMock
from aiogram import types, Bot
from payment_accounts import (
    classify_payment_intent,
    is_annual_pay_intent,
    is_monthly_pay_intent,
    is_how_to_pay_video_intent,
    MARS_POST_ID,
    MARS_VIDEO_ID,
    YANGI_TEXNOLOGIYALAR_POST_ID,
    YANGI_TEXNOLOGIYALAR_VIDEO_ID
)
from handlers.intents.billing import billing_intent_handler
from user_memory import user_memory

async def run_tests():
    print("=" * 70)
    print("🧪 TO'LOV VA VIDEO YO'RIQNOMA QOIDALARI TESTI")
    print("=" * 70)

    # 1. INTENT ANIQLANISHI TESTLARI
    print("\n--- 1-QISM: Intent klassifikatsiyasi ---")
    annual_phrases = [
        "yillik tulamoqchiydim",
        "yillik to'lamoqchi edim",
        "yillik tolamoqchiydim",
        "yillikka to'lamoqchiydim",
        "yillik to'lov qilmoqchiman",
        "yillik tolamoqchiman",
        "yillik shot tashlang",
        "йиллик тўламоқчийдим",
        "йиллик туламокчи эдим"
    ]
    for p in annual_phrases:
        intent = classify_payment_intent(p)
        ann = is_annual_pay_intent(p)
        vid = is_how_to_pay_video_intent(p)
        assert intent == "annual" or ann, f"Xato: '{p}' yillik deb topilmadi (intent={intent}, ann={ann})"
        assert not vid, f"Xato: '{p}' so'rovida video so'ralmagan bo'lsa ham video=True bo'ldi"
        print(f"✅ '{p}' -> Yillik to'lov aniqlandi, video=False")

    monthly_phrases = [
        "oylik to'lamoqchi",
        "oylik tolamoqchiydim",
        "oylik tulamoqchiydim",
        "oylik to'lamoqchi edim",
        "oylikka to'lamoqchiydim",
        "oylik tolov qilmoqchiman",
        "oylik tolamoqchiman",
        "oylik shot tashlang",
        "ойлик тўламоқчийдим",
        "ойлик туламокчи эдим"
    ]
    for p in monthly_phrases:
        intent = classify_payment_intent(p)
        mon = is_monthly_pay_intent(p)
        vid = is_how_to_pay_video_intent(p)
        assert intent == "monthly" or mon, f"Xato: '{p}' oylik deb topilmadi (intent={intent}, mon={mon})"
        assert not vid, f"Xato: '{p}' so'rovida video so'ralmagan bo'lsa ham video=True bo'ldi"
        print(f"✅ '{p}' -> Oylik to'lov aniqlandi, video=False")

    video_phrases = [
        "qanday to'lanadi",
        "qanday tolanadi",
        "qanday to'lash kerak",
        "qanday tolasa boladi",
        "to'lash videosi",
        "o'rgatilgan video",
        "videoni tashlang",
        "to'lash tartibini o'rgating",
        "yillik qanday to'lanadi",
        "oylik qanday to'lanadi"
    ]
    for p in video_phrases:
        vid = is_how_to_pay_video_intent(p)
        assert vid, f"Xato: '{p}' video so'rovi deb topilmadi"
        print(f"✅ '{p}' -> Video so'rovi to'g'ri aniqlandi (is_video=True)")

    # 2. BOT ORQALI SIMULYATSIYA TESTLARI
    print("\n--- 2-QISM: BillingIntentHandler amaliy javoblari ---")

    chat_id = 999888777
    user_id = 112233

    # Test 2.1: "yillik tulamoqchiydim"
    user_memory.clear_context(chat_id, user_id)
    bot = AsyncMock(spec=Bot)
    copied_messages = []
    async def mock_copy(chat_id, from_chat_id, message_id, **kwargs):
        copied_messages.append(message_id)
    bot.copy_message = mock_copy

    msg = AsyncMock()
    msg.chat = MagicMock()
    msg.chat.id = chat_id
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.from_user.username = "test_user"
    msg.text = "yillik tulamoqchiydim"
    msg.message_id = 100
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()

    handled = await billing_intent_handler.handle(msg, bot, "latin")
    assert handled, "Xabar handled bo'lmadi"
    assert YANGI_TEXNOLOGIYALAR_POST_ID in copied_messages, f"Post {YANGI_TEXNOLOGIYALAR_POST_ID} uzatilmadi! ({copied_messages})"
    assert YANGI_TEXNOLOGIYALAR_VIDEO_ID not in copied_messages, f"Xato: Video {YANGI_TEXNOLOGIYALAR_VIDEO_ID} avtomatik uzatib yuborildi!"
    assert MARS_POST_ID not in copied_messages, "Xato: Mars posti yillik so'rovida uzatildi"
    print("✅ 'yillik tulamoqchiydim' -> Faqat 34-post (Yangi Texnologiyalar shot) uzatildi, video uzatilmadi!")

    # Test 2.2: "oylik to'lamoqchiman"
    copied_messages.clear()
    msg.text = "oylik to'lamoqchiman"
    handled = await billing_intent_handler.handle(msg, bot, "latin")
    assert handled, "Xabar handled bo'lmadi"
    assert MARS_POST_ID in copied_messages, f"Post {MARS_POST_ID} uzatilmadi! ({copied_messages})"
    assert MARS_VIDEO_ID not in copied_messages, f"Xato: Video {MARS_VIDEO_ID} avtomatik uzatib yuborildi!"
    assert YANGI_TEXNOLOGIYALAR_POST_ID not in copied_messages, "Xato: Yangi Texnologiyalar posti oylik so'rovida uzatildi"
    print("✅ 'oylik to'lamoqchiman' -> Faqat 85-post (Mars oylik shot) uzatildi, video uzatilmadi!")

    # Test 2.3: "qanday to'lanadi" (oylik / umumiy kontekstda)
    copied_messages.clear()
    msg.text = "qanday to'lanadi"
    handled = await billing_intent_handler.handle(msg, bot, "latin")
    assert handled, "Xabar handled bo'lmadi"
    assert MARS_POST_ID in copied_messages, f"Post {MARS_POST_ID} uzatilmadi! ({copied_messages})"
    assert MARS_VIDEO_ID in copied_messages, f"Video {MARS_VIDEO_ID} uzatilmadi! ({copied_messages})"
    print("✅ 'qanday to'lanadi' -> 85-post va 148-video (Oylik to'lov videosi) muvaffaqiyatli uzatildi!")

    # Test 2.4: "yillik qanday to'lanadi"
    copied_messages.clear()
    msg.text = "yillik qanday to'lanadi"
    handled = await billing_intent_handler.handle(msg, bot, "latin")
    assert handled, "Xabar handled bo'lmadi"
    assert YANGI_TEXNOLOGIYALAR_POST_ID in copied_messages, f"Post {YANGI_TEXNOLOGIYALAR_POST_ID} uzatilmadi! ({copied_messages})"
    assert YANGI_TEXNOLOGIYALAR_VIDEO_ID in copied_messages, f"Video {YANGI_TEXNOLOGIYALAR_VIDEO_ID} uzatilmadi! ({copied_messages})"
    print("✅ 'yillik qanday to'lanadi' -> 34-post va 145-video (Yillik to'lov videosi) muvaffaqiyatli uzatildi!")

    # Test 2.5: "qayerga to'layman" -> video uzatilmasligi kerak!
    copied_messages.clear()
    msg.text = "qayerga to'layman"
    handled = await billing_intent_handler.handle(msg, bot, "latin")
    assert handled, "Xabar handled bo'lmadi"
    assert (MARS_POST_ID in copied_messages or YANGI_TEXNOLOGIYALAR_POST_ID in copied_messages), "Shot posti uzatilmadi"
    assert MARS_VIDEO_ID not in copied_messages, "Xato: 'qayerga to'layman' ga video uzatildi!"
    assert YANGI_TEXNOLOGIYALAR_VIDEO_ID not in copied_messages, "Xato: 'qayerga to'layman' ga yillik video uzatildi!"
    print("✅ 'qayerga to'layman' -> Faqat rekvizit posti uzatildi, video uzatilmadi!")

    print("\n🎉 BARCHA TESTLAR 100% MUVAFFAQIYATLI O'TDI!")

if __name__ == "__main__":
    asyncio.run(run_tests())
