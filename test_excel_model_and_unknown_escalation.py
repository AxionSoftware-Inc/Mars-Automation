"""
test_excel_model_and_unknown_escalation.py
==========================================
1. Excel rangiga qarab apparat modelini aniqlash (P3 Humo sariq vs Smart One oq).
2. Xavfsiz Excel yangilash (buzuq / yaroqsiz fayl rad etilishi, original baza saqlanishi).
3. AI bilmagan narsasi so'ralganda taxmin qilmasdan adminga yo'naltirishi (needs_admin flag va eskalatsiya).
"""

import os
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from excel_manager import excel_manager
from ai_helper import generate_ai_reply_ex, AIHelper
from admin_manager import admin_manager
from core.models import DecisionResult, ActionType
from core.engine import core_engine
from handlers.chat import handle_user_chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_excel_and_escalation")

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

def test_excel_device_model_separation():
    logger.info(">>> TEST 1: Exceldagi rangga qarab apparat modelini ajratish...")
    
    # Bazada 7200+ korxona bor
    assert excel_manager.records_count > 5000, f"Baza kam yuklangan: {excel_manager.records_count}"
    
    # 1. P3 Humo (sariq qator) misoli:
    # 311481235 (Jaloliddin Panjiyev XK) sariq qatorda
    is_p3_jalol = excel_manager.is_p3_for_inn("311481235")
    res_jalol = excel_manager.search("311481235")
    assert res_jalol, "Jaloliddin Panjiyev XK topilmadi"
    model_jalol = excel_manager.get_device_model_summary(res_jalol)
    logger.info(f"INN 311481235 model: {model_jalol} (is_p3: {is_p3_jalol})")
    assert "P3 Humo" in model_jalol, f"P3 Humo topilmadi: {model_jalol}"
    assert is_p3_jalol is True, "P3 Humo uchun is_p3 True bo'lishi kerak"

    # 2. Smart One (oq qator) misoli:
    # 311790999 (Alisher Bobo Qurilish Mollari) oq qatorda
    is_p3_alisher = excel_manager.is_p3_for_inn("311790999")
    res_alisher = excel_manager.search("311790999")
    assert res_alisher, "Alisher Bobo topilmadi"
    model_alisher = excel_manager.get_device_model_summary(res_alisher)
    logger.info(f"INN 311790999 model: {model_alisher} (is_p3: {is_p3_alisher})")
    assert "Smart One" in model_alisher, f"Smart One topilmadi: {model_alisher}"
    assert is_p3_alisher is False, "Smart One uchun is_p3 False bo'lishi kerak"

    logger.info("✅ Excel rangiga qarab P3 Humo (sariq) va Smart One (oq) 100% to'g'ri ajratildi!")

def test_safe_excel_update():
    logger.info(">>> TEST 2: Xavfsiz Excel yangilash (buzilgan yoki yaroqsiz faylni rad etish)...")
    
    original_count = excel_manager.records_count
    
    import tempfile
    # A) Yaroqsiz bo'sh .xlsx fayl
    tmp_empty = tempfile.mktemp(suffix=".xlsx")
    with open(tmp_empty, "w") as f:
        f.write("not an excel file")
    
    success = excel_manager.update_file(tmp_empty)
    assert success is False, "Buzuq fayl rad etilishi kerak edi!"
    assert excel_manager.records_count == original_count, "Eski baza saqlanib qolishi shart edi!"
    logger.info(f"✅ Buzuq fayl muvaffaqiyatli rad etildi, sabab: '{excel_manager.last_update_error}'")

    # B) Eski .xls formati
    tmp_xls = tempfile.mktemp(suffix=".xls")
    with open(tmp_xls, "w") as f:
        f.write("old xls")
    success_xls = excel_manager.update_file(tmp_xls)
    assert success_xls is False, ".xls formati rad etilishi kerak!"
    assert "xls" in excel_manager.last_update_error.lower()
    logger.info(f"✅ .xls formati rad etildi, sabab: '{excel_manager.last_update_error}'")

    if os.path.exists(tmp_empty):
        os.remove(tmp_empty)
    if os.path.exists(tmp_xls):
        os.remove(tmp_xls)

    logger.info("✅ Xavfsiz Excel yangilash to'liq tasdiqlandi!")

async def test_unknown_question_admin_escalation():
    logger.info(">>> TEST 3: AI bilmagan narsasini taxmin qilmasdan adminga yo'naltirishi...")
    
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.copy_message = AsyncMock()

    user = MockUser(998811, "Farrux", "farrux_biznes")
    chat = MockChat(-100992211)

    # 1. generate_ai_reply_ex ni soxta bilmaydigan javob bilan sinaymiz
    with patch("ai_helper.openrouter_client.chat_completion", return_value="Bu savol bo'yicha menda aniq ma'lumot yo'q. Savolingizni mas'ul mutaxassisimizga yubordim. [ADMINGA_SAVOL]"):
        reply, vid, needs_admin = generate_ai_reply_ex("Sizlarda yangi kassa dasturining narxi qancha bo'ladi?")
        assert needs_admin is True, "needs_admin True bo'lishi shart edi!"
        assert "[ADMINGA_SAVOL]" not in reply, "Teg mijozga ko'rinmasligi kerak!"
        assert "aniq ma'lumot yo'q" in reply.lower()
        logger.info(f"✅ generate_ai_reply_ex needs_admin=True qaytardi va tegni tozaladi: '{reply}'")

    # 2. handle_user_chat orqali real eskalatsiya chaqiruvini tekshiramiz
    with patch("handlers.chat.generate_ai_reply_ex_async", new_callable=AsyncMock, return_value=("Kechirasiz, menda bu haqda aniq ma'lumot yo'q. Mutaxassisga yubordim.", None, True)), \
         patch("handlers.chat.generate_ai_reply_ex", return_value=("Kechirasiz, menda bu haqda aniq ma'lumot yo'q. Mutaxassisga yubordim.", None, True)), \
         patch("admin_manager.admin_manager.notify_user_query_escalation", new_callable=AsyncMock) as mock_notify:
        
        msg = MockMessage(101, user, chat, "Menda umuman boshqa dastur bor, shuni ulab berasizlarmi?")
        await handle_user_chat(msg, bot)

        # Adminga xabar ketganini tekshiramiz:
        assert mock_notify.called, "admin_manager.notify_user_query_escalation chaqirilmadi!"
        call_kwargs = mock_notify.call_args.kwargs
        assert call_kwargs["chat_id"] == -100992211
        assert "boshqa dastur" in call_kwargs["query_text"]
        logger.info(f"✅ Adminga eskalatsiya xabarnomasi muvaffaqiyatli yuborildi: {call_kwargs['reason']}")

    # 3. CoreEngine process_text_inquiry orqali sinash:
    with patch("ai_helper.ai_helper.ask_with_context_ex", return_value=("Aniq ma'lumot yo'q.", None, True)):
        res = await core_engine.process_text_inquiry(
            text="Ijaraga kassa apparati berasizlarmi?",
            chat_id=-100992211,
            user_id=998811
        )
        assert res.should_notify_admin is True, "CoreEngine should_notify_admin True bo'lishi shart!"
        assert "AI bilmadi" in res.admin_alert_text
        logger.info(f"✅ CoreEngine yadro darajasida ham adminga xabar belgisini yoqdi: {res.admin_alert_text}")

    logger.info("🎉 BARCHA EXCEL VA NO-HALLUCINATION ESKALATSIYA TESTLARI 100% MUVAFFAQIYATLI O'TDI!")

async def main():
    test_excel_device_model_separation()
    test_safe_excel_update()
    await test_unknown_question_admin_escalation()

if __name__ == "__main__":
    asyncio.run(main())
