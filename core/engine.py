import logging
import re
from typing import Optional, Dict, Any, List

from core.models import DeviceFacts, ReceiptFacts, DecisionResult, ActionType
from error_manager import error_manager
from excel_manager import excel_manager
from user_memory import user_memory
from admin_manager import admin_manager

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

RECEIPT_FALLBACK_REPLY = (
    "⚠️ <b>Kvitansiyani to'liq tahlil qilib bo'lmadi.</b>\n"
    "Iltimos, to'lov chekini aniqroq rasmga olib yoki PDF formatda qayta yuboring "
    "yoki korxonangizning <b>INN</b> raqamini yozing."
)

class CoreEngine:
    """
    Markaziy Algoritmik Yadro (Decision Engine).
    Barcha sensorlar (POS ekrani, to'lov kvitansiyalari, matn tahlili) faktlarini qabul qilib,
    qat'iy zanjir (pipeline) bo'yicha yakuniy qaror chiqaradi va zarur bo'lsa adminga eskalatsiya qiladi.
    """

    # =========================================================================
    # 1. POS APPARATI EKRAN FAKTLARINI TAHLIL QILISH
    # =========================================================================
    def process_device_facts(self, facts: DeviceFacts, chat_id: int, user_id: int, user_comment: str = "") -> DecisionResult:
        """
        Kassa apparati faktlarini tahlil qilish va qaror chiqarish.
        Agar internet ishlab turgan, lekin qarzdorlik bo'lmagan holda xatolik bo'lsa -> Adminga eskalatsiya!
        """
        # 0-BOSQICH: ZANJIR UZILIB QOLISHIDAN HIMOYA (RESILIENCE / FAIL-SAFE)
        if facts.extraction_error:
            logger.warning(f"Sensor uzilishi: {facts.extraction_error}. Zaxira himoya ishga tushdi.")
            if facts.detected_inn:
                return self._resolve_inn_only(facts.detected_inn, chat_id, user_id)
            return DecisionResult(
                action=ActionType.FALLBACK_SAFE,
                reply_text=SAFE_FALLBACK_REPLY,
                log_reason=f"Extraction failure: {facts.extraction_error}"
            )

        # 1-BOSQICH: GUARDRAIL (BEGONA RASMLARNI CHIQARIB TASHLASH)
        if not facts.is_real_pos_device and not facts.detected_inn:
            logger.info("Guardrail: Tasvir kassa apparati emas. E'tiborsiz qoldiriladi.")
            return DecisionResult(
                action=ActionType.IGNORE,
                log_reason="Not a real POS device image"
            )

        # 2-BOSQICH: PRE-CONDITION (STATUS BAR / SOAT VA TARMOQ QATORI)
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
        has_error: bool = False

        matched_rule = error_manager.match_error(facts.raw_facts)
        if matched_rule:
            has_error = True
            diag_text = matched_rule.get("response_text", "")
            diag_video_id = matched_rule.get("video_id")
        elif facts.screen_text_summary and facts.screen_text_summary.lower() not in ["none", "normal", ""]:
            has_error = True
            diag_text = (
                f"ℹ️ <b>Ekrandagi holat:</b> {facts.screen_text_summary}\n"
                f"Nosozlik davom etsa, korxona INN raqamini yuboring."
            )

        if facts.time_mismatch or facts.error_type != "none":
            has_error = True

        # 4-BOSQICH: BIZNES VA EXCEL INTEGRATSIYASI (INN VA QARZ)
        debt_text: Optional[str] = None
        total_debt: float = 0.0
        org_name: str = ""

        # INN qidirish: Ekranda yoki xotirada
        target_inn = facts.detected_inn or user_memory.get_last_id(chat_id, user_id)

        if target_inn:
            from handlers.debt import format_debt_response
            results = excel_manager.search(target_inn)
            if results:
                org_name = results[0].get("name", "")
                total_debt = sum(item.get("debt", 0.0) for item in results)
                debt_text = format_debt_response(results)

                # Xotiraga korxona va qarzni yozish
                user_memory.set_last_id(chat_id, user_id, target_inn, org_name=org_name, debt=total_debt)
                user_memory.set_last_topic(chat_id, user_id, "screen_diagnostics_with_inn")

        # 5-BOSQICH: ADMINGA ESKALATSIYA HOLATI (INTERNET BOR + QARZ YO'Q + LEKIN XATOLIK BOR, YOKI JIDDIY APPARAT XATOSI)
        is_fatal_hardware = bool(matched_rule and matched_rule.get("escalate_to_admin"))
        should_escalate = is_fatal_hardware or (facts.has_internet and total_debt <= 0 and has_error and not facts.time_mismatch)

        if should_escalate:
            issue_desc = diag_text or facts.screen_text_summary or "Noma'lum apparat nosozligi"
            contacts_info = admin_manager.get_contacts_display()
            status_prefix = "✅ <b>Apparatingizda abonent to'lovidan qarzdorlik yo'q va internet tarmog'i faol.</b>\n\n" if not is_fatal_hardware else ""
            escalation_reply = (
                f"{status_prefix}"
                f"{diag_text}\n\n"
                f"👨‍💻 <b>Ushbu masala bo'yicha ma'lumotlar bosh administratorimizga (@Yashnarbek_butaev) hamda ustalariga yetkazildi.</b> "
                f"Mutaxassislarimiz tez orada siz bilan bog'lanishadi.\n\n"
                f"{contacts_info}"
            )

            return DecisionResult(
                action=ActionType.ESCALATE_TO_ADMIN,
                reply_text=escalation_reply,
                video_id=diag_video_id,
                detected_inn=target_inn,
                debt_amount=total_debt,
                org_name=org_name,
                should_notify_admin=True,
                admin_alert_type="tech_issue",
                admin_alert_text=issue_desc,
                log_reason="Hardware fatal error or Internet active & no debt -> Escalated to admin"
            )

        # 6-BOSQICH: ODDIY TASHXIS VA JAVOB SINTEZI
        final_reply: str = ""
        final_video_id: Optional[int] = diag_video_id

        if diag_text and debt_text:
            final_reply = f"{diag_text}\n\n──────────────\n{debt_text}"
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
            detected_inn=target_inn,
            debt_amount=total_debt,
            org_name=org_name,
            log_reason="Successfully diagnosed POS screen facts"
        )

    # =========================================================================
    # 2. TO'LOV KVITANSIYASI (CHEK / PDF) FAKTLARINI TAHLIL QILISH
    # =========================================================================
    def process_receipt_facts(
        self,
        facts: ReceiptFacts,
        chat_id: int,
        user_id: int,
        user_comment: str = ""
    ) -> DecisionResult:
        """
        Kvitansiya faktlarini tahlil qilish:
        1. Kvitansiya Mars Elektron Texnikaga to'langanmi?
        2. To'lovchi INN aniqlanadimi (kvitansiyadan, izohdan yoki xotiradan)?
        3. Excel bazadagi qarz bilan solishtirish:
           - Qarzni to'liq yopdimi?
           - Qisman yopdimi?
           - Avans to'lovmi?
        4. Adminga to'liq hisobot uzatish!
        """
        # 0. Fail-Safe
        if facts.extraction_error:
            logger.warning(f"Kvitansiya tahlilida xatolik: {facts.extraction_error}")
            return DecisionResult(
                action=ActionType.FALLBACK_SAFE,
                reply_text=RECEIPT_FALLBACK_REPLY,
                log_reason=f"Receipt extraction failed: {facts.extraction_error}"
            )

        # 1. Guardrail: Haqiqatan kvitansiyami?
        if not facts.is_receipt:
            logger.info("Guardrail: Hujjat/tasvir to'lov kvitansiyasi emas.")
            return DecisionResult(
                action=ActionType.IGNORE,
                log_reason="Not a payment receipt"
            )

        # 2. To'lov qabul qiluvchi tekshiruvi
        if not facts.is_mars_recipient and facts.recipient_account:
            warning_text = (
                f"⚠️ <b>Diqqat: Ushbu to'lov «Mars Elektron Texnika»ga tegishli emasdek ko'rinmoqda.</b>\n\n"
                f"📌 <b>Kvitansiyadagi qabul qiluvchi:</b> {facts.recipient_account}\n"
                f"💵 <b>Summa:</b> {facts.amount:,.0f} so'm\n\n"
                f"«Mars Elektron Texnika» hisob raqami: <code>20208000800208044003</code>\n"
                f"Iltimos, to'lov ma'lumotlarini tekshiring yoki adminga murojaat qiling."
            )
            return DecisionResult(
                action=ActionType.RECEIPT_PROCESSED,
                reply_text=warning_text,
                paid_amount=facts.amount,
                receipt_facts=facts,
                log_reason="Receipt recipient is not Mars Elektron Texnika"
            )

        # 3. To'lovchi korxona INN/JSHSHIR raqamini aniqlash
        inn = facts.payer_inn
        if not inn and user_comment:
            inn_found = re.findall(r"\b(\d{14}|\d{9})\b", user_comment)
            if inn_found:
                inn = inn_found[0]

        if not inn:
            inn = user_memory.get_last_id(chat_id, user_id)

        # Agar INN umuman aniqlanmasa -> Kvitansiyani xotirada saqlab, foydalanuvchidan INN so'rash
        if not inn:
            receipt_dict = {
                "recipient_account": facts.recipient_account,
                "is_mars_recipient": facts.is_mars_recipient,
                "amount": facts.amount,
                "payer_name": facts.payer_name,
                "payment_date": facts.payment_date,
                "transaction_id": facts.transaction_id,
                "payment_system": facts.payment_system,
                "raw_facts": facts.raw_facts
            }
            user_memory.set_pending_receipt(chat_id, user_id, receipt_dict)
            ask_inn_reply = (
                f"🧾 <b>To'lov kvitansiyasi qabul qilindi!</b>\n\n"
                f"💰 <b>O'tkazilgan summa:</b> <b>{facts.amount:,.0f} so'm</b>\n"
                f"🏦 <b>Qabul qiluvchi:</b> {facts.recipient_account or '«Mars Elektron Texnika»'}\n"
                f"🆔 <b>Chek / Tranzaksiya:</b> <code>{facts.transaction_id or '-'}</code>\n\n"
                f"❓ <b>Iltimos, ushbu to'lov aynan qaysi korxona hisobiga kiritilishini bilishimiz uchun, "
                f"korxonangizning INN (9 xonali) yoki JSHSHIR (14 xonali) raqamini yozib yuboring.</b>"
            )
            return DecisionResult(
                action=ActionType.RECEIPT_PROCESSED,
                reply_text=ask_inn_reply,
                paid_amount=facts.amount,
                receipt_facts=facts,
                log_reason="Receipt accepted, waiting for user INN"
            )

        # 4. INN aniq bo'lsa -> Excel bazadan tekshirish va qarzni solishtirish
        return self._evaluate_receipt_with_inn(inn, facts, chat_id, user_id)

    def _evaluate_receipt_with_inn(
        self,
        inn: str,
        facts: ReceiptFacts,
        chat_id: int,
        user_id: int
    ) -> DecisionResult:
        """Kvitansiya summasini Exceldagi qarz bilan solishtirish va adminga hisobot tayyorlash"""
        results = excel_manager.search(inn)
        org_name = ""
        prev_debt = 0.0

        if results:
            org_name = results[0].get("name", "")
            prev_debt = sum(item.get("debt", 0.0) for item in results)
        else:
            org_name = facts.payer_name or "Yangi / Noma'lum korxona"

        paid_amount = facts.amount
        remaining_debt = 0.0
        debt_covered = False

        if prev_debt > 0:
            if paid_amount >= prev_debt:
                debt_covered = True
                remaining_debt = 0.0
                user_reply = (
                    f"✅ <b>To'lov muvaffaqiyatli qabul qilindi!</b>\n\n"
                    f"🏢 <b>Korxona:</b> <b>{org_name}</b>\n"
                    f"🔢 <b>INN:</b> <code>{inn}</code>\n"
                    f"💵 <b>To'langan summa:</b> <b>{paid_amount:,.0f} so'm</b>\n"
                    f"📉 <b>Avvalgi qarz:</b> {prev_debt:,.0f} so'm\n"
                    f"🎉 <b>Qarzdorlik to'liq bartaraf etildi!</b>\n\n"
                    f"📩 <i>To'lov ma'lumotlari kassa apparatingizni tizimda faollashtirish uchun "
                    f"mas'ul operator va adminga yuborildi. Tez orada tizim yangilanadi.</i>"
                )
            else:
                debt_covered = False
                remaining_debt = prev_debt - paid_amount
                user_reply = (
                    f"⚠️ <b>To'lov qabul qilindi, ammo qarz to'liq yopilmadi.</b>\n\n"
                    f"🏢 <b>Korxona:</b> <b>{org_name}</b>\n"
                    f"🔢 <b>INN:</b> <code>{inn}</code>\n"
                    f"💵 <b>To'langan summa:</b> <b>{paid_amount:,.0f} so'm</b>\n"
                    f"📉 <b>Avvalgi qarz:</b> {prev_debt:,.0f} so'm\n"
                    f"🔴 <b>Qolgan qarzdorlik:</b> <b>{remaining_debt:,.0f} so'm</b>\n\n"
                    f"📩 <i>Kvitansiya adminga yuborildi. Apparat to'siqsiz ishlashi uchun "
                    f"qolgan summani ham to'lashingiz lozim.</i>"
                )
        else:
            debt_covered = True
            remaining_debt = prev_debt - paid_amount
            user_reply = (
                f"✅ <b>To'lov muvaffaqiyatli qabul qilindi!</b>\n\n"
                f"🏢 <b>Korxona:</b> <b>{org_name}</b>\n"
                f"🔢 <b>INN:</b> <code>{inn}</code>\n"
                f"💵 <b>To'langan summa:</b> <b>{paid_amount:,.0f} so'm</b>\n"
                f"🟢 <b>Qarzdorlik mavjud emas edi (Oldindan to'lov).</b>\n\n"
                f"📩 <i>Ushbu mablag' kelgusi oylar abonent to'lovi hisobiga kiritiladi. "
                f"Kvitansiya adminga yetkazildi.</i>"
            )

        # Xotiraga saqlash va pending receiptni tozalash
        user_memory.clear_pending_receipt(chat_id, user_id)
        user_memory.set_last_id(chat_id, user_id, inn, org_name=org_name, debt=remaining_debt)
        user_memory.set_last_topic(chat_id, user_id, "receipt_verified")

        debt_status_info = {
            "org_name": org_name,
            "inn": inn,
            "prev_debt": prev_debt,
            "remaining_debt": remaining_debt,
            "debt_covered": debt_covered
        }

        return DecisionResult(
            action=ActionType.RECEIPT_PROCESSED,
            reply_text=user_reply,
            detected_inn=inn,
            debt_amount=prev_debt,
            paid_amount=paid_amount,
            remaining_debt=remaining_debt,
            org_name=org_name,
            should_notify_admin=True,
            admin_alert_type="receipt",
            receipt_facts=facts,
            debt_status_info=debt_status_info,
            log_reason="Receipt successfully verified against Excel debt and prepared for admin"
        )

    def resolve_pending_receipt_if_any(self, inn: str, chat_id: int, user_id: int) -> Optional[DecisionResult]:
        """Foydalanuvchi avval kvitansiya tashlab, endi INN yozganda uni avtomatik ulash"""
        pending_data = user_memory.get_pending_receipt(chat_id, user_id)
        if not pending_data:
            return None

        # Pending receipt faktlarini tiklash
        facts = ReceiptFacts(
            is_receipt=True,
            recipient_account=pending_data.get("recipient_account", "«Mars Elektron Texnika»"),
            is_mars_recipient=pending_data.get("is_mars_recipient", True),
            amount=float(pending_data.get("amount", 0.0)),
            payer_inn=inn,
            payer_name=pending_data.get("payer_name", ""),
            payment_date=pending_data.get("payment_date", ""),
            transaction_id=pending_data.get("transaction_id", ""),
            payment_system=pending_data.get("payment_system", ""),
            raw_facts=pending_data
        )

        return self._evaluate_receipt_with_inn(inn, facts, chat_id, user_id)

    # =========================================================================
    # 3. ADMINGA UMUMIY ESKALATSIYA (OPERATOR / USTA TALAB QILINGANDA)
    # =========================================================================
    def escalate_general_issue(self, user_text: str, chat_id: int, user_id: int) -> DecisionResult:
        """Mijoz operator, usta yoki shaxsiy yordam so'raganda adminga uzatish"""
        inn = user_memory.get_last_id(chat_id, user_id) or "-"
        debt_info = user_memory.get_debt_info(chat_id, user_id) or {}
        org_name = debt_info.get("org_name", "-")

        contacts_info = admin_manager.get_contacts_display()
        reply_text = (
            f"👨‍💻 <b>Murojaatingiz qabul qilindi va mutaxassisimizga (adminga) yetkazildi!</b>\n\n"
            f"Operatorlarimiz tez orada siz bilan bog'lanishadi.\n\n"
            f"{contacts_info}"
        )

        return DecisionResult(
            action=ActionType.ESCALATE_TO_ADMIN,
            reply_text=reply_text,
            detected_inn=inn if inn != "-" else None,
            org_name=org_name if org_name != "-" else None,
            should_notify_admin=True,
            admin_alert_type="escalation",
            admin_alert_text=user_text,
            log_reason="User requested human support/operator"
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
