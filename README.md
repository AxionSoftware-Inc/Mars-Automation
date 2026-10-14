# 🤖 Mars Telegram Bot — Smart POS Assistant & Financial Intelligence

«Mars Elektron Texnika» servis markazi uchun ishlab chiqilgan, Aiogram 3 va zamonaviy mikro-yadroli arxitekturaga (Domain-Driven Pipeline Engine) asoslangan ko'p funksiyali Telegram bot.

---

## 📌 Asosiy Xususiyatlari

- 🧠 **Markaziy Yadro (Core Engine):** Barcha biznes qarorlar va tashxislar bitta markaziy zanjir (pipeline) orqali boshqariladi.
- 👁 **Vizual Sensor va Guardrail:** 
  - Kassa apparati bo'lmagan begona rasmlarni (taom, hayvon, tabiat, xona) so'zsiz e'tiborsiz qoldirish (`ActionType.IGNORE`).
  - Ekran tepasidagi soat va tarmoq qatori (status bar) ko'rinmagan rasmlardan to'liq ekranni talab qilish (`ActionType.ASK_FULL_SCREEN`).
- 💳 **7,200+ Korxona Qarzdorlik Bazasi:** Excel orqali korxona INN/JSHSHIR bo'yicha qarz, joriy oy va yil oxirigacha kerakli to'lov summasini aniq hisoblash.
- 🎬 **Video Katalog (50+ qo'llanma):** Apparat xatolarini tuzatish, chek bekor qilish, Click orqali to'lash va boshqa amallar bo'yicha video-ko'rsatmalar.
- 👥 **Ko'p Foydalanuvchili Xotira (Multi-User Isolation):** Guruhlarda 5+ kishi parallel savol berganda bir-birining kontekstiga xalaqit bermaslik (`chat_id:user_id` izolyatsiyasi).
- 🛡 **Fail-Safe Zanjir Himoyasi:** Tashqi servislar (AI API yoki tarmoq) uzilib qolsa ham bot qulab tushmaydi, xavfsiz zaxira rejimiga o'tadi.

---

## 🏗 Loyiha Tuzilishi

```text
├── bot.py                     # Botning kirish nuqtasi (~45 qator)
├── core/                      # MARKAZIY YADRO
│   ├── engine.py              # 6 bosqichli qaror qabul qiluvchi algoritm
│   └── models.py              # DeviceFacts, DecisionResult, ActionType
├── handlers/                  # Telegram qabul qiluvchilari (Faqat UI)
│   ├── commands.py            # /start, /help, /tekshir, /tolov, /tarix
│   ├── media.py               # Rasm va Excel fayllarni qabul qilish
│   ├── debt.py                # INN tekshiruvi va qarz hisob-kitobi
│   ├── chat.py                # Erkin matnli savol-javob va AI maslahatchi
│   └── channel.py             # Kanaldan videolarni avto-indekslash
├── image_analyzer.py          # Rasmdan faktlarni ajratuvchi Sensor
├── excel_manager.py           # Excel bazasi (qarz, to'lovlar, avto-yuklash)
├── error_manager.py           # Ekran nosozliklari qoidalari (JSON asosida)
├── catalog_manager.py         # 50+ video qo'llanmalar qidiruv moduli
├── user_memory.py             # 1 soatlik ko'p foydalanuvchili sessiya xotirasi
├── openrouter_client.py       # Gemini 2.5 Flash Lite API mijozi
├── data/                      # Konfiguratsiya va ma'lumotlar
│   ├── screen_errors.json     # Ekran xatoliklari deklaratsiyasi
│   └── video_catalog.json     # Video qo'llanmalar katalogi
├── test_multi_user_stress.py  # 5 kishilik parallel stress-test
└── ARCHITECTURE.md            # To'liq texnik arxitektura va kengaytirish qo'llanmasi
```

---

## ⚙️ O'rnatish va Ishga Tushirish

### 1. Talablar
- Python 3.10+
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))
- Gemini / OpenRouter API Key

### 2. Virtual muhitni sozlash
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. `.env` faylini sozlash
`.env.example` dan nusxa oling va kalitlarni kiriting:
```bash
cp .env.example .env
```
`.env` tarkibi:
```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_ID=123456789
CHANNEL_ID=-1001234567890
OPENROUTER_API_KEY=your_openrouter_api_key
# yoki to'g'ridan-to'g'ri Gemini kaliti:
GEMINI_API_KEY=your_gemini_api_key
```

### 4. Botni ishga tushirish
```bash
python bot.py
```

---

## 🧪 Sinovlar (Testing)

Loyihada parallel foydalanuvchilar va algoritmik Yadro ishonchliligini tekshiruvchi avtomatlashtirilgan test mavjud:

```bash
python test_multi_user_stress.py
```

Ushbu test quyidagilarni kafolatlaydi:
1. 5 xil foydalanuvchi bitta guruhda bir vaqtda so'rov yuborganda kontekstlar aralashib ketmasligi.
2. POS apparati bo'lmagan rasmlar so'zsiz e'tiborsiz qoldirilishi (`IGNORE`).
3. Tepasida soati ko'rinmagan rasmlardan to'liq rasm so'ralishi (`ASK_FULL_SCREEN`).
4. To'lov tarixi so'ralganda to'g'ri foydalanuvchiga to'g'ri INN bo'yicha javob qaytishi.

---

## 🚀 Yangi Imkoniyatlar (Features) Qo'shish Qoidasi

Loyihaning arxitekturasi **Open-Closed** tamoyiliga asoslangan. Yangi imkoniyatlar qo'shilganda mavjud kodlarni buzmaslik kafolatlangan:

1. **Yangi Telegram komandasi:** `handlers/commands.py` ga qo'shiladi.
2. **Yangi ekran nosozligi qoidasi:** `data/screen_errors.json` ga JSON obyekti sifatida kiritiladi.
3. **Yangi video-qo'llanma:** `data/video_catalog.json` ga qo'shiladi yoki kanalga tashlanadi.
4. **Biznes mantiq / Yangi shart:** Faqat `core/engine.py` pipeline bosqichlariga qo'shiladi.

Batafsil ma'lumot va arxitektura diagrammalari uchun **[ARCHITECTURE.md](file:///Users/macbookpro/Downloads/Mars%20Telegram%20bot/ARCHITECTURE.md)** fayliga qarang.
