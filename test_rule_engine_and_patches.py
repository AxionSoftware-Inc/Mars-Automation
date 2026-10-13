"""
test_rule_engine_and_patches.py
===============================
Modulli RuleEngine va mayda patchlar tizimining to'liq testi:
1. Deklarativ patch qo'shish (JSON orqali, kodga tegmasdan)
2. Python FunctionalRule qo'shish va prioriteti
3. Qoidani yoqish/o'chirish (enabled=False)
4. Xatolikdan himoya (bitta patch xato bersa ham yadro buzilmaydi)
5. 10 ta mayda patchni ketma-ket qo'shib sinash (Yadroga 0 ta'sir)
"""

import os
import json
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from core.models import ActionType, DecisionResult
from core.engine import core_engine
from core.rule_engine import rule_engine, BaseRule, FunctionalRule, RuleContext

# Testlar haqiqiy data/custom_patches.json ga TEGMASLIGI uchun vaqtinchalik fayl ishlatiladi
# (aks holda test yarim yo'lda yiqilsa, test patchlari serverga deploy bo'lib ketishi mumkin edi).
import tempfile
_TMP_PATCHES = os.path.join(tempfile.mkdtemp(prefix="mars_patches_"), "custom_patches.json")
with open(_TMP_PATCHES, "w", encoding="utf-8") as _f:
    _f.write("[]")
rule_engine.patches_path = _TMP_PATCHES
rule_engine.reload_patches()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_rule_engine")

TEST_PATCHES_FILE = os.path.join(os.path.dirname(__file__), "data", "test_custom_patches.json")

async def test_declarative_patch_via_engine():
    logger.info(">>> TEST 1: Deklarativ patch qo'shish (kodga tegmasdan)...")
    chat_id = 11001
    user_id = 22001

    # 1. Yangi patch qo'shamiz (masalan: "terminal id qayerda" deb so'ralsa)
    patch_id = "test_terminal_location"
    rule_engine.add_patch(
        patch_id=patch_id,
        keywords=["terminal id qayerda", "tid qayerda", "terminal raqam qayerda"],
        reply_text="📟 <b>Terminal ID</b> apparat orqasidagi stikerda yoki chekning yuqori qismida yozilgan bo'ladi.",
        video_id=None,
        priority=90
    )

    res = await core_engine.process_text_inquiry(
        text="aka terminal id qayerda yozilgan?",
        chat_id=chat_id,
        user_id=user_id
    )

    assert res is not None
    assert "Terminal ID" in res.reply_text
    assert "orqasidagi stikerda" in res.reply_text
    logger.info("✅ Deklarativ patch yadroga tegmasdan to'liq ishladi!")

    # Tozalash
    rule_engine.remove_patch(patch_id)

async def test_functional_rule_registration():
    logger.info(">>> TEST 2: Python funktsional qoidasini ro'yxatga olish...")
    chat_id = 11002
    user_id = 22002

    # Maxsus shart: agar mijoz "sariq kassa" deb yozsa va INN bo'lmasa
    def condition(ctx: RuleContext) -> bool:
        return "sariq kassa" in ctx.lower_text

    def handler(ctx: RuleContext) -> DecisionResult:
        return DecisionResult(
            action=ActionType.DIAGNOSE_AND_REPLY,
            reply_text="🟡 <b>Sariq kassa bu — P3 Humo apparati!</b> Uning kartalar bo'yicha xizmat ko'rsatish qo'llanmasi mavjud.",
            video_id=141,
            log_reason="Functional rule P3 matched"
        )

    f_rule = FunctionalRule(
        name="p3_yellow_special_rule",
        condition_fn=condition,
        handler_fn=handler,
        priority=88
    )
    rule_engine.register_rule(f_rule)

    res = await core_engine.process_text_inquiry(
        text="bizdagi sariq kassa qanaqa apparat o'zi?",
        chat_id=chat_id,
        user_id=user_id
    )

    assert res is not None
    assert "P3 Humo apparati" in res.reply_text
    assert res.video_id == 141
    logger.info("✅ Python funktsional qoidasi muvaffaqiyatli ishladi!")

    # O'chirish (disable) testi
    f_rule.enabled = False
    res_disabled = await core_engine.process_text_inquiry(
        text="bizdagi sariq kassa qanaqa apparat o'zi?",
        chat_id=chat_id,
        user_id=user_id
    )
    # Endi bu qoida ishlamasligi va umumiy suhbat oqimiga o'tishi kerak
    assert "P3 Humo apparati" not in res_disabled.reply_text
    logger.info("✅ Qoidani enabled=False qilish bilan u darhol to'xtatilishi tasdiqlandi!")

    rule_engine.unregister_rule("p3_yellow_special_rule")

async def test_exception_isolation_shield():
    logger.info(">>> TEST 3: Xatolikdan himoya qalqoni (bitta patch xato bersa ham yadro ishlaydi)...")
    chat_id = 11003
    user_id = 22003

    def faulty_condition(ctx: RuleContext) -> bool:
        return "buzilgan patch" in ctx.lower_text

    def faulty_handler(ctx: RuleContext):
        # Qasddan xatolik keltirib chiqaramiz (ZeroDivisionError)
        return 1 / 0

    bad_rule = FunctionalRule(
        name="bad_crashing_rule",
        condition_fn=faulty_condition,
        handler_fn=faulty_handler,
        priority=99 # Eng yuqori prioritet
    )
    rule_engine.register_rule(bad_rule)

    # Bot qulab tushmasligi, xatolikni ushlab olib, zanjirni davom ettirishi kerak:
    res = await core_engine.process_text_inquiry(
        text="mana bu buzilgan patch bilan tekshir",
        chat_id=chat_id,
        user_id=user_id
    )

    assert res is not None, "Yadro qulab tushdi!"
    logger.info("✅ Bitta patch ichidagi nosozlik yadroni to'xtata olmasligi isbotlandi!")

    rule_engine.unregister_rule("bad_crashing_rule")

async def test_ten_micro_patches_batch():
    logger.info(">>> TEST 4: Ketma-ket 10 ta mayda patchni kiritish va sinash...")
    chat_id = 11004
    user_id = 22004

    micro_patches = [
        ("p1", ["chek qog'ozi", "lenta qayerdan"], "🧾 Chek qog'ozi (57mm) har qanday kantselyariya do'konida sotiladi.", 80),
        ("p2", ["wifi parol", "vayfay parol"], "📶 Wi-Fi parolini apparat Sozlamalar -> Tarmoq bo'limidan o'zgartirasiz.", 80),
        ("p3", ["zaryadkasi", "quvvatlovchi"], "🔋 Apparat Type-C zaryadlash moslamasi orqali quvvatlanadi.", 80),
        ("p4", ["quloqchin", "sim karta qayerda"], "📱 SIM-karta apparat orqa qopqog'i ostidagi 1-slotga joylashtiriladi.", 80),
        ("p5", ["ovozini o'chirish", "ovozini pasaytirish"], "🔊 Ovozni o'ng tomondagi tugmalar yoki Sozlamalar -> Ovoz bo'limidan pasaytirasiz.", 80),
        ("p6", ["ruscha qilish", "tilini o'zgartirish"], "🌐 Apparat tilini Sozlamalar -> Tillar bo'limidan ruscha yoki o'zbekchaga o'tkazasiz.", 80),
        ("p7", ["bluetooth ulash", "blyutus"], "🔵 Bluetooth sozlamalar menyusida joylashgan.", 80),
        ("p8", ["ekran yorug'ligi", "ekran qorong'i"], "☀️ Ekran yorug'ligini yuqoridan pastga tortib parda menyusidan sozlaysiz.", 80),
        ("p9", ["yangilash qanday", "dasturni yangilash"], "🔄 Kassa dasturini yangilash 'Mars Market' ilovasi orqali amalga oshiriladi.", 80),
        ("p10", ["ish vaqti", "soat nechagacha"], "⏰ «Mars Elektron Texnika» qo'llab-quvvatlash xizmati har kuni 09:00 dan 18:00 gacha ishlaydi.", 80)
    ]

    for pid, kws, reply, prio in micro_patches:
        rule_engine.add_patch(
            patch_id=pid,
            keywords=kws,
            reply_text=reply,
            priority=prio
        )

    # 10 tasini ham tekshirib chiqamiz:
    test_queries = [
        ("chek qog'ozi qanaqa bo'ladi?", "57mm"),
        ("vayfay parol qayerdan ulanadi?", "Sozlamalar -> Tarmoq"),
        ("zaryadkasi qanaqa buni?", "Type-C"),
        ("sim karta qayerda turadi?", "1-slotga"),
        ("ovozini pasaytirish kerak", "Ovoz bo'limidan"),
        ("tilini o'zgartirish qanday?", "Sozlamalar -> Tillar"),
        ("blyutus qayerda?", "Bluetooth"),
        ("ekran qorong'i bo'lib qoldi", "parda menyusidan"),
        ("dasturni yangilash qanaqa?", "Mars Market"),
        ("ish vaqti qachongacha sizlarda?", "09:00 dan 18:00 gacha")
    ]

    for query, expected_snippet in test_queries:
        r = await core_engine.process_text_inquiry(text=query, chat_id=chat_id, user_id=user_id)
        assert r is not None, f"Query javobsiz qoldi: {query}"
        assert expected_snippet in r.reply_text, f"Kutilgan '{expected_snippet}' topilmadi: {r.reply_text}"

    logger.info("✅ Barcha 10 ta mayda patch 100% muvaffaqiyatli javob berdi!")

    # Tozalash
    for pid, _, _, _ in micro_patches:
        rule_engine.remove_patch(pid)

    logger.info("✅ Barcha patchlar xavfsiz tozalandi.")

async def main():
    await test_declarative_patch_via_engine()
    await test_functional_rule_registration()
    await test_exception_isolation_shield()
    await test_ten_micro_patches_batch()
    logger.info("🎉 BARCHA RULE ENGINE VA PATCHLAR TESTLARI 100% MUVAFFAQIYATLI O'TDI!")

if __name__ == "__main__":
    asyncio.run(main())
