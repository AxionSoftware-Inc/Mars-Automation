import asyncio
import time
import paramiko
from telethon import TelegramClient

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
GROUP_ID = -1003742874507


async def run_live_test():
    print("=" * 70)
    print("🚀 GURUHDA JONLI (LIVE) KVITANSIYA TESTI (-1003742874507)")
    print("=" * 70)

    client = TelegramClient("data/userbot_test_2", API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print("Userbot authorized emas! data/ofd_user sinab ko'riladi...")
        await client.disconnect()
        client = TelegramClient("data/ofd_user", API_ID, API_HASH)
        await client.connect()

    me = await client.get_me()
    print(f"Connected as: {me.first_name} (@{me.username}, id={me.id})")

    # 1-Qadam: Guruhga avval qarzdor INN (307314860 -> 2,100,000 so'm qarz) yuboramiz
    print("\n1) Guruhga qarzdor INN (307314860) yuborilmoqda...")
    sent_inn = await client.send_message(GROUP_ID, "307314860")
    await asyncio.sleep(5)

    msgs = await client.get_messages(GROUP_ID, limit=5)
    for m in msgs:
        if m.reply_to and m.reply_to.reply_to_msg_id == sent_inn.id:
            print(f"\n[BOT JAVOBI 1 - INN 307314860]:\n{m.text}\n")
            break

    # 2-Qadam: Guruhdan yuklab olingan haqiqiy kvitansiyani (/tmp/group_msg_1139.jpg) qayta tashlaymiz!
    print("2) Guruhga haqiqiy kvitansiya (/tmp/group_msg_1139.jpg - 08.10.2026, 100,000 so'm, 32108755590021) yuborilmoqda...")
    sent_photo = await client.send_file(GROUP_ID, "/tmp/group_msg_1139.jpg")
    await asyncio.sleep(10)

    msgs2 = await client.get_messages(GROUP_ID, limit=6)
    bot_receipt_reply = None
    for m in msgs2:
        if m.reply_to and m.reply_to.reply_to_msg_id == sent_photo.id:
            bot_receipt_reply = m.text
            print(f"\n[BOT JAVOBI 2 - KVITANSIYAGA]:\n{m.text}\n")
            break

    # 3-Qadam: Kvitansiyadan keyin "oylikchi" deb so'rab ko'ramiz — qarz 0 bo'lib qolmadimi yoki 2,100,000 so'm turibdimi?
    print("3) Kvitansiyadan keyin 'oylikchi' deb so'ralmoqda (qarz 0 ga aylanib qolmaganini tekshirish)...")
    sent_oylik = await client.send_message(GROUP_ID, "oylikchi")
    await asyncio.sleep(6)

    msgs3 = await client.get_messages(GROUP_ID, limit=6)
    for m in msgs3:
        if m.reply_to and m.reply_to.reply_to_msg_id == sent_oylik.id:
            print(f"\n[BOT JAVOBI 3 - 'oylikchi' KVITANSIYADAN KEYIN]:\n{m.text}\n")
            break

    await client.disconnect()

    # 4-Qadam: Server loglaridan va adminga borgan xabardan tekshirish
    print("\n4) Serverdagi journalctl loglari tekshirilmoqda...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("169.58.123.200", username="root", password="LEGIONGAMING", timeout=15)
    _, stdout, _ = ssh.exec_command("journalctl -u mars-bot.service -n 40 --no-pager")
    print(stdout.read().decode())
    ssh.close()


if __name__ == "__main__":
    asyncio.run(run_live_test())
