import logging
from typing import Optional, Dict, Any

from core.models import DeviceFacts, DecisionResult, ActionType
from error_manager import error_manager
from excel_manager import excel_manager
from user_memory import user_memory

logger = logging.getLogger(__name__)

INCOMPLETE_SCREEN_REPLY = (
    "⚠️ <b>Ekranning tepa qismi (soat va tarmoq qatori) ko'rinmayapti.</b>\n"
    "Aniq tashxis qo'yishimiz uchun apparat ekranining yuqori qismidagi soat va internet belgisi tushgan holda qayta rasm yuboring."
)

SAFE_FALLBACK_REPLY = (
    "⚠️ <b>Tasvirni to'liq tahlil qilib bo'lmadi.</b>\n"
    "Iltimos, apparat ekranini to'liqroq va yorug'roq joyda rasmga olib qayta yuboring "
    "yoki korxonangizning <b>INN (STIR)</b> raqamini yozing."
)

class CoreEngine:
    """
    Markaziy Algoritmik Yadro (Decision Engine).
    Barcha sensorlar (rasm tahlili, matn tahlili) faktlarini qabul qilib,
    qat'iy zanjir (pipeline) bo'yicha yakuniy qaror chiqaradi.
    """

    def process_device_facts(self, facts: DeviceFacts, chat_id: int, user_id: int) -> DecisionResult:
        """
        Kassa apparati faktlarini tahlil qilib, yagona yakuniy harakatni (Action) belgilash.
        """
        # 0-BOSQICH: ZANJIR UZILIB QOLISHIDAN HIMOYA (RESILIENCE / FAIL-SAFE)
        if facts.extraction_error:
            logger.warning(f"Sensor uzilishi: {facts.extraction_error}. Zaxira himoya ishga tushdi.")
            # Agar tasodifan INN aniqlangan bo'lsa, baribir Exceldan tekshirib beramiz
            if facts.detected_inn:
                return self._resolve_inn_only(facts.detected_inn, chat_id, user_id)
            return DecisionResult(
                action=ActionType.FALLBACK_SAFE,
                reply_text=SAFE_FALLBACK_REPLY,
                log_reason=f"Extraction failure: {facts.extraction_error}"
            )

        # 1-BOSQICH: GUARDRAIL (BEGONA RASMLARNI CHIQARIB TASHLASH)
        # Agar rasm kassa apparatiga tegishli bo'lmasa va unda INN ham bo'lmasa -> MUTLAQO JIM TURISH
        if not facts.is_real_pos_device and not facts.detected_inn:
            logger.info("Guardrail: Tasvir kassa apparati emas. E'tiborsiz qoldiriladi.")
            return DecisionResult(
                action=ActionType.IGNORE,
                log_reason="Not a real POS device image"
            )

        # 2-BOSQICH: PRE-CONDITION (STATUS BAR / SOAT VA TARMOQ QATORI)
        # Kassa apparati bo'lsa-yu, tepasidagi soat ko'rinmasa -> TO'LIQ EKRAN TALAB QILISH
        if not facts.is_status_bar_visible:
            logger.info("Pre-condition: Status bar ko'rinmayapti. To'liq ekran talab qilinadi.")
            return DecisionResult(
                action=ActionType.ASK_FULL_SCREEN,
                reply_text=INCOMPLETE_SCREEN_REPLY,
                detected_inn=facts.detected_inn,
                log_reason="Status bar invisible"
            )

        # 3-BOSQICH: EKRAN TASHXISI (ERROR MANAGER QOIDALARI)
        diag_text: Optional[str] = None
        diag_video_id: Optional[int] = None

        matched_rule = error_manager.match_error(facts.raw_facts)
        if matched_rule:
            diag_text = matched_rule.get("response_text", "")
            diag_video_id = matched_rule.get("video_id")
        elif facts.screen_text_summary and facts.screen_text_summary.lower() != "none":
            diag_text = (
                f"ℹ️ <b>Ekrandagi holat:</b> {facts.screen_text_summary}\n"
                f"Nosozlik davom etsa, korxona INN raqamini yuboring."
            )

        # 4-BOSQICH: BIZNES VA EXCEL INTEGRATSIYASI (INN VA QARZ)
        debt_text: Optional[str] = None
        total_debt: float = 0.0
        org_name: str = ""

        if facts.detected_inn:
            from handlers.debt import format_debt_response
            results = excel_manager.search(facts.detected_inn)
            if results:
                org_name = results[0].get("name", "")
                total_debt = sum(item.get("debt", 0.0) for item in results)
                debt_text = format_debt_response(results)

                # Foydalanuvchi xotirasiga korxona va qarzni yozish
                user_memory.set_last_id(chat_id, user_id, facts.detected_inn, org_name=org_name, debt=total_debt)
                user_memory.set_last_topic(chat_id, user_id, "screen_diagnostics_with_inn")

        # 5-BOSQICH: YAKUNIY SINTEZ (DECISION SYNTHESIS)
        # Agar ham ekran tashxisi, ham qarz ma'lumoti bo'lsa -> ularni birlashtiramiz
        final_reply: str = ""
        final_video_id: Optional[int] = diag_video_id

        if diag_text and debt_text:
            final_reply = f"{diag_text}\n\n──────────────\n{debt_text}"
            # Agar qarz bo'lsa, qarz to'lash videosi ustuvor bo'lishi mumkin
            if total_debt > 0:
                final_video_id = 148
        elif debt_text:
            final_reply = debt_text
            if total_debt > 0:
                final_video_id = 148
        elif diag_text:
            final_reply = diag_text
        else:
            final_reply = "✅ <b>Apparat ekrani normal holatda.</b>"

        return DecisionResult(
            action=ActionType.DIAGNOSE_AND_REPLY,
            reply_text=final_reply,
            video_id=final_video_id,
            detected_inn=facts.detected_inn,
            debt_amount=total_debt,
            org_name=org_name,
            log_reason="Successfully diagnosed POS screen facts"
        )

    def _resolve_inn_only(self, inn: str, chat_id: int, user_id: int) -> DecisionResult:
        """Faqat INN aniqlanganda zaxira yechimi"""
        from handlers.debt import format_debt_response
        results = excel_manager.search(inn)
        if not results:
            return DecisionResult(
                action=ActionType.FALLBACK_SAFE,
                reply_text=f"❌ <code>{inn}</code> bo'yicha ma'lumot topilmadi.",
                detected_inn=inn
            )

        org_name = results[0].get("name", "")
        total_debt = sum(item.get("debt", 0.0) for item in results)
        user_memory.set_last_id(chat_id, user_id, inn, org_name=org_name, debt=total_debt)

        debt_text = format_debt_response(results)
        video_id = 148 if total_debt > 0 else None

        return DecisionResult(
            action=ActionType.DIAGNOSE_AND_REPLY,
            reply_text=debt_text,
            video_id=video_id,
            detected_inn=inn,
            debt_amount=total_debt,
            org_name=org_name,
            log_reason="Resolved INN from fallback flow"
        )

core_engine = CoreEngine()
