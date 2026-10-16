# 🏛 «Mars POS Assistant» — Tizim Arxitekturasi va Dasturlash Standartlari

Ushbu hujjat loyihaning texnik arxitekturasi, ma'lumotlar oqimi, qarorlar qabul qilish Yadrosi (**Core Decision Engine**), xotira tizimi hamda loyihani kelgusida buzmasdan kengaytirish (**Extensibility Guide**) qoidalarini belgilaydi.

---

## 1. Arxitektura Falsafasi va Tamoyillari

Loyiha **Domain-Driven Design (DDD)** hamda **Pipeline / Orchestrator Pattern** tamoyillariga asoslangan:

1. **Yadro Ustuvorligi (Core-Centric):**
   Hech bir Telegram handler (qabul qiluvchi) o'zboshimchalik bilan biznes qaror chiqarmaydi, if-else lab ketmaydi. Barcha mantiqiy qarorlar markaziy Yadro (`core/engine.py`) tomonidan qabul qilinadi.
2. **Sensorlar va Ijrochilar Ajratilishi (Sensory vs Execution Separation):**
   Rasm tahlilchisi (`image_analyzer.py`) faqat tasvirdan sof faktlarni ajratadi (Sensor). Handlerlar (`handlers/`) esa Yadroning qarorini Telegramga yetkazadi (Runner).
3. **Kengaytirish uchun ochiq, buzish uchun yopiq (Open-Closed Principle):**
   Yangi ekran xatoligi yoki yangi buyruq qo'shilganda mavjud kodlarga tegish shart emas. Yangi modul zanjirga yangi filtr yoki qoida sifatida xavfsiz ulanadi.
4. **Zanjir uzilishidan himoya (Fault-Tolerant & Fail-Safe):**
   Tashqi servislar (AI API, internet, Excel o'qish) uzilib qolsa ham bot qulab tushmaydi, xavfsiz zaxira ssenariysiga o'tadi.

---

## 2. Tizimning Blok Diagrammasi

```mermaid
flowchart TD
    User([Telegram Foydalanuvchisi]) -->|Rasm / Matn / Komanda| Bot[aiogram 3 Router Qatlami]

    subgraph Handlers ["1. Qabul Qiluvchilar (Handlers)"]
        CmdH[commands.py]
        MediaH[media.py]
        DebtH[debt.py]
        ChatH[chat.py]
    end

    Bot --> Handlers

    subgraph Pipeline ["2. YAGONA TEZKOR PIPELINE"]
        direction TB
        P0["0-bosqich: RuleEngine & Custom Patches (data/custom_patches.json)"]
        P1["1-bosqich: QARZDORLIK TEKSHIRUVI (60%+ sabab) - Avval Oylik, keyin Yillik"]
        P2["2-bosqich: TEXNIK TASHXIS (Qarzdorlik bo'lmaganda) - 1 marta Soat/Internet/Reboot"]
        P3["2.1-bosqich: TEZKOR ESKALATSIYA (Ko'p cho'zmasdan zudlik bilan adminga yo'naltirish)"]
        P4["3-bosqich: MXIK / To'lov Kvitansiyalari / Gemini AI lo'nda muloqoti"]

        P0 --> P1 --> P2 --> P3
        P1 -.->|Qarz bor| Runner[Telegram Javobi + Video]
        P2 -.->|Reboot taklifi| Runner
        P3 -->|Adminga xabar + Usta kontaktlari| Runner
        P4 --> Runner
    end

    ChatH --> Pipeline
    MediaH --> Pipeline
    DebtH --> Pipeline
```

---

## 3. Qaror Qabul Qilish Algoritmi (Pipeline Bosqichlari)

### 0-bosqich: Modulli Rule Engine (Plug & Play)
* **Qoida:** Telegram xabari kelishi bilan eng avval `data/custom_patches.json` va dinamik qoidalar tekshiriladi.
* **Xatti-harakat:** Yangi kiritilgan kichik patchlar (Wi-Fi paroli, quloqchin va h.k.) asosiy biznes mantig'iga teginmasdan tezkor javob beradi.

### 1-bosqich: Qarzdorlik Tekshiruvi (Oylik -> Yillik)
Kassa apparatlari to'xtab qolishining 60%+ sababi aynan to'lovlardagi qarzdorlik bo'ladi.
1. **Oylik abonent to'lovi («Mars Elektron Texnika» — 100 000 so'm/oy):**
   - Agar INN kiritilmagan bo'lsa -> INN so'raladi.
   - Agar qarzdorlik bo'lsa -> Aniq summa (`Shu oy ishlashi uchun`, `Yil oxirigacha`), hisob raqam (Post 85) va Click video (Post 148).
2. **Yillik fiskal modul to'lovi (Soliq / «Yangi Texnologiyalar» DUK — 440 000 so'm/yil):**
   - Oylik to'lovdan qarz bo'lmasa -> Kassa chekining pastki qismidagi **Fiskal modul raqami (LG... yoki YG...)** so'raladi va OFD tizimidan tekshiriladi.

### 2-bosqich: Texnik Tashxis va Reboot (Qarzdorlik yo'q bo'lsa)
* Oylik va yillik to'lovlar to'langan, lekin apparat ishlamayapti:
  - 1-urinishda: Internet (Wi-Fi/SIM), Soat (Post 141) va Kassa apparatini reboot qilish (Перезагрузка) tavsiya etiladi.
  - P3 Humo apparatida ekrandagi xabar aniq tahlil qilinadi.

### 2.1-bosqich: TEZKOR ESKALATSIYA (Ko'p cho'zmasdan!)
* **QAT'IY QOIDA:** Agar 1 ta urinishdan so'ng muammo hal bo'lmasa, yoki ekrandan aniq xatolik bilib bo'lmasa, yoki mijoz *"ishlamadi", "bo'lmadi", "o'xshamadi", "usta kerak"* deb yozsa:
  - **Bot yana bir xil gapni takrorlamaydi va vaqtni cho'zmaydi!**
  - Darhol adminga (`@Yashnarbek_butaev` va `@quvonchbek_admin`) kassa rasmi, INN, korxona va hudud (tuman) bilan bildirishnoma boradi.
  - Mijozga esa uning o'z hududi bo'yicha mas'ul usta kontaktlari beriladi.

### 3-bosqich: Kvitansiyalar, MXIK va AI Muloqoti
* Kvitansiyalar tahlili (Click/Payme/Bank) firibgarlik va dublikatlardan himoyalangan (`transaction_tracker.py`).
* INN kiritilmagan kvitansiyalar bot qayta ishga tushganda ham saqlanadi (`data/pending_receipts.json`).
* AI Gemini 2.5 Flash asinxron (`httpx.AsyncClient`) ishlaydi, hech qachon botni muzlatmaydi.
* AI anti-hallucination: faqat P3 Humo va Smart One modellarini taniydi, hisob raqamlarni matnda to'qimaydi, lo'nda (2-3 jumla) javob beradi.

---

## 4. Xotira va Ko'p Foydalanuvchili Kontekst (`user_memory.py`)

Guruhlarda bir necha kishi bir vaqtda gaplashganda chalkashmaslik uchun quyidagi tizim ishlaydi:
* **Izolyatsiya kaliti:** `chat_id:user_id` (Masalan: `-100999888:1001` va `-100999888:1002`).
* **Sessiya muddati (TTL):** 1 soat (3600 soniya). Eskirgan sessiyalar xotiradan avtomatik tozalanadi.
* **Saqlanadigan ma'lumotlar:**
  * `last_id`: Foydalanuvchi qidirgan oxirgi INN/JSHSHIR raqami.
  * `debt_info`: Korxona nomi va oxirgi hisoblangan qarz summasi.
  * `last_topic`: Oxirgi muhokama qilingan mavzu (`time_error`, `fiscal_module`, `debt_checked`).
  * `history`: Oxirgi 6 ta muloqot zanjiri.

---

## 5. Yangi Feature / Modul Qo'shish Qo'llanmasi

Kelgusida loyihani buzmasdan yangi funksiya qo'shish uchun quyidagi qat'iy qoidalarga amal qilinadi:

### 1-Misol: Yangi Buyruq (Command) qo'shish
*Faqat* `handlers/commands.py` fayliga yangi funksiya yoziladi:
```python
@router.message(Command("yangi_buyruq"))
async def cmd_yangi_buyruq(message: types.Message):
    await message.answer("Yangi buyruq muvaffaqiyatli ishladi!")
```
*Hech qaysi boshqa faylga yoki `bot.py` ga teginish shart emas.*

### 2-Misol: Ekrandagi yangi nosozlik (Error Rule) qo'shish
*Faqat* `data/screen_errors.json` fayliga yangi qoida kiritiladi:
```json
{
  "id": "battery_low",
  "name": "Batareya quvvati past",
  "screen_keywords": ["quvvat past", "low battery", "batareya"],
  "response_text": "⚠️ <b>Kassa apparati quvvati kam qolgan.</b> Iltimos, quvvatlagichga ulang.",
  "video_id": null,
  "require_inn": false
}
```
*Yadroning o'zi ushbu yangi qoidani avtomatik taniydi va ishga tushiradi.*

### 3-Misol: Yangi Video-qo'llanma qo'shish
*Faqat* `data/video_catalog.json` fayliga yangi post qo'shiladi:
```json
{
  "id": 150,
  "title": "Kassada chekni bekor qilish (Vozvrat)",
  "keywords": ["vozvrat", "bekor qilish", "chekni qaytarish", "qaytuv"],
  "description": "Chekni bekor qilish videosi"
}
```
*Yoki kanalga yangi video tashlansa, bot uni AI orqali avtomatik indekslab o'zi qo'shib oladi.*

---

## 6. Yangi Modullar: Kvitansiya va Admin Eskalatsiyasi

### A. Kvitansiya Tahlil Moduli (`receipt_analyzer.py`)
- **Formatlar:** Rasm (`photo`) yoki PDF (`.pdf` document).
- **Sensory Extractor:** `pypdf` va OpenRouter multimodal orqali kvitansiyadan to'lov faktlarini ajratadi:
  - Qabul qiluvchi hisob raqami (Mars: `20208000800208044003`).
  - To'langan summa (float).
  - To'lovchi INN/JSHSHIR raqami, chek ID, sana, to'lov tizimi (Click, Payme, Bank).
- **Yadroda qarz bilan solishtirish:**
  - Agar `to'lov >= qarz` bo'lsa -> Qarzdorlik to'liq yopilgani qayd etiladi va adminga apparatni faollashtirish buyrug'i yuboriladi.
  - Agar `to'lov < qarz` bo'lsa -> Qisman to'lov deb belgilanadi, qolgan qarz ko'rsatiladi.
  - Agar INN topilmasa -> Kvitansiya vaqtincha xotirada saqlanadi (`pending_receipt`) va foydalanuvchidan INN so'raladi.

### B. Admin Moduli va Eskalatsiya (`admin_manager.py`, `handlers/admin.py`)
- **Adminlar va kontaktlar:**
  - `.env` va `data/admin_config.json` orqali admin Telegram ID lari va mas'ul mutaxassislar kontaktlari boshqariladi.
  - Buyruqlar: `/admin`, `/statistika`, `/admins`, `/add_admin`, `/contacts`, `/add_contact`.
- **Eskalatsiya holatlari (Avtomatik adminga yuborish):**
  1. **Kvitansiya kelganda:** Yangi to'lov summasi, korxona nomi, INN, qarz yopilgani va chek nusxasi bilan birga barcha adminlarga hisobot uzatiladi.
  2. **Texnik nosozlik (Internet bor + Qarz yo'q):** Agar apparatda internet ishlab turgan bo'lsa, qarz bo'lmasa, lekin ekranda nosozlik bo'lsa -> Bot muammoni adminga rasm bilan yetkazadi va mijozga mas'ul xodim kontaktlarini beradi.
  3. **Mijoz yordam so'raganda:** "operator kerak", "usta yuboring", "hal bo'lmadi" so'zlari yozilganda adminga bildirishnoma boradi.

---

## 7. Loyiha Fayllari Mundarijasi

| Fayl / Papka | Vazifasi |
| :--- | :--- |
| `core/engine.py` | 🧠 Markaziy Yadro (Qarorlar chiqaruvchi orkestrator) |
| `core/rule_engine.py` | 🔌 Modulli Patch va Qoidalar Dvigateli (Plug & Play Rule Engine) |
| `data/custom_patches.json`| 📑 Deklarativ mayda patchlar bazasi (kodga tegmasdan yangi shartlar qo'shish) |
| `core/models.py` | 📦 Ma'lumot modellari (`DeviceFacts`, `ReceiptFacts`, `DecisionResult`, `ActionType`) |
| `admin_manager.py` | 👨‍💻 Adminlar, mas'ul xodimlar kontaktlari va bildirishnomalar (Escalation) boshqaruvchisi |
| `receipt_analyzer.py`| 🧾 To'lov kvitansiyalari (rasm / PDF) faktlarini ajratuvchi Sensor |
| `handlers/admin.py` | ⚙️ Admin boshqaruv paneli (`/admin`, `/statistika`, `/admins`, `/contacts`) |
| `handlers/commands.py` | 🕹 Barcha Telegram komandalar (`/start`, `/help`, `/tekshir`, `/tolov`, `/tarix`) |
| `handlers/debt.py` | 💳 Qarz tekshiruvi (INN) va to'lov tarixi so'rovlari |
| `handlers/media.py` | 📸 Ekran rasmlari, to'lov kvitansiyalari (rasm/PDF) va Excel yangilash |
| `handlers/chat.py` | 💬 Erkin matnli muloqot dispetcheri (Intent Pipeline koordinatori) |
| `handlers/intents/` | 🧩 Modulli Intent protsessorlari (`billing`, `hardware`, `mxik`, `operator`, `conversation`) |
| `handlers/channel.py` | 📢 Kanaldan postlarni forward qilish va avto-indekslash |
| `image_analyzer.py` | 👁 Kassa ekrani tasviridan sof faktlarni ajratuvchi Sensor |
| `excel_manager.py` | 📊 7,200+ korxona bazasi, qarz va to'lovlar hisob-kitobi |
| `error_manager.py` | ⚙️ Ekran xatoliklari qoidalari dispetcheri |
| `catalog_manager.py` | 🎬 50+ video postlar qidiruv mexanizmi |
| `user_memory.py` | 💾 Ko'p foydalanuvchili 12 soatlik sessiya va pending kvitansiya xotirasi |
| `openrouter_client.py`| ⚡️ Gemini 3.5 Flash Lite modeli bilan barqaror aloqa |
| `bot.py` | 🚀 Botni ishga tushiruvchi ixcham dastur |

---

## 8. Modulli Qoidalar va Mayda Patchlar Tizimi (Plug & Play Rule Engine)

### Nega bu arxitektura joriy etildi?
Ilgari botga mayda shartlar (masalan: *"Wi-Fi parolini qayerdan o'zgartirish kerak?", "quloqchin bormi?", "lenta qayerdan olinadi?"*) to'g'ridan-to'g'ri `handlers/chat.py` yoki `core/engine.py` ichidagi if/elif zanjiriga kiritilardi. Bu esa asosiy biznes mantig'ini (INN qarz tekshiruvi, 406 xatolik, kvitansiyalar, eskalatsiya) buzib qo'yardi yoki regressiyalarga olib kelardi.

### Yangi yechim:
1. **Yakkalangan maydon (Blast Radius = 0):**
   Yangi qoidalar `core/rule_engine.py` orqali yoki `data/custom_patches.json` da bitta JSON obyekti sifatida qo'shiladi.
2. **Prioritet zanjiri (Priority Ordering):**
   - `90 - 100`: Favqulodda override yoki qat'iy shartlar.
   - `70 - 89`: Mayda patchlar, savol-javoblar (`data/custom_patches.json`).
   - `10 - 40`: Fallback va umumiy tavsiyalar.
3. **Xatolikdan himoya qalqoni (Crash Isolation):**
   Bitta yangi kiritilgan patchda xatolik bo'lsa ham, `RuleEngine` uni logga yozadi va asosiy 4 bosqichli yadro o'z ishini hech to'xtovsiz davom ettiradi.
4. **Kodga tegmasdan deklarativ patch qo'shish:**
   `rule_engine.add_patch(patch_id, keywords, reply_text, priority)` orqali yoki to'g'ridan-to'g'ri `data/custom_patches.json` ga yozish orqali yangi javoblar bir zumda ishga tushadi.

---

## 9. Yangi Modulli Intent Pipeline (Intent-Based Architecture 2.0)

`handlers/chat.py` dagi avvalgi 700 qatorli monolit `if/elif` zanjiri to'liq ajratilib, 5 ta mustaqil Intent protsessoriga bo'lindi:

1. **`BillingIntentHandler` (`handlers/intents/billing.py`)**:
   - Fiskal modul (LG..., YG..., UZ...) to'g'ridan-to'g'ri kiritilishi va `@ofd943_bot` so'rovi;
   - Yillik (`is_annual_check_intent`) va Oylik (`is_monthly_check_intent`) qarz tekshiruvi;
   - Ikkala to'lovni birgalikda tekshirish (`is_both_check_intent`);
   - Aniq to'lov rekvizitlari va hisob raqamlari (`is_annual_pay_intent`, `is_monthly_pay_intent`, `classify_payment_intent`);
   - Click to'lov yo'riqnomasi videosi.

2. **`HardwareIntentHandler` (`handlers/intents/hardware.py`)**:
   - Apparat ishlamay qolganida 4 bosqichli standart tashxis:
     - 1-bosqich: Mars oylik abonent qarzini tekshirish;
     - 2-bosqich: Soliq (OFD) yillik litsenziya muddatini tekshirish;
     - 3-bosqich: Wi-Fi/Internet, soat/sana va kassa apparatini reboot qilish;
     - 4-bosqich: Hududiy usta va mutaxassisga yo'naltirish.

3. **`MxikIntentHandler` (`handlers/intents/mxik.py`)**:
   - MXIK (IKPU), tasnif.soliq va tovar qo'shish qoidalari;
   - Maxsus video-qo'llanmalar (Post 15, Post 133).

4. **`OperatorIntentHandler` (`handlers/intents/operator.py`)**:
   - Mijoz "usta kerak", "operator", "admin" deb murojaat qilganda hududiy usta yoki adminga kassa rasmi va INN bilan eskalatsiya qilish.

5. **`ConversationIntentHandler` (`handlers/intents/conversation.py`)**:
   - Davomiy suhbat konteksti va Gemini 3.5 Flash Lite AI tahlili;
   - Qat'iy himoyalangan video katalog qidiruvi (faqat texnik savollarga video beriladi, qarz/to'lov savollariga tasodifiy video berilmaydi);
   - Tushunarsiz savollar yuzaga kelganda admin bildirishnomasi.


