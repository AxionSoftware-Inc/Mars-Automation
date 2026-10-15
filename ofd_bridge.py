import os
import re
import json
import time
import asyncio
import logging
from typing import Optional, Dict, Any, List
from aiogram import Bot, types

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OFD_CONFIG_FILE = os.path.join(DATA_DIR, "ofd_config.json")

DEFAULT_OFD_USERNAME = os.getenv("OFD_BOT_USERNAME", "ofd943_bot").lstrip("@").lower()
OFD_KNOWN_USERNAMES = {"ofd943_bot", "ofd943", "ofd_bot"}
OFD_KNOWN_BOT_IDS = {7032599443, 1248163578}
CACHE_TTL_SECONDS = 300  # 5 daqiqa kesh (bir xil INN qayta-qayta so'ralganda)

API_ID = int(os.getenv("TG_API_ID", "2040"))
API_HASH = os.getenv("TG_API_HASH", "b18441a1ff607e10a989891a5462e627")
USER_SESSION_FILE = os.path.join(DATA_DIR, "ofd_user.session")


class OFDBridgeManager:
    """
    Maxfiy guruh (yoki Telethon user-session) orqali @ofd943_bot bilan bog'lanish ko'prigi:
    1. Mijoz asosiy guruhda yoki bot lichkasida INN yuborganda, botimiz ushbu INNni maxfiy guruhga / @ofd943_bot ga yozadi.
    2. @ofd943_bot javob qaytaradi (1 ta yoki bir nechta ketma-ket xabar).
    3. Botimiz maxfiy guruhda @ofd943_bot ga hech qachon javob qaytarmaydi (cheksiz sikl bo'lmasligi uchun),
       faqat uning javobini ushlab olib, asosiy guruhdagi / lichkadagi mijozga chiqarib beradi.
    4. Parallel so'rovlar navbat (asyncio.Lock) bilan ketma-ket bajariladi — mijozlar javobi adashib ketmaydi.
    """

    def __init__(self, config_path: str = OFD_CONFIG_FILE):
        self.config_path = config_path
        self.ofd_username: str = DEFAULT_OFD_USERNAME
        self.ofd_group_id: Optional[int] = None
        self._query_lock = asyncio.Lock()
        self._active_collector: Optional[Dict[str, Any]] = None
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.load_config()

    def load_config(self):
        """Maxfiy guruh ID si va OFD username sozlamalarini yuklash"""
        env_group = os.getenv("OFD_GROUP_ID", "").strip()
        if env_group:
            try:
                self.ofd_group_id = int(env_group)
            except ValueError:
                pass

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("ofd_group_id"):
                    self.ofd_group_id = int(data["ofd_group_id"])
                if data.get("ofd_username"):
                    self.ofd_username = str(data["ofd_username"]).lstrip("@").lower()
                logger.info(
                    f"OFDBridge yuklandi: group_id={self.ofd_group_id}, ofd_username=@{self.ofd_username}"
                )
            except Exception as e:
                logger.error(f"OFDBridge config o'qishda xatolik: {e}")

    def save_config(self):
        """Maxfiy guruh ID sini doimiy faylga saqlash"""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "ofd_group_id": self.ofd_group_id,
                        "ofd_username": self.ofd_username,
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    },
                    f,
                    ensure_ascii=False,
                    indent=2
                )
            logger.info(f"OFDBridge config saqlandi: group_id={self.ofd_group_id}")
        except Exception as e:
            logger.error(f"OFDBridge config saqlashda xatolik: {e}")

    def set_ofd_group(self, chat_id: int) -> bool:
        """Maxfiy guruh yoki kanal ID sini o'rnatish"""
        if self.ofd_group_id != chat_id:
            self.ofd_group_id = chat_id
            self.save_config()
            return True
        return False

    def is_configured(self) -> bool:
        """Maxfiy guruh yoki kanal ulanganligini tekshirish"""
        return self.ofd_group_id is not None

    def is_ready(self) -> bool:
        """OFD ko'prigi tayyorligini (kanal yoki userbot sessiyasi borligini) tekshirish"""
        return self.ofd_group_id is not None or self.has_user_session()

    def is_ofd_user(self, user: Optional[types.User]) -> bool:
        """Xabar yuboruvchi @ofd943_bot (yoki ofd943, ofd_bot) ekanligini tekshirish"""
        if not user:
            return False
        uid = getattr(user, "id", None)
        if uid in OFD_KNOWN_BOT_IDS:
            return True
        uname = (getattr(user, "username", "") or "").lstrip("@").lower()
        fname = (getattr(user, "full_name", "") or "").strip().lower()
        return uname in OFD_KNOWN_USERNAMES or uname == self.ofd_username or "ofd" in uname or fname in ("ofd943", "ofd")

    def is_ofd_group(self, chat_id: int) -> bool:
        """Berilgan chat maxfiy OFD guruhi yoki kanali ekanligini tekshirish"""
        return self.ofd_group_id is not None and chat_id == self.ofd_group_id

    @staticmethod
    def _is_loading_placeholder(text: str) -> bool:
        """Agar @ofd943 avval 'Kuting...' kabi qisqa oraliq xabar yozsa, uni o'tkazib haqiqiy javobni kutish"""
        t = text.strip().lower()
        if len(t) > 40:
            return False
        loading_words = ["kuting", "tekshirilmoqda", "кутинг", "текширилмоқда", "загрузка", "подождите", "⏳"]
        return any(w in t for w in loading_words)

    @staticmethod
    def _is_ofd_signature_text(text: str) -> bool:
        """Xabar matni @ofd943_bot ning xos javobi ekanligini aniqlash"""
        t = text.lower()
        has_fm = any(w in t for w in ["fiskal modul", "фискал модул", "fmo", "stir:", "inn:"])
        has_status = any(w in t for w in [
            "faol holatda", "qarzdorlik mavjud", "qarzdorlik mavjud emas", "qarzdorlik yo'q",
            "qarzdorlik yo‘q", "bunday fiskal modul", "vmq-943", "to'lov qilish muddati", "to‘lov qilish muddati"
        ])
        return has_fm and has_status

    async def check_and_bind_chat_if_ofd(self, chat_id: int, bot: Bot) -> bool:
        """Berilgan guruh yoki kanalda @ofd943_bot borligini tekshirib, agar bo'lsa uni OFD ko'prigi qilib ulash"""
        try:
            admins = await bot.get_chat_administrators(chat_id)
            for a in admins:
                if self.is_ofd_user(a.user):
                    self.set_ofd_group(chat_id)
                    logger.info(f"✅ Maxfiy OFD kanali/guruhi @{self.ofd_username} adminligi orqali ulandi: chat_id={chat_id}")
                    return True
        except Exception as e:
            logger.debug(f"check_and_bind_chat_if_ofd xatoligi: {e}")
        return False

    async def handle_incoming_message(self, message: types.Message, bot: Optional[Bot] = None) -> bool:
        """
        Outer middleware orqali chaqiriladi (message, edited_message, channel_post, edited_channel_post).
        Agar xabar:
        1) Admin tomonidan /set_ofd_channel yoki /set_ofd_group buyrug'i yuborilgan bo'lsa -> ulash;
        2) Maxfiy OFD kanali / guruhi ichida bo'lsa -> javobni yig'ib olish yoki echo/loadingni filtrlash;
        3) @ofd943 dan kelgan bo'lsa -> tutib qolish va kerak bo'lsa avto-ulash.
        True qaytaradi (boshqa handlerlar ishlamaydi, cheksiz sikl bo'lmaydi!).
        """
        chat_id = message.chat.id
        user = message.from_user
        text = (message.text or message.caption or "").strip()
        lower_text = text.lower()

        # 1. Admin guruhda, kanalda yoki lichkada /set_ofd_channel yoki /set_ofd_group deb yozsa
        if lower_text.startswith(("/set_ofd_channel", "/set_ofd_group", "/ofd_kanal", "/ofd_guruh", "!ofd_kanal", "!ofd_guruh")):
            parts = text.split()
            target_chat_id = chat_id
            if len(parts) > 1:
                target_arg = parts[1].strip()
                if target_arg.startswith("https://t.me/"):
                    target_arg = "@" + target_arg.replace("https://t.me/", "").strip("/")
                try:
                    target_chat_id = int(target_arg)
                except ValueError:
                    target_chat_id = target_arg

            real_chat_id = target_chat_id
            if bot and isinstance(target_chat_id, str):
                try:
                    ch = await bot.get_chat(target_chat_id)
                    real_chat_id = ch.id
                except Exception:
                    pass

            if isinstance(real_chat_id, int):
                self.set_ofd_group(real_chat_id)
                logger.info(f"✅ Maxfiy OFD kanali/guruhi buyruq orqali ulandi: chat_id={real_chat_id}")
                confirm_msg = (
                    f"✅ <b>Maxfiy OFD ko'prigi muvaffaqiyatli ulandi!</b>\n\n"
                    f"🆔 Chat ID: <code>{real_chat_id}</code>\n"
                    f"🤖 OFD bot: @{self.ofd_username}\n\n"
                    f"Endi botda Fiskal modul yoki INN tekshirilganda, ushbu chat orqali "
                    f"@{self.ofd_username} dan yillik to'lov ma'lumoti olinadi."
                )
                if bot:
                    try:
                        await message.reply(confirm_msg, parse_mode="HTML")
                    except Exception:
                        try:
                            if user:
                                await bot.send_message(chat_id=user.id, text=confirm_msg, parse_mode="HTML")
                        except Exception:
                            pass
                return True


        # 2. Agar maxfiy chat hali sozlanmagan bo'lsa -> avtomatik aniqlashga urinish
        if self.ofd_group_id is None and bot and message.chat.type in ("channel", "group", "supergroup"):
            # A) Agar xabar yuboruvchi @ofd943 bo'lsa
            if self.is_ofd_user(user):
                self.set_ofd_group(chat_id)
                logger.info(f"✅ Maxfiy OFD guruhi @{self.ofd_username} xabari orqali AVTOMATIK ulandi: chat_id={chat_id}")
            # B) Agar xabar matni OFD botining rasmiy javob formatiga to'g'ri kelsa (ayniqsa kanallarda user=None bo'ladi)
            elif text and self._is_ofd_signature_text(text):
                self.set_ofd_group(chat_id)
                logger.info(f"✅ Maxfiy OFD kanali xabar matni imzosi orqali AVTOMATIK ulandi: chat_id={chat_id}")
            # C) Chat adminlari orasida @ofd943_bot borligini tekshirish
            else:
                await self.check_and_bind_chat_if_ofd(chat_id, bot)

        # 3. Agar xabar maxfiy OFD chatida bo'lsa (channel, group yoki supergroup):
        if self.is_ofd_group(chat_id):
            collector = self._active_collector

            # A) Agar bu bizning botimiz yuborgan so'rov bo'lsa (echo) -> o'tkazib yuborish
            if collector:
                sent_msg_id = collector.get("sent_message_id")
                sent_code = collector.get("inn", "")
                if sent_msg_id and message.message_id == sent_msg_id:
                    return True
                if text and sent_code and text.strip().upper() == sent_code:
                    return True

            # B) Agar bu loading indicator bo'lsa ("Kuting...", "Tekshirilmoqda...") -> o'tkazib yuborish
            if text and self._is_loading_placeholder(text):
                return True

            # C) Agar bu OFD botining javobi bo'lsa -> yig'ib olish
            if text:
                self._record_ofd_reply_chunk(text)

            # Maxfiy OFD chatidagi barcha xabarlar tutib qolinadi (boshqa handlerlar ishlamaydi, sikl bo'lmaydi!)
            return True

        # 4. Maxfiy chatdan tashqarida @ofd943 dan to'g'ridan-to'g'ri kelgan xabarlar (sikl bo'lmasligi uchun)
        if self.is_ofd_user(user):
            return True

        return False

    def _record_ofd_reply_chunk(self, text: str):
        """@ofd943 dan kelgan javob matnini yig'ish (agar 2-3 ta xabar ketma-ket kelsa birlashtirish)"""
        collector = self._active_collector
        if not collector or collector.get("done"):
            return

        collector["chunks"].append(text)
        event: asyncio.Event = collector["first_chunk_event"]
        if not event.is_set():
            event.set()

    def has_user_session(self) -> bool:
        """Telethon user-akkaunt sessiyasi mavjudligini tekshirish"""
        return os.path.exists(USER_SESSION_FILE)

    async def _query_telethon(self, inn: str, timeout: float = 9.0) -> Optional[str]:
        """Telethon user-akkaunt orqali maxfiy guruhga yoki to'g'ridan-to'g'ri @ofd943_bot ga INN yuborib javob olish"""
        if not self.has_user_session():
            return None
        try:
            from telethon import TelegramClient
            session_prefix = os.path.join(DATA_DIR, "ofd_user")
            client = TelegramClient(session_prefix, API_ID, API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                return None

            target = self.ofd_group_id if (self.ofd_group_id and self.is_configured()) else self.ofd_username
            sent = await client.send_message(target, inn)
            logger.info(f"📤 OFDBridge (Telethon Userbot): {target} ga INN yuborildi: {inn}")

            t0 = time.time()
            reply_texts = []
            collected_ids = set()

            while time.time() - t0 < timeout:
                await asyncio.sleep(0.6)
                msgs = await client.get_messages(target, limit=5)
                for m in msgs:
                    if m.id > sent.id and m.id not in collected_ids:
                        sender = await m.get_sender()
                        s_uname = (getattr(sender, 'username', '') or '').lstrip('@').lower()
                        s_fname = (getattr(sender, 'first_name', '') or '').strip().lower()
                        if s_uname in OFD_KNOWN_USERNAMES or s_uname == self.ofd_username or s_fname == "ofd943":
                            t = (m.text or "").strip()
                            if t and not self._is_loading_placeholder(t):
                                collected_ids.add(m.id)
                                reply_texts.append(t)
                if reply_texts:
                    await asyncio.sleep(0.5)
                    break

            await client.disconnect()
            if reply_texts:
                full_reply = "\n\n".join(reply_texts).strip()
                logger.info(f"📥 OFDBridge (Telethon Userbot): @{self.ofd_username} dan javob olindi (len={len(full_reply)})")
                return full_reply
        except Exception as e:
            logger.error(f"❌ Telethon query xatoligi: {e}")
        return None

    async def query_fiscal_module(self, bot: Optional[Bot], fiscal_code: str, timeout: float = 9.0) -> Optional[str]:
        """
        Maxfiy guruhga yoki @ofd943_bot ga Fiskal modul seriya raqamini (LG..., YG... va h.k.) yuborib javob olish.
        Agar Telethon user-akkaunt ulangan bo'lsa -> Userbot orqali so'raydi (Bot-to-Bot cheklovini 100% chetlab o'tadi!).
        Aks holda -> Bot API orqali maxfiy guruhga yuboradi.
        """
        clean_code = re.sub(r"[^A-Za-z0-9]", "", str(fiscal_code)).upper()
        if not clean_code or len(clean_code) < 8 or len(clean_code) > 20:
            return None

        # 1. Keshni tekshirish
        now = time.time()
        cached = self._cache.get(clean_code)
        if cached and (now - cached["ts"] < CACHE_TTL_SECONDS):
            return cached["text"]

        # 2. Navbat bilan so'rov yuborish
        async with self._query_lock:
            now = time.time()
            cached = self._cache.get(clean_code)
            if cached and (now - cached["ts"] < CACHE_TTL_SECONDS):
                return cached["text"]

            # A) Agar Telethon user session mavjud bo'lsa -> Userbot orqali so'rash
            if self.has_user_session():
                tele_res = await self._query_telethon(clean_code, timeout=timeout)
                if tele_res:
                    self._cache[clean_code] = {"text": tele_res, "ts": time.time()}
                    return tele_res

            # B) Agar Telethon bo'lmasa -> Bot API orqali maxfiy guruhga yozish
            if not self.is_configured() or not self.ofd_group_id or not bot:
                return None

            first_event = asyncio.Event()
            collector: Dict[str, Any] = {
                "inn": clean_code,
                "chunks": [],
                "first_chunk_event": first_event,
                "done": False,
                "sent_message_id": None
            }
            self._active_collector = collector

            try:
                sent = await bot.send_message(chat_id=self.ofd_group_id, text=clean_code)
                collector["sent_message_id"] = getattr(sent, "message_id", None)
                logger.info(f"📤 OFDBridge (Bot API): Maxfiy chatga ({self.ofd_group_id}) FM yuborildi: {clean_code} (msg_id={collector['sent_message_id']})")

                await asyncio.wait_for(first_event.wait(), timeout=timeout)
                await asyncio.sleep(0.6)
                collector["done"] = True

                full_reply = "\n\n".join(collector["chunks"]).strip()
                if full_reply:
                    self._cache[clean_code] = {"text": full_reply, "ts": time.time()}
                    logger.info(f"📥 OFDBridge: @{self.ofd_username} dan javob olindi (FM={clean_code}, len={len(full_reply)})")
                    return full_reply

            except asyncio.TimeoutError:
                logger.warning(f"⏳ OFDBridge: @{self.ofd_username} {timeout}s ichida javob bermadi (FM={clean_code})")
            except Exception as e:
                logger.error(f"❌ OFDBridge query_fiscal_module xatoligi (FM={clean_code}): {e}")
            finally:
                collector["done"] = True
                if self._active_collector is collector:
                    self._active_collector = None

        return None

    async def get_status_info(self, bot: Optional[Bot] = None) -> Dict[str, Any]:
        """OFD ko'prigi holatini batafsil tekshirish (admin diagnostikasi uchun)"""
        status: Dict[str, Any] = {
            "configured": self.is_configured(),
            "chat_id": self.ofd_group_id,
            "ofd_username": self.ofd_username,
            "has_user_session": self.has_user_session(),
            "cached_keys_count": len(self._cache),
            "chat_title": None,
            "chat_type": None,
            "ofd_bot_present": False,
            "our_bot_present": False,
            "can_post_messages": None,
            "error": None
        }

        if self.ofd_group_id and bot:
            try:
                chat = await bot.get_chat(self.ofd_group_id)
                status["chat_title"] = chat.title or chat.first_name or "Nomsiz"
                status["chat_type"] = chat.type
                try:
                    admins = await bot.get_chat_administrators(self.ofd_group_id)
                    me = await bot.get_me()
                    for a in admins:
                        if a.user.id == me.id:
                            status["our_bot_present"] = True
                            if chat.type == "channel":
                                status["can_post_messages"] = getattr(a, "can_post_messages", True)
                        if self.is_ofd_user(a.user):
                            status["ofd_bot_present"] = True
                except Exception as ex_admin:
                    status["admin_check_note"] = str(ex_admin)
            except Exception as e:
                status["error"] = str(e)

        return status

    async def test_connection(self, bot: Bot, test_code: str = "LG420230615712", timeout: float = 8.0) -> Dict[str, Any]:
        """Jonli OFD so'rovini yuborib javob tezligi va natijasini o'lchash"""
        t0 = time.time()
        # Keshni chetlab o'tish uchun keshdan tozalash
        clean_code = re.sub(r"[^A-Za-z0-9]", "", str(test_code)).upper()
        if clean_code in self._cache:
            del self._cache[clean_code]

        reply = await self.query_fiscal_module(bot, clean_code, timeout=timeout)
        duration = round(time.time() - t0, 2)
        return {
            "success": bool(reply),
            "code": clean_code,
            "duration_sec": duration,
            "reply": reply
        }

    async def query_inn(self, bot: Optional[Bot], inn: str, timeout: float = 9.0) -> Optional[str]:
        """Eski kod bilan moslik uchun alias"""
        return await self.query_fiscal_module(bot, inn, timeout=timeout)

    async def sync_excel_from_channel(self, channel_id: int = -1001795471853) -> bool:
        """
        Telethon user-akkaunt orqali Excel bazasi yuboriladigan kanaldan (masalan: Абонент тулови🏦💸💰 -1001795471853)
        eng so'nggi .xlsx faylni avtomatik yuklab olib, excel_manager bazasini yangilash.
        """
        if not self.has_user_session():
            logger.warning("sync_excel_from_channel: User session topilmadi.")
            return False

        target_channel = int(os.getenv("EXCEL_CHANNEL_ID", str(channel_id)))
        client = None
        try:
            from telethon import TelegramClient
            from excel_manager import excel_manager
            from state_manager import get_last_excel_channel_msg_id, set_last_excel_channel_msg_id

            session_prefix = os.path.join(DATA_DIR, "ofd_user")
            client = TelegramClient(session_prefix, API_ID, API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning("sync_excel_from_channel: Telethon user-akkaunt avtorizatsiyadan o'tmagan.")
                return False

            last_synced_id = get_last_excel_channel_msg_id()
            found_msg = None

            async for message in client.iter_messages(target_channel, limit=20):
                if message.file and getattr(message.file, "name", None):
                    fn = message.file.name.lower()
                    if fn.endswith(".xlsx") or fn.endswith(".xls"):
                        found_msg = message
                        break

            if not found_msg:
                logger.info(f"sync_excel_from_channel: Kanaldan ({target_channel}) Excel fayl topilmadi.")
                return False

            if last_synced_id and found_msg.id <= last_synced_id:
                logger.info(f"sync_excel_from_channel: Yangi Excel fayl yo'q (oxirgi yuklangan msg_id={last_synced_id}).")
                return False

            temp_path = os.path.join(DATA_DIR, f"auto_sync_{found_msg.file.name}")
            logger.info(f"📥 sync_excel_from_channel: Yangi Excel fayl yuklab olinmoqda (msg_id={found_msg.id}, name={found_msg.file.name})...")
            await client.download_media(found_msg, file=temp_path)

            if os.path.exists(temp_path):
                success = excel_manager.update_file(temp_path)
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

                if success:
                    set_last_excel_channel_msg_id(found_msg.id)
                    logger.info(
                        f"✅ sync_excel_from_channel: Baza muvaffaqiyatli yangilandi! "
                        f"MsgID={found_msg.id}, Yozuvlar={excel_manager.records_count}"
                    )
                    return True
                else:
                    logger.error("❌ sync_excel_from_channel: excel_manager faylni qabul qilmadi.")
                    return False

        except Exception as e:
            logger.error(f"❌ sync_excel_from_channel xatoligi: {e}", exc_info=True)
            return False
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass

        return False


ofd_bridge = OFDBridgeManager()



