import os
import io
import re
import logging
from aiogram import Router, types, Bot, F
from aiogram.enums import ChatType
from excel_manager import excel_manager, DATA_DIR
from image_analyzer import analyze_pos_screen, INCOMPLETE_SCREEN_REPLY
from user_memory import user_memory
from state_manager import get_last_file_message_id, set_last_file_message_id
from handlers.debt import format_debt_response

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


# 2. POS APPARATI EKRAN RASMLARINI TAHLIL QILISH
@router.message(F.photo)
async def handle_pos_photo(message: types.Message, bot: Bot):
    """Ekran rasmini AI yordamida professional tashxis qilish"""
    caption = message.caption or ""
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id
    
    # Agar rasm tagida INN yozilgan bo'lsa
    found_nums = re.findall(r"\b(\d{14}|\d{9})\b", caption)
    if found_nums:
        query_num = found_nums[0]
        results = excel_manager.search(query_num)
        org_name = results[0].get("name", "") if results else ""
        total_debt = sum(item.get("debt", 0.0) for item in results) if results else 0.0

        user_memory.set_last_id(chat_id, user_id, query_num, org_name=org_name, debt=total_debt)
        user_memory.set_last_topic(chat_id, user_id, "photo_with_inn")

        resp = format_debt_response(results)
        await message.reply(resp, parse_mode="HTML")

        if total_debt > 0:
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=148,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.error(f"To'lov videosini yuborishda xatolik: {e}")
        return

    # Android POS ekran tahlili: Soat, internet, xatolik kodi
    try:
        photo = message.photo[-1]
        file_io = io.BytesIO()
        await bot.download(photo, destination=file_io)
        image_bytes = file_io.getvalue()
        
        reply_text, video_id, detected_inn = analyze_pos_screen(image_bytes=image_bytes, user_caption=caption)
        
        # 1. Agar rasm haqiqiy kassa apparatiga tegishli bo'lmasa -> E'TIBORSIZ QOLDIRILADI (jim turadi)
        if not reply_text:
            return

        # 2. Agar apparat tepasida soat va tarmoq qatori ko'rinmasa -> To'liq ekran talab qilish
        if reply_text == INCOMPLETE_SCREEN_REPLY:
            await message.reply(INCOMPLETE_SCREEN_REPLY, parse_mode="HTML")
            return

        # 3. Agar rasmning o'zidan INN/JSHSHIR topilgan bo'lsa -> bazadan ham tekshirish va birga qo'shib berish
        if detected_inn:
            results = excel_manager.search(detected_inn)
            org_name = results[0].get("name", "") if results else ""
            total_debt = sum(item.get("debt", 0.0) for item in results) if results else 0.0

            user_memory.set_last_id(chat_id, user_id, detected_inn, org_name=org_name, debt=total_debt)
            user_memory.set_last_topic(chat_id, user_id, "photo_analysis_with_inn")

            debt_resp = format_debt_response(results)
            combined_resp = f"{reply_text}\n\n──────────────\n{debt_resp}" if reply_text else debt_resp
            try:
                await message.reply(combined_resp, parse_mode="HTML")
            except Exception:
                await message.reply(combined_resp)

            user_memory.add_user_message(chat_id, user_id, f"[Ekran rasmi] INN: {detected_inn}")
            user_memory.add_assistant_message(chat_id, user_id, combined_resp)

            if total_debt > 0:
                try:
                    await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=SOURCE_CHANNEL_ID,
                        message_id=148,
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    logger.error(f"To'lov videosini yuborishda xatolik: {e}")
            return

        # 4. Oddiy holatda AI tahlil matnini yuborish
        try:
            await message.reply(reply_text, parse_mode="HTML")
        except Exception:
            await message.reply(reply_text)

        # Xotiraga saqlash
        user_memory.add_user_message(chat_id, user_id, f"[Ekran rasmi] {caption}".strip())
        user_memory.add_assistant_message(chat_id, user_id, reply_text)
        user_memory.set_last_topic(chat_id, user_id, "photo_diagnosed")

        # Tashxis bo'yicha yechim videosi mavjud bo'lsa (masalan soat uchun 141)
        if video_id:
            try:
                await bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=SOURCE_CHANNEL_ID,
                    message_id=video_id,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.error(f"Tashxis videosini yuborishda xatolik: {e}")

    except Exception as e:
        logger.error(f"Rasmni tahlil qilishda xatolik: {e}")
