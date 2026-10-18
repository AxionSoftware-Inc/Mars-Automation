import os
import sys
import asyncio
from telethon import TelegramClient

API_ID = int(os.getenv("TG_API_ID", "2040"))
API_HASH = os.getenv("TG_API_HASH", "b18441a1ff607e10a989891a5462e627")
BOT_USERNAME = "@marselektrontexnikamchj_bot"


async def send_and_wait_reply(client: TelegramClient, bot_entity, prompt: str, timeout: int = 10):
    """Xabar jo'natib botning javobini kutish va qaytarish"""
    print(f"\n📤 Yuborilmoqda: {prompt!r}")
    # Avval eng oxirgi xabar ID sini bilib olamiz
    last_id = 0
    async for m in client.iter_messages(bot_entity, limit=1):
        last_id = m.id

    await client.send_message(bot_entity, prompt)

    # Botdan javob kutish
    replies = []
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        await asyncio.sleep(1)
        async for m in client.iter_messages(bot_entity, limit=3):
            if m.id > last_id and m.out is False and m.id not in [r.id for r in replies]:
                replies.append(m)
        if replies:
            # Biroz kutamiz, balki 2-xabar (video yoki forward post) ham kelar
            await asyncio.sleep(1.5)
            async for m in client.iter_messages(bot_entity, limit=3):
                if m.id > last_id and m.out is False and m.id not in [r.id for r in replies]:
                    replies.append(m)
            break

    if not replies:
        print("⚠️ Botdan javob kelmadi (timeout).")
        return []

    print(f"📥 Botdan {len(replies)} ta javob keldi:")
    for idx, r in enumerate(reversed(replies), 1):
        btn_info = ""
        if r.reply_markup and hasattr(r.reply_markup, 'rows'):
            btn_texts = []
            for row in r.reply_markup.rows:
                for b in row.buttons:
                    btn_texts.append(f"[{b.text}]")
            btn_info = " | Tugmalar: " + ", ".join(btn_texts)
        media_info = f" [Media/Post: {r.media.__class__.__name__}]" if r.media else ""
        print(f"  {idx}) {r.text[:300] if r.text else ''}{media_info}{btn_info}")
    return replies


async def run_scenario_suite():
    # 1-akkaunt bilan test: Shahrisabz va hisob raqamlar
    c1 = TelegramClient('data/tester_user', API_ID, API_HASH)
    await c1.connect()
    bot = await c1.get_entity(BOT_USERNAME)

    print("==================================================")
    print("TEST 1: Akkaunt 1 (@BIM_Project_Manager) — Qarz va Hisob raqamlar")
    print("==================================================")
    
    # 1. Shahrisabz INN qarzini tekshirish
    await send_and_wait_reply(c1, bot, "203347382")
    await asyncio.sleep(2)

    # 2. Oylikchi / Yillikchi kontekstual hisob raqam so'rovi
    await send_and_wait_reply(c1, bot, "oylik shot tashlang")
    await asyncio.sleep(2)

    # 3. Yillikchi so'rovi (to'g'ri rekvizit post uzatilishi kerak)
    await send_and_wait_reply(c1, bot, "yillikchi")
    await asyncio.sleep(2)

    # 4. Apparat nosozligi va eskalatsiya
    await send_and_wait_reply(c1, bot, "aparatim qotib qoldi ishlamayapti")
    await asyncio.sleep(2)

    await c1.disconnect()

    # 2-akkaunt bilan test: Qarshi INN va xatoliklar
    print("\n==================================================")
    print("TEST 2: Akkaunt 2 — Chala INN va Bitta hisobga to'lash")
    print("==================================================")
    c2 = TelegramClient('data/tester_user_2', API_ID, API_HASH)
    await c2.connect()
    bot2 = await c2.get_entity(BOT_USERNAME)

    # 5. Chala INN
    await send_and_wait_reply(c2, bot2, "INN 12345")
    await asyncio.sleep(2)

    # 6. Bitta shotga to'lasam bo'ladimi?
    await send_and_wait_reply(c2, bot2, "ikkala tolovni bitta shotga tashlasam boladimi")
    await asyncio.sleep(2)

    # 7. Kitob INN tekshirish
    await send_and_wait_reply(c2, bot2, "301427795")
    await asyncio.sleep(2)

    await c2.disconnect()
    print("\n==================================================")
    print("BARCHA TESTLAR YAKUNLANDI!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(run_scenario_suite())
