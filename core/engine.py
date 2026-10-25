import logging
import re
from typing import Optional, Dict, Any, List

from core.models import DeviceFacts, ReceiptFacts, DecisionResult, ActionType, extract_clean_inn, extract_fiscal_module
from error_manager import error_manager
from excel_manager import excel_manager
from user_memory import user_memory
from admin_manager import admin_manager
from templates import (
    get_receipt_ack_template,
    get_hardware_step1_inn_template,
    get_hardware_step2_fm_template,
    get_hardware_step3_clear_template,
    get_escalate_admin_template,
)

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
        pos_error_indicators = [
            "qarzdorlik", "blok", "to'xtatil", "o'chiril", "cheklandi", "cheklangan",
            "xatolik", "xato", "smena", "z-hisobot", "z-otchet", "qog'oz", "lenta",
            "soliq to'lovchi", "soliq organ", "soliq qo'mita", "abonent to'lov",
            "muddati tugagan", "sertifikat", "chek urish", "jo'natilmagan chek",
            "остановки", "пополните", "заблокирован", "ошибка", "смена", "приостановлен"
        ]
        receipt_signals = [
            "to'lov amalga", "tolov amalga", "to'lov muvaffaqiyatli", "muvaffaqiyatli",
            "kvitansiya", "click", "payme", "oplata", "o'tkazildi", "otkazildi",
            "pul o'tkazma", "munis", "uzum", "anorbank", "платежное поручение"
        ]
        is_pos_error_text = any(ind in summary_lower for ind in pos_error_indicators)
        if not is_pos_error_text and any(sig in summary_lower for sig in receipt_signals):
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

        # 2-BOSQICH: BIZNES KETMA-KETLIGI (INN -> FISKAL MODUL -> INTERNET/SOAT -> USTA)
        # QAT'IY QOIDA: Smart One apparatlari ekranidagi xatolikka qarab AI o'zidan taxminiy xulosa chiqarmasin!
        # Faqat P3 Humo apparatida ekranda aniq yozuv bo'ladi.
        from core.models import extract_clean_inn, extract_fiscal_module
        from handlers.debt import format_debt_response

        target_inn = (
            facts.detected_inn
            or (extract_clean_inn(user_comment) if user_comment else None)
            or user_memory.get_last_id(chat_id, user_id)
        )

        target_fm = (
            extract_fiscal_module(user_comment)
            or user_memory.get_last_fm(chat_id, user_id)
        )

        # Agar INN topilmagan bo'lsa, ekran yozuvidan (kassa/terminal raqami yoki INN) qidirish
        if not target_inn and facts.screen_text_summary:
            inn_in_text = extract_clean_inn(facts.screen_text_summary)
            if inn_in_text:
                target_inn = inn_in_text
            else:
                # Ekranda kassa/terminal raqamlari bo'lsa (masalan: UZ84577361 yoki 8-10 xonali sonlar)
                digits_matches = re.findall(r'\b\d{7,10}\b', facts.screen_text_summary)
                for dig in digits_matches:
                    search_res = excel_manager.search(dig)
                    if search_res and search_res[0].get("stir"):
                        target_inn = search_res[0].get("stir")
                        logger.info(f"Ekran matnidagi raqam ({dig}) orqali INN ({target_inn}) topildi!")
                        break

        # Agar target_fm topilmagan bo'lsa, ekran yozuvidan qidirish
        if not target_fm and facts.screen_text_summary:
            fm_in_text = extract_fiscal_module(facts.screen_text_summary)
            if fm_in_text:
                target_fm = fm_in_text

        match_payload = dict(facts.raw_facts or {})
        if facts.screen_text_summary:
            match_payload["screen_text_summary"] = facts.screen_text_summary
        if facts.error_type:
            match_payload["error_type"] = facts.error_type

        raw_facts = facts.raw_facts or {}
        is_p3_explicit = raw_facts.get("is_p3_device")
        if is_p3_explicit is not None:
            is_p3_device = bool(is_p3_explicit)
        else:
            is_p3_device = False
            if target_inn:
                res = excel_manager.search(target_inn)
                if res and any(bool(item.get("is_p3", False)) for item in res):
                    is_p3_device = True
            elif not facts.is_status_bar_visible and error_manager.match_error(match_payload):
                is_p3_device = True

        # Maxsus holat: Jiddiy apparat nosozligi (Tamper detected / jismoniy buzilish)
        # Bunday holatda apparat bloklanadi va faqat servis markazida usta tomonidan tuzatiladi
        matched_fatal = error_manager.match_error(match_payload)
        if facts.error_type == "hardware_tamper" or (matched_fatal and matched_fatal.get("id") == "fatal_hardware_damage"):
            rule_text = (matched_fatal.get("response_text") if matched_fatal else "") or "🚨 <b>TAMPER DETECTED — Apparat xavfsizlik datchigi qulflangan!</b>"
            escalation_reply = (
                f"{rule_text}\n\n"
                f"👨‍💻 <b>Ushbu masala bo'yicha ma'lumotlar bosh administratorimizga (@Yashnarbek_butaev) hamda ustalariga yetkazildi.</b> "
                f"Mutaxassislarimiz tez orada siz bilan bog'lanishadi.\n\n"
                f"{admin_manager.get_contacts_display()}"
            )
            return DecisionResult(
                action=ActionType.ESCALATE_TO_ADMIN,
                reply_text=escalation_reply,
                video_id=None,
                detected_inn=target_inn,
                should_notify_admin=True,
                admin_alert_type="tech_issue",
                admin_alert_text=f"Apparat jiddiy xatosi (Tamper): {facts.screen_text_summary or 'hardware_tamper'}",
                log_reason="Fatal hardware damage / Tamper detected requires direct admin escalation"
            )

        # A) P3 HUMO APPARATI (Sariq qator):
        # P3 apparat ekranida aniq gap chiqadi ("p3 bo'lsa mayli uni ekranida aniq yozuv chiqadi")
        if is_p3_device:
            matched_rule = error_manager.match_error(match_payload)
            clean_summary = (facts.screen_text_summary or "").strip()
            is_meaningful_summary = clean_summary.lower() not in ["none", "normal", "", "asosiy oyna", "bosh oyna"]

            p3_diag_text = ""
            p3_video_id = None
            if matched_rule:
                rule_text = matched_rule.get("response_text", "")
                if is_meaningful_summary:
                    p3_diag_text = f"🖥 <b>P3 Humo apparat ekranidagi xabar:</b> {clean_summary}\n\n{rule_text}"
                else:
                    p3_diag_text = rule_text
                p3_video_id = matched_rule.get("video_id")
                if matched_rule.get("escalate_to_admin"):
                    return DecisionResult(
                        action=ActionType.ESCALATE_TO_ADMIN,
                        reply_text=p3_diag_text,
                        video_id=p3_video_id,
                        detected_inn=target_inn,
                        should_notify_admin=True,
                        admin_alert_type="tech_issue",
                        admin_alert_text=f"Apparat xatosi: {clean_summary}",
                        log_reason="P3 Humo screen error requires admin escalation"
                    )
            elif is_meaningful_summary:
                p3_diag_text = f"🖥 <b>P3 Humo apparat ekranidagi xabar:</b> {clean_summary}"

            # Agar INN bo'lsa, oylik qarzni ham ko'ramiz
            if target_inn:
                results = excel_manager.search(target_inn)
                if results:
                    org_name = results[0].get("name", "")
                    total_debt = sum(item.get("debt", 0.0) for item in results)
                    user_memory.set_last_id(chat_id, user_id, target_inn, org_name=org_name, debt=total_debt)
                    if total_debt > 0:
                        debt_reply = format_debt_response(results)
                        return DecisionResult(
                            action=ActionType.DIAGNOSE_AND_REPLY,
                            reply_text=f"{p3_diag_text}\n\n──────────────\n{debt_reply}" if p3_diag_text else debt_reply,
                            video_id=None,
                            detected_inn=target_inn,
                            debt_amount=total_debt,
                            org_name=org_name,
                            log_reason="P3 Humo with monthly debt"
                        )

            return DecisionResult(
                action=ActionType.DIAGNOSE_AND_REPLY,
                reply_text=p3_diag_text or "🖥 <b>P3 Humo apparat holati qabul qilindi.</b>",
                video_id=p3_video_id,
                detected_inn=target_inn,
                log_reason="P3 Humo screen handled"
            )

        # Smart One apparatida tanish xato kodi bo'lmasa, status bar ko'rinmasa va hali FM tekshirilmagan bo'lsa -> To'liq ekran so'rash
        if not facts.is_status_bar_visible and not target_fm and not error_manager.match_error(match_payload):
            return DecisionResult(
                action=ActionType.ASK_FULL_SCREEN,
                reply_text=INCOMPLETE_SCREEN_REPLY,
                detected_inn=target_inn,
                log_reason="Status bar invisible on Smart One"
            )

        # B) SMART ONE (VA BOSHQA BARCHA APPARATLAR):
        # QAT'IY QOIDA: AI Smart One apparati ekranidagi yozuvga qarab HECH QANDAY taxminiy xulosa chiqarmaydi!
        # Ekran rasmi xotirada saqlanadi (agar keyin adminga kerak bo'lsa uzatiladi).
        # Standart ketma-ketlik:
        # 1-QADAM: INN tekshiruvi (Oylik Mars to'lovi)
        # 2-QADAM: Fiskal modul tekshiruvi (Yillik Soliq to'lovi)
        # 3-QADAM: Internet, Soat va Reboot
        # 4-QADAM: Adminga / ustaga yo'naltirish

        # 1-QADAM: INN SO'RASH VA TEKSHIRISH
        if not target_inn:
            return DecisionResult(
                action=ActionType.ASK_FULL_SCREEN,
                reply_text=get_hardware_step1_inn_template(),
                detected_inn=None,
                log_reason="Smart One Step 1: Asking for INN first"
            )

        # INN ma'lum bo'lsa -> Excel bazadan tekshirish
        if excel_manager.is_decommissioned(target_inn):
            decom_list = excel_manager.get_decommissioned(target_inn)
            org_name = decom_list[0].get("name", "") if decom_list else ""
            decom_reply = (
                f"🏢 <b>Korxona:</b> {org_name}\n"
                f"🆔 <b>СТИР (INN):</b> <code>{target_inn}</code>\n"
                f"ℹ️ Ushbu korxona xizmat ko'rsatish bazasidan hisobdan chiqarilgan (o'chirilgan). Qarzdorlik hisoblanmaydi (0 so'm)."
            )
            return DecisionResult(
                action=ActionType.DEBT_INFO,
                reply_text=decom_reply,
                detected_inn=target_inn,
                org_name=org_name,
                debt_amount=0.0,
                log_reason="Smart One: Decommissioned"
            )

        results = excel_manager.search(target_inn)
        if not results:
            return DecisionResult(
                action=ActionType.DEBT_INFO,
                reply_text=f"❌ <b>СТИР (INN):</b> <code>{target_inn}</code> bazadan topilmadi. Raqamni to'g'ri kiritganingizni tekshiring.",
                detected_inn=target_inn,
                log_reason="Smart One: INN not found"
            )

        org_name = results[0].get("name", "")
        total_debt = sum(item.get("debt", 0.0) for item in results)
        user_memory.set_last_id(chat_id, user_id, target_inn, org_name=org_name, debt=total_debt)

        # 1-A: AGAR OYLIK ABONENT QARZI BO'LSA (total_debt > 0) -> FAQAT QARZ VA REKVIZITLAR!
        if total_debt > 0:
            debt_reply = format_debt_response(results)
            return DecisionResult(
                action=ActionType.DIAGNOSE_AND_REPLY,
                reply_text=debt_reply,
                video_id=None,
                detected_inn=target_inn,
                debt_amount=total_debt,
                org_name=org_name,
                log_reason="Smart One Step 1: Monthly debt exists"
            )

        # 2-QADAM: MARS QARZI YO'Q (total_debt <= 0) -> FISKAL MODULNI TEKSHIRISH (YILLIK SOLIQ TO'LOVI)
        if not target_fm:
            fm_ask_reply = get_hardware_step2_fm_template(org_name, target_inn)
            return DecisionResult(
                action=ActionType.DEBT_INFO,
                reply_text=fm_ask_reply,
                detected_inn=target_inn,
                debt_amount=total_debt,
                org_name=org_name,
                log_reason="Smart One Step 2: Asking for fiscal module"
            )

        # 3-QADAM: OYLIK VA YILLIK QARZI BO'LMASA -> INTERNET, SOAT VA REBOOT
        reboot_reply = get_hardware_step3_clear_template(org_name, target_inn, target_fm)
        return DecisionResult(
            action=ActionType.DIAGNOSE_AND_REPLY,
            reply_text=reboot_reply,
            detected_inn=target_inn,
            debt_amount=total_debt,
            org_name=org_name,
            log_reason="Smart One Step 3: Verified debts clear, suggested network/time and reboot"
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

        # 1. Guardrail: Haqiqatan to'lov kvitansiyasimi? (Kassa cheki to'lov kvitansiyasi EMAS)
        if not facts.is_receipt or getattr(facts, "is_fiscal_chek", False):
            logger.info("Guardrail: Hujjat/tasvir to'lov kvitansiyasi emas (yoki kassa cheki).")
            return DecisionResult(
                action=ActionType.IGNORE,
                log_reason="Not a payment receipt or is a fiscal chek"
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
            # Xotiradagi Fiskal modul (FM) ni tekshirish
            user_fm = user_memory.get_last_fm(chat_id, user_id)
            annual_reply = get_receipt_ack_template(is_recent_dup=False)
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
                    "inn": facts.payer_inn or user_memory.get_last_id(chat_id, user_id) or "",
                    "fiscal_module": user_fm,
                    "paid_amount": facts.amount,
                    "recipient": YANGI_TEXNOLOGIYALAR_ORG_NAME,
                    "is_duplicate": facts.is_duplicate,
                    "is_old_receipt": facts.is_old_receipt,
                    "old_receipt_warning": facts.old_receipt_warning,
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
            raw_last_id = user_memory._get_or_create_session(chat_id, user_id).get("last_id")
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

            ask_inn_reply = get_receipt_ack_template(missing_inn=True)
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
                    "is_inn_missing": True,
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
        """
        Kvitansiyani yuzaki tahlil qilib, INN va sanasiga ko'ra (eski vs bugungi)
        Exceldagi qarzdorlik bilan solishtirib adminga hisobot tayyorlash.
        Mijozga esa faqat kvitansiya adminga yuborilgani haqida oddiy, qisqa javob qaytariladi.
        """
        session_data = user_memory._get_or_create_session(chat_id, user_id)
        session_inn = session_data.get("last_id")
        inn_mismatch = bool(session_inn and inn and session_inn != inn)

        session_org_name = ""
        session_debt = 0.0
        if session_inn:
            s_res = excel_manager.search(session_inn)
            if s_res:
                session_org_name = s_res[0].get("name", "")
                session_debt = sum(item.get("debt", 0.0) for item in s_res)
            elif session_data.get("debt_info"):
                session_org_name = session_data["debt_info"].get("org_name", "")
                session_debt = float(session_data["debt_info"].get("debt", 0.0) or 0.0)

        results = excel_manager.search(inn)
        org_name = ""
        prev_debt = 0.0
        inn_in_db = False

        if results:
            inn_in_db = True
            org_name = results[0].get("name", "")
            prev_debt = sum(item.get("debt", 0.0) for item in results)
        else:
            org_name = facts.payer_name or "Bazadan topilmadi"

        # Agar mijoz suhbatda o'zining qarzdor INNsini (masalan 307314860 -> 2,100,000) tekshirib turib,
        # boshqa INN (masalan 32108755590021) kvitansiyasini tashlagan bo'lsa, solishtirish uchun mijozning haqiqiy qarzini ham hisobga olamiz!
        effective_prev_debt = session_debt if (inn_mismatch and session_debt > 0 and prev_debt == 0) else prev_debt

        paid_amount = facts.amount
        remaining_debt = effective_prev_debt
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

        # 3.4 Takroriy kvitansiya spamidan himoya (oxirgi 30 daqiqa ichida yuborilgan bo'lsa)
        is_recent_dup = user_memory.is_recent_duplicate_receipt(
            chat_id=chat_id,
            user_id=user_id,
            tx_id=facts.transaction_id,
            amount=facts.amount,
            p_date=facts.payment_date
        )

        tuman = excel_manager.get_district_for_inn(session_inn if (inn_mismatch and session_inn) else inn)

        # Qarz bilan solishtirish:
        # Agar mijoz bir necha kvitansiya yuborayotgan bo'lsa (masalan 100k + 100k),
        # bugungi barcha yuborilgan kvitansiyalar yig'indisini hisobga olamiz!
        prior_todays_paid = user_memory.get_todays_paid_total(chat_id, user_id, inn=inn)
        cumulative_paid = prior_todays_paid + paid_amount

        # Qarz bilan solishtirish FAQAT bugungi (eski bo'lmagan) va INN mos kelgan kvitansiyalar uchun bajariladi!
        if not facts.is_old_receipt and not inn_mismatch:
            if effective_prev_debt > 0:
                if cumulative_paid >= effective_prev_debt:
                    debt_covered = True
                    remaining_debt = 0.0
                else:
                    debt_covered = False
                    remaining_debt = max(0.0, effective_prev_debt - cumulative_paid)
            else:
                debt_covered = (inn_in_db and paid_amount > 0)
                remaining_debt = 0.0
        else:
            # Eski kvitansiya yoki boshqa INN kvitansiyasi joriy qarzni yopmaydi!
            debt_covered = False
            remaining_debt = effective_prev_debt

        # Foydalanuvchiga oddiy, sodda va qisqa javob qaytarish:
        user_reply = get_receipt_ack_template(is_recent_dup=(is_recent_dup or facts.is_duplicate))

        # Xotirada pending receiptni tozalash (MUHIM: mijozning kunlik Exceldagi qarzini va avvalgi INNsini buzmaslik!)
        user_memory.clear_pending_receipt(chat_id, user_id)
        if not session_inn and inn_in_db:
            user_memory.set_last_id(chat_id, user_id, inn, org_name=org_name, debt=prev_debt)

        user_memory.set_last_receipt(chat_id, user_id, {
            "inn": inn,
            "amount": paid_amount,
            "cumulative_paid": cumulative_paid,
            "date": facts.payment_date,
            "transaction_id": facts.transaction_id,
            "prev_debt": effective_prev_debt,
            "remaining_debt": remaining_debt,
            "debt_covered": debt_covered,
            "is_old_receipt": facts.is_old_receipt,
            "inn_mismatch": inn_mismatch,
            "payment_purpose": facts.payment_purpose,
            "purpose_label": facts.purpose_label,
            "tuman": tuman,
            "admin_notified": True
        })
        user_memory.set_last_topic(chat_id, user_id, "receipt_verified")

        debt_status_info = {
            "org_name": org_name,
            "inn": inn,
            "inn_in_db": inn_in_db,
            "inn_missing": False,
            "is_inn_missing": False,
            "inn_mismatch": inn_mismatch,
            "session_inn": session_inn,
            "session_org_name": session_org_name,
            "session_debt": session_debt,
            "prev_debt": effective_prev_debt,
            "receipt_inn_debt": prev_debt,
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
            debt_amount=effective_prev_debt,
            paid_amount=paid_amount,
            remaining_debt=remaining_debt,
            org_name=org_name,
            should_notify_admin=not is_recent_dup,
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
            log_reason="Receipt surface-analyzed and prepared for admin"
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
        """Mijoz operator, usta yoki shaxsiy yordam so'raganda o'z hududi bo'yicha adminga uzatish"""
        inn = user_memory.get_last_id(chat_id, user_id) or "-"
        debt_info = user_memory.get_debt_info(chat_id, user_id) or {}
        org_name = debt_info.get("org_name", "-")

        tuman = excel_manager.get_district_for_inn(inn) if (inn and inn != "-") else ""
        contacts_info = admin_manager.get_contacts_display(inn=inn if inn != "-" else None, tuman=tuman)
        reply_text = get_escalate_admin_template(contacts_info)

        return DecisionResult(
            action=ActionType.ESCALATE_TO_ADMIN,
            reply_text=reply_text,
            detected_inn=inn if inn != "-" else None,
            org_name=org_name if org_name != "-" else None,
            tuman=tuman,
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
        video_id = None

        return DecisionResult(
            action=ActionType.DIAGNOSE_AND_REPLY,
            reply_text=debt_text,
            video_id=video_id,
            detected_inn=inn,
            debt_amount=total_debt,
            org_name=org_name,
            log_reason="Resolved INN from fallback flow"
        )

    # =========================================================================
    # 4. MATNLI MUROJAAT VA TEKSHIRUV INQUIRY (TEXT PROCESSING ENGINE)
    # =========================================================================
    async def process_text_inquiry(
        self,
        text: str,
        chat_id: int,
        user_id: int,
        user_name: str = "Mijoz",
        user_username: str = "",
        bot: Optional[Any] = None
    ) -> DecisionResult:
        """
        Foydalanuvchining har qanday matnli so'rovini qat'iy 4 bosqichli formula bo'yicha tahlil qilish:
        1-bosqich (Qarzdorlik - 60%+): INN va Fiskal modul orqali oylik va yillik qarz tekshiruvi;
        2-bosqich: Ekrandagi xatolik yozuvi tahlili (rasm bo'lsa);
        3-bosqich: Apparatning o'zini tekshirish (Soat, Internet, Reboot);
        4-bosqich: Eskalatsiya (Adminga va texniklarga yo'naltirish).
        """
        user_script = user_memory.detect_and_update_script(chat_id, user_id, text)
        clean_text = text.strip()
        lower_text = clean_text.lower()

        found_inn = extract_clean_inn(clean_text)
        found_fm = extract_fiscal_module(clean_text)
        remembered_id = user_memory.get_last_id(chat_id, user_id)

        # -1. MODULLI RULE ENGINE VA MAYDA PATCHLAR TEKSHIRUVI (PLUG & PLAY):
        from core.rule_engine import rule_engine, RuleContext
        rule_ctx = RuleContext(
            text=text,
            clean_text=clean_text,
            lower_text=lower_text,
            chat_id=chat_id,
            user_id=user_id,
            user_name=user_name,
            user_username=user_username,
            user_script=user_script,
            found_inn=found_inn,
            found_fm=found_fm,
            remembered_id=remembered_id,
            bot=bot
        )
        patch_result = await rule_engine.evaluate(rule_ctx)
        if patch_result is not None:
            return patch_result

        # 0. Agar foydalanuvchi avval kvitansiya yuklagan bo'lsa va endi INN yozsa:
        if found_inn:
            pending_res = self.resolve_pending_receipt_if_any(found_inn, chat_id, user_id)
            if pending_res:
                return pending_res

        # 1. Operator / Usta / Admin talab qilinganda:
        OPERATOR_KEYWORDS = [
            "operator", "adminga", "admin kerak", "admin", "adminga gapim bor", "adminga gap",
            "adminga yozish", "admin bormi", "admin qani", "admin kim", "adminga bog'la", "adminga bogla",
            "operator bormi", "operator kerak", "operatorga ula", "operator chaqir", "operator bilan",
            "texnik", "texnik kerak", "texnik bormi", "texnikka gapim bor", "texnikka yoz",
            "texnik bilan", "texnik bilan gaplashmoqchiman", "usta kerak", "usta bormi", "usta chaqir",
            "mutaxassis", "mutaxassis kerak", "inson bilan gaplashmoqchiman", "jonli odam",
            "bog'lanish", "boglanish", "telefon raqam", "aloqaga chiq", "aloqaga chiqing",
            "bog'laning", "boglaning", "yordam bering usta", "yordam bering", "telefon qiling",
            "qongiroq qiling", "qo'ng'iroq qiling", "kimga murojaat", "kimga yozay", "kimga aytay",
            "hal bo'lmadi", "hal bolmadi", "tushunmadim usta", "operator bilan gaplashmoqchiman",
            "menga usta kerak", "menga admin kerak", "menga texnik kerak",
            "оператор", "админ", "техник", "мастер", "позвоните", "свяжитесь", "помогите"
        ]
        if any(kw in lower_text for kw in OPERATOR_KEYWORDS):
            return self.escalate_general_issue(clean_text, chat_id, user_id)

        # 2. 406-xatolik (Oflayn rejim chegarasi) haqida so'ralganda:
        is_406_query = any(k in lower_text for k in [
            "406", "kod 406", "xatolik 406", "ashebka 406", "ошибка 406",
            "oflayn rejim", "офлайн режим", "maksimal davomiylik", "davomiylik oralig'i", "davomiylik oraligi"
        ])
        if is_406_query:
            err_406_reply = (
                "✅ <b>Ha, aynan to'g'ri! 406-xatolik («Oflayn rejimning maksimal davomiylik oralig'i oshib ketdi») — bu Oylik abonent to'lovi emas, "
                "balki YILLIK FISKAL MODUL TO'LOVI («Yangi Texnologiyalar» DUK / Soliq) xatoligidir!</b>\n\n"
                "📌 <b>Nima sababdan yuzaga keladi?</b>\n"
                "1. Kassa apparatining Davlat Soliq Qo'mitasidagi <b>yillik fiskal xizmat to'lovi</b> muddati tugagan bo'lishi mumkin;\n"
                "2. Yoki kassa apparati uzoq vaqt internetga ulanmaganligi sababli Soliq (OFD) tizimi chek qabul qilishni to'xtatgan.\n\n"
                "💡 <b>Yechimi:</b>\n"
                "▫️ Click ilovasi orqali <b>«Yangi Texnologiyalar DUK»</b> xizmatiga yillik to'lovni (<code>20210000100431200010</code>) to'lang;\n"
                "▫️ Kassa apparatini barqaror Wi-Fi yoki mobil internetga ulang va apparatni o'chirib qayta yoqing (Restart).\n\n"
                "👇 <i>Quyida Yillik to'lovni Click orqali amalga oshirish video-qo'llanmasi yuborildi:</i>"
            )
            user_memory.set_last_topic(chat_id, user_id, "error_406_annual")
            return DecisionResult(
                action=ActionType.DIAGNOSE_AND_REPLY,
                reply_text=err_406_reply,
                video_id=145,
                log_reason="Error 406 inquiry resolved"
            )

        # 3. To'lov rekvizitlari va hisob raqamlar so'rovi (agar aniq INN yoki Fiskal modul kiritilmagan bo'lsa):
        from payment_accounts import (
            classify_payment_intent, get_monthly_payment_card, get_monthly_post_note,
            get_annual_payment_card, get_annual_post_note, is_how_to_pay_video_intent,
            get_fiscal_module_request_prompt
        )
        p_intent = classify_payment_intent(clean_text)
        if p_intent and not found_fm and not found_inn:
            wants_vid = is_how_to_pay_video_intent(clean_text)
            if p_intent == "monthly":
                card_text = f"{get_monthly_payment_card()}\n\n{get_monthly_post_note(user_script)}"
                return DecisionResult(
                    action=ActionType.DIAGNOSE_AND_REPLY,
                    reply_text=card_text,
                    video_id=148 if wants_vid else None,
                    log_reason="Monthly payment account inquiry"
                )
            else:
                card_text = f"{get_annual_payment_card()}\n\n{get_annual_post_note(user_script)}"
                return DecisionResult(
                    action=ActionType.DIAGNOSE_AND_REPLY,
                    reply_text=card_text,
                    video_id=145 if wants_vid else None,
                    log_reason="Annual payment account inquiry"
                )

        # 4. Yillik to'lov yoki OFD muddatini tekshirish alohida so'ralganda:
        ofd_check_keywords = [
            "yillik qarz", "yillikni tekshir", "ofd tekshir", "ofdni tekshir",
            "fiskal modul muddat", "fiskal modul qachon", "yillik muddat", "fiskal modul tekshir",
            "йиллик қарз", "йиллик карз", "йилликни текшир", "офд текшир", "фискал модул муддат"
        ]
        if any(kw in lower_text for kw in ofd_check_keywords) and not found_fm:
            fm_ask = get_fiscal_module_request_prompt(user_script)
            return DecisionResult(
                action=ActionType.DEBT_INFO,
                reply_text=fm_ask,
                log_reason="Prompted for fiscal module for annual check"
            )

        # 5. INN yoki FISKAL MODUL kiritilganda (yoki ikkalasi birgalikda):
        if found_inn or found_fm:
            debt_res_text = ""
            total_debt = 0.0
            target_inn = found_inn or remembered_id
            target_org = ""
            tuman = ""

            # A) INN bo'yicha Mars oylik abonent qarzini tekshirish
            if target_inn:
                from handlers.debt import format_debt_response
                results = excel_manager.search(target_inn)
                if not results and excel_manager.is_decommissioned(target_inn):
                    decom_list = excel_manager.get_decommissioned(target_inn)
                    decom_org = decom_list[0].get("name", "") if decom_list else ""
                    debt_res_text = (
                        f"ℹ️ <b>{decom_org}</b> korxonasi xizmat ko'rsatish bazasidan hisobdan chiqarilgan (o'chirilgan).\n"
                        f"Qarzdorlik hisoblanmaydi (0 so'm).\n\n"
                        f"Agar yangitdan xizmat ko'rsatish yoki apparatni qayta faollashtirish kerak bo'lsa, «Usta kerak» deb yozishingiz mumkin."
                    )
                elif results:
                    target_org = results[0].get("name", "")
                    total_debt = sum(item.get("debt", 0.0) for item in results)
                    tuman = excel_manager.get_district_for_inn(target_inn)
                    model_summary = excel_manager.get_device_model_summary(results)
                    user_memory.set_last_id(chat_id, user_id, target_inn, org_name=target_org, debt=total_debt, device_models=model_summary)
                    user_memory.set_last_topic(chat_id, user_id, "debt_checked")
                    debt_res_text = format_debt_response(results)

                    pending_screen = user_memory.get_pending_device_screen(chat_id, user_id)
                    if pending_screen:
                        is_p3 = any(bool(item.get("is_p3", False)) for item in results)
                        saved_summary = (pending_screen.get("screen_text_summary") or "").strip()
                        if is_p3 and saved_summary:
                            debt_res_text = f"🖥 <b>P3 Humo apparat ekranidagi xabar:</b> {saved_summary}\n\n──────────────\n{debt_res_text}"
                else:
                    debt_res_text = format_debt_response([])

            # B) Fiskal modul bo'yicha OFD tekshiruvi
            ofd_text = ""
            if found_fm:
                from ofd_bridge import ofd_bridge
                ofd_reply = await ofd_bridge.query_fiscal_module(bot, found_fm)
                if ofd_reply:
                    ofd_text = f"🏛 <b>OFD / Soliq tizimi ma'lumoti (Fiskal modul: <code>{found_fm}</code>):</b>\n{ofd_reply}"
                else:
                    ofd_text = (
                        f"⚠️ <b>Fiskal modul (<code>{found_fm}</code>) bo'yicha ma'lumot olinmadi.</b>\n\n"
                        f"Iltimos, kassa chekining eng pastki qismidagi seriya raqami (masalan: <code>LG42021...</code>, <code>YG...</code> yoki <code>UZ...</code>) to'g'ri yozilganini tekshiring yoki chekni rasmga olib yuboring."
                    )

            # C) Birlashtirish va Yakuniy Sintez
            if debt_res_text and ofd_text:
                combined_reply = f"{debt_res_text}\n\n{ofd_text}"
                vid = 148 if total_debt > 0 else None
                return DecisionResult(
                    action=ActionType.DEBT_INFO,
                    reply_text=combined_reply,
                    video_id=vid,
                    detected_inn=target_inn,
                    debt_amount=total_debt,
                    org_name=target_org,
                    tuman=tuman,
                    log_reason="Evaluated both INN and Fiscal Module"
                )
            elif debt_res_text:
                if total_debt > 0:
                    fm_tip = (
                        "\n\n💡 <b>Yillik fiskal modul to'lovi va Soliq (OFD) muddatini ham tekshirish uchun:</b>\n"
                        "Apparat chekining pastki qismidagi <b>Fiskal modul raqamini</b> (masalan: <code>LG...</code>, <code>YG...</code> yoki <code>UZ...</code>) yuboring."
                    )
                    wants_vid = is_how_to_pay_video_intent(clean_text)
                    return DecisionResult(
                        action=ActionType.DEBT_INFO,
                        reply_text=f"{debt_res_text}{fm_tip}",
                        video_id=148 if wants_vid else None,
                        detected_inn=target_inn,
                        debt_amount=total_debt,
                        org_name=target_org,
                        tuman=tuman,
                        log_reason="Debt checked from INN"
                    )
                else:
                    stage3_note = (
                        "\n\n📌 <b>Apparatni ishga tushirish uchun quyidagilarni tekshiring:</b>\n"
                        "1️⃣ <b>Internet va Soat:</b> Wi-Fi/SIM belgisi va sana-vaqt to'g'ri ekanini tekshiring;\n"
                        "2️⃣ <b>Reboot:</b> Kassa dasturidan to'liq chiqib qayta kiring yoki apparatni o'chirib qayta yoqing (Перезагрузка);\n"
                        "3️⃣ <b>Ekran rasmi:</b> Agar ekranda xatolik yozuvi chiqayotgan bo'lsa, ekranini rasmga olib yuboring (ko'pincha ekranda sababi aniq yozilgan bo'ladi);\n\n"
                        "💡 <i>Yillik fiskal modul muddatini ham tekshirish uchun chekdagi Fiskal modul raqamini (LG... yoki YG...) yuborishingiz mumkin.</i>"
                    )
                    return DecisionResult(
                        action=ActionType.DEBT_INFO,
                        reply_text=f"{debt_res_text}{stage3_note}",
                        detected_inn=target_inn,
                        debt_amount=0.0,
                        org_name=target_org,
                        tuman=tuman,
                        log_reason="No debt verified, Stage 3 provided"
                    )
            elif ofd_text:
                monthly_hint = "\n\n💡 <i>«Mars Elektron Texnika» oylik abonent to'lovini ham tekshirmoqchi bo'lsangiz, korxonangiz INN (9 xonali) raqamini yuboring.</i>"
                return DecisionResult(
                    action=ActionType.DEBT_INFO,
                    reply_text=f"{ofd_text}{monthly_hint}",
                    log_reason="Fiscal module checked"
                )

        # 6. Kassa ishlamay qolganligi yoki tekshiruv so'rovi (INN/FM berilmaganda):
        DEVICE_ISSUE_PHRASES = [
            "apparat ishlamayapti", "apparatim ishlamayapti", "kassa ishlamayapti",
            "kassa ishlamay qoldi", "apparat ishlamay qoldi", "chek urmayapti",
            "chek chiqmayapti", "kassa qotib qoldi", "apparat qotib qoldi",
            "ishlamayapti apparat", "ishlamayapti kassa", "ne rabotayet apparat",
            "не работает касса", "не работает аппарат", "аппарат не работает", "касса не работает"
        ]
        CHECK_REQUEST_PHRASES = [
            "tekshirib ber", "tekshirib beriyla", "tekshirib bering", "tekshirib beringlar",
            "tekshirib berish", "apparatni tekshir", "apparatimni tekshir", "aparatni tekshir", "aparatimni tekshir",
            "aparatimga qarab", "apparatimga qarab", "tashkilotni tekshir", "tashkilotimni tekshir", "tashkilotmni tekshir",
            "yangi tashkilot", "qarzim bormi", "qarzimni tekshir", "qarzdorlikni tekshir", "qarz bormi",
            "warzim bormi", "aarzim bor", "tekshiring", "tekshirib kor", "tekshirib ko'r",
            "текшириб бер", "текшириб беринг", "қарзим борми", "карзим борми", "текширинг"
        ]
        is_issue_or_check = any(p in lower_text for p in DEVICE_ISSUE_PHRASES) or any(p in lower_text for p in CHECK_REQUEST_PHRASES)

        if is_issue_or_check:
            if remembered_id:
                return await self.process_text_inquiry(remembered_id, chat_id, user_id, user_name, user_username, bot)
            else:
                guide_msg = (
                    "🔍 <b>Qarzdorlik va apparat holatini tekshirish:</b>\n\n"
                    "Kassa apparatlari to'xtab qolishining 60%+ sababi abonent yoki soliq to'lovidagi qarzdorlik bo'ladi.\n\n"
                    "Iltimos, korxonangizning <b>INN (9 xonali)</b> raqamini hamda iloji bo'lsa apparat chekining pastki qismidagi <b>Fiskal modul raqamini (LG... yoki YG...)</b> yuboring.\n\n"
                    "💡 <i>Biz bir vaqtning o'zida «Mars» oylik abonent to'lovini hamda Davlat Soliq Qo'mitasi (OFD) yillik litsenziya muddatini to'liq tekshirib beramiz!</i>"
                )
                return DecisionResult(
                    action=ActionType.DEBT_INFO,
                    reply_text=guide_msg,
                    log_reason="Requested INN and Fiscal Module for issue/check inquiry"
                )

        # 7. Unresolved problem keywords -> Adminga tinchgina xabarnoma yuborish
        unresolved_keywords = ["ishlamayapti", "ishlamadi", "o'xshamadi", "oxshamadi", "bo'lmadi", "bolmadi", "tushunmadim", "yana xato", "tushunarsiz"]
        should_alert_tech = any(ukw in lower_text for ukw in unresolved_keywords)

        # 8. Video katalogdan aniq amallarni qidirish (vozvrat, x-hisobot va h.k.)
        from catalog_manager import catalog_manager
        cat_result = catalog_manager.search(clean_text)
        if cat_result:
            cat_reply = (
                f"🎬 <b>{cat_result.get('title', 'Video-qo‘llanma')}</b>\n\n"
                f"{cat_result.get('description', '')}\n\n"
                f"👇 <i>Quyida so'ralgan video-qo'llanma yuborildi:</i>"
            )
            return DecisionResult(
                action=ActionType.DIAGNOSE_AND_REPLY,
                reply_text=cat_reply,
                video_id=cat_result.get("id"),
                should_notify_admin=should_alert_tech,
                admin_alert_text=f"Mijoz so'rovi (katalog): {clean_text}",
                log_reason="Catalog match"
            )

        # 9. AI helper / Davomiy muloqot
        from ai_helper import ai_helper
        ai_resp, ai_video_id, ai_needs_admin = await ai_helper.ask_with_context_ex(
            user_text=clean_text,
            chat_id=chat_id,
            user_id=user_id,
            catalog=catalog_manager.get_all_videos()
        )
        final_notify = should_alert_tech or ai_needs_admin
        alert_reason = (
            f"Mijozda hal bo'lmagan muammo: {clean_text}" if should_alert_tech
            else f"Mijoz noma'lum savol berdi (AI bilmadi va adminga yo'naltirdi): {clean_text}"
        )
        return DecisionResult(
            action=ActionType.DIAGNOSE_AND_REPLY,
            reply_text=ai_resp,
            video_id=ai_video_id,
            should_notify_admin=final_notify,
            admin_alert_text=alert_reason,
            log_reason="AI conversational response"
        )

core_engine = CoreEngine()
