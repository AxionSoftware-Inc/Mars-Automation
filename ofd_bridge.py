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
OFD_KNOWN_USERNAMES = {"ofd943_bot", "ofd943"}
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
        """Maxfiy guruh ID sini o'rnatish"""
        if self.ofd_group_id != chat_id:
            self.ofd_group_id = chat_id
            self.save_config()
            return True
        return False

    def is_configured(self) -> bool:
        """Maxfiy guruh ulanganligini tekshirish"""
        return self.ofd_group_id is not None

    def is_ofd_user(self, user: Optional[types.User]) -> bool:
        """Xabar yuboruvchi @ofd943_bot (yoki ofd943) ekanligini tekshirish"""
        if not user:
            return False
        uname = (getattr(user, "username", "") or "").lstrip("@").lower()
        fname = (getattr(user, "full_name", "") or "").strip().lower()
        return uname in OFD_KNOWN_USERNAMES or uname == self.ofd_username or fname == "ofd943"

    def is_ofd_group(self, chat_id: int) -> bool:
        """Berilgan chat maxfiy OFD guruhi ekanligini tekshirish"""
        return self.ofd_group_id is not None and chat_id == self.ofd_group_id

    @staticmethod
    def _is_loading_placeholder(text: str) -> bool:
        """Agar @ofd943 avval 'Kuting...' kabi qisqa oraliq xabar yozsa, uni o'tkazib haqiqiy javobni kutish"""
        t = text.strip().lower()
        if len(t) > 40:
            return False
        loading_words = ["kuting", "tekshirilmoqda", "кутинг", "текширилмоқда", "загрузка", "подождите", "⏳"]
        return any(w in t for w in loading_words)

    async def handle_incoming_message(self, message: types.Message, bot: Optional[Bot] = None) -> bool:
        """
        Outer middleware orqali chaqiriladi.
        Agar xabar:
        1) @ofd943 dan kelgan bo'lsa, YOKI
        2) Maxfiy OFD guruhi ichida yozilgan bo'lsa, YOKI
        3) Admin tomonidan /set_ofd_group buyrug'i yuborilgan bo'lsa ->
        shu yerning o'zida ushlab qolinadi va True qaytaradi (boshqa handlerlar ishlamaydi, sikl bo'lmaydi!).
        """
        chat_id = message.chat.id
        user = message.from_user
        text = (message.text or message.caption or "").strip()

        # 1. Admin guruhda /set_ofd_group yoki /ofd_guruh deb yozsa -> shu guruhni maxfiy OFD guruh sifatida ulash
        if text.lower().startswith(("/set_ofd_group", "/ofd_guruh", "!ofd_guruh")):
            self.set_ofd_group(chat_id)
            logger.info(f"✅ Maxfiy OFD guruhi buyruq orqali ulandi: chat_id={chat_id}")
            # Guruh ichiga yozmasdan (chunki @ofd943 javob qaytarib yuboradi), adminga lichkada xabar berish:
            if bot and user:
                try:
                    await bot.send_message(
                        chat_id=user.id,
                        text=(
                            f"✅ <b>Maxfiy OFD guruhi muvaffaqiyatli ulandi!</b>\n"
                            f"🆔 Guruh ID: <code>{chat_id}</code>\n"
                            f"🤖 OFD bot: @{self.ofd_username}\n\n"
                            f"Endi asosiy guruhda yoki botda INN tekshirilganda, botimiz avtomatik shu maxfiy guruh orqali "
                            f"@{self.ofd_username} dan yillik/OFD ma'lumotini olib mijozga chiqarib beradi."
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            return True

        # 2. Agar xabar @ofd943 dan kelgan bo'lsa
        if self.is_ofd_user(user):
            # Agar maxfiy guruh hali sozlanmagan bo'lsa yoki bu kichik maxfiy guruh bo'lsa -> avtomatik ulash!
            if self.ofd_group_id is None and message.chat.type in ("group", "supergroup"):
                should_bind = True
                if bot:
                    try:
                        member_count = await bot.get_chat_member_count(chat_id)
                        # Katta mijozlar guruhini adashib ulab qo'ymaslik uchun (maxfiy guruhda odatda 3-15 kishi bo'ladi)
                        if member_count > 35:
                            should_bind = False
                    except Exception:
                        pass
                if should_bind:
                    self.set_ofd_group(chat_id)
                    logger.info(f"✅ Maxfiy OFD guruhi @{self.ofd_username} xabari orqali AVTOMATIK ulandi: chat_id={chat_id}")

            # Agar hozirgi vaqtda OFD so'rovi javob kutayotgan bo'lsa va xabar maxfiy guruhdan kelgan bo'lsa
            if self.is_ofd_group(chat_id) and text and not self._is_loading_placeholder(text):
                self._record_ofd_reply_chunk(text)

            # @ofd943 ning har qanday xabariga botimiz HECH QACHON javob yozmasligi shart!
            return True

        # 3. Agar xabar maxfiy OFD guruhi ichida boshqa a'zo tomonidan yozilgan bo'lsa ham,
        # oddiy mijoz handlerlari (qarz, AI suhbat va h.k.) maxfiy guruh ichida ishlamasligi kerak!
        if self.is_ofd_group(chat_id):
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
                "done": False
            }
            self._active_collector = collector

            try:
                await bot.send_message(chat_id=self.ofd_group_id, text=clean_code)
                logger.info(f"📤 OFDBridge (Bot API): Maxfiy guruhga ({self.ofd_group_id}) FM yuborildi: {clean_code}")

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

    async def query_inn(self, bot: Optional[Bot], inn: str, timeout: float = 9.0) -> Optional[str]:
        """Eski kod bilan moslik uchun alias"""
        return await self.query_fiscal_module(bot, inn, timeout=timeout)


ofd_bridge = OFDBridgeManager()


