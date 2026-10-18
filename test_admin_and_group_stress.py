import os
import asyncio
from telethon import TelegramClient

API_ID = int(os.getenv("TG_API_ID", "2040"))
API_HASH = os.getenv("TG_API_HASH", "b18441a1ff607e10a989891a5462e627")
BOT_USERNAME = "@marselektrontexnikamchj_bot"
GROUP_ID = -1003742874507  # Mars guruhi


async def send_cmd_and_get_reply(client: TelegramClient, entity, cmd: str, timeout: int = 8):
    print(f"\n📤 Yuborilmoqda: {cmd!r}")
    last_id = 0
    async for m in client.iter_messages(entity, limit=1):
        last_id = m.id

    await client.send_message(entity, cmd)

    replies = []
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        await asyncio.sleep(1)
        async for m in client.iter_messages(entity, limit=3):
            if m.id > last_id and m.out is False and m.id not in [r.id for r in replies]:
                replies.append(m)
        if replies:
            break

    if not replies:
        print("  ⚠️ Javob kelmadi (timeout).")
        return None

    print(f"  📥 Javob ({len(replies)} ta):")
    for r in replies:
        print(f"   >>> {r.text[:250]}...")
    return replies[0]


async def run_full_suite():
    # =========================================================================
    # 1-QISM: ADMIN MODULINI TO'LIQ TEST QILISH (Akkaunt 1 orqali)
    # =========================================================================
    print("=" * 60)
    print("1-BOSQICH: ADMIN MODULI TESTLARI (Akkaunt 1: @BIM_Project_Manager)")
    print("=" * 60)
    c1 = TelegramClient('data/tester_user', API_ID, API_HASH)
    await c1.connect()
    bot = await c1.get_entity(BOT_USERNAME)

    # 1.1 /admin paneli
    await send_cmd_and_get_reply(c1, bot, "/admin")
    await asyncio.sleep(1.5)

    # 1.2 /hududlar ro'yxati
    await send_cmd_and_get_reply(c1, bot, "/hududlar")
    await asyncio.sleep(1.5)

    # 1.3 /statistika
    await send_cmd_and_get_reply(c1, bot, "/statistika")
    await asyncio.sleep(1.5)

    # 1.4 /modules (Ulangan modullar)
    await send_cmd_and_get_reply(c1, bot, "/modules")
    await asyncio.sleep(1.5)

    # 1.5 /errors (Kassa xatoliklari bazasi)
    await send_cmd_and_get_reply(c1, bot, "/errors")
    await asyncio.sleep(1.5)

    # 1.6 /patches (Dinamik qoidalar)
    await send_cmd_and_get_reply(c1, bot, "/patches")
    await asyncio.sleep(1.5)

    # =========================================================================
    # 2-QISM: ADMINGA TEGISHLI BO'LMAGAN AKKAUNT (Akkaunt 2) ADMIN COMMAND BOSGANDA
    # =========================================================================
    print("\n" + "=" * 60)
    print("2-BOSQICH: XAVFSIZLIK TESTI (Oddiy mijoz /admin buyrug'ini bossa)")
    print("=" * 60)
    c2 = TelegramClient('data/tester_user_2', API_ID, API_HASH)
    await c2.connect()
    bot2 = await c2.get_entity(BOT_USERNAME)

    # Oddiy user /admin bossa, unga panel ochilmasligi kerak!
    r_unauth = await send_cmd_and_get_reply(c2, bot2, "/admin", timeout=4)
    if not r_unauth:
        print("  ✅ Muvaffaqiyatli: Oddiy foydalanuvchiga /admin javob bermadi (ruxsat yo'q)!")

    # =========================================================================
    # 3-QISM: GURUHDA «MAZGINI QOTIRADIGAN» MANTIQSIZ VA QAYTA SAVOLLAR STRESS-TESTI
    # =========================================================================
    print("\n" + "=" * 60)
    print("3-BOSQICH: GURUHDA MANTIQSIZ VA OG'IR SAVOLLAR STRESS-TESTI (Akkaunt 2 -> Guruh)")
    print("=" * 60)
    group_entity = await c2.get_entity(GROUP_ID)

    stress_messages = [
        # 1. Mantiqsiz gap
        "keldi lekin ketmadi nima qilay endi",
        
        # 2. Asabiylashish / sabrsizlik
        "alo alo kimdir bormi nega indamaysizlar",
        
        # 3. Ketma-ket takroriy sabrsizlik (eskalatsiya qulfi tekshiruvi)
        "qachon javob berasizlar jonga tegdi",
        
        # 4. Kassa apparati buzilishi lekin INN aytmaslik
        "aparatim ishlamay qoldi umuman ochmayapti pul yechyapti lekin yoqilmayapti",
        
        # 5. Mantiqsiz rad etish: "inn bilmayman o'zing top"
        "inn bilmayman o'zing topib ber",
        
        # 6. Haqiqiy INN tashlash (boshqa qadamga sakrash)
        "mana INN 311756421 (Koson tumani)",
        
        # 7. Qarzini ko'rgandan keyin: "qayerga to'layman"
        "qayerga to'layman",
        
        # 8. Yana chalkash qisqa so'rov: "yillikchi"
        "yillikchi",
        
        # 9. Usta so'rash
        "usta qani menga tezda usta kerak",
        
        # 10. Usta yo'naltirilgandan keyin yangi oddiy savol (eskalatsiya qulfi yechilishi kerak):
        "salom apparat soatini qanday to'g'irlayman"
    ]

    for idx, text in enumerate(stress_messages, 1):
        print(f"\n[Stress #{idx}] Guruhga jo'natilmoqda...")
        await send_cmd_and_get_reply(c2, group_entity, text, timeout=8)
        await asyncio.sleep(2.5)

    # 4-QISM: Akkaunt 1 (Admin) ning shaxsiy chatiga bildirishnoma yetib kelganini tekshirish
    print("\n" + "=" * 60)
    print("4-BOSQICH: AKKAUNT 1 GA ADMINGA YETKAZILGAN XABARNOMALARNI TEKSHIRISH")
    print("=" * 60)
    admin_notifications = []
    async for m in c1.iter_messages(bot, limit=5):
        if m.out is False:
            admin_notifications.append(m)

    print(f"📥 Adminga oxirgi kelgan {len(admin_notifications)} ta xabar:")
    for an in admin_notifications:
        print(f"  --- [{an.date}] ---\n{an.text[:200]}...")

    await c1.disconnect()
    await c2.disconnect()
    print("\n" + "=" * 60)
    print("HAMMA BOSQICHLAR YAKUNLANDI!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_full_suite())
