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
logger = logging.getLogger("stubborn_tester")

# Injiq, hech narsani tushunmaydigan, qayta-qayta savol beradigan mijoz replikalari:
SCENARIOS = [
    {
        "step": 1,
        "input": "e nimaga ishlamayapti bu narsa",
        "description": "Noaniq shikoyat (hech narsa tushuntirmagan mijoz)",
        "expect_any": ["qanday xatolik", "muammo", "ekran", "STIR", "yordam", "qanday holat", "rasm"]
    },
    {
        "step": 2,
        "input": "qayerga to'lash kerak o'zi tushunmadim",
        "description": "Tushunmasdan to'lov haqida chala savol berish",
        "expect_any": ["oylik", "yillik", "to'lov", "Mars", "Yangi Texnologiyalar", "kartasi"]
    },
    {
        "step": 3,
        "input": "oylikka qancha to'layman o'zi",
        "description": "Oylik to'lov summasi haqida so'rash",
        "expect_any": ["100 000", "100000", "oylik", "Mars"]
    },
    {
        "step": 4,
        "input": "nega yuz ming qimmatku, yillik qancha unda",
        "description": "Injiqlik qilib yillikka sakrash (kontekst almashishi)",
        "expect_any": ["440 000", "440000", "Yangi Texnologiyalar", "litsenziya", "DUK"]
    },
    {
        "step": 5,
        "input": "yana qanaqa yangi texnologiyalar u nima u",
        "description": "Yangi Texnologiyalar DUK nimaligini tushunmasdan so'rash",
        "expect_any": ["Davlat soliq", "DUK", "Yangi Texnologiyalar", "OFD", "litsenziya", "soliq", "unitar"]
    },
    {
        "step": 6,
        "input": "oylikni qayerga tolayman deb soradimku boya",
        "description": "Yana injiqlik qilib oylik to'lov kartasini qayta talab qilish",
        "expect_any": ["100 000", "Mars", "hisob", "karta", "85", "148", "clik"]
    },
    {
        "step": 7,
        "input": "fiskal modul nima u qayerda boladi chekim yoqda meni",
        "description": "Chekim yo'q deb fiskal modul qayerdaligini so'rash",
        "expect_any": ["korpus", "nakleyka", "oq", "orqa", "LG", "YG", "rasm"]
    },
    {
        "step": 8,
        "input": "cheksiz bilib bolmaydimi apparatim yonimda turibdiku",
        "description": "Qayta tushunmaslik: cheksiz qanday bilish",
        "expect_any": ["korpus", "nakleyka", "orqa", "batareya", "rasm", "LG", "СТИР", "INN"]
    },
    {
        "step": 9,
        "input": "ha orqasida LG420210630789 deb yozilgan ekan shu nima endi",
        "description": "FM raqamini aytib berish",
        "expect_any": ["LG420210630789", "OFD", "muddat", "litsenziya", "faol", "amal qilish", "to'lov", "qarzdorlik"]
    },
    {
        "step": 10,
        "input": "yaxshi endi oylik qarzim bormi yoqmi shuni ayt menga",
        "description": "Oylik qarzni tekshirishni talab qilish",
        "expect_any": ["STIR", "INN", "raqam", "qarzdorlik", "korxona"]
    },
    {
        "step": 11,
        "input": "mana 305123456 qara qancha ekan",
        "description": "STIR yuborish (qo'polroq ohangda)",
        "expect_any": ["305123456", "qarz", "oylik", "so'm", "holat", "topilmadi"]
    },
    {
        "step": 12,
        "input": "ha tushundim raxmat katta sizlarga",
        "description": "Minnatdorchilik bildirish (adminga aslo o'tmasligi shart)",
        "expect_any": ["arzimaydi", "salomat", "yordam", "xizmat", "xushvaqt"]
    }
]

async def wait_for_bot_reply(client, peer, sent_msg_id, my_id, timeout=12):
    await asyncio.sleep(2.0)
    for _ in range(int(timeout * 2)):
        msgs = await client.get_messages(peer, limit=6)
        bot_msgs = [
            m for m in msgs 
            if m.id > sent_msg_id and (m.from_id is None or getattr(m.from_id, 'user_id', None) != my_id)
        ]
        if bot_msgs:
            # Kutamiz, agar ikkinchi xabar (video/post) ham uzatilayotgan bo'lsa
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
    print(f"\n🎭 INJIQ MIJOZ SIFATIDA TEST BOSHLANDI")
    print(f"👤 Mijoz akkaunti: {me.first_name} (ID: {me.id})")
    print(f"👥 Guruh ID: {GROUP_ID}")
    print(f"🤖 Bot: @{BOT_USERNAME}\n" + "="*60)

    all_passed = True
    test_logs = []

    for item in SCENARIOS:
        step_num = item["step"]
        user_msg = item["input"]
        desc = item["description"]

        print(f"\n▶️ [QADAM {step_num}/12] {desc}")
        print(f"   💬 Injiq mijoz yozdi: \"{user_msg}\"")

        # Guruhga yuboramiz
        sent = await client.send_message(GROUP_ID, user_msg)
        reply = await wait_for_bot_reply(client, GROUP_ID, sent.id, me.id, timeout=14)

        if not reply:
            print(f"   ❌ BOT JAVOB BERMADI!")
            all_passed = False
            test_logs.append((step_num, user_msg, "JAVOB YO'Q", False))
            continue

        # Matnni qisqartirib ko'rsatamiz
        preview = reply.replace("\n", " ")[:150]
        print(f"   🤖 Bot javobi: {preview}...")

        # Kutilgan kalit so'zlar bormi
        matched = any(exp.lower() in reply.lower() for exp in item["expect_any"])
        
        # Salbiy tekshiruv: 12-qadamda "adminga yo'naltirildi" bo'lmasligi shart
        if step_num == 12 and "administratorga yo'naltirilgan" in reply:
            matched = False

        status_str = "✅ PASSED" if matched else "⚠️ QISMAN / TEKSHIRISH KERAK"
        print(f"   Holat: {status_str}")
        test_logs.append((step_num, user_msg, reply, matched))

        # Injiq odamdek ozgina kutib keyingi savolni beramiz
        await asyncio.sleep(3)

    print("\n" + "="*60)
    print("📊 XULOSA:")
    passed_cnt = sum(1 for _, _, _, m in test_logs if m)
    print(f"Jami sinovlar: {len(test_logs)} ta | Muvaffaqiyatli: {passed_cnt} ta")
    for s, inp, _, m in test_logs:
        icon = "✅" if m else "❌"
        print(f"{icon} {s}-qadam: \"{inp}\"")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
