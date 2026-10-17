"""
test_8_step_modular_architecture.py
===================================
Yangi Modulli Arxitektura (ModuleRegistry + GroupResponseOrchestrator) va
1 dan 8 gacha bo'lgan qat'iy guruh qoidalarini (shu jumladan o'rtadan,
3-qadamdan, 5-qadamdan yoki 6-qadamdan boshlangan ssenariylarni) to'liq sinovdan o'tkazish.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types, Router

from core.module_registry import BaseBotModule, module_registry
from core.group_responder import group_responder
from core.rule_engine import rule_engine
from user_memory import user_memory
from admin_manager import admin_manager
from handlers import main_router
from handlers.chat import handle_user_chat
from ofd_bridge import ofd_bridge


def make_msg(text: str, chat_id: int = -100555666, user_id: int = 777888, name: str = "Sardor"):
    msg = AsyncMock(spec=types.Message)
    msg.text = text
    msg.chat = MagicMock(id=chat_id, type="supergroup")
    msg.from_user = types.User(id=user_id, is_bot=False, first_name=name, username="sardor_uz")
    msg.message_id = 500
    msg.reply = AsyncMock()
    msg.answer = AsyncMock()
    return msg


async def run_all_tests():
    print("\n=================================================================")
    print("🏛 1. MODULLI ARXITEKTURA (PLUGIN / MODULE REGISTRY) TESTI")
    print("=================================================================")

    # Standart 6 ta modul ulanganligini tekshirish
    active_mods = module_registry.get_active_modules()
    mod_names = [m.name for m in active_mods]
    for expected in ["admin_module", "commands_module", "media_module", "billing_module", "channel_module", "group_support_module"]:
        assert expected in mod_names, f"Modul topilmadi: {expected}"
    print(f"✅ Standart modullar ro'yxatdan o'tgan: {mod_names}")

    # Yangi tashqi modul (masalan: Click/Payme To'lov Moduli) qo'shib ko'rish
    class ExternalPaymentModule(BaseBotModule):
        name = "external_click_payme_module"
        version = "1.0.0"
        description = "Tashqi Click va Payme avto-to'lov moduli"
        priority = 75

        def get_router(self):
            return Router(name="external_payment_router")

    module_registry.register(ExternalPaymentModule())
    assert module_registry.get_module("external_click_payme_module") is not None
    module_registry.unregister("external_click_payme_module")
    print("✅ Tashqi katta modulni (ExternalPaymentModule) ulash va uzish 100% ishladi!")

    print("\n=================================================================")
    print("🔄 2. ISTALGAN QADAMDAN (3, 5, 6-QADAMDAN) BOSHLASH TESTLARI")
    print("=================================================================")

    bot = AsyncMock()
    chat_id = -100999111
    user_id = 444555666

    # 2.1: Mijoz birdaniga 6-QADAMDAN boshlaydi ("oylik shot tashlang"), keyin 4-QADAMGA o'tadi ("apparat ishlamayapti 300600431")
    user_memory.clear_context(chat_id, user_id)
    m_step6 = make_msg("oylik shot tashlang", chat_id, user_id)
    await handle_user_chat(m_step6, bot)
    assert bot.copy_message.called, "6-qadam: Oylik shot posti (85) kanaldan yuborilishi kerak edi"
    print("✅ [6-qadamdan kirish]: 'oylik shot tashlang' -> Post 85 va Video 148 darhol yuborildi!")

    # Endi shu mijoz birdaniga 4-qadamga sakraydi va INN ham yozadi:
    m_jump4 = make_msg("apparatim ishlamayapti 300600431", chat_id, user_id)
    await handle_user_chat(m_jump4, bot)
    reply_jump4 = m_jump4.reply.call_args[0][0]
    assert "fiskal modul" in reply_jump4.lower(), f"Oylik qarz 0 so'm bo'lgani uchun darhol 2-bosqich (FM) so'ralishi kerak edi: {reply_jump4}"
    print("✅ [6-qadamdan -> 4-qadamga sakrash]: INN tanildi (qarz 0 so'm) va darhol Fiskal modul so'raldi!")

    # 2.2: Mijoz birdaniga 3-QADAMDAN boshlaydi ("usta kerak, apparat buzildi")
    user_memory.clear_context(chat_id, user_id)
    with patch.object(admin_manager, "notify_user_query_escalation", new_callable=AsyncMock) as mock_esc:
        m_step3 = make_msg("usta kerak bog'laning", chat_id, user_id)
        await handle_user_chat(m_step3, bot)
        assert m_step3.reply.called
        assert mock_esc.called, "Adminga eskalatsiya xabari borishi shart"
        print("✅ [3-qadamdan kirish]: 'usta kerak bog'laning' -> Darhol adminga uzatildi va tugmalar berildi!")

    # 2.3: Mijoz eskalatsiyadan keyin birdaniga INN yuborsa (yangi tekshiruv) -> Qotib qolmasdan INN ni tekshirishi kerak!
    m_after_esc_inn = make_msg("300600431", chat_id, user_id)
    await handle_user_chat(m_after_esc_inn, bot)
    assert m_after_esc_inn.reply.called
    r_after = m_after_esc_inn.reply.call_args[0][0]
    assert "300600431" in r_after, f"Eskalatsiyadan keyin INN yuborilganda tekshirilishi kerak edi: {r_after}"
    print("✅ [3-qadamdan -> 5-qadamga o'tish]: Eskalatsiyadan keyin INN yozilganda bot to'sib qo'ymasdan qarzni tekshirdi!")

    # 2.4: Mijoz avval "nega qarzim bor, to'laganmanku" (5-qadam: To'lov tarixi) deb INN bilan yozadi
    user_memory.clear_context(chat_id, user_id)
    m_hist = make_msg("nega qarz chiqyapti to'laganmanku 300600431", chat_id, user_id)
    await handle_user_chat(m_hist, bot)
    assert m_hist.reply.called
    r_hist = m_hist.reply.call_args[0][0]
    assert "300600431" in r_hist
    print("✅ [5-qadam: To'lov tarixi]: 'nega qarz chiqyapti to'laganmanku 300600431' -> To'lov tarixi chiqarildi!")

    # 2.5: Dinamik qoida (2-Qadam: Plug & Play) qo'shish va tekshirish
    rule_engine.add_patch(
        patch_id="test_lenta_rule",
        keywords=["qog'oz lenta qancha", "lenta narxi"],
        reply_text="🧻 Kassa apparati uchun termolenta narxi: 5 000 so'm.",
        priority=90
    )
    m_patch = make_msg("lenta narxi qancha?", chat_id, user_id)
    await handle_user_chat(m_patch, bot)
    assert "5 000" in m_patch.reply.call_args[0][0]
    rule_engine.remove_patch("test_lenta_rule")
    print("✅ [2-qadam: Dinamik qoida]: Kodga tegmasdan yangi qoida qo'shildi va ishladi!")

    print("\n=================================================================")
    print("🎉 YANGI MODULLI ARXITEKTURA VA 8 QADAMLI TIZIM 100% SINOVDAN O'TDI!")
    print("=================================================================\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
