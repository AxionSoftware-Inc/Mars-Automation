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

        # Maxsus xavfsizlik filtri: Agar tasvir to'lov kvitansiyasiga oid bo'lsa,
        # status bar (soat) so'ramasdan to'g'ridan-to'g'ri kvitansiya protsessoriga yo'naltirish
        summary_lower = (facts.screen_text_summary or "").lower()
        caption_lower = (user_comment or "").lower()
        receipt_signals = [
            "to'lov", "tolov", "chek", "kvitansiya", "click", "payme", "oplata",
            "muvaffaqiyatli", "o'tkazildi", "otkazildi", "pul o'tkazma", "munis", "uzum"
        ]
        if any(sig in summary_lower for sig in receipt_signals) or any(sig in caption_lower for sig in receipt_signals):
            logger.info("Ekrandagi yozuv to'lov kvitansiyasiga tegishli ekanligi aniqlandi -> Kvitansiya rejimiga yo'naltiriladi.")
            
            detected_amount = 0.0
            sum_matches = re.findall(r"(\d[\d\s]{2,}\d)\s*(?:so['`]?m|sum)", summary_lower)
            if sum_matches:
                try:
                    detected_amount = float(sum_matches[0].replace(" ", ""))
                except Exception:
                    detected_amount = 0.0

            receipt_facts = ReceiptFacts(
                is_receipt=True,
                recipient_account="«Mars Elektron Texnika» MCHJ",
                is_mars_recipient=True,
                amount=detected_amount,
                payer_inn=facts.detected_inn,
                raw_text=facts.screen_text_summary,
                raw_facts=facts.raw_facts
            )
            return self.process_receipt_facts(
                facts=receipt_facts,
                chat_id=chat_id,
                user_id=user_id,
                user_comment=user_comment
            )

        # 2-BOSQICH: EKRAN TASHXISI (P3 va barcha modellarda avval ekrandagi yozuv va xatolikni tekshirish)
        diag_text: Optional[str] = None
        diag_video_id: Optional[int] = None
        has_error: bool = False

        matched_rule = error_manager.match_error(facts.raw_facts)
        if matched_rule:
            has_error = True
            diag_text = matched_rule.get("response_text", "")
            diag_video_id = matched_rule.get("video_id")
        elif facts.screen_text_summary and facts.screen_text_summary.lower() not in ["none", "normal", "", "asosiy oyna", "bosh oyna"]:
            has_error = True
            diag_text = (
                f"ℹ️ <b>Ekrandagi holat:</b> {facts.screen_text_summary}\n"
                f"Nosozlik davom etsa, korxona INN raqamini yuboring."
            )

        if facts.time_mismatch or facts.error_type != "none":
            has_error = True

        # 3-BOSQICH: BIZNES VA EXCEL INTEGRATSIYASI (INN VA QARZ)
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

        # 4-BOSQICH: PRE-CONDITION (STATUS BAR / SOAT VA TARMOQ QATORI)
        # P3 kabi modellarda tepada soat qatori bo'lmaydi.
        # Avval ekrandagi yozuvni o'qib yechishga harakat qilinadi.
        # Faqatgina ekranda va qarzda hech qanday muammo aniqlanmasa va status bar ko'rinmasa -> to'liq ekran so'raladi!
        if not has_error and total_debt <= 0 and not facts.is_status_bar_visible:
            logger.info("Pre-condition: Ekrandan muammo aniqlanmadi va status bar ko'rinmayapti. To'liq ekran talab qilinadi.")
            return DecisionResult(
                action=ActionType.ASK_FULL_SCREEN,
                reply_text=INCOMPLETE_SCREEN_REPLY,
                detected_inn=facts.detected_inn,
                log_reason="No error diagnosed from screen and status bar invisible"
            )

        # 5-BOSQICH: ADMINGA ESKALATSIYA HOLATI (INTERNET BOR + QARZ YO'Q + LEKIN XATOLIK BOR, YOKI JIDDIY APPARAT XATOSI)
        is_fatal_hardware = bool(matched_rule and matched_rule.get("escalate_to_admin"))
        debt_verified_clear = bool(target_inn and total_debt <= 0)
        should_escalate = is_fatal_hardware or (facts.has_internet and debt_verified_clear and has_error and not facts.time_mismatch)

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
                log_reason="Hardware fatal error or Internet active & verified no debt -> Escalated to admin"
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
            if not target_inn and has_error and not is_fatal_hardware:
                final_reply = f"{diag_text}\n\n💡 <b>Qarzdorlik holatini tekshirishimiz uchun korxonangizning INN raqamini yuboring.</b>"
            else:
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
        user_comment: str = "",
        file_id: Optional[str] = None,
        is_photo: bool = True
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

        # 1.1. Firibgarlik va takrorlanishdan himoya & to'lov maqsadi (Fraud & Duplicates)
        from transaction_tracker import transaction_tracker

        purpose, purpose_label = transaction_tracker.detect_payment_purpose(facts.raw_text or user_comment)
        facts.payment_purpose = purpose
        facts.purpose_label = purpose_label

        is_dup = transaction_tracker.is_duplicate(facts.transaction_id)
        facts.is_duplicate = is_dup

        is_old, old_warn = transaction_tracker.check_old_receipt(facts.payment_date)
        facts.is_old_receipt = is_old
        facts.old_receipt_warning = old_warn

        # 2. To'lov qabul qiluvchi va to'lov toifasi tekshiruvi (Oylik vs Yillik)
        from payment_accounts import (
            MARS_ACCOUNT, MARS_ORG_NAME,
            YANGI_TEXNOLOGIYALAR_ACCOUNT, YANGI_TEXNOLOGIYALAR_ORG_NAME,
            classify_receipt_target
        )

        category = getattr(facts, "payment_category", None)
        if not category or category == "monthly":
            category = classify_receipt_target(
                facts.recipient_account, facts.amount, facts.raw_text
            )

        # A) YILLIK FISKAL MODUL TO'LOVI («Yangi Texnologiyalar» DUK)
        if category == "annual" or facts.is_annual_fiscal_fee:
            logger.info("Kvitansiya tahlili: Yillik fiskal modul to'lovi («Yangi Texnologiyalar» DUK) aniqlandi.")
            annual_reply = (
                f"🧾 <b>Fiskal modulning yillik to'lov kvitansiyasi qabul qilindi!</b>\n\n"
                f"🏢 <b>Qabul qiluvchi:</b> {YANGI_TEXNOLOGIYALAR_ORG_NAME} (Davlat Soliq Qo'mitasi)\n"
                f"🏦 <b>Hisob raqam:</b> <code>{YANGI_TEXNOLOGIYALAR_ACCOUNT}</code>\n"
                f"💰 <b>To'langan summa:</b> <b>{facts.amount:,.0f} so'm</b>\n"
                f"🆔 <b>Chek / Tranzaksiya:</b> <code>{facts.transaction_id or '-'}</code>\n\n"
                f"ℹ️ <b>MUHIM MA'LUMOT:</b>\n"
                f"Ushbu to'lov kassa apparatingizdagi Fiskal modulning 1 yillik ishlash muddatini uzaytirish uchun Davlat Soliq Qo'mitasiga («Yangi Texnologiyalar» DUK) to'landi.\n"
                f"⏳ Soliq tizimi to'lovni <b>2 soatdan 24 soatgacha</b> bo'lgan muddatda avtomatik tasdiqlaydi va fiskal modul muddati uzaytiriladi.\n\n"
                f"⚠️ <b>Eslatma:</b> «Mars Elektron Texnika» apparatiga har oylik servis xizmati (oylik abonent to'lovi: 100 000 so'm) alohida to'lanadi va ularni adashtirmaslik lozim."
            )
            return DecisionResult(
                action=ActionType.RECEIPT_PROCESSED,
                reply_text=annual_reply,
                paid_amount=facts.amount,
                receipt_facts=facts,
                file_id=file_id,
                is_photo=is_photo,
                should_notify_admin=True,
                admin_alert_type="annual_receipt",
                payment_purpose="annual_fiscal_fee",
                purpose_label="Yillik fiskal modul to'lovi",
                is_old_receipt=facts.is_old_receipt,
                is_duplicate=facts.is_duplicate,
                tuman="",
                debt_status_info={
                    "is_annual": True,
                    "org_name": facts.payer_name or "Yillik to'lov",
                    "inn": facts.payer_inn or "",
                    "paid_amount": facts.amount,
                    "recipient": YANGI_TEXNOLOGIYALAR_ORG_NAME,
                    "is_duplicate": facts.is_duplicate,
                    "is_old_receipt": facts.is_old_receipt,
                    "payment_purpose": "annual_fiscal_fee"
                },
                log_reason="Annual fiscal fee receipt processed"
            )

        # B) BEGONA TASHKILOT TO'LOVI
        if not facts.is_mars_recipient and category == "other" and facts.recipient_account:
            warning_text = (
                f"⚠️ <b>Diqqat: Ushbu to'lov «Mars Elektron Texnika»ga ham, «Yangi Texnologiyalar» DUK ga ham tegishli emasdek ko'rinmoqda.</b>\n\n"
                f"📌 <b>Kvitansiyadagi qabul qiluvchi:</b> {facts.recipient_account}\n"
                f"💵 <b>Summa:</b> {facts.amount:,.0f} so'm\n\n"
                f"🏢 <b>«Mars Elektron Texnika» (Oylik to'lov):</b> <code>{MARS_ACCOUNT}</code>\n"
                f"🏛 <b>«Yangi Texnologiyalar» DUK (Yillik to'lov):</b> <code>{YANGI_TEXNOLOGIYALAR_ACCOUNT}</code>\n\n"
                f"Iltimos, to'lov rekvizitlarini tekshiring yoki adminga murojaat qiling."
            )
            return DecisionResult(
                action=ActionType.RECEIPT_PROCESSED,
                reply_text=warning_text,
                paid_amount=facts.amount,
                receipt_facts=facts,
                file_id=file_id,
                is_photo=is_photo,
                log_reason="Receipt recipient is neither Mars nor Yangi Texnologiyalar"
            )

        # 3. To'lovchi korxona INN/JSHSHIR raqamini aniqlash
        from core.models import extract_clean_inn
        inn = extract_clean_inn(facts.payer_inn) if facts.payer_inn else None
        if not inn and user_comment:
            inn = extract_clean_inn(user_comment)

        if not inn:
            raw_last_id = user_memory.get_last_id(chat_id, user_id)
            if raw_last_id:
                inn = extract_clean_inn(raw_last_id)

        # Agar INN umuman aniqlanmasa (chekda yo'q yoki '000' bo'sh qoldirilgan) ->
        # Kvitansiyani xotirada saqlab, foydalanuvchidan INN so'rash VA
        # adminga darhol "Kvitansiyada INN topilmadi" deb xabarnoma uzatish!
        if not inn:
            receipt_dict = {
                "recipient_account": facts.recipient_account,
                "is_mars_recipient": facts.is_mars_recipient,
                "amount": facts.amount,
                "payer_name": facts.payer_name,
                "payment_date": facts.payment_date,
                "transaction_id": facts.transaction_id,
                "payment_system": facts.payment_system,
                "payment_purpose": facts.payment_purpose,
                "purpose_label": facts.purpose_label,
                "is_duplicate": facts.is_duplicate,
                "is_old_receipt": facts.is_old_receipt,
                "old_receipt_warning": facts.old_receipt_warning,
                "raw_text": facts.raw_text,
                "raw_facts": facts.raw_facts,
                "file_id": file_id,
                "is_photo": is_photo
            }
            user_memory.set_pending_receipt(chat_id, user_id, receipt_dict)

            warning_notes = []
            if facts.is_duplicate:
                warning_notes.append(
                    f"⚠️ <b>DIQQAT: Ushbu to'lov cheki (Tranzaksiya ID: <code>{facts.transaction_id or '-'}</code>) "
                    f"avval ham tizimga yuborilgan! Takroriy yuborilgan kvitansiya adminga tekshiruv uchun uzatildi.</b>"
                )
            if facts.is_old_receipt and facts.old_receipt_warning:
                warning_notes.append(
                    f"⚠️ <b>DIQQAT: {facts.old_receipt_warning}</b>"
                )
            warn_extra = ("\n\n" + "\n\n".join(warning_notes)) if warning_notes else ""

            ask_inn_reply = (
                f"🧾 <b>To'lov kvitansiyasi qabul qilindi!</b>\n\n"
                f"💰 <b>O'tkazilgan summa:</b> <b>{facts.amount:,.0f} so'm</b>\n"
                f"🏦 <b>Qabul qiluvchi:</b> {facts.recipient_account or '«Mars Elektron Texnika»'}\n"
                f"🆔 <b>Chek / Tranzaksiya:</b> <code>{facts.transaction_id or '-'}</code>\n\n"
                f"❓ <b>Iltimos, ushbu to'lov aynan qaysi korxona hisobiga kiritilishini bilishimiz uchun, "
                f"korxonangizning INN (9 xonali) yoki JSHSHIR (14 xonali) raqamini yozib yuboring.</b>"
                f"{warn_extra}"
            )
            return DecisionResult(
                action=ActionType.RECEIPT_PROCESSED,
                reply_text=ask_inn_reply,
                paid_amount=facts.amount,
                receipt_facts=facts,
                file_id=file_id,
                is_photo=is_photo,
                should_notify_admin=True,
                admin_alert_type="receipt_missing_inn",
                payment_purpose=facts.payment_purpose,
                purpose_label=facts.purpose_label,
                is_old_receipt=facts.is_old_receipt,
                is_duplicate=facts.is_duplicate,
                tuman="",
                debt_status_info={
                    "org_name": facts.payer_name or "Noma'lum korxona",
                    "inn": None,
                    "inn_missing": True,
                    "paid_amount": facts.amount,
                    "prev_debt": 0.0,
                    "remaining_debt": 0.0,
                    "debt_covered": False,
                    "tuman": "",
                    "is_duplicate": facts.is_duplicate,
                    "is_old_receipt": facts.is_old_receipt,
                    "old_receipt_warning": facts.old_receipt_warning,
                    "payment_purpose": facts.payment_purpose,
                    "purpose_label": facts.purpose_label
                },
                log_reason="Receipt accepted, waiting for user INN -> Admin notified with missing INN status"
            )

        # 4. INN aniq bo'lsa -> Excel bazadan tekshirish va qarzni solishtirish
        return self._evaluate_receipt_with_inn(inn, facts, chat_id, user_id, file_id=file_id, is_photo=is_photo)

    def _evaluate_receipt_with_inn(
        self,
        inn: str,
        facts: ReceiptFacts,
        chat_id: int,
        user_id: int,
        file_id: Optional[str] = None,
        is_photo: bool = True
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

        # Tranzaksiyani ro'yxatga olish (agar dublikat bo'lmasa)
        from transaction_tracker import transaction_tracker
        if not facts.is_duplicate and facts.transaction_id:
            transaction_tracker.record_transaction(
                transaction_id=facts.transaction_id,
                inn=inn,
                amount=facts.amount,
                user_id=user_id,
                payment_date=facts.payment_date
            )

        tuman = excel_manager.get_district_for_inn(inn)

        # Ogohlantirish xabarlari (Dublikat yoki Eski kvitansiya)
        warning_notes = []
        if facts.is_duplicate:
            warning_notes.append(
                f"⚠️ <b>DIQQAT: Ushbu to'lov cheki (Tranzaksiya ID: <code>{facts.transaction_id or '-'}</code>) "
                f"avval ham tizimga yuborilgan! Takroriy yuborilgan kvitansiya adminga tekshiruv uchun uzatildi.</b>"
            )
        if facts.is_old_receipt and facts.old_receipt_warning:
            warning_notes.append(
                f"⚠️ <b>DIQQAT: {facts.old_receipt_warning}</b>"
            )
        warning_block = ("\n\n" + "\n\n".join(warning_notes)) if warning_notes else ""

        # To'lov maqsadiga ko'ra xabarni shakllantirish
        if facts.payment_purpose == "repair":
            debt_covered = True
            user_reply = (
                f"🔧 <b>Kassa apparati ta'miri (remont) uchun to'lov qabul qilindi!</b>\n\n"
                f"🏢 <b>Korxona:</b> <b>{org_name}</b>\n"
                f"🔢 <b>INN:</b> <code>{inn}</code>\n"
                f"💵 <b>To'langan summa:</b> <b>{paid_amount:,.0f} so'm</b>\n"
                f"🎯 <b>To'lov turi:</b> {facts.purpose_label}\n"
                f"🆔 <b>Chek / Tranzaksiya:</b> <code>{facts.transaction_id or '-'}</code>\n\n"
                f"👨‍🔧 <i>Ushbu to'lov oylik abonent to'lovi emas, balki apparat ta'miri / ehtiyot qismlari xizmati uchun hisoblanadi. "
                f"Ma'lumotlar servis ustaxonamiz va adminga yetkazildi.</i>"
                f"{warning_block}"
            )
        elif facts.payment_purpose == "hardware_purchase":
            debt_covered = True
            user_reply = (
                f"📦 <b>Yangi kassa apparati xaridi uchun to'lov qabul qilindi!</b>\n\n"
                f"🏢 <b>Korxona:</b> <b>{org_name}</b>\n"
                f"🔢 <b>INN:</b> <code>{inn}</code>\n"
                f"💵 <b>To'langan summa:</b> <b>{paid_amount:,.0f} so'm</b>\n"
                f"🎯 <b>To'lov turi:</b> {facts.purpose_label}\n"
                f"🆔 <b>Chek / Tranzaksiya:</b> <code>{facts.transaction_id or '-'}</code>\n\n"
                f"📋 <i>Yangi apparat xaridi to'lovi bo'yicha ma'lumotlar sotuv va rasmiylashtirish bo'limiga yetkazildi. "
                f"Mutaxassislarimiz apparatni tayyorlash uchun siz bilan bog'lanishadi.</i>"
                f"{warning_block}"
            )
        elif facts.payment_purpose == "registration":
            debt_covered = True
            user_reply = (
                f"📋 <b>Kassani qayta ro'yxatdan o'tkazish (pere-registratsiya) to'lovi qabul qilindi!</b>\n\n"
                f"🏢 <b>Korxona:</b> <b>{org_name}</b>\n"
                f"🔢 <b>INN:</b> <code>{inn}</code>\n"
                f"💵 <b>To'langan summa:</b> <b>{paid_amount:,.0f} so'm</b>\n"
                f"🎯 <b>To'lov turi:</b> {facts.purpose_label}\n"
                f"🆔 <b>Chek / Tranzaksiya:</b> <code>{facts.transaction_id or '-'}</code>\n\n"
                f"📑 <i>Kassa apparatini soliq ro'yxatidan o'tkazish bo'yicha mas'ul xodimga ma'lumotlar yetkazildi.</i>"
                f"{warning_block}"
            )
        elif prev_debt > 0:
            if paid_amount >= prev_debt:
                debt_covered = True
                overpayment = max(0.0, paid_amount - prev_debt)
                remaining_debt = -overpayment if overpayment > 0 else 0.0
                overpay_line = f"🟢 <b>Ortiqcha to'lov (avans):</b> <code>{overpayment:,.0f}</code> so'm kelgusi oylar uchun hisobga o'tdi.\n" if overpayment > 0 else ""
                user_reply = (
                    f"✅ <b>To'lov muvaffaqiyatli qabul qilindi!</b>\n\n"
                    f"🏢 <b>Korxona:</b> <b>{org_name}</b>\n"
                    f"🔢 <b>INN:</b> <code>{inn}</code>\n"
                    f"💵 <b>To'langan summa:</b> <b>{paid_amount:,.0f} so'm</b>\n"
                    f"📉 <b>Avvalgi qarz:</b> {prev_debt:,.0f} so'm\n"
                    f"🎉 <b>Qarzdorlik to'liq bartaraf etildi!</b>\n"
                    f"{overpay_line}\n"
                    f"📩 <i>To'lov ma'lumotlari kassa apparatingizni tizimda faollashtirish uchun "
                    f"mas'ul operator va adminga yuborildi. Tez orada tizim yangilanadi.</i>"
                    f"{warning_block}"
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
                    f"{warning_block}"
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
                f"{warning_block}"
            )

        # Xotiraga saqlash va pending receiptni tozalash
        user_memory.clear_pending_receipt(chat_id, user_id)
        user_memory.set_last_id(chat_id, user_id, inn, org_name=org_name, debt=remaining_debt)
        user_memory.set_last_receipt(chat_id, user_id, {
            "amount": paid_amount,
            "date": facts.payment_date,
            "transaction_id": facts.transaction_id,
            "prev_debt": prev_debt,
            "remaining_debt": remaining_debt,
            "debt_covered": debt_covered,
            "payment_purpose": facts.payment_purpose,
            "purpose_label": facts.purpose_label,
            "tuman": tuman,
            "admin_notified": True
        })
        user_memory.set_last_topic(chat_id, user_id, "receipt_verified")

        debt_status_info = {
            "org_name": org_name,
            "inn": inn,
            "inn_missing": False,
            "prev_debt": prev_debt,
            "remaining_debt": remaining_debt,
            "debt_covered": debt_covered,
            "tuman": tuman,
            "is_duplicate": facts.is_duplicate,
            "is_old_receipt": facts.is_old_receipt,
            "old_receipt_warning": facts.old_receipt_warning,
            "payment_purpose": facts.payment_purpose,
            "purpose_label": facts.purpose_label
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
            file_id=file_id,
            is_photo=is_photo,
            payment_purpose=facts.payment_purpose,
            purpose_label=facts.purpose_label,
            is_old_receipt=facts.is_old_receipt,
            is_duplicate=facts.is_duplicate,
            tuman=tuman,
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
            payment_purpose=pending_data.get("payment_purpose", "monthly_subscription"),
            purpose_label=pending_data.get("purpose_label", "Oylik abonent to'lovi"),
            is_old_receipt=pending_data.get("is_old_receipt", False),
            old_receipt_warning=pending_data.get("old_receipt_warning"),
            is_duplicate=pending_data.get("is_duplicate", False),
            raw_text=pending_data.get("raw_text", ""),
            raw_facts=pending_data
        )

        file_id = pending_data.get("file_id")
        is_photo = pending_data.get("is_photo", True)
        return self._evaluate_receipt_with_inn(inn, facts, chat_id, user_id, file_id=file_id, is_photo=is_photo)


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
