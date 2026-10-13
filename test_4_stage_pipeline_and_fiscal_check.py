"""
test_4_stage_pipeline_and_fiscal_check.py
=========================================
4 bosqichli to'liq tashxis algoritmi, INN va Fiskal modul tekshiruvi,
406-xatolik va dual-texnik eskalatsiyasi testi.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from core.models import ActionType, DeviceFacts, ReceiptFacts
from core.engine import core_engine
from excel_manager import excel_manager
from user_memory import user_memory
from admin_manager import admin_manager
from handlers.chat import handle_user_chat
from handlers.debt import handle_inn_query, process_and_send_debt_result
from ofd_bridge import ofd_bridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_4_stage_pipeline")

class MockUser:
    def __init__(self, user_id: int, first_name: str, username: str = ""):
        self.id = user_id
        self.first_name = first_name
        self.full_name = first_name
        self.username = username

class MockChat:
    def __init__(self, chat_id: int, chat_type: str = "private"):
        self.id = chat_id
        self.type = chat_type

class MockMessage:
    def __init__(self, message_id: int, user: MockUser, chat: MockChat, text: str = ""):
        self.message_id = message_id
        self.from_user = user
        self.chat = chat
        self.text = text
        self.replies = []

    async def reply(self, text: str, parse_mode: str = "HTML", **kwargs):
        self.replies.append(text)
        return self

    async def answer(self, text: str, parse_mode: str = "HTML", **kwargs):
        self.replies.append(text)
        return self

def create_mock_bot():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.copy_message = AsyncMock()
    return bot

async def test_stage1_problem_without_inn_or_fm():
    logger.info(">>> TEST 1: Muammo bilan yozilganda INN va Fiskal modul so'ralishi...")
    chat_id = 9911
    user_id = 8811
    user_memory.clear_context(chat_id, user_id)

    # 1. "apparat ishlamayapti"
    res1 = await core_engine.process_text_inquiry(
        text="apparat ishlamayapti",
        chat_id=chat_id,
        user_id=user_id
    )
    assert res1.action == ActionType.DEBT_INFO
    assert "INN" in res1.reply_text
    assert "Fiskal modul" in res1.reply_text
    assert "LG" in res1.reply_text or "YG" in res1.reply_text
    assert "60%" in res1.reply_text
    logger.info("✅ 'apparat ishlamayapti' so'rovida INN va Fiskal modul so'raldi!")

    # 2. "tekshirib bering"
    res2 = await core_engine.process_text_inquiry(
        text="iltimos kassa apparatimni tekshirib bering",
        chat_id=chat_id,
        user_id=user_id
    )
    assert res2.action == ActionType.DEBT_INFO
    assert "INN" in res2.reply_text
    assert "Fiskal modul" in res2.reply_text
    logger.info("✅ 'tekshirib bering' so'rovida INN va Fiskal modul so'raldi!")

async def test_stage1_debt_checked_with_inn():
    logger.info(">>> TEST 2: INN orqali qarz tekshiruvi (qarzli va qarzsiz)...")
    chat_id = 9922
    user_id = 8822
    user_memory.clear_context(chat_id, user_id)

    # A) Qarzli korxona (INN: 206011507 - Qashqadaryo Sharq Gavhari)
    res_debt = await core_engine.process_text_inquiry(
        text="206011507",
        chat_id=chat_id,
        user_id=user_id
    )
    assert res_debt.action == ActionType.DEBT_INFO
    assert res_debt.debt_amount > 0
    assert "1,500,400" in res_debt.reply_text
    assert res_debt.video_id == 148
    assert "Fiskal modul" in res_debt.reply_text
    logger.info("✅ Qarzli korxonada summa, video 148 va fiskal modul eslatmasi chiqdi!")

    # B) Qarzsiz korxona (INN: 311790999 - Alisher Bobo Qurilish Mollari)
    res_clean = await core_engine.process_text_inquiry(
        text="311790999",
        chat_id=chat_id,
        user_id=user_id
    )
    assert res_clean.action == ActionType.DEBT_INFO
    assert res_clean.debt_amount == 0.0
    assert "qarzdorlik mavjud emas" in res_clean.reply_text.lower() or "qarzdorlik yo'q" in res_clean.reply_text.lower()
    # Qarzsiz bo'lganda darhol 3-bosqich tavsiyasi berilishi kerak
    assert "Internet va Soat" in res_clean.reply_text or "soat" in res_clean.reply_text.lower()
    assert "Reboot" in res_clean.reply_text or "qayta yoqing" in res_clean.reply_text.lower()
    logger.info("✅ Qarzsiz korxonada 0 qarz tasdiqlandi va Stage 3 tavsiyalari chiqdi!")

async def test_stage1_combined_inn_and_fiscal_module():
    logger.info(">>> TEST 3: INN va Fiskal modul birga yuborilganda yagona sintez javobi...")
    chat_id = 9933
    user_id = 8833
    user_memory.clear_context(chat_id, user_id)

    mock_bot = create_mock_bot()

    # ofd_bridge ni mock qilamiz
    with patch.object(ofd_bridge, "query_fiscal_module", new_callable=AsyncMock) as mock_ofd:
        mock_ofd.return_value = "🟢 Soliq tizimida faol. Litsenziya muddati: 2027-01-15 gacha."
        res_both = await core_engine.process_text_inquiry(
            text="Bizning INN 311790999, apparat moduli LG420210009999",
            chat_id=chat_id,
            user_id=user_id,
            bot=mock_bot
        )
        assert res_both.action == ActionType.DEBT_INFO
        # Ham oylik Mars qarz holati, ham OFD yillik litsenziyasi bitta javobda bo'lishi kerak
        assert "Alisher Bobo" in res_both.reply_text or "ALISHER BOBO" in res_both.reply_text
        assert "OFD / Soliq" in res_both.reply_text
        assert "2027-01-15" in res_both.reply_text
        logger.info("✅ INN va Fiskal modul birga yuborilganda to'liq sintez javobi shakllandi!")

async def test_error_406_distinction_and_video():
    logger.info(">>> TEST 4: 406-xatolik va Yillik to'lov ajratilishi...")
    chat_id = 9944
    user_id = 8844
    user_memory.clear_context(chat_id, user_id)

    # 406 so'rovi
    res_406 = await core_engine.process_text_inquiry(
        text="ekranda 406 xatolik chiqyapti, bu nima?",
        chat_id=chat_id,
        user_id=user_id
    )
    assert res_406.action == ActionType.DIAGNOSE_AND_REPLY
    assert "406" in res_406.reply_text
    assert "Oylik abonent to'lovi emas" in res_406.reply_text or "Oylik abonent to'lovi EMAS" in res_406.reply_text
    assert "Yangi Texnologiyalar" in res_406.reply_text
    assert res_406.video_id == 145  # Click orqali Yillik to'lov videosi
    logger.info("✅ 406-xatolik oylik emas, Yillik Soliq to'lovi ekanligi 145-video bilan tasdiqlandi!")

async def test_dual_technician_escalation():
    logger.info(">>> TEST 5: Ikkala mas'ul texnikka (@quvonchbek_admin, @Yashnarbek_butaev) eskalatsiya...")
    chat_id = 9955
    user_id = 8855
    user_memory.clear_context(chat_id, user_id)
    user_memory.set_last_id(chat_id, user_id, "206011507")  # Shahrisabz tumanidagi korxona

    mock_bot = create_mock_bot()
    admin_manager.admin_ids = [1966874161, 6436610869]

    # Usta / operator so'rovi
    res_esc = await core_engine.process_text_inquiry(
        text="apparat tuzalmadi usta chaqirib bering",
        chat_id=chat_id,
        user_id=user_id,
        user_name="Ali Valiyev",
        user_username="ali_valiyev",
        bot=mock_bot
    )
    assert res_esc.action == ActionType.ESCALATE_TO_ADMIN
    assert "@quvonchbek_admin" in res_esc.reply_text
    assert "@Yashnarbek_butaev" in res_esc.reply_text
    assert "карши" in res_esc.reply_text.lower() or res_esc.tuman == "карши"

    # Adminga yuborilgan xabarnomani tekshirish
    await admin_manager.notify_user_query_escalation(
        bot=mock_bot,
        user=MockUser(user_id, "Ali Valiyev", "ali_valiyev"),
        chat_id=chat_id,
        query_text="apparat tuzalmadi usta chaqirib bering",
        inn="206011507",
        org_name=res_esc.org_name
    )
    assert mock_bot.send_message.called
    sent_text = mock_bot.send_message.call_args.kwargs["text"]
    assert "@quvonchbek_admin" in sent_text
    assert "@Yashnarbek_butaev" in sent_text
    assert "206011507" in sent_text
    logger.info("✅ Eskalatsiya xabari va foydalanuvchi javobida ikkala texnik aniq ko'rsatildi!")

async def main():
    await test_stage1_problem_without_inn_or_fm()
    await test_stage1_debt_checked_with_inn()
    await test_stage1_combined_inn_and_fiscal_module()
    await test_error_406_distinction_and_video()
    await test_dual_technician_escalation()
    logger.info("🎉 BARCHA 4-BOSQICHLI PIPELINE VA TEXNIK TESTLAR 100% MUVAFFAQIYATLI O'TDI!")

if __name__ == "__main__":
    asyncio.run(main())
