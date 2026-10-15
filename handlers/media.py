import os
import io
import re
import time
import logging
from typing import Dict, Optional
from aiogram import Router, types, Bot, F
from aiogram.enums import ChatType

from excel_manager import excel_manager, DATA_DIR
from image_analyzer import analyze_media_image, extract_device_facts
from receipt_analyzer import extract_receipt_facts
from admin_manager import admin_manager
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
            
            success = excel_manager.update_file(temp_file)
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
                try:
                    await message.reply(decision.reply_text, parse_mode="HTML")
                except Exception:
                    await message.reply(decision.reply_text)

                user_memory.add_user_message(chat_id, user_id, f"[PDF Kvitansiya] {caption}".strip())
                user_memory.add_assistant_message(chat_id, user_id, decision.reply_text)

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

    if inn:
        debt_res = excel_manager.check_debt(inn)
        record = debt_res.get("record") if debt_res else None
        if record:
            org_from_rec = record.get("org_name")
            if org_from_rec and not org_name:
                org_name = org_from_rec
            status = record.get("status", "")
            debt_amount = float(record.get("debt_amount", 0.0) or 0.0)
            paid_to = record.get("paid_up_to", "") or record.get("payment_date", "")

            if status == "qarzdor" or debt_amount > 0:
                has_monthly_debt = True
                monthly_status_lines.append(
                    f"⚠️ <b>Qarzdorlik mavjud:</b> <b>{debt_amount:,.0f} so'm</b>"
                )
                if paid_to:
                    monthly_status_lines.append(f"📅 To'lov muddati: <b>{paid_to}</b> gacha to'langan.")
                monthly_status_lines.append(f"💳 Mars X/R: <code>{MARS_ACCOUNT}</code>")
            else:
                monthly_status_lines.append("✅ <b>Qarzdorlik yo'q (To'langan).</b>")
                if paid_to:
                    monthly_status_lines.append(f"📅 Xizmat muddati: <b>{paid_to}</b> gacha faol.")
        else:
            monthly_status_lines.append(
                f"ℹ️ СТИР: <code>{inn}</code> bo'yicha «Mars» ma'lumotlar bazasida yozuv topilmadi."
            )
        results = excel_manager.search(inn)
        if results:
            model_summary = excel_manager.get_device_model_summary(results)
    else:
        monthly_status_lines.append(
            "⚠️ <i>Chekdan СТИР (INN) aniqlanmadi. 9 xonali INN raqamingizni yuborsangiz, oylik to'lovni tekshirib beramiz.</i>"
        )

    # 2. Davlat Soliq (OFD) yillik litsenziyasi holati (440 000 so'm/yil)
    annual_status_lines = []
    has_annual_debt = False
    ofd_details = "To'langan va faol"
    if fm:
        ofd_reply = await ofd_bridge.query_fiscal_module(bot, fm)
        if ofd_reply:
            ofd_fmt = format_ofd_annual_status(fm, ofd_reply, user_script)
            annual_status_lines.append(ofd_fmt)
            if any(w in ofd_reply.lower() for w in ["qarzdorlik mavjud", "fmo dan qarzdorlik", "qarzdorlik"]):
                has_annual_debt = True
                ofd_details = "Qarzdorlik mavjud"
            else:
                ofd_details = "Faol"
        else:
            annual_status_lines.append(
                f"📟 <b>Fiskal modul:</b> <code>{fm}</code>\n"
                f"ℹ️ Soliq (@ofd943_bot) tizimi bilan tekshirilmoqda..."
            )
    else:
        annual_status_lines.append(
            "🏛 <i>Yillik Soliq (OFD) to'lovini tekshirish uchun kassa chekining pastki qismidagi "
            "<b>Fiskal modul seriya raqamini (LG..., YG..., UZ...)</b> yuboring.</i>"
        )

    # Xotiraga to'liq saqlash (qarz, apparat modeli va yillik holat bilan)
    if inn:
        user_memory.set_last_id(chat_id, user_id, inn, org_name=org_name, debt=debt_amount, device_models=model_summary)
    if fm:
        user_memory.set_last_fm(chat_id, user_id, fm)
    user_memory.set_annual_status(chat_id, user_id, has_debt=has_annual_debt, details=ofd_details)
    user_memory.set_last_photo(chat_id, user_id, file_id)
    user_memory.set_last_topic(chat_id, user_id, "fiscal_receipt_checked")

    # Xabarni chiroyli yig'ish
    header_parts = ["🧾 <b>KASSA CHEKI MA'LUMOTLARI:</b>\n"]
    if org_name:
        header_parts.append(f"🏢 <b>Tashkilot:</b> {org_name}")
    if inn:
        header_parts.append(f"🔢 <b>СТИР (INN):</b> <code>{inn}</code>")
    if fm:
        header_parts.append(f"📟 <b>Fiskal modul:</b> <code>{fm}</code>")
    if terminal_id:
        header_parts.append(f"🆔 <b>Terminal:</b> <code>{terminal_id}</code>")

    body_parts = [
        "\n".join(header_parts),
        "────────────────────",
        "1️⃣ <b>«Mars» oylik abonent to'lovi (100 000 so'm/oy):</b>\n" + "\n".join(monthly_status_lines),
        "────────────────────",
        "2️⃣ <b>Davlat Soliq (OFD) yillik litsenziyasi (440 000 so'm/yil):</b>\n" + "\n".join(annual_status_lines)
    ]

    if has_monthly_debt and not has_annual_debt:
        body_parts.append(
            "\n💡 <i>Oylik to'lovni Click orqali to'lash uchun «oylik to'layman» deb yozishingiz mumkin.</i>"
        )
    elif has_annual_debt and not has_monthly_debt:
        body_parts.append(
            "\n💡 <i>Yillik Soliq to'lovini to'lash uchun «yillik to'layman» deb yozishingiz mumkin.</i>"
        )
    elif has_monthly_debt and has_annual_debt:
        body_parts.append(
            "\n💡 <i>To'lov rekvizitlarini olish uchun «to'lov rekvizitlari» yoki «to'layman» deb yozing.</i>"
        )

    final_text = adapt_to_user_script("\n".join(body_parts), user_script)

    try:
        await message.reply(final_text, parse_mode="HTML")
    except Exception:
        await message.reply(final_text)

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

        if decision.reply_text:
            reply_text = adapt_to_user_script(decision.reply_text, user_script)
            try:
                await message.reply(reply_text, parse_mode="HTML")
            except Exception:
                await message.reply(reply_text)

            user_memory.add_user_message(chat_id, user_id, f"[Ekran rasmi] {caption}".strip())
            user_memory.add_assistant_message(chat_id, user_id, reply_text)

        if decision.should_notify_admin and decision.admin_alert_type == "tech_issue":
            await admin_manager.notify_technical_issue(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                org_name=decision.org_name or "",
                inn=decision.detected_inn or "",
                issue_summary=decision.admin_alert_text or "Texnik nosozlik",
                user_comment=caption,
                photo_file_id=file_id
            )

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
    if message.media_group_id and not _check_and_register_media_group(message.media_group_id):
        logger.info(f"Media group {message.media_group_id} ning keyingi rasmi o'tkazib yuborildi.")
        if message.photo:
            try:
                user_id = message.from_user.id if message.from_user else 0
                user_memory.set_last_photo(message.chat.id, user_id, message.photo[-1].file_id)
            except Exception:
                pass
        return

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
