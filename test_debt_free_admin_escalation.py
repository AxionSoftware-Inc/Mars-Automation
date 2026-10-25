import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types

from user_memory import user_memory
from admin_manager import admin_manager, get_admin_contact_keyboard
from handlers.intents.hardware import hardware_intent_handler
from handlers.intents.billing import billing_intent_handler
from handlers.intents.operator import operator_intent_handler
from excel_manager import excel_manager

async def run_tests():
    print("=== TEST 1: Admin keyboard structure ===")
    kb = get_admin_contact_keyboard()
    assert kb is not None
    assert any("quvonchbek_admin" in row[0].url for row in kb.inline_keyboard if row[0].url)
    assert any("Yashnarbek_butaev" in row[0].url for row in kb.inline_keyboard if row[0].url)
    print("✅ TEST 1 PASSED: Admin keyboard to'g'ri yaratildi.")

    print("\n=== TEST 2: Hardware 3-bosqich (Qarzsiz nosozlik eskalatsiyasi va rasm) ===")
    chat_id = 99887711
    user_id = 55443322
    user_memory.sessions.clear()
    
    # Foydalanuvchi avval rasm yuborgan deb hisoblaymiz:
    test_photo_id = "AgACAgIAAxkBAAI_test_photo_file_id"
    user_memory.set_last_photo(chat_id, user_id, test_photo_id)
    user_memory.set_issue_mode(chat_id, user_id, True, initial_query="kassa apparatim ishlamayapti ekran qotib qoldi")

    # Mock bot va message
    mock_bot = AsyncMock()
    mock_user = types.User(id=user_id, is_bot=False, first_name="Ali", username="ali_tadbirkor")

    # Mock excel_manager to return 0 debt for INN 112233445
    with patch.object(excel_manager, "search", return_value=[{"name": "TEST MEGA SERVIS MCHJ", "debt": 0.0, "inn": "112233445"}]):
        with patch.object(admin_manager, "notify_debt_free_device_issue", new_callable=AsyncMock) as mock_notify:
            # 1. Mijoz INN kiritadi
            msg_inn = AsyncMock(spec=types.Message)
            msg_inn.reply = AsyncMock()
            msg_inn.text = "112233445"
            msg_inn.chat = MagicMock(id=chat_id)
            msg_inn.from_user = mock_user
            msg_inn.message_id = 101

            handled = await hardware_intent_handler.handle(msg_inn, mock_bot, "latin")
            assert handled is True
            # Bot FM so'ragan bo'lishi kerak
            reply_call = msg_inn.reply.call_args
            assert reply_call is not None
            reply_text = reply_call[0][0]
            assert "2-bosqich" in reply_text or "Fiskal modul" in reply_text
            print("✅ 1-qadam: INN bo'yicha qarz 0 bo'lgach, Fiskal modul so'raldi.")

            # 2. Mijoz Fiskal modulni kiritadi: LG420210630789
            msg_fm = AsyncMock(spec=types.Message)
            msg_fm.reply = AsyncMock()
            msg_fm.text = "LG420210630789"
            msg_fm.chat = MagicMock(id=chat_id)
            msg_fm.from_user = mock_user
            msg_fm.message_id = 102

            with patch("handlers.intents.hardware.ofd_bridge.query_fiscal_module", new_callable=AsyncMock, return_value="Litsenziya muddati faol"):
                handled2 = await hardware_intent_handler.handle(msg_fm, mock_bot, "latin")
                assert handled2 is True
                reply_call2 = msg_fm.reply.call_args
                assert reply_call2 is not None
                step3_text = reply_call2[0][0]
                assert "hech qanday qarzdorlik yo'q" in step3_text or "qarzdorlik yo'q" in step3_text
                # reply_markup tekshirish
                reply_kw = reply_call2[1]
                assert "reply_markup" in reply_kw
                assert reply_kw["reply_markup"] is not None
                assert any("quvonchbek_admin" in btn[0].url for btn in reply_kw["reply_markup"].inline_keyboard if btn[0].url)
                
                # Adminga photo_file_id bilan eskalatsiya ketganini tekshirish
                assert mock_notify.called
                notify_kw = mock_notify.call_args[1]
                assert notify_kw["photo_file_id"] == test_photo_id
                assert notify_kw["inn"] == "112233445"
                assert notify_kw["org_name"] == "TEST MEGA SERVIS MCHJ"
                assert notify_kw["fiscal_module"] == "LG420210630789"
                print("✅ 2-qadam: Ikkala qarz ham 0 bo'lganda adminga rasm bilan eskalatsiya ketdi va foydalanuvchiga admin inline tugmalari berildi!")

    print("\n=== TEST 3: Operator / Usta chaqirilganda inline tugmalar ===")
    user_memory.sessions.clear()
    msg_op = AsyncMock(spec=types.Message)
    msg_op.reply = AsyncMock()
    msg_op.text = "menga usta kerak apparat buzildi"
    msg_op.chat = MagicMock(id=chat_id)
    msg_op.from_user = mock_user
    msg_op.message_id = 103

    handled_op = await operator_intent_handler.handle(msg_op, mock_bot, "latin")
    assert handled_op is True
    op_reply = msg_op.reply.call_args
    assert op_reply is not None
    assert "reply_markup" in op_reply[1]
    assert any("quvonchbek_admin" in btn[0].url for btn in op_reply[1]["reply_markup"].inline_keyboard if btn[0].url)
    print("✅ TEST 3 PASSED: Operator so'ralganda ham to'g'ridan-to'g'ri admin tugmalari berildi.")

    print("\n🎉 BARCHA TESTLAR 100% MUVAFFAQIShLI O'TDI!")

if __name__ == "__main__":
    asyncio.run(run_tests())
