import unittest
import asyncio
from unittest.mock import AsyncMock, patch

from core.tools import (
    check_monthly_debt,
    check_fiscal_license,
    get_payment_requisites,
    verify_receipt_data,
    pos_troubleshoot_step,
    escalate_to_admin,
    get_instruction,
)
from excel_manager import excel_manager
from transaction_tracker import transaction_tracker


class TestCoreToolsLayer1(unittest.TestCase):
    """
    1-Qatlam: Pastki qatlam (Clean Tools) unit testlari.
    """

    def setUp(self):
        transaction_tracker.transactions.clear()

    def test_check_monthly_debt_with_known_and_unknown_inn(self):
        # 1. Noto'g'ri INN
        res_invalid = check_monthly_debt("abc")
        self.assertFalse(res_invalid["success"])

        # 2. Mavjud bo'lmagan INN
        res_unknown = check_monthly_debt("999999999")
        self.assertTrue(res_unknown["success"])
        self.assertFalse(res_unknown["found"])

        # 3. Mavjud INN
        mock_debt_res = {
            "found": True,
            "total_debt": 200000,
            "record": {"org_name": "TEST MCHJ", "stir": "302568138"},
            "results": [{"name": "TEST MCHJ", "stir": "302568138", "debt": 200000, "is_p3": False}]
        }
        with patch.object(excel_manager, "check_debt", return_value=mock_debt_res):
            res = check_monthly_debt("302568138")
            self.assertTrue(res["success"])
            self.assertTrue(res["found"])
            self.assertEqual(res["debt_amount"], 200000)
            self.assertTrue(res["has_debt"])
            self.assertIn("302568138", res["formatted_text"])
            self.assertIn("200,000", res["formatted_text"])

    def test_get_payment_requisites(self):
        res_monthly = get_payment_requisites("monthly")
        self.assertEqual(res_monthly["payment_type"], "monthly")
        self.assertIn("20208000800208044003", res_monthly["formatted_text"])

        res_annual = get_payment_requisites("annual")
        self.assertEqual(res_annual["payment_type"], "annual")
        self.assertIn("20210000100431200010", res_annual["formatted_text"])

    def test_verify_receipt_duplicate_detection(self):
        # 1. Yangi tranzaksiya
        res1 = verify_receipt_data(transaction_id="TX_TEST_001", inn="302568138", amount=100000)
        self.assertTrue(res1["success"])
        self.assertFalse(res1["is_duplicate"])

        # 2. Aynan shu tranzaksiya yana kelsa -> dublikat deb tan olinishi kerak
        res2 = verify_receipt_data(transaction_id="TX_TEST_001", inn="302568138", amount=100000)
        self.assertTrue(res2["is_duplicate"])

    def test_escalate_to_admin(self):
        res = escalate_to_admin(inn="302568138", reason="Usta kerak")
        self.assertTrue(res["success"])
        self.assertTrue(res["escalated"])
        self.assertIn("@", res["formatted_text"])

    def test_get_instruction(self):
        res_mxik = get_instruction("mxik")
        self.assertIn("tasnif.soliq.uz", res_mxik["formatted_text"])
        self.assertEqual(res_mxik["video_id"], 28)

        res_vozvrat = get_instruction("vozvrat")
        self.assertEqual(res_vozvrat["video_id"], 140)

    def test_pos_troubleshoot_step(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Step 1: No INN -> ASK_INN
        res1 = loop.run_until_complete(pos_troubleshoot_step(inn=None))
        self.assertEqual(res1["step"], 1)
        self.assertEqual(res1["action"], "ASK_INN")

        # Step 1: Monthly debt exists -> PAY_MONTHLY_DEBT
        mock_debt_res = {
            "found": True,
            "total_debt": 300000,
            "record": {"org_name": "QARZDOR MCHJ", "stir": "302568138"},
            "results": [{"name": "QARZDOR MCHJ", "stir": "302568138", "debt": 300000, "is_p3": False}]
        }
        with patch.object(excel_manager, "check_debt", return_value=mock_debt_res):
            res_debt = loop.run_until_complete(pos_troubleshoot_step(inn="302568138"))
            self.assertEqual(res_debt["step"], 1)
            self.assertEqual(res_debt["action"], "PAY_MONTHLY_DEBT")

        # Step 2: Monthly debt clear, but FM is None -> ASK_FM
        mock_clear_res = {
            "found": True,
            "total_debt": 0,
            "record": {"org_name": "TOZA MCHJ", "stir": "302568138"},
            "results": [{"name": "TOZA MCHJ", "stir": "302568138", "debt": 0, "is_p3": False}]
        }
        with patch.object(excel_manager, "check_debt", return_value=mock_clear_res):
            res2 = loop.run_until_complete(pos_troubleshoot_step(inn="302568138", fiscal_module=None))
            self.assertEqual(res2["step"], 2)
            self.assertEqual(res2["action"], "ASK_FM")

        # Step 3: Monthly debt clear, FM active, reboot_tried=False -> REBOOT_AND_CHECK_NET
        with patch.object(excel_manager, "check_debt", return_value=mock_clear_res), \
             patch("core.tools.check_fiscal_license", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = {"has_debt": False, "status": "active"}
            res3 = loop.run_until_complete(pos_troubleshoot_step(
                inn="302568138", fiscal_module="LG420230615712", reboot_tried=False
            ))
            self.assertEqual(res3["step"], 3)
            self.assertEqual(res3["action"], "REBOOT_AND_CHECK_NET")

        # Step 4: Both clear, reboot_tried=True -> ESCALATE_ADMIN
        with patch.object(excel_manager, "check_debt", return_value=mock_clear_res), \
             patch("core.tools.check_fiscal_license", new_callable=AsyncMock) as mock_ofd:
            mock_ofd.return_value = {"has_debt": False, "status": "active"}
            res4 = loop.run_until_complete(pos_troubleshoot_step(
                inn="302568138", fiscal_module="LG420230615712", reboot_tried=True
            ))
            self.assertEqual(res4["step"], 4)
            self.assertEqual(res4["action"], "ESCALATE_ADMIN")


if __name__ == "__main__":
    unittest.main()
