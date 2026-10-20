import os
import asyncio
import logging
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "21950664"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "77189115ec44347fb9dc7c8dd29a39f6")
BOT_USERNAME = "marselektrontexnikamchj_bot"
GROUP_ID = -1003742874507

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def wait_for_bot_reply(client, peer, sent_msg_id, my_id, timeout=12):
    await asyncio.sleep(2.0)
    for _ in range(int(timeout * 2)):
        msgs = await client.get_messages(peer, limit=6)
        bot_msgs = [
            m for m in msgs 
            if m.id > sent_msg_id and (m.from_id is None or getattr(m.from_id, 'user_id', None) != my_id)
        ]
        if bot_msgs:
            await asyncio.sleep(1.5)
            msgs2 = await client.get_messages(peer, limit=6)
            bot_msgs2 = [
                m for m in msgs2 
                if m.id > sent_msg_id and (m.from_id is None or getattr(m.from_id, 'user_id', None) != my_id)
            ]
            bot_msgs2.sort(key=lambda x: x.id)
            combined_text = "\n---\n".join(m.text or "[Media/Post]" for m in bot_msgs2)
            return combined_text
        await asyncio.sleep(0.5)
    return None

async def main():
    client = TelegramClient("data/tester_user_2", API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    print(f"\n🔄 OYLIKCHI - YILLIKCHI - OYLIKCHI TAKRORIY SINOVI")
    print(f"👤 Mijoz akkaunti: {me.first_name} (ID: {me.id})")
    print(f"👥 Guruh ID: {GROUP_ID}\n" + "="*60)

    # 1. Avval korxona INN raqamini beramiz (NARZILLO BOBO MALLAYEV MCHJ: 311756421)
    print("\n[1-QADAM] INN tekshiruvi: '311756421'")
    s1 = await client.send_message(GROUP_ID, "311756421")
    r1 = await wait_for_bot_reply(client, GROUP_ID, s1.id, me.id)
    print(f"Bot javobi:\n{r1}\n")

    # 2. Endi 'oylikchi'
    print("\n[2-QADAM] Mijoz: 'oylikchi'")
    s2 = await client.send_message(GROUP_ID, "oylikchi")
    r2 = await wait_for_bot_reply(client, GROUP_ID, s2.id, me.id)
    print(f"Bot javobi:\n{r2}\n")

    # 3. Endi 'yillikchi'
    print("\n[3-QADAM] Mijoz: 'yillikchi'")
    s3 = await client.send_message(GROUP_ID, "yillikchi")
    r3 = await wait_for_bot_reply(client, GROUP_ID, s3.id, me.id)
    print(f"Bot javobi:\n{r3}\n")

    # 4. Yana 'oylikchi' (Aslo 'qarzdorlik yo'q 0 so'm' deyilmasligi shart!)
    print("\n[4-QADAM] Mijoz: 'oylikchi'")
    s4 = await client.send_message(GROUP_ID, "oylikchi")
    r4 = await wait_for_bot_reply(client, GROUP_ID, s4.id, me.id)
    print(f"Bot javobi:\n{r4}\n")

    # 5. Yana 'yillikchi'
    print("\n[5-QADAM] Mijoz: 'yillikchi'")
    s5 = await client.send_message(GROUP_ID, "yillikchi")
    r5 = await wait_for_bot_reply(client, GROUP_ID, s5.id, me.id)
    print(f"Bot javobi:\n{r5}\n")

    # 6. Yana 'oylikchi'
    print("\n[6-QADAM] Mijoz: 'oylikchi'")
    s6 = await client.send_message(GROUP_ID, "oylikchi")
    r6 = await wait_for_bot_reply(client, GROUP_ID, s6.id, me.id)
    print(f"Bot javobi:\n{r6}\n")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
