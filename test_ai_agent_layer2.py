import unittest
import asyncio
from unittest.mock import AsyncMock, patch

from core.ai_agent import mars_ai_agent, AgentResult
from excel_manager import excel_manager
from user_memory import user_memory


class TestMarsAIAgentLayer2(unittest.TestCase):
    """
    2-Qatlam: Yuqori qatlam (AI Agent & Tool Orchestrator) testlari.
    """

    def setUp(self):
        user_memory.clear_context(chat_id=1001, user_id=2001)

    def test_direct_numeric_inn_routing(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_debt_res = {
            "found": True,
            "total_debt": 0,
            "record": {"org_name": "TOZA MCHJ", "stir": "302568138"},
            "results": [{"name": "TOZA MCHJ", "stir": "302568138", "debt": 0, "is_p3": False}]
        }
        with patch.object(excel_manager, "check_debt", return_value=mock_debt_res):
            res: AgentResult = loop.run_until_complete(
                mars_ai_agent.process_user_turn(
                    text="302568138",
                    user_id=2001,
                    chat_id=1001
                )
            )
            self.assertEqual(res.action, "CHECK_DEBT")
            self.assertEqual(res.tool_called, "check_monthly_debt")
            self.assertIn("302568138", res.reply_text)

    def test_direct_fm_routing(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        with patch("core.tools.check_fiscal_license", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = {
                "success": True,
                "fm": "LG420230615712",
                "status": "active",
                "has_debt": False,
                "formatted_text": "🏛 Fiskal modul: LG420230615712 faol!"
            }
            res: AgentResult = loop.run_until_complete(
                mars_ai_agent.process_user_turn(
                    text="LG420230615712",
                    user_id=2001,
                    chat_id=1001
                )
            )
            self.assertEqual(res.action, "CHECK_OFD")
            self.assertEqual(res.tool_called, "check_fiscal_license")
            self.assertIn("LG420230615712", res.reply_text)

    def test_ai_tool_call_execution(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # AI mock: Gemini tool call qaytardi
        mock_ai_resp = {
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "get_payment_requisites",
                        "arguments": '{"payment_type": "annual"}'
                    }
                }
            ]
        }

        with patch("openrouter_client.openrouter_client.chat_completion_with_tools_async", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_ai_resp

            res: AgentResult = loop.run_until_complete(
                mars_ai_agent.process_user_turn(
                    text="soliqqa yillik to'lov hisob raqamini ber",
                    user_id=2001,
                    chat_id=1001
                )
            )
            self.assertEqual(res.action, "REQUISITES")
            self.assertEqual(res.tool_called, "get_payment_requisites")
            self.assertIn("20210000100431200010", res.reply_text)
            self.assertEqual(res.media_video_id, 145)

    def test_ai_fallback_when_api_down(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        with patch("openrouter_client.openrouter_client.chat_completion_with_tools_async", side_effect=Exception("API Timeout")):
            res: AgentResult = loop.run_until_complete(
                mars_ai_agent.process_user_turn(
                    text="menga tezda usta kerak",
                    user_id=2001,
                    chat_id=1001
                )
            )
            # Fallback must gracefully escalate without throwing unhandled exception
            self.assertEqual(res.action, "ESCALATE_ADMIN")
            self.assertIn("@", res.reply_text)


if __name__ == "__main__":
    unittest.main()
