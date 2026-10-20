import os
import io
import re
import time
import asyncio
import logging
from typing import Dict, Optional
from aiogram import Router, types, Bot, F
from aiogram.enums import ChatType

from excel_manager import excel_manager, DATA_DIR
from image_analyzer import analyze_media_image, extract_device_facts
from receipt_analyzer import extract_receipt_facts
from admin_manager import admin_manager, get_admin_contact_keyboard
from core import core_engine, ActionType
from core.models import extract_clean_inn, extract_fiscal_module, ReceiptFacts, FiscalChekFacts
from user_memory import user_memory
from state_manager import get_last_file_message_id, set_last_file_message_id
from translit_manager import adapt_to_user_script, detect_script
from ofd_bridge import ofd_bridge
from payment_accounts import MARS_ACCOUNT, YANGI_TEXNOLOGIYALAR_ACCOUNT, format_ofd_annual_status

logger = logging.getLogger(__name__)

router = Router(name="media_router")

DESTINATION_CHANNEL_ID = -1003784534841  # marsfayllar
SOURCE_CHANNEL_ID = -1001641871516       # @POS_Terminal_UzSmart_Bank
EXCEL_CHANNEL_ID = int(os.getenv("EXCEL_CHANNEL_ID", "-1001795471853"))  # Абонент тулови🏦💸💰

RECEIPT_KEYWORDS = [
    "to'lov", "tolov", "chek", "kvitansiya", "click", "payme", "oplata",
    "to'ladim", "toladim", "to'landi", "tolandi", "pul o'tkazdim", "pul otkazdim"
]

_PROCESSED_MEDIA_GROUPS: Dict[str, float] = {}

def _check_and_register_media_group(media_group_id: Optional[str]) -> bool:
    """
    Bir vaqtda guruhlab (album) yuborilgan rasmlardan faqat birinchisini to'liq tahlil qilish,
    qolgan nusxalarida takroriy xabarlar va notification spam bo'lishining oldini olish.
    Qaytaradi: True agar bu media guruhning birinchi rasmi bo'lsa (yoki media group bo'lmasa).
    """
    if not media_group_id:
        return True
    now = time.time()
    # 60 soniyadan eski yozuvlarni tozalash
    to_delete = [k for k, ts in _PROCESSED_MEDIA_GROUPS.items() if now - ts > 60]
    for k in to_delete:
        _PROCESSED_MEDIA_GROUPS.pop(k, None)

    if media_group_id in _PROCESSED_MEDIA_GROUPS:
        return False
    _PROCESSED_MEDIA_GROUPS[media_group_id] = now
    return True

# 1. HUJJATLAR (EXCEL BAZA YOKI PDF KVITANSIYA)
@router.channel_post(F.document)
@router.message(F.document)
async def handle_document(message: types.Message, bot: Bot):
    """
    Hujjatlarni qabul qilish:
    - .xlsx / .xls -> Baza yangilash
    - .pdf -> To'lov kvitansiyasini tahlil qilish va adminga yuborish
    """
    doc = message.document
    if not doc or not doc.file_name:
        return

    file_name = doc.file_name.lower()
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    caption = message.caption or ""

    # A) EXCEL BAZA FAYLI
    if file_name.endswith(".xlsx") or file_name.endswith(".xls"):
        # XAVFSIZLIK: Faqat rasmiy kanal yoki vakolatli adminlar (@Yashnarbek_butaev) bazani yangilashi mumkin!
        is_channel = (message.chat.id in (DESTINATION_CHANNEL_ID, EXCEL_CHANNEL_ID) or message.chat.type == ChatType.CHANNEL)
        username = message.from_user.username if message.from_user else None
        is_authorized_admin = admin_manager.is_admin(user_id, username)

        if not is_channel and not is_authorized_admin:
            logger.warning(f"Ruxsatsiz Excel yuklash urinishi: User {user_id} (@{username})")
            await message.reply(
                "❌ <b>Kechirasiz, sizda ma'lumotlar bazasini (Excel) yangilash huquqi yo'q!</b>\n\n"
                "Ushbu amal faqat tizim administratori (@Yashnarbek_butaev) yoki rasmiy kanal orqali amalga oshiriladi.",
                parse_mode="HTML"
            )
            return

        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            temp_file = os.path.join(DATA_DIR, f"temp_{doc.file_name}")
            await bot.download(doc, destination=temp_file)
            
            success = await asyncio.to_thread(excel_manager.update_file, temp_file)
            if os.path.exists(temp_file):
                os.remove(temp_file)

            # Kanaldagi eski fayl posti FAQAT yangi fayl qabul qilingandan keyin o'chiriladi
            if success and message.chat.id == DESTINATION_CHANNEL_ID:
                last_msg_id = get_last_file_message_id()
                if last_msg_id and last_msg_id != message.message_id:
                    try:
                        await bot.delete_message(chat_id=DESTINATION_CHANNEL_ID, message_id=last_msg_id)
                        logger.info(f"Kanaldan avvalgi eski fayl posti o'chirildi (ID: {last_msg_id})")
                    except Exception as err:
                        logger.warning(f"Avvalgi fayl postini o'chirishda xatolik: {err}")
                set_last_file_message_id(message.message_id)

            if success:
                logger.info(f"Yangi Excel bazasi yangilandi! Yozuvlar: {excel_manager.records_count}")
                if message.chat.type != ChatType.CHANNEL:
                    await message.reply(
                        f"✅ <b>Baza muvaffaqiyatli yangilandi!</b>\n"
                        f"📁 Fayl: <code>{doc.file_name}</code>\n"
                        f"📊 Jami yozuvlar: <b>{excel_manager.records_count} ta</b>",
                        parse_mode="HTML"
                    )
            else:
                reason = getattr(excel_manager, "last_update_error", "") or "Noma'lum xatolik"
                logger.error(f"Excel yangilash RAD ETILDI ({doc.file_name}): {reason}")
                fail_text = (
                    f"⚠️ <b>Yangi Excel qabul qilinmadi, eski baza ishlashda davom etmoqda.</b>\n"
                    f"📁 Fayl: <code>{doc.file_name}</code>\n"
                    f"❗️ Sabab: {reason}\n"
                    f"📊 Hozirgi baza: <b>{excel_manager.records_count} ta</b> yozuv"
                )
                if message.chat.type != ChatType.CHANNEL:
                    await message.reply(fail_text, parse_mode="HTML")
                else:
                    await admin_manager.notify_admins(bot, text=fail_text)
        except Exception as e:
            logger.error(f"Excel faylni yuklashda xatolik: {e}")
        return

    # B) PDF FORMATDAGI TO'LOV KVITANSIYASI
    if file_name.endswith(".pdf"):
        if message.media_group_id and not _check_and_register_media_group(message.media_group_id):
            logger.info(f"Media group {message.media_group_id} ning keyingi PDF kvitansiyasi o'tkazib yuborildi.")
            return
        try:
            file_io = io.BytesIO()
            await bot.download(doc, destination=file_io)
            pdf_bytes = file_io.getvalue()

            facts = extract_receipt_facts(
                file_bytes=pdf_bytes,
                filename=doc.file_name,
                mime_type="application/pdf",
                user_caption=caption
            )

            # Agar bu kassa cheki bo'lsa (fiskal chek)
            if facts.is_fiscal_chek:
                user_script = user_memory.get_preferred_script(chat_id, user_id)
                if caption:
                    sc = detect_script(caption)
                    if sc in ("cyrillic", "latin"):
                        user_script = sc
                await _process_fiscal_receipt_content(
                    message=message,
                    bot=bot,
                    receipt_facts=facts,
                    user_script=user_script,
                    caption=caption,
                    file_id=doc.file_id
                )
                return

            decision = core_engine.process_receipt_facts(
                facts=facts,
                chat_id=chat_id,
                user_id=user_id,
                user_comment=caption,
                file_id=doc.file_id,
                is_photo=False
            )

            if decision.action == ActionType.IGNORE:
                logger.info("PDF to'lov kvitansiyasi emas -> Javobsiz qoldirildi.")
                return

            if decision.reply_text:
                user_script = user_memory.get_preferred_script(chat_id, user_id)
                reply_text = adapt_to_user_script(decision.reply_text, user_script)
                try:
                    await message.reply(reply_text, parse_mode="HTML")
                except Exception:
                    await message.reply(reply_text)

                user_memory.add_user_message(chat_id, user_id, f"[PDF Kvitansiya] {caption}".strip())
                user_memory.add_assistant_message(chat_id, user_id, reply_text)

            # Adminga hisobot yuborish
            if decision.should_notify_admin and decision.receipt_facts:
                await admin_manager.notify_receipt_escalation(
                    bot=bot,
                    user=message.from_user,
                    chat_id=chat_id,
                    receipt_facts=decision.receipt_facts,
                    debt_status_info=decision.debt_status_info,
                    file_id=doc.file_id,
                    is_photo=False
                )

        except Exception as e:
            logger.error(f"PDF kvitansiyani qayta ishlashda xatolik: {e}")
        return

    # C) RASMLI FAYL FORMATIDAGI HUJJATLAR (.PNG, .JPG, .JPEG, .WEBP)
    if any(file_name.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        if message.media_group_id and not _check_and_register_media_group(message.media_group_id):
            logger.info(f"Media group {message.media_group_id} ning keyingi hujjat rasmi o'tkazib yuborildi.")
            return
        try:
            file_io = io.BytesIO()
            await bot.download(doc, destination=file_io)
            img_bytes = file_io.getvalue()
            mime = "image/png" if file_name.endswith(".png") else "image/jpeg"
            await _process_image_content(
                message=message,
                bot=bot,
                image_bytes=img_bytes,
                caption=caption,
                file_id=doc.file_id,
                is_document=True,
                mime_type=mime
            )
        except Exception as e:
            logger.error(f"Hujjat rasmini qayta ishlashda xatolik: {e}")
        return


# 2. KASSA CHEKI (FISKAL CHEK / SAVDO CHEKI / ONLAYN-NKM) QAYTA ISHLASH
async def _process_fiscal_receipt_content(
    message: types.Message,
    bot: Bot,
    receipt_facts: ReceiptFacts,
    user_script: str,
    caption: str,
    file_id: str
):
    """
    Kassa apparatidan chiqqan qog'oz savdo cheki (fiskal chek / Onlayn-NKM) tahlili:
    1. INN (9 xonali) va Fiskal modul seriya raqami (LG..., YG..., UZ...) ni ajratib oladi.
    2. user_memory ga INN va FM ni saqlaydi (keyingi savollarda bot eslab qolishi uchun).
    3. Excel bazadan «Mars» oylik abonent to'lovi (100 000 so'm) qarzini tekshiradi.
    4. Agar Fiskal modul bo'lsa, @ofd943_bot orqali Davlat Soliq (OFD) yillik litsenziyasini tekshiradi.
    5. Foydalanuvchiga to'liq va tushunarli kartochka yuboradi.
    6. Adminga to'lov kvitansiyasi sifatida soxta xabarnoma YUBORMAYDI!
    """
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    fisc = receipt_facts.fiscal_facts
    inn = receipt_facts.payer_inn or (fisc.inn if fisc else None) or extract_clean_inn(caption)
    fm = receipt_facts.fiscal_module or (fisc.fiscal_module if fisc else None) or extract_fiscal_module(caption)
    org_name = (fisc.org_name if fisc and fisc.org_name else "") or receipt_facts.payer_name or ""
    terminal_id = (fisc.terminal_id if fisc and fisc.terminal_id else "") or receipt_facts.terminal_id or ""

    # Agar na INN, na FM topilmasa -> Foydalanuvchidan so'rash
    if not inn and not fm:
        fail_msg = (
            "🧾 <b>Kassa cheki tasviri qabul qilindi.</b>\n\n"
            "⚠️ Afsuski, chekdan <b>СТИР (INN)</b> yoki <b>Fiskal modul (LG..., YG..., UZ...)</b> raqamini aniq o'qib bo'lmadi.\n\n"
            "📌 <b>Iltimos:</b>\n"
            "🔹 Chekning yuqori (INN) yoki pastki (Fiskal modul) qismini yaqinroqdan aniq rasmga olib yuboring;\n"
            "🔹 Yoki korxonangiz <b>9 xonali СТИР (INN)</b> raqamini yozib yuboring."
        )
        fail_msg = adapt_to_user_script(fail_msg, user_script)
        try:
            await message.reply(fail_msg, parse_mode="HTML")
        except Exception:
            await message.reply(fail_msg)
        return

    # 1. «Mars» oylik abonent to'lovi holati (100 000 so'm/oy)
    monthly_status_lines = []
    has_monthly_debt = False
    debt_amount = 0.0
    model_summary = ""
    inn_found_in_db = False

    if inn:
        results = excel_manager.search(inn)
        if results:
            inn_found_in_db = True
            if not org_name:
                org_name = results[0].get("name", "")
            debt_amount = sum(item.get("debt", 0.0) for item in results)
            has_monthly_debt = (debt_amount > 0)
            model_summary = excel_manager.get_device_model_summary(results)
        elif excel_manager.is_decommissioned(inn):
            inn_found_in_db = True
        else:
            debt_res = excel_manager.check_debt(inn)
            record = debt_res.get("record") if debt_res else None
            if record and record.get("status") != "not_found":
                inn_found_in_db = True
                if not org_name:
                    org_name = record.get("org_name", "")
                debt_amount = float(record.get("debt_amount", 0.0) or 0.0)
                has_monthly_debt = (record.get("status") == "qarzdor" or debt_amount > 0)

    # 2. Davlat Soliq (OFD) yillik litsenziyasi holati (440 000 so'm/yil)
    from payment_accounts import parse_ofd_reply_status
    has_annual_debt = False
    ofd_status = "not_checked"
    ofd_details = ""
    if fm:
        ofd_reply = await ofd_bridge.query_fiscal_module(bot, fm)
        ofd_status = parse_ofd_reply_status(ofd_reply)
        if ofd_status == "unavailable":
            ofd_details = "OFD tizimi vaqtincha javob bermadi"
        elif ofd_status == "not_found":
            ofd_details = "Fiskal modul topilmadi"
        elif ofd_status == "debt":
            has_annual_debt = True
            ofd_details = "Qarzdorlik mavjud"
        else:
            ofd_details = "Faol"

    # Xotiraga to'liq saqlash (qarz, apparat modeli va yillik holat bilan)
    if inn and inn_found_in_db:
        user_memory.set_last_id(chat_id, user_id, inn, org_name=org_name, debt=debt_amount, device_models=model_summary)
    if fm and ofd_status != "not_found":
        user_memory.set_last_fm(chat_id, user_id, fm)
    if ofd_status in ("debt", "active", "unavailable"):
        user_memory.set_annual_status(chat_id, user_id, has_debt=has_annual_debt, details=ofd_details, unavailable=(ofd_status == "unavailable"))
    user_memory.set_last_photo(chat_id, user_id, file_id)
    user_memory.set_last_topic(chat_id, user_id, "fiscal_receipt_checked")

    # Xabarni qisqa, lo'nda va tushunarli yig'ish (hisob raqamlarsiz)
    lines = ["🧾 <b>KASSA CHEKI TEKSHIRUVI:</b>\n"]
    if org_name:
        lines.append(f"🏢 <b>Korxona:</b> {org_name}")
    meta = []
    if inn:
        meta.append(f"🔢 <b>СТИР:</b> <code>{inn}</code>")
    if fm:
        meta.append(f"📟 <b>FM:</b> <code>{fm}</code>")
    if terminal_id:
        meta.append(f"🆔 <b>Terminal:</b> <code>{terminal_id}</code>")
    if meta:
        lines.append(" | ".join(meta))
    lines.append("────────────────────")

    # 1. Oylik abonent holati
    if inn:
        if not inn_found_in_db:
            lines.append(f"1️⃣ <b>«Mars» oylik abonent to'lovi:</b>\nℹ️ <b>СТИР (<code>{inn}</code>) bazadan topilmadi</b> (Iltimos, korxonangizning 9 xonali STIR raqamini yozib yuboring)")
        elif has_monthly_debt:
            debt_formatted = f"{debt_amount:,.0f}".replace(",", " ")
            lines.append(f"1️⃣ <b>«Mars» oylik abonent to'lovi:</b>\n🔴 <b>Qarzdorlik: {debt_formatted} so'm</b>")
        else:
            lines.append("1️⃣ <b>«Mars» oylik abonent to'lovi:</b>\n🟢 <b>Qarzdorlik yo'q (To'langan)</b>")
    else:
        lines.append("1️⃣ <b>«Mars» oylik to'lovi:</b> СТИР (INN) aniqlanmadi (9 xonali INN raqamingizni yuborsangiz tekshirib beramiz)")

    lines.append("────────────────────")

    # 2. Yillik Soliq (OFD) holati
    if fm:
        if ofd_status == "debt":
            lines.append("2️⃣ <b>Davlat Soliq (OFD) yillik to'lovi:</b>\n🔴 <b>Qarzdorlik mavjud: 440 000 so'm</b>")
        elif ofd_status == "active":
            lines.append("2️⃣ <b>Davlat Soliq (OFD) yillik to'lovi:</b>\n🟢 <b>Qarzdorlik yo'q (Litsenziya muddati faol)</b>")
        elif ofd_status == "not_found":
            lines.append(f"2️⃣ <b>Davlat Soliq (OFD) yillik to'lovi:</b>\n❌ <b>Fiskal modul (<code>{fm}</code>) Soliq bazasidan topilmadi</b> (Chekdagi seriya raqamini tekshiring)")
        else:
            lines.append("2️⃣ <b>Davlat Soliq (OFD) yillik to'lovi:</b>\n⏳ <b>Davlat Soliq (OFD) tizimi vaqtincha javob bermayapti</b> (Birozdan so'ng qayta tekshiring)")
    else:
        lines.append("2️⃣ <b>Davlat Soliq (OFD) to'lovi:</b>\n<i>Fiskal modul seriya raqami aniqlanmadi. Yillik to'lovni tekshirish uchun Fiskal modul seriya raqamini (LG..., YG...) yuboring.</i>")

    final_text = adapt_to_user_script("\n".join(lines), user_script)

    is_issue = user_memory.is_issue_mode(chat_id, user_id)
    if inn_found_in_db and not has_monthly_debt and not has_annual_debt and ofd_status == "active" and fm and is_issue:
        final_text += adapt_to_user_script(
            f"\n\n🟢 <b>To'lovlar bo'yicha qarzdorlik yo'q!</b>\n"
            f"{admin_manager.get_contacts_display(inn=inn)}\n\n"
            "Kassa cheki va apparat ma'lumotlari zudlik bilan hududiy mas'ul adminga yetkazildi.\n"
            "Quyidagi tugmalar orqali to'g'ridan-to'g'ri mas'ul mutaxassis bilan bog'lanishingiz mumkin:",
            user_script
        )
        kb = get_admin_contact_keyboard(inn=inn)
        try:
            await message.reply(final_text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await message.reply(final_text, reply_markup=kb)

        init_q = user_memory.get_issue_initial_query(chat_id, user_id) or "Apparat ishlamayapti"
        await admin_manager.notify_debt_free_device_issue(
            bot=bot,
            user=message.from_user,
            chat_id=chat_id,
            org_name=org_name,
            inn=inn or "",
            issue_summary=f"Mijoz kassa chekini yubordi. Dastlabki murojaat: {init_q}. Izoh: {caption}",
            user_comment=caption,
            photo_file_id=file_id,
            fiscal_module=fm
        )
        user_memory.clear_issue_mode(chat_id, user_id)
        user_memory.set_last_topic(chat_id, user_id, "issue_escalated_to_admin")
    else:
        try:
            await message.reply(final_text, parse_mode="HTML")
        except Exception:
            await message.reply(final_text)

    # Qarz bo'lsa hisob raqamni matnda yozmasdan, kanaldan rasmiy post uzatiladi
    if has_monthly_debt:
        from payment_accounts import MARS_POST_ID
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=SOURCE_CHANNEL_ID,
                message_id=MARS_POST_ID,
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.warning(f"Oylik shot postini (85) nusxalashda xatolik: {e}")

    if has_annual_debt:
        from payment_accounts import YANGI_TEXNOLOGIYALAR_POST_ID
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=SOURCE_CHANNEL_ID,
                message_id=YANGI_TEXNOLOGIYALAR_POST_ID
            )
        except Exception as e:
            logger.warning(f"Yillik shot postini (34) nusxalashda xatolik: {e}")

    user_memory.add_user_message(chat_id, user_id, f"[Kassa cheki] {caption}".strip())
    user_memory.add_assistant_message(chat_id, user_id, final_text)


# 3. MARKAZIY RASM TAHLIL VA QAROR QABUL QILISH FUNKSIYASI
async def _process_image_content(
    message: types.Message,
    bot: Bot,
    image_bytes: bytes,
    caption: str,
    file_id: str,
    is_document: bool = False,
    mime_type: str = "image/jpeg"
):
    """
    Rasmlar (Photo yoki Image Document) uchun yagona tahlilchi:
    1. analyze_media_image orqali tasvir turini aniqlaydi:
       - "fiscal_receipt" -> Kassa cheki (INN va FM o'qish, oylik va yillik qarz tekshirish)
       - "receipt" -> To'lov kvitansiyasi (Click/Payme to'lovi, adminga eskalatsiya)
       - "pos_device" -> Smart POS apparati ekrani (tashxis va video)
       - "other" -> Begona tasvir (jim turish)
    """
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    user_script = user_memory.get_preferred_script(chat_id, user_id)
    if caption:
        sc = detect_script(caption)
        if sc in ("cyrillic", "latin"):
            user_script = sc
            user_memory.detect_and_update_script(chat_id, user_id, caption)

    media_type, receipt_facts, device_facts = analyze_media_image(
        image_bytes=image_bytes,
        user_caption=caption,
        mime_type=mime_type
    )

    mg_id = getattr(message, "media_group_id", None)
    if mg_id and media_type in ("pos_device", "fiscal_receipt", "other"):
        if not _check_and_register_media_group(f"{mg_id}:{media_type}"):
            logger.info(f"Media group {mg_id} ichidagi takroriy '{media_type}' rasmi o'tkazib yuborildi.")
            if media_type == "pos_device" and file_id:
                user_memory.set_last_photo(chat_id, user_id, file_id)
            return

    # 1. KASSA CHEKI (FISKAL CHEK / SAVDO CHEKI / ONLAYN-NKM)
    if media_type == "fiscal_receipt" or (receipt_facts and receipt_facts.is_fiscal_chek):
        await _process_fiscal_receipt_content(
            message=message,
            bot=bot,
            receipt_facts=receipt_facts,
            user_script=user_script,
            caption=caption,
            file_id=file_id
        )
        return

    # 2. TO'LOV KVITANSIYASI
    elif media_type == "receipt" and receipt_facts and receipt_facts.is_receipt:
        decision = core_engine.process_receipt_facts(
            facts=receipt_facts,
            chat_id=chat_id,
            user_id=user_id,
            user_comment=caption,
            file_id=file_id,
            is_photo=not is_document
        )
        if decision.reply_text:
            reply_text = adapt_to_user_script(decision.reply_text, user_script)
            try:
                await message.reply(reply_text, parse_mode="HTML")
            except Exception:
                await message.reply(reply_text)

            user_memory.add_user_message(chat_id, user_id, f"[To'lov kvitansiyasi] {caption}".strip())
            user_memory.add_assistant_message(chat_id, user_id, reply_text)

        if decision.should_notify_admin and decision.receipt_facts:
            await admin_manager.notify_receipt_escalation(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                receipt_facts=decision.receipt_facts,
                debt_status_info=decision.debt_status_info,
                file_id=file_id,
                is_photo=not is_document
            )
        return

    # 2. SMART POS KASSA APPARATI
    elif media_type == "pos_device" and device_facts:
        user_memory.set_last_photo(chat_id, user_id, file_id)
        decision = core_engine.process_device_facts(
            facts=device_facts,
            chat_id=chat_id,
            user_id=user_id,
            user_comment=caption
        )
        if decision.action == ActionType.IGNORE:
            return

        is_issue = user_memory.is_issue_mode(chat_id, user_id)
        last_topic = user_memory.get_last_topic(chat_id, user_id)
        is_awaiting_photo = last_topic in ("awaiting_screen_photo", "issue_escalated_to_admin")
        is_escalation_target = (decision.should_notify_admin and decision.admin_alert_type == "tech_issue") or is_issue or is_awaiting_photo

        inn_to_use = decision.detected_inn or user_memory.get_last_id(chat_id, user_id) or ""
        org_to_use = decision.org_name or user_memory.get_org_name(chat_id, user_id) or ""
        alert_text = decision.admin_alert_text or (device_facts.screen_text_summary if device_facts else "") or "Ekrandagi nosozlik"
        
        ann_st = user_memory.get_annual_status(chat_id, user_id)
        target_fm = user_memory.get_last_fm(chat_id, user_id)
        ann_verified_clear = bool(target_fm and ann_st and not ann_st.get("has_debt", False) and not ann_st.get("unavailable", False))
        monthly_verified_clear = (decision.debt_amount is not None and decision.debt_amount <= 0)

        # AGAR OYLIK VA YILLIK QARZDORLIK TEKSHIRILGAN VA YO'Q BO'LSA (yoki 3-bosqich rasm kutilayotgan bo'lsa) -> ADMINGA YUBORISH:
        if monthly_verified_clear and (ann_verified_clear or is_awaiting_photo) and inn_to_use:
            await admin_manager.notify_debt_free_device_issue(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                org_name=org_to_use,
                inn=inn_to_use,
                issue_summary=alert_text,
                user_comment=caption,
                photo_file_id=file_id,
                fiscal_module=target_fm
            )
            fm_text = f"\n🏛 <b>Fiskal modul:</b> <code>{target_fm}</code>" if target_fm else ""
            esc_ack = (
                "👨‍💻 <b>Iltimos kuting, barcha ma'lumotlaringiz hududiy mas'ul adminga yuborildi!</b>\n\n"
                f"🏢 <b>Korxona:</b> {org_to_use}\n"
                f"🆔 <b>INN:</b> <code>{inn_to_use}</code>"
                f"{fm_text}\n\n"
                f"{admin_manager.get_contacts_display(inn=inn_to_use)}\n\n"
                "📸 Kassa apparati ekranidagi xatolik rasmi va korxona ma'lumotlari hududingiz bo'yicha mas'ul adminga yetkazildi. Tez orada admin o'zi siz bilan bog'lanadi!\n"
                "Quyidagi tugmalar orqali ham to'g'ridan-to'g'ri aloqaga chiqishingiz mumkin:"
            )
            esc_ack = adapt_to_user_script(esc_ack, user_script)
            kb = get_admin_contact_keyboard(inn=inn_to_use)
            try:
                await message.reply(esc_ack, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await message.reply(esc_ack, reply_markup=kb)

            user_memory.mark_escalated_to_admin(chat_id, user_id, reason="Ekran rasmi qabul qilindi va adminga yuborildi")
            user_memory.add_user_message(chat_id, user_id, f"[Ekran rasmi] {caption}".strip())
            user_memory.add_assistant_message(chat_id, user_id, esc_ack)
            return

        if decision.reply_text:
            reply_text = adapt_to_user_script(decision.reply_text, user_script)
            kb = get_admin_contact_keyboard(inn=inn_to_use) if is_escalation_target else None
            try:
                if kb:
                    await message.reply(reply_text, parse_mode="HTML", reply_markup=kb)
                else:
                    await message.reply(reply_text, parse_mode="HTML")
            except Exception:
                if kb:
                    await message.reply(reply_text, reply_markup=kb)
                else:
                    await message.reply(reply_text)

            user_memory.add_user_message(chat_id, user_id, f"[Ekran rasmi] {caption}".strip())
            user_memory.add_assistant_message(chat_id, user_id, reply_text)

        if is_escalation_target:
            await admin_manager.notify_technical_issue(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                org_name=org_to_use,
                inn=inn_to_use,
                issue_summary=alert_text,
                user_comment=caption,
                photo_file_id=file_id
            )

            if is_issue:
                user_memory.clear_issue_mode(chat_id, user_id)
                user_memory.set_last_topic(chat_id, user_id, "issue_escalated_to_admin")

        if decision.video_id:
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=decision.video_id,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.error(f"Videoni yuborishda xatolik: {e}")
        return

    # 3. BEGONA TASVIR YOKI XATOLIK BO'LGANDA XAVFSIZLIK CHIQISHI
    else:
        is_issue = user_memory.is_issue_mode(chat_id, user_id)
        last_topic = user_memory.get_last_topic(chat_id, user_id)
        if is_issue or last_topic in ("awaiting_screen_photo", "issue_escalated_to_admin"):
            user_memory.set_last_photo(chat_id, user_id, file_id)
            inn_to_use = user_memory.get_last_id(chat_id, user_id) or ""
            org_to_use = user_memory.get_org_name(chat_id, user_id) or ""
            init_q = user_memory.get_issue_initial_query(chat_id, user_id) or "Apparat nosozligi rasmi"
            await admin_manager.notify_user_query_escalation(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                query_text=f"Mijoz apparat rasmini yubordi. Dastlabki murojaat: {init_q}. Izoh: {caption}",
                reason="Apparat nosozligi rasmi yuborildi",
                inn=inn_to_use,
                org_name=org_to_use,
                photo_file_id=file_id
            )
            user_memory.clear_issue_mode(chat_id, user_id)
            user_memory.set_last_topic(chat_id, user_id, "issue_escalated_to_admin")
            ack_msg = (
                "📸 <b>Tasvir qabul qilindi va hududiy mutaxassisimizga uzatildi.</b>\n\n"
                f"{admin_manager.get_contacts_display(inn=inn_to_use)}\n\n"
                "👨‍💻 Hududingiz bo'yicha mas'ul adminimiz apparatingiz holatini tekshirib, tez orada o'zi siz bilan bog'lanadi.\n"
                "Quyidagi tugmalar orqali to'g'ridan-to'g'ri mas'ul mutaxassis bilan bog'lanishingiz mumkin:"
            )
            kb = get_admin_contact_keyboard(inn=inn_to_use)
            try:
                await message.reply(adapt_to_user_script(ack_msg, user_script), parse_mode="HTML", reply_markup=kb)
            except Exception:
                await message.reply(ack_msg, reply_markup=kb)
            return

        if device_facts and device_facts.extraction_error:
            logger.warning(f"Tasvir sensori xatoligi: {device_facts.extraction_error}")
            if caption or message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
                err_msg = adapt_to_user_script(
                    "⚠️ <b>Tasvirni yuklashda yoki tahlil qilishda nosozlik yuz berdi.</b>\n"
                    "Iltimos, qayta yuboring yoki korxona <b>INN</b> raqamini yozing.",
                    user_script
                )
                try:
                    await message.reply(err_msg, parse_mode="HTML")
                except Exception:
                    pass
            return

        # Agar shaxsiy chat bo'lsa yoki rasm bilan izoh yozilgan bo'lsa -> jim turmaslik!
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP] or caption:
            try:
                unrec_msg = (
                    "📸 <b>Kechirasiz, yuborilgan tasvirdan kassa apparati ekrani yoki to'lov kvitansiyasini aniqlab bo'lmadi.</b>\n\n"
                    "📌 <b>Iltimos:</b>\n"
                    "🔹 Agar bu <b>kassa apparati</b> bo'lsa, ekranidagi xatolikni (soat va tarmoq qatori bilan) yaqinroqdan rasmga olib yuboring.\n"
                    "🔹 Agar bu <b>to'lov cheki</b> bo'lsa, to'lov kvitansiyasini aniq qilib yuboring yoki korxonangiz <b>INN (STIR)</b> raqamini yozing."
                )
                await message.reply(adapt_to_user_script(unrec_msg, user_script), parse_mode="HTML")
            except Exception:
                pass
            return

        logger.info("Guardrail: Guruhda kassa apparati ham, to'lov cheki ham bo'lmagan begona rasm e'tiborsiz qoldiriladi.")
        return


# 3. RASMLARNI QABUL QILISH (PHOTO HANDLER)
@router.message(F.photo)
async def handle_photo(message: types.Message, bot: Bot):
    """
    Rasm qabul qiluvchi markaziy handler:
    1. Agar to'lov kvitansiyasi bo'lsa -> Kvitansiya tahlili + Qarz solishtiruvi + Adminga bildirishnoma
    2. Agar POS apparati bo'lsa -> Ekran tashxisi + Qarz holati + Nosozlik bo'lsa adminga eskalatsiya
    3. Agar begona narsa bo'lsa -> Jim turish (Guardrail)
    """
    caption = message.caption or ""
    try:
        photo = message.photo[-1]
        file_io = io.BytesIO()
        await bot.download(photo, destination=file_io)
        image_bytes = file_io.getvalue()

        await _process_image_content(
            message=message,
            bot=bot,
            image_bytes=image_bytes,
            caption=caption,
            file_id=photo.file_id,
            is_document=False,
            mime_type="image/jpeg"
        )
    except Exception as e:
        logger.error(f"Media handler ijrosida xatolik: {e}")
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP] or caption:
            try:
                await message.reply(
                    "⚠️ Rasmni qayta ishlashda texnik nosozlik yuz berdi. Iltimos, qaytadan yuborib ko'ring yoki korxona INN raqamini yozing."
                )
            except Exception:
                pass


# 4. OVOZLI XABARLAR (VOICE / AUDIO / VIDEO NOTE) HANDLERI
@router.message(F.voice | F.audio | F.video_note)
async def handle_audio_message(message: types.Message):
    """
    Foydalanuvchi audio (ovozli xabar yoki audio fayl) yuborganida:
    "Iltimos, matn bilan yozing" deb so'rash.
    """
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    user_script = user_memory.get_preferred_script(chat_id, user_id)

    reply_text = "✍️ <b>Iltimos, murojaatingizni matn ko'rinishida yozib yuboring.</b>"
    reply_text = adapt_to_user_script(reply_text, user_script)

    try:
        await message.reply(reply_text, parse_mode="HTML")
    except Exception:
        await message.reply(reply_text)

    user_memory.add_user_message(chat_id, user_id, "[Audio/Ovozli xabar yuborildi]")
    user_memory.add_assistant_message(chat_id, user_id, reply_text)

