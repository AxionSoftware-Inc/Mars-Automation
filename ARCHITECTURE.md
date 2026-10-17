# 🏛 «Mars POS Assistant» — Tizim Arxitekturasi va Modulli Dasturlash Standartlari (v3.0)

Ushbu hujjat loyihaning yangi modulli arxitekturasi (**ModuleRegistry & Plugin Bus**), guruhda va shaxsiy chatlarda javob beruvchi yagona 8-qadamli orkestrator (**GroupResponseOrchestrator**), hamda loyihaga mavjud kodni buzmasdan yangi katta modullar va yangi qoidalar qo'shish tartibini belgilaydi.

---

## 1. Arxitektura Tamoyillari

1. **Modulli Arxitektura (`core/module_registry.py` va `modules/`):**
   Tizimning har bir bo'limi (`AdminModule`, `CommandsModule`, `MediaModule`, `BillingModule`, `ChannelModule`, `GroupSupportModule`) `BaseBotModule` interfeysiga asoslangan mustaqil modul sifatida ishlaydi. Kelajakda katta tashqi modullar (masalan: *To'lov tizimi Click/Payme API*, *CRM moduli*, *Web-Admin*) mavjud kodga tegmasdan `module_registry.register(...)` orqali ulanadi.
2. **Yagona 8-Qadamli Guruh Orkestratori (`core/group_responder.py`):**
   Guruhda va chatlarda keladigan har qanday xabar **faqat bitta markaziy zanjir** (`group_responder.process_message`) orqali 1 dan 8 gacha qat'iy ketma-ketlikda tekshiriladi.
3. **Istalgan Qadamdan Kirishga Chidamlilik (State-Resilient Entrypoints):**
   Mijoz muloqotni 1-qadamdanmi, 3-qadamdanmi ("usta kerak"), 5-qadamdanmi (faqat INN yoki FM) yoki 6-qadamdanmi ("oylik shot") boshlashidan qat'i nazar, 1-qadamda barcha identifikatorlar (`INN`, `Fiskal modul`, `Alifbo`) xotiraga (`user_memory`) darhol yozib olinadi va kerakli bosqich hech qachon yiqilmasdan ishlaydi.
4. **Ulangan Kanallar va Sessiyalar Daxlsizligi:**
   - `@POS_Terminal_UzSmart_Bank` (`-1001641871516`) — video va hisob raqam postlari manbasi;
   - `marsfayllar` (`-1003784534841`) va `Абонент тулови` (`-1001795471853`) — Excel baza kanallari;
   - `@ofd943_bot` va `data/ofd_user.session` — OFD litsenziya tekshiruvi ko'prigi.

---

## 2. Guruhda va Chatlarda Javob Berish Bo'limi (8 Qadamli Qoida)

Barcha matnli xabarlar [`core/group_responder.py`](file:///Users/macbookpro/Downloads/Mars%20Telegram%20bot/core/group_responder.py) da quyidagi 8 ta qat'iy qadam bo'yicha ishlaydi:

| Qadam | Nomi | Vazifasi (Oddiy tilda) |
| :--- | :--- | :--- |
| **1-Qadam** | **Alifbo va Kontekst** | Lotin/Kirill alifbosini aniqlaydi. Xabar ichida INN (9/14 xona) yoki Fiskal modul (LG/YG/UZ) bo'lsa darhol `user_memory` ga saqlaydi. Agar avval INN-siz kvitansiya tashlangan bo'lsa, INN kelishi bilan kvitansiyaga ulab yuboradi. |
| **2-Qadam** | **Plug & Play Qoidalar** | `data/custom_patches.json` yoki `/add_patch` orqali qo'shilgan maxsus qoidalarni (`RuleEngine`) hamda tashqi modullar qadamlarini tekshiradi. |
| **3-Qadam** | **Eskalatsiya va Sabrsizlik** | *"Usta kerak", "admin", "operator"* deyilsa yoki mijoz sabrsizlik qilsa (*"alo", "qachon javob", "tashladimku boya"*) — tortishmasdan adminga (`@Yashnarbek_butaev`, `@quvonchbek_admin`) INN va rasm bilan uzatadi. |
| **4-Qadam** | **Apparat Nosozligi (3 bosqich)** | *"Apparat ishlamayapti / xatolik"* deyilsa: **1)** INN orqali Mars oylik qarzini tekshiradi -> **2)** Qarz 0 bo'lsa, Fiskal modul orqali OFD yillik qarzini tekshiradi -> **3)** Ikkalasi ham to'langan bo'lsa, Internet/Soat/Rebootni aytib, rasm so'raydi va darhol Adminga xabar beradi. |
| **5-Qadam** | **Qarz va To'lov Tarixi** | INN, Telefon yoki Fiskal modul yuborilganda oylik/yillik qarzni tekshiradi. *"Nega qarz?", "To'laganmanku"* deyilsa oylar kesimida to'lov tarixini chiqaradi. |
| **6-Qadam** | **Hisob Raqamlar (Shotlar)** | *"Oylik shot"* -> Post 85 + Video 148. *"Yillik shot"* -> Post 34 + Video 145. *"Ikkalasini bitta hisobga to'lasam bo'ladimi?"* -> Qat'iy rad javobi va ikkala post. *"Qachongacha to'lanadi?"* -> Har oyning 6-sanasigacha. |
| **7-Qadam** | **MXIK va Texnik Yo'riqnoma** | MXIK / IKPU / `tasnif.soliq.uz` / Tovar qo'shish savollariga aniq yo'riqnoma va tegishli videolarni yuboradi. |
| **8-Qadam** | **Video Katalog va AI** | Katalogdan aniq videoni (`vozvrat`, `x-otchet`, `soat`) qidiradi yoki Gemini AI orqali mijoz kontekstiga tayangan holda qisqa (2-3 jumla) javob beradi. |

---

## 3. Yangi Qoida yoki Katta Modul Qo'shish Qo'llanmasi

### A) 10 soniyada yangi savol-javob qoidasini qo'shish (Kodga tegmasdan!)
Telegram orqali admin sifatida botga yozing:
```text
/add_patch wifi_rule | wifi parol, kassa paroli | 🔑 Kassa apparati standart paroli: 0000 | 141
```
Yoki `data/custom_patches.json` fayliga qo'shing. O'chirish uchun: `/del_patch wifi_rule`.

### B) Ekrandagi yangi xatolikni qo'shish
Telegramda admin sifatida:
```text
/add_error err_id | Xatolik nomi | kalit1, kalit2 | Yechim matni | video_id
```

### C) Tashqi Katta Modul (masalan: Click/Payme To'lov Moduli yoki Admin CRM) ulash
[`modules/__init__.py`](file:///Users/macbookpro/Downloads/Mars%20Telegram%20bot/modules/__init__.py) ichida yangi modul klassini e'lon qilib, `module_registry.register(...)` ga qo'shing:

```python
from aiogram import Router
from core.module_registry import BaseBotModule, module_registry

class ClickPaymentModule(BaseBotModule):
    name = "click_payment_module"
    version = "1.0.0"
    description = "Click va Payme avto-to'lov integratsiyasi"
    priority = 75

    def get_router(self) -> Router:
        router = Router(name="click_router")
        # Shu yerda modulning barcha handlerlari yoziladi
        return router

module_registry.register(ClickPaymentModule())
```
Barcha ulangan modullarni Telegramda `/modules` buyrug'i orqali ko'rish mumkin.
