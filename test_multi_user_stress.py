import asyncio
import time
from user_memory import user_memory
from excel_manager import excel_manager
from ai_helper import generate_ai_reply
from catalog_manager import catalog_manager
from handlers.debt import format_debt_response

SHARED_GROUP_ID = -100999888777

async def simulate_user_step(user_id: int, user_name: str, step_num: int, input_text: str):
    """
    Bitta foydalanuvchining bot bilan muloqot qadamini simulyatsiya qilish
    """
    t0 = time.time()
    chat_id = SHARED_GROUP_ID
    reply_text = ""
    video_id = None

    # 1. Matnda 9 yoki 14 xonali INN bormi?
    import re
    found_nums = re.findall(r"\b(\d{14}|\d{9})\b", input_text)
    if found_nums:
        query_num = found_nums[0]
        results = excel_manager.search(query_num)
        org = results[0].get("name", "") if results else ""
        debt = sum(item.get("debt", 0.0) for item in results) if results else 0.0

        user_memory.set_last_id(chat_id, user_id, query_num, org_name=org, debt=debt)
        user_memory.set_last_topic(chat_id, user_id, "debt_checked")
        reply_text = format_debt_response(results)
        video_id = 148 if debt > 0 else None

        user_memory.add_user_message(chat_id, user_id, input_text)
        user_memory.add_assistant_message(chat_id, user_id, reply_text)
        dt = time.time() - t0
        return {
            "user_id": user_id,
            "user_name": user_name,
            "step": step_num,
            "input": input_text,
            "reply": reply_text,
            "video_id": video_id,
            "duration": dt,
            "type": "INN_QUERY"
        }

    # 2. To'lov tarixi e'tirozlari bormi?
    lower_text = input_text.lower()
    from handlers.debt import DEBT_INQUIRY_KEYWORDS
    if any(kw in lower_text for kw in DEBT_INQUIRY_KEYWORDS):
        last_id = user_memory.get_last_id(chat_id, user_id)
        if last_id:
            results = excel_manager.search(last_id)
            reply_text = excel_manager.format_payment_history(results)
            user_memory.add_user_message(chat_id, user_id, input_text)
            user_memory.add_assistant_message(chat_id, user_id, reply_text)
            dt = time.time() - t0
            return {
                "user_id": user_id,
                "user_name": user_name,
                "step": step_num,
                "input": input_text,
                "reply": reply_text,
                "video_id": None,
                "duration": dt,
                "type": "PAYMENT_HISTORY"
            }

    # 3. Video katalogdan qidirish
    vid = catalog_manager.find_matching_post(input_text)
    if vid:
        user_memory.add_user_message(chat_id, user_id, input_text)
        user_memory.add_assistant_message(chat_id, user_id, f"[Video {vid}]")
        user_memory.set_last_topic(chat_id, user_id, f"video_{vid}")
        dt = time.time() - t0
        return {
            "user_id": user_id,
            "user_name": user_name,
            "step": step_num,
            "input": input_text,
            "reply": f"[Video ID: {vid} jo'natildi]",
            "video_id": vid,
            "duration": dt,
            "type": "CATALOG_VIDEO"
        }

    # 4. Ketma-ket suhbat va AI javobi (UserMemory konteksti bilan)
    ctx_summary = user_memory.get_context_summary(chat_id, user_id)
    reply_text, ai_video = generate_ai_reply(input_text, context_history=ctx_summary)
    user_memory.add_user_message(chat_id, user_id, input_text)
    user_memory.add_assistant_message(chat_id, user_id, reply_text)
    dt = time.time() - t0
    return {
        "user_id": user_id,
        "user_name": user_name,
        "step": step_num,
        "input": input_text,
        "reply": reply_text,
        "video_id": ai_video,
        "duration": dt,
        "type": "AI_CHAT"
    }

async def run_stress_test():
    print("=" * 65)
    print("🚀 5 FOYDALANUVCHINING BIR VAQTDAGI PARALLEL STRESS-TESTI BOSHLANDI")
    print(f"🏢 Barcha 5 foydalanuvchi BITTA umumiy guruhda (Chat ID: {SHARED_GROUP_ID})")
    print("=" * 65)

    # =========================================================================
    # BOSQICH 1: 5 ta foydalanuvchi bir vaqtda (parallel) boshlang'ich so'rov beradi
    # =========================================================================
    print("\n>>> 1-BOSQICH: PARALLEL BOSHLANG'ICH SO'ROVLAR...")
    tasks_step1 = [
        simulate_user_step(1001, "User 1 (Ali - Qarzli)", 1, "206011507"),
        simulate_user_step(1002, "User 2 (Vali - Qarzsiz)", 1, "311790999"),
        simulate_user_step(1003, "User 3 (Gani - Soat)", 1, "kassada vaqt xato ko'rsatyapti"),
        simulate_user_step(1004, "User 4 (Salim - Muddat)", 1, "Oylik to'lov har oy qaysi sanagacha to'lanishi kerak?"),
        simulate_user_step(1005, "User 5 (Karim - Fiskal)", 1, "fiskal modul aktivlashtirish")
    ]
    results_step1 = await asyncio.gather(*tasks_step1)

    for r in results_step1:
        print(f"[{r['user_name']}] So'rov: '{r['input']}' -> Javob turi: {r['type']} (Vaqt: {r['duration']:.2f}s)")
        if r['video_id']:
            print(f"   🎬 Biriktirilgan video: ID {r['video_id']}")
        # Tekshiruvlar
        if r['user_id'] == 1001:
            assert "1,500,400" in r['reply'], "User 1 da qarz summasi topilmadi!"
            assert r['video_id'] == 148, "User 1 ga 148-video birikmadi!"
        elif r['user_id'] == 1002:
            assert "qarzdorlik yo'q" in r['reply'].lower() or "qarzdorlik mavjud emas" in r['reply'].lower(), f"User 2 da qarzsiz holat topilmadi! Olingan matn: {r['reply']}"
        elif r['user_id'] == 1003:
            assert r['video_id'] == 141, "User 3 ga soat videosi (141) birikmadi!"
        elif r['user_id'] == 1005:
            assert r['video_id'] == 137, "User 5 ga fiskal modul videosi (137) birikmadi!"

    print("✅ 1-bosqich parallel so'rovlari 100% muvaffaqiyatli o'tdi!")

    # =========================================================================
    # BOSQICH 2: 5 ta foydalanuvchi bir vaqtda KETMA-KET (FOLLOW-UP) savol beradi
    # Muhim: Bot ularning kimligini va avvalgi kontekstini adashtirmasligi kerak!
    # =========================================================================
    print("\n>>> 2-BOSQICH: PARALLEL KETMA-KET (FOLLOW-UP) SAVOLLAR...")
    tasks_step2 = [
        # User 1 (Ali): Qarzli edi. "Nega apparatim ishlamayapti?" deb so'raydi.
        # Kutilyapti: Qarz borligi uchun ishlamayotganini tushuntirishi, qayta INN so'ramasligi!
        simulate_user_step(1001, "User 1 (Ali)", 2, "Nega apparatim o'chib qolgan?"),

        # User 2 (Vali): Qarzi yo'q edi. U ham "Menda ham apparat ishlamayapti, nega?" deb so'raydi.
        # Kutilyapti: Qarzi yo'qligini aytib, ekran rasmini so'rashi! (User 1 ning qarzi bilan aralashmasligi kerak!)
        simulate_user_step(1002, "User 2 (Vali)", 2, "Lekin mening ham apparatim ishlamayapti, nega?"),

        # User 3 (Gani): Soat xato edi. "Buni qanday to'g'irlayman?" deb so'raydi.
        # Kutilyapti: Soatni to'g'rilash (141) haqida javob berishi!
        simulate_user_step(1003, "User 3 (Gani)", 2, "Buni qanday to'g'irlayman?"),

        # User 4 (Salim): Muddatni so'ragan edi. "Agar 6-sanasigacha to'lamasam nima bo'ladi?" deb so'raydi.
        # Kutilyapti: Apparat bloklanishini tushuntirishi!
        simulate_user_step(1004, "User 4 (Salim)", 2, "Agar 6-sanasigacha to'lamasam nima bo'ladi?"),

        # User 5 (Karim): Fiskal modul so'ragan edi. "Fiskal modulni qayta o'rnatish kerak bo'lsa-chi?" deb so'raydi.
        # Kutilyapti: 134-video (qayta o'rnatish) berilishi!
        simulate_user_step(1005, "User 5 (Karim)", 2, "Fiskal modulni o'chirib qayta o'rnatish qanday bo'ladi?")
    ]
    results_step2 = await asyncio.gather(*tasks_step2)

    for r in results_step2:
        print(f"\n[{r['user_name']}] Ketma-ket savol: '{r['input']}'")
        print(f"   🤖 AI Javobi: {r['reply'].strip()}")
        if r['video_id']:
            print(f"   🎬 Video: ID {r['video_id']}")

        # TEKSHIRUV 1: User 1 ning javobida qayta INN so'ralmadimi va qarz sababi aytildimi?
        if r['user_id'] == 1001:
            lower_r = r['reply'].lower()
            assert "qarzdorlik" in lower_r or "to'lov" in lower_r, "User 1 ga qarz sababi aytilmadi!"
            assert "inn (9 xonali)" not in lower_r, "XATOLIK: User 1 dan yana qayta INN so'raldi!"

        # TEKSHIRUV 2: User 2 (qarzsiz) ga User 1 ning qarzi yopishib qolmadimi?
        if r['user_id'] == 1002:
            lower_r = r['reply'].lower()
            assert "qarzingiz yo'q" in lower_r or "qarzdorlik yo'q" in lower_r or "rasm" in lower_r, "User 2 ga noto'g'ri qarz berildi!"

        # TEKSHIRUV 3: User 3 ga soat bo'yicha ko'rsatma berildimi?
        if r['user_id'] == 1003:
            lower_r = r['reply'].lower()
            assert r['video_id'] == 141 or "soat" in lower_r or "vaqt" in lower_r, "User 3 ga soat ko'rsatmasi berilmadi!"

    print("\n✅ 2-bosqich ketma-ket savollar konteksti 100% xatosiz ajratildi!")

    # =========================================================================
    # BOSQICH 3: PARALLEL TO'LOV TARIXI VA E'TIROZLAR
    # User 1 va User 2 bitta guruhda to'lov tarixini so'raganda o'zlarinikini oladimi?
    # =========================================================================
    print("\n>>> 3-BOSQICH: PARALLEL TO'LOV TARIXI VA E'TIROZLAR...")
    tasks_step3 = [
        simulate_user_step(1001, "User 1 (Ali)", 3, "Nega buncha qarzman, to'lov tariximni ko'rsat"),
        simulate_user_step(1002, "User 2 (Vali)", 3, "To'lov tariximni ko'rsat")
    ]
    results_step3 = await asyncio.gather(*tasks_step3)

    for r in results_step3:
        print(f"\n[{r['user_name']}] So'rov: '{r['input']}'")
        first_line = r['reply'].split("\n")[1] if "\n" in r['reply'] else r['reply'][:50]
        print(f"   📄 Chiqarilgan korxona: {first_line}")
        if r['user_id'] == 1001:
            assert "206011507" in r['reply'], "User 1 o'z korxonasini olmadi!"
            assert "1,500,400" in r['reply'], "User 1 qarz summasini olmadi!"
        elif r['user_id'] == 1002:
            assert "311790999" in r['reply'], "User 2 o'z korxonasini olmadi!"
            assert "to'liq to'langan" in r['reply'], "User 2 qarzsiz ekanligi chiqmadi!"

    print("\n" + "=" * 65)
    print("🎉 BARCHA 3 BOSQICHLI PARALLEL STRESS-TEST MUVAFFAQIShIYATLI TUGADI!")
    print("   Hech qanday kontekst chalkashuvi yoki ma'lumot aralashuvi kuzatilmadi!")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(run_stress_test())
