import os
import io
import re
import logging
from aiogram import Router, types, Bot, F
from aiogram.enums import ChatType

from excel_manager import excel_manager, DATA_DIR
from image_analyzer import extract_device_facts
from receipt_analyzer import extract_receipt_facts
from admin_manager import admin_manager
from core import core_engine, ActionType
from user_memory import user_memory
from state_manager import get_last_file_message_id, set_last_file_message_id

logger = logging.getLogger(__name__)

router = Router(name="media_router")

DESTINATION_CHANNEL_ID = -1003784534841  # marsfayllar
SOURCE_CHANNEL_ID = -1001641871516       # @POS_Terminal_UzSmart_Bank

RECEIPT_KEYWORDS = [
    "to'lov", "tolov", "chek", "kvitansiya", "click", "payme", "oplata",
    "to'ladim", "toladim", "to'landi", "tolandi", "pul o'tkazdim", "pul otkazdim"
]

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
        try:
            if message.chat.id == DESTINATION_CHANNEL_ID:
                last_msg_id = get_last_file_message_id()
                if last_msg_id and last_msg_id != message.message_id:
                    try:
                        await bot.delete_message(chat_id=DESTINATION_CHANNEL_ID, message_id=last_msg_id)
                        logger.info(f"Kanaldan avvalgi eski fayl posti o'chirildi (ID: {last_msg_id})")
                    except Exception as err:
                        logger.warning(f"Avvalgi fayl postini o'chirishda xatolik: {err}")
                set_last_file_message_id(message.message_id)

            os.makedirs(DATA_DIR, exist_ok=True)
            temp_file = os.path.join(DATA_DIR, f"temp_{doc.file_name}")
            await bot.download(doc, destination=temp_file)
            
            success = excel_manager.update_file(temp_file)
            if os.path.exists(temp_file):
                os.remove(temp_file)

            if success:
                logger.info(f"Yangi Excel bazasi yangilandi! Yozuvlar: {excel_manager.records_count}")
                if message.chat.type != ChatType.CHANNEL:
                    await message.reply(
                        f"✅ <b>Baza muvaffaqiyatli yangilandi!</b>\n"
                        f"📁 Fayl: <code>{doc.file_name}</code>\n"
                        f"📊 Jami yozuvlar: <b>{excel_manager.records_count} ta</b>",
                        parse_mode="HTML"
                    )
        except Exception as e:
            logger.error(f"Excel faylni yuklashda xatolik: {e}")
        return

    # B) PDF FORMATDAGI TO'LOV KVITANSIYASI
    if file_name.endswith(".pdf"):
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

            decision = core_engine.process_receipt_facts(
                facts=facts,
                chat_id=chat_id,
                user_id=user_id,
                user_comment=caption
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


# 2. RASMLARNI QABUL QILISH (POS EKRANI YOKI KVITANSIYA RASMI)
@router.message(F.photo)
async def handle_photo(message: types.Message, bot: Bot):
    """
    Rasm qabul qiluvchi markaziy handler:
    1. Agar to'lov kvitansiyasi bo'lsa -> Kvitansiya tahlili + Qarz solishtiruvi + Adminga bildirishnoma
    2. Agar POS apparati bo'lsa -> Ekran tashxisi + Qarz holati + Nosozlik bo'lsa adminga eskalatsiya
    3. Agar begona narsa bo'lsa -> Jim turish (Guardrail)
    """
    caption = message.caption or ""
    lower_caption = caption.lower()
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    try:
        photo = message.photo[-1]
        file_io = io.BytesIO()
        await bot.download(photo, destination=file_io)
        image_bytes = file_io.getvalue()

        # Izohda to'lov haqida so'zlar bo'lsa yoki oxirgi mavzu to'lov bo'lsa
        last_topic = user_memory.get_last_topic(chat_id, user_id)
        has_receipt_intent = any(kw in lower_caption for kw in RECEIPT_KEYWORDS) or last_topic in ["payment_instruction", "debt_checked"]

        # A) AGAR KVITANSIYA BO'LISHI EHTIMOLI YUQORI BO'LSA
        if has_receipt_intent:
            receipt_facts = extract_receipt_facts(
                file_bytes=image_bytes,
                filename="receipt.jpg",
                mime_type="image/jpeg",
                user_caption=caption
            )
            if receipt_facts.is_receipt:
                decision = core_engine.process_receipt_facts(
                    facts=receipt_facts,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_comment=caption
                )
                if decision.reply_text:
                    try:
                        await message.reply(decision.reply_text, parse_mode="HTML")
                    except Exception:
                        await message.reply(decision.reply_text)

                    user_memory.add_user_message(chat_id, user_id, f"[To'lov kvitansiyasi] {caption}".strip())
                    user_memory.add_assistant_message(chat_id, user_id, decision.reply_text)

                if decision.should_notify_admin and decision.receipt_facts:
                    await admin_manager.notify_receipt_escalation(
                        bot=bot,
                        user=message.from_user,
                        chat_id=chat_id,
                        receipt_facts=decision.receipt_facts,
                        debt_status_info=decision.debt_status_info,
                        file_id=photo.file_id,
                        is_photo=True
                    )
                return

        # B) KASSA APPARATI EKRANINI TAHLIL QILISH
        device_facts = extract_device_facts(image_bytes=image_bytes, user_caption=caption)

        # Agar kassa apparati bo'lmasa, har ehtimolga qarshi kvitansiya ekanligini yana bir bor tekshirish
        if not device_facts.is_real_pos_device and not device_facts.detected_inn:
            receipt_facts = extract_receipt_facts(
                file_bytes=image_bytes,
                filename="check.jpg",
                mime_type="image/jpeg",
                user_caption=caption
            )
            if receipt_facts.is_receipt:
                decision = core_engine.process_receipt_facts(
                    facts=receipt_facts,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_comment=caption
                )
                if decision.reply_text:
                    try:
                        await message.reply(decision.reply_text, parse_mode="HTML")
                    except Exception:
                        await message.reply(decision.reply_text)
                if decision.should_notify_admin and decision.receipt_facts:
                    await admin_manager.notify_receipt_escalation(
                        bot=bot,
                        user=message.from_user,
                        chat_id=chat_id,
                        receipt_facts=decision.receipt_facts,
                        debt_status_info=decision.debt_status_info,
                        file_id=photo.file_id,
                        is_photo=True
                    )
                return

            # Begona rasm -> Jim turish
            logger.info("Guardrail: Rasm kassa apparati ham, to'lov cheki ham emas. Javobsiz qoldirildi.")
            return

        # Yadro orqali qaror chiqarish
        decision = core_engine.process_device_facts(device_facts, chat_id=chat_id, user_id=user_id, user_comment=caption)

        if decision.action == ActionType.IGNORE:
            return

        # Foydalanuvchiga javob
        if decision.reply_text:
            try:
                await message.reply(decision.reply_text, parse_mode="HTML")
            except Exception:
                await message.reply(decision.reply_text)

            user_memory.add_user_message(chat_id, user_id, f"[Ekran rasmi] {caption}".strip())
            user_memory.add_assistant_message(chat_id, user_id, decision.reply_text)

        # ADMINGA ESKALATSIYA (INTERNET BOR + QARZ YO'Q + NOSOZLIK MAVJUD)
        if decision.should_notify_admin and decision.admin_alert_type == "tech_issue":
            await admin_manager.notify_technical_issue(
                bot=bot,
                user=message.from_user,
                chat_id=chat_id,
                org_name=decision.org_name or "",
                inn=decision.detected_inn or "",
                issue_summary=decision.admin_alert_text or "Texnik nosozlik",
                user_comment=caption,
                photo_file_id=photo.file_id
            )

        # Video qo'llanma
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

    except Exception as e:
        logger.error(f"Media handler ijrosida xatolik: {e}")
