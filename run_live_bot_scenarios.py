import os
import asyncio
import logging
from telethon import TelegramClient, events
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "21950664"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "77189115ec44347fb9dc7c8dd29a39f6")
BOT_USERNAME = "marselektrontexnikamchj_bot"
GROUP_ID = -1003742874507

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scenario_runner")

async def run_scenario_test():
    # Account 1: Admin (@BIM_Project_Manager)
    admin_client = TelegramClient("data/tester_user", API_ID, API_HASH)
    # Account 2: Client
    client_client = TelegramClient("data/tester_user_2", API_ID, API_HASH)

    await admin_client.start()
    await client_client.start()

    admin_me = await admin_client.get_me()
    client_me = await client_client.get_me()

    print(f"\n========================================================")
    print(f"✅ Admin Account: {admin_me.first_name} (@{admin_me.username}, ID: {admin_me.id})")
    print(f"✅ Client Account: {client_me.first_name} (Phone: {client_me.phone}, ID: {client_me.id})")
    print(f"========================================================\n")

    results = []

    async def wait_for_bot_reply(peer, sent_msg_id, timeout=12):
        # Bot xabarlari bir nechta bo'lishi mumkin (matn + post kopiyasi)
        # Barchasini birlashtirib qaytaradi
        await asyncio.sleep(1.5)
        for _ in range(int(timeout * 2)):
            msgs = await client_client.get_messages(peer, limit=8)
            bot_msgs = [m for m in msgs if m.id > sent_msg_id and (m.from_id is None or getattr(m.from_id, 'user_id', None) != client_me.id)]
            if bot_msgs:
                await asyncio.sleep(1.0)
                # Qayta olamiz (balki qo'shimcha post kelayotgandir)
                msgs2 = await client_client.get_messages(peer, limit=8)
                bot_msgs2 = [m for m in msgs2 if m.id > sent_msg_id and (m.from_id is None or getattr(m.from_id, 'user_id', None) != client_me.id)]
                # Eng qadimgidan eng yangisiga tartiblab barcha matnlarini birlashtiramiz
                bot_msgs2.sort(key=lambda x: x.id)
                combined_text = "\n---\n".join(m.text or "" for m in bot_msgs2)
                
                class CombinedReply:
                    def __init__(self, text, msgs):
                        self.text = text
                        self.msgs = msgs
                return CombinedReply(combined_text, bot_msgs2)
            await asyncio.sleep(0.5)
        return None

    # ----------------------------------------------------
    # 1-BLOK: SALOM / GREETING TESTI (Adminga yo'naltirmasligi shart!)
    # ----------------------------------------------------
    print("\n--- 1-BLOK: SALOM / GREETING TESTI ---")
    
    # 1.1 Shaxsiy chatda "salom"
    print("1.1 Client -> Bot (Lichka): 'salom'")
    s1 = await client_client.send_message(BOT_USERNAME, "salom")
    r1 = await wait_for_bot_reply(BOT_USERNAME, s1.id)
    r1_text = r1.text if r1 else "[Javob yo'q]"
    is_greeting_ok = "Assalomu alaykum" in r1_text and "mas'ul administratorga yo'naltirilgan" not in r1_text
    print(f"  Bot javobi: {r1_text[:120]}...")
    print(f"  Natija: {'✅ PASSED (Salomlashdi, adminga yo‘naltirmadi)' if is_greeting_ok else '❌ FAILED'}")
    results.append(("1.1 Salom lichkada", is_greeting_ok))

    # 1.2 Guruhda "assalomu alaykum"
    print("1.2 Client -> Guruh: 'assalomu alaykum'")
    s2 = await client_client.send_message(GROUP_ID, "assalomu alaykum")
    r2 = await wait_for_bot_reply(GROUP_ID, s2.id)
    r2_text = r2.text if r2 else "[Javob yo'q]"
    is_g2_ok = "Assalomu alaykum" in r2_text and "mas'ul administratorga yo'naltirilgan" not in r2_text
    print(f"  Bot javobi: {r2_text[:120]}...")
    print(f"  Natija: {'✅ PASSED' if is_g2_ok else '❌ FAILED'}")
    results.append(("1.2 Salom guruhda", is_g2_ok))

    # ----------------------------------------------------
    # 2-BLOK: YILLIK TEKSHIRUV (INN SO'RALMASLIGI SHART!)
    # ----------------------------------------------------
    print("\n--- 2-BLOK: YILLIK TEKSHIRUV (INN SO'RALMASLIGI SHART!) ---")
    
    # 2.1 Lichkada "yillik"
    print("2.1 Client -> Bot (Lichka): 'yillik'")
    s3 = await client_client.send_message(BOT_USERNAME, "yillik")
    r3 = await wait_for_bot_reply(BOT_USERNAME, s3.id)
    r3_text = r3.text if r3 else "[Javob yo'q]"
    # Yillik tekshiruvda bot Fiskal modul (LG/YG) so'rashi yoki xotiradagi litsenziya holatini berishi kerak, INN so'ramasligi shart!
    is_yillik_ok = (
        ("Fiskal modul" in r3_text or "LG" in r3_text or "qarzdorlik yo'q" in r3_text or "Litsenziya faol" in r3_text or "OFD" in r3_text)
        and ("korxonangizning СТИР (INN) raqamini yuboring" not in r3_text)
    )
    print(f"  Bot javobi: {r3_text[:120]}...")
    print(f"  Natija: {'✅ PASSED (Fiskal modul so‘radi, INN so‘ramadi!)' if is_yillik_ok else '❌ FAILED'}")
    results.append(("2.1 'yillik' so'rovi (Fiskal modul so'rash)", is_yillik_ok))

    # 2.2 Guruhda "yillik tekshir"
    print("2.2 Client -> Guruh: 'yillik tekshir'")
    s4 = await client_client.send_message(GROUP_ID, "yillik tekshir")
    r4 = await wait_for_bot_reply(GROUP_ID, s4.id)
    r4_text = r4.text if r4 else "[Javob yo'q]"
    is_yillik_gr_ok = ("Fiskal modul" in r4_text or "LG" in r4_text) and ("korxonangizning СТИР (INN) raqamini yuboring" not in r4_text)
    print(f"  Bot javobi: {r4_text[:120]}...")
    print(f"  Natija: {'✅ PASSED' if is_yillik_gr_ok else '❌ FAILED'}")
    results.append(("2.2 'yillik tekshir' guruhda", is_yillik_gr_ok))

    # 2.3 Fiskal modul kiritilganda OFD tekshiruvi: "LG420210630789"
    print("2.3 Client -> Bot: 'LG420210630789'")
    s5 = await client_client.send_message(BOT_USERNAME, "LG420210630789")
    r5 = await wait_for_bot_reply(BOT_USERNAME, s5.id, timeout=15)
    r5_text = r5.text if r5 else "[Javob yo'q]"
    is_fm_ok = "LG420210630789" in r5_text or "Yillik Soliq" in r5_text or "OFD" in r5_text
    print(f"  Bot javobi: {r5_text[:120]}...")
    print(f"  Natija: {'✅ PASSED (OFD holati ko‘rsatildi)' if is_fm_ok else '❌ FAILED'}")
    results.append(("2.3 FM bo'yicha OFD tekshiruvi", is_fm_ok))

    # ----------------------------------------------------
    # 3-BLOK: CHALA, MANTIQSIZ VA MURAKKAB SENARIYLAR
    # ----------------------------------------------------
    print("\n--- 3-BLOK: CHALA VA MANTIQSIZ SENARIYLAR ---")

    # 3.1 Chala INN: "12345"
    print("3.1 Client -> Bot: '12345'")
    s6 = await client_client.send_message(BOT_USERNAME, "12345")
    r6 = await wait_for_bot_reply(BOT_USERNAME, s6.id)
    r6_text = r6.text if r6 else "[Javob yo'q]"
    is_chala_ok = "to'liq emas" in r6_text or "9 xonali" in r6_text
    print(f"  Bot javobi: {r6_text[:120]}...")
    print(f"  Natija: {'✅ PASSED (Chala INN to‘g‘ri tushuntirildi)' if is_chala_ok else '❌ FAILED'}")
    results.append(("3.1 Chala INN ('12345')", is_chala_ok))

    # 3.2 Muammo ichida turib mavzuni o'zgartirish (State Trapping oldini olish)
    print("3.2 Client -> Bot: 'aparatim ishlamay qoldi'")
    s7 = await client_client.send_message(BOT_USERNAME, "aparatim ishlamay qoldi")
    r7 = await wait_for_bot_reply(BOT_USERNAME, s7.id)
    print(f"  1-bosqich javobi: {r7.text[:100] if r7 else ''}...")

    print("3.2.1 Client mavzuni o'zgartirib 'salom' deb yozadi (Bot 1-bosqichni takrorlamasligi kerak):")
    s8 = await client_client.send_message(BOT_USERNAME, "salom")
    r8 = await wait_for_bot_reply(BOT_USERNAME, s8.id)
    r8_text = r8.text if r8 else "[Javob yo'q]"
    is_trap_ok = "Assalomu alaykum" in r8_text and "korxonangizning СТИР (INN) raqamini yuboring" not in r8_text
    print(f"  Bot javobi: {r8_text[:120]}...")
    print(f"  Natija: {'✅ PASSED (Qopqondan chiqildi, salomlashdi)' if is_trap_ok else '❌ FAILED'}")
    results.append(("3.2 Qopqondan chiqish (Issue -> Salom)", is_trap_ok))

    # 3.3 Bitta hisobga ikkala to'lovni qilish taqiqi
    print("3.3 Client -> Bot: 'ikkala to'lovni bitta hisob raqamga to'lasam bo'ladimi?'")
    s9 = await client_client.send_message(BOT_USERNAME, "ikkala to'lovni bitta hisob raqamga to'lasam bo'ladimi?")
    r9 = await wait_for_bot_reply(BOT_USERNAME, s9.id)
    r9_text = r9.text if r9 else "[Javob yo'q]"
    is_single_acc_ok = "mutlaqo bo'lmaydi" in r9_text or "alohida" in r9_text
    print(f"  Bot javobi: {r9_text[:120]}...")
    print(f"  Natija: {'✅ PASSED (Bitta hisobga to‘lash qat’iy taqiqlandi)' if is_single_acc_ok else '❌ FAILED'}")
    results.append(("3.3 Bitta hisobga to'lash taqiqi", is_single_acc_ok))

    # 3.4 Sabrsizlik / Provokatsiya: "admin qani tezroq qara"
    print("3.4 Client -> Bot: 'admin qani tezroq qara'")
    s10 = await client_client.send_message(BOT_USERNAME, "admin qani tezroq qara")
    r10 = await wait_for_bot_reply(BOT_USERNAME, s10.id)
    r10_text = r10.text if r10 else "[Javob yo'q]"
    is_admin_ask_ok = "administrator" in r10_text or "admin" in r10_text or "@" in r10_text
    print(f"  Bot javobi: {r10_text[:120]}...")
    print(f"  Natija: {'✅ PASSED (Admin kontaktlari berildi)' if is_admin_ask_ok else '❌ FAILED'}")
    results.append(("3.4 Admin so'rovi / Sabrsizlik", is_admin_ask_ok))

    # ----------------------------------------------------
    # 4-BLOK: RASMLAR, KVITANSIYALAR VA CHEKLAR TESTI
    # ----------------------------------------------------
    print("\n--- 4-BLOK: RASMLAR VA CHEKLAR TESTI ---")

    # 4.1 To'lov kvitansiyasi rasmi (Click)
    print("4.1 Client -> Bot: Click to'lov kvitansiyasi rasmi")
    receipt_path = "data/test_images/click_receipt.png"
    if os.path.exists(receipt_path):
        s11 = await client_client.send_file(BOT_USERNAME, receipt_path, caption="To'lov qildim 100 000 so'm")
        r11 = await wait_for_bot_reply(BOT_USERNAME, s11.id, timeout=18)
        r11_text = r11.text if r11 else "[Javob yo'q]"
        is_rec_ok = "kvitansiya" in r11_text.lower() or "qabul qilindi" in r11_text.lower() or "admin" in r11_text.lower() or "100" in r11_text
        print(f"  Bot javobi: {r11_text[:120]}...")
        print(f"  Natija: {'✅ PASSED (Kvitansiya qabul qilindi)' if is_rec_ok else '❌ FAILED'}")
        results.append(("4.1 Click kvitansiyasi tahlili", is_rec_ok))

    # 4.2 Kassa savdo cheki rasmi (Fiskal chek)
    print("4.2 Client -> Bot: Kassa savdo cheki rasmi (INN + Fiskal modul)")
    chek_path = "data/test_images/kassa_chek.png"
    if os.path.exists(chek_path):
        s12 = await client_client.send_file(BOT_USERNAME, chek_path, caption="Mana chek")
        r12 = await wait_for_bot_reply(BOT_USERNAME, s12.id, timeout=18)
        r12_text = r12.text if r12 else "[Javob yo'q]"
        is_chek_ok = "302568138" in r12_text or "LG420210630789" in r12_text or "chek" in r12_text.lower() or "korxona" in r12_text.lower()
        print(f"  Bot javobi: {r12_text[:120]}...")
        print(f"  Natija: {'✅ PASSED (Kassa cheki ma’lumotlari aniqlandi)' if is_chek_ok else '❌ FAILED'}")
        results.append(("4.2 Kassa savdo cheki tahlili", is_chek_ok))

    # 4.3 POS apparati nosozlik ekrani
    print("4.3 Client -> Bot: POS apparati ekrani xatoligi rasmi")
    pos_path = "data/test_images/pos_error.png"
    if os.path.exists(pos_path):
        s13 = await client_client.send_file(BOT_USERNAME, pos_path, caption="Aparat shunaqa bo'lib qoldi")
        r13 = await wait_for_bot_reply(BOT_USERNAME, s13.id, timeout=18)
        r13_text = r13.text if r13 else "[Javob yo'q]"
        is_pos_ok = "tasvir" in r13_text.lower() or "xatolik" in r13_text.lower() or "admin" in r13_text.lower() or "internet" in r13_text.lower() or "aloqa" in r13_text.lower()
        print(f"  Bot javobi: {r13_text[:120]}...")
        print(f"  Natija: {'✅ PASSED (Apparat ekrani tahlil qilindi)' if is_pos_ok else '❌ FAILED'}")
        results.append(("4.3 POS xatolik ekrani tahlili", is_pos_ok))

    # 4.4 Begona rasm (Guardrail testi guruhda)
    print("4.4 Client -> Guruh: Begona rasm (Tabiat fotosurati)")
    random_path = "data/test_images/random_pic.png"
    if os.path.exists(random_path):
        s14 = await client_client.send_file(GROUP_ID, random_path)
        r14 = await wait_for_bot_reply(GROUP_ID, s14.id, timeout=8)
        # Guruhda begona rasmlar uchun Guardrail jim turishi kerak (r14 is None)!
        is_guardrail_ok = (r14 is None)
        print(f"  Bot harakati: {'Jim turdi (Guardrail ishladi)' if is_guardrail_ok else f'Xabar yozdi: {r14.text[:80]}'}")
        print(f"  Natija: {'✅ PASSED (Guruhga keraksiz xabar yozilmadi)' if is_guardrail_ok else '⚠️ Notice'}")
        results.append(("4.4 Begona rasm Guardrail (Guruhda jim turish)", is_guardrail_ok))

    # ----------------------------------------------------
    # YAKUNIY HISOBOT
    # ----------------------------------------------------
    print("\n========================================================")
    print("📊 BARCHA TEST SENARIYLARI NATIJASI:")
    print("========================================================")
    passed = 0
    for name, ok in results:
        status = "✅ O'TDI (PASSED)" if ok else "❌ YIQILDI (FAILED)"
        print(f"{name:<50} | {status}")
        if ok:
            passed += 1
    print("========================================================")
    print(f"JAMI: {len(results)} tadan {passed} tasi muvaffaqiyatli o'tdi ({passed/len(results)*100:.1f}%)")
    print("========================================================\n")

    await admin_client.disconnect()
    await client_client.disconnect()

if __name__ == "__main__":
    asyncio.run(run_scenario_test())
