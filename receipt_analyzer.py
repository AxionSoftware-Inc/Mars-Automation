import os
import re
import io
import json
import base64
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

import pypdf

from openrouter_client import openrouter_client
from core.models import ReceiptFacts, extract_clean_inn

load_dotenv()
logger = logging.getLogger(__name__)

from payment_accounts import (
    MARS_ACCOUNT, MARS_INN, MARS_KEYWORDS, MARS_ORG_NAME,
    YANGI_TEXNOLOGIYALAR_ACCOUNT, YANGI_TEXNOLOGIYALAR_INN,
    YANGI_TEXNOLOGIYALAR_KEYWORDS, YANGI_TEXNOLOGIYALAR_ORG_NAME,
    classify_receipt_target
)

def extract_receipt_facts(
    file_bytes: bytes,
    filename: str = "",
    mime_type: str = "image/jpeg",
    user_caption: str = ""
) -> ReceiptFacts:
    """
    Kvitansiya sensor moduli (Sensory Extractor):
    Rasm yoki PDF formatdagi to'lov cheki/kvitansiyasidan sof faktlarni ajratib oladi.
    Hech qanday qaror chiqarmaydi, faqat ReceiptFacts modelini to'ldiradi.
    """
    caption_inn = extract_clean_inn(user_caption) if user_caption else None

    is_pdf = filename.lower().endswith(".pdf") or "pdf" in mime_type.lower()
    pdf_text = ""
    pdf_image_bytes = None

    if not is_pdf:
        from image_analyzer import analyze_media_image
        m_type, r_facts, d_facts = analyze_media_image(
            image_bytes=file_bytes,
            user_caption=user_caption,
            mime_type=mime_type
        )
        if r_facts:
            return r_facts
        return ReceiptFacts(is_receipt=False, payer_inn=caption_inn)

    if is_pdf:
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            text_chunks = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text_chunks.append(t)
            pdf_text = "\n".join(text_chunks).strip()

            # Agar PDF da matn bo'lmasa, ichidagi birinchi rasmni ajratish
            if not pdf_text and reader.pages and reader.pages[0].images:
                first_img = reader.pages[0].images[0]
                pdf_image_bytes = first_img.data
        except Exception as e:
            logger.error(f"PDF o'qishda xatolik: {e}")

    prompt = f"""
Siz to'lov kvitansiyalari (chek, to'lov topshiriqnomasi, Click, Payme, Uzum, Munis, Bank kvitansiyasi) bo'yicha professional tahlilchisiz.
Ushbu hujjat yoki tasvirdan TO'LOV FAKTLARINI aniqlab, FAQAT quyidagi JSON formatida javob bering.

QAT'IY QOIDALAR:
1. "is_receipt": true/false -> Bu to'lov cheki, kvitansiya yoki to'lov topshiriqnomasi ekanligini tekshiring. Oddiy rasm, apparat ekrani, shartnoma yoki to'lov bo'lmagan hujjat bo'lsa -> ALBATTA false deb belgilang!
2. "recipient_account": Qabul qiluvchi hisob raqami (masalan 20208... yoki «Mars Elektron Texnika» MCHJ).
3. "is_mars_recipient": true/false -> To'lov «Mars Elektron Texnika»ga (yoki hisob raqami: 20208000800208044003, INN: 302568138) qaratilganmi?
4. "amount": To'langan summa (faqat raqam, so'mda, float). Masalan: 100000 yoki 200000.
5. "payer_inn": To'lovchi korxona STIR/INN (9 xonali) yoki JSHSHIR (14 xonali), agar chekda/xizmat identifikatorida ko'rsatilgan bo'lsa.
6. "payer_name": To'lovchi korxona yoki shaxs nomi.
7. "payment_date": To'lov sanasi va vaqti.
8. "transaction_id": Chek/tranzaksiya raqami yoki fiskal belgi.
9. "payment_system": Qaysi tizim orqali to'langan (Click, Payme, Bank, Munis, Uzum, va h.k.).
10. "summary": To'lov haqida 1 qatorlik qisqa ma'lumot.

JAVOB FORMATI FAQAT JSON:
{{
  "is_receipt": true/false,
  "recipient_account": "20208000800208044003",
  "is_mars_recipient": true/false,
  "amount": 100000.0,
  "payer_inn": "123456789" yoki null,
  "payer_name": "Korxona yoki shaxs nomi",
  "payment_date": "2026-10-10 11:30",
  "transaction_id": "1234567890",
  "payment_system": "Click",
  "summary": "Mars Elektron Texnika uchun 100 000 so'm abonent to'lovi"
}}

Foydalanuvchi izohi: "{user_caption}"
"""

    try:
        messages: List[Dict[str, Any]] = []

        if is_pdf and pdf_text:
            # Matnli PDF
            full_prompt = f"{prompt}\n\nPDF HUJJAT MATNI:\n\"\"\"\n{pdf_text[:4000]}\n\"\"\""
            messages = [
                {
                    "role": "user",
                    "content": full_prompt
                }
            ]
        else:
            # Rasm yoki skanerlangan PDF
            target_bytes = pdf_image_bytes if pdf_image_bytes else file_bytes
            effective_mime = "image/png" if pdf_image_bytes else mime_type
            b64_img = base64.b64encode(target_bytes).decode("utf-8")
            image_url = f"data:{effective_mime};base64,{b64_img}"

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ]

        raw_json = openrouter_client.chat_completion(
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"}
        ) or "{}"

        try:
            facts = json.loads(raw_json)
        except Exception:
            match = re.search(r"\{.*\}", raw_json, re.DOTALL)
            facts = json.loads(match.group(0)) if match else {}

        # Fallback tekshiruvlar: Matndan INN va Mars qabul qiluvchisini aniqlash
        raw_payer_inn = str(facts.get("payer_inn") or "")
        payer_inn = extract_clean_inn(raw_payer_inn) or caption_inn
        if not payer_inn and pdf_text:
            text_inns = re.findall(r"\b(\d{14}|\d{9})\b", pdf_text)
            # Mars INN (302568138) bo'lmagan birinchi haqiqiy INN ni to'lovchi deb olamiz
            for candidate in text_inns:
                clean_cand = extract_clean_inn(candidate)
                if clean_cand and clean_cand != MARS_INN:
                    payer_inn = clean_cand
                    break

        recipient_account = str(facts.get("recipient_account", "")).strip()
        combined_text = (pdf_text + " " + recipient_account + " " + user_caption + " " + str(facts.get("summary", ""))).lower()

        raw_amount = facts.get("amount", 0.0)
        try:
            amount = float(raw_amount)
        except (ValueError, TypeError):
            amount = 0.0

        category = classify_receipt_target(recipient_account, amount, raw_text=combined_text)
        is_annual_fiscal = (category == "annual")
        if is_annual_fiscal:
            is_mars_recipient = False
            recipient_org_name = YANGI_TEXNOLOGIYALAR_ORG_NAME
            recipient_account = recipient_account or YANGI_TEXNOLOGIYALAR_ACCOUNT
        elif category == "monthly":
            is_mars_recipient = True
            recipient_org_name = MARS_ORG_NAME
            recipient_account = recipient_account or MARS_ACCOUNT
        else:
            is_mars_recipient = bool(facts.get("is_mars_recipient", False)) or any(kw in combined_text for kw in MARS_KEYWORDS)
            recipient_org_name = recipient_account or "Begona tashkilot"

        return ReceiptFacts(
            is_receipt=bool(facts.get("is_receipt", False)),
            recipient_account=recipient_account or recipient_org_name,
            is_mars_recipient=is_mars_recipient,
            is_annual_fiscal_fee=is_annual_fiscal,
            payment_category=category,
            recipient_org_name=recipient_org_name,
            amount=amount,
            payer_inn=str(payer_inn) if payer_inn else None,
            payer_name=str(facts.get("payer_name", "")),
            payment_date=str(facts.get("payment_date", "")),
            transaction_id=str(facts.get("transaction_id", "")),
            payment_system=str(facts.get("payment_system", "")),
            raw_text=str(facts.get("summary", "")),
            raw_facts=facts,
            extraction_error=None
        )

    except Exception as e:
        logger.error(f"Receipt extraction error: {e}")
        return ReceiptFacts(
            is_receipt=False,
            payer_inn=caption_inn,
            raw_text="",
            extraction_error=str(e)
        )
