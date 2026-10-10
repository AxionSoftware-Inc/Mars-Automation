import os
import io
import logging
from aiogram import Router, types, Bot, F
from aiogram.enums import ChatType

from excel_manager import excel_manager, DATA_DIR
from image_analyzer import extract_device_facts
from core import core_engine, ActionType
from user_memory import user_memory
from state_manager import get_last_file_message_id, set_last_file_message_id

logger = logging.getLogger(__name__)

router = Router(name="media_router")

DESTINATION_CHANNEL_ID = -1003784534841  # marsfayllar
SOURCE_CHANNEL_ID = -1001641871516       # @POS_Terminal_UzSmart_Bank

# 1. EXCEL FAYLLARNI QABUL QILISH VA BAZANI YANGILASH
@router.channel_post(F.document)
@router.message(F.document)
async def handle_excel_document(message: types.Message, bot: Bot):
    """Kanal yoki adminga yangi Excel fayl yuborilganda bazani yangilash"""
    doc = message.document
    if not doc or not doc.file_name:
        return

    if not (doc.file_name.endswith(".xlsx") or doc.file_name.endswith(".xls")):
        return

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
        logger.error(f"Faylni yuklashda xatolik: {e}")


# 2. POS APPARATI EKRAN RASMLARINI TAHLIL QILISH (YADRO ORQALI)
@router.message(F.photo)
async def handle_pos_photo(message: types.Message, bot: Bot):
    """
    Rasm qabul qiluvchi handler:
    Faqat rasmni yuklab oladi -> Sensorga beradi -> Yadroga uzatadi -> Qarorni Telegramga jo'natadi.
    Hech qanday ichki if-else chalkashliklarsiz sof orkestratsiya!
    """
    caption = message.caption or ""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    try:
        photo = message.photo[-1]
        file_io = io.BytesIO()
        await bot.download(photo, destination=file_io)
        image_bytes = file_io.getvalue()

        # 1-BOSQICH (SENSOR): Faktlarni ajratib olish
        facts = extract_device_facts(image_bytes=image_bytes, user_caption=caption)

        # 2-BOSQICH (YADRO): Markaziy qarorlar tizimi
        decision = core_engine.process_device_facts(facts, chat_id=chat_id, user_id=user_id)

        # 3-BOSQICH (RUNNER): Yadroning chiqargan qarorini Telegramda ijro etish
        if decision.action == ActionType.IGNORE:
            logger.info(f"Yadro qarori: IGNORE ({decision.log_reason}) -> Javobsiz qoldirildi.")
            return

        # Matnli javob yuborish
        if decision.reply_text:
            try:
                await message.reply(decision.reply_text, parse_mode="HTML")
            except Exception:
                await message.reply(decision.reply_text)

            # Xotiraga saqlash
            user_memory.add_user_message(chat_id, user_id, f"[Ekran rasmi] {caption}".strip())
            user_memory.add_assistant_message(chat_id, user_id, decision.reply_text)

        # Video jo'natish (agar yadro video belgilagan bo'lsa)
        if decision.video_id:
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=decision.video_id,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.error(f"Yadro belgilagan videoni yuborishda xatolik (ID: {decision.video_id}): {e}")

    except Exception as e:
        logger.error(f"Media handler ijrosida kutilmagan xatolik: {e}")
