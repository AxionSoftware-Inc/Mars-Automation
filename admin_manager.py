import os
import json
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from aiogram import Bot, types

load_dotenv()
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ADMIN_CONFIG_PATH = os.path.join(DATA_DIR, "admin_config.json")

DEFAULT_ADMIN_USERNAMES = ["yashnarbek_butaev"]

DEFAULT_CONTACTS = [
    {
        "name": "Bosh administrator (Eskalatsiya va to'lovlar)",
        "phone": "@Yashnarbek_butaev",
        "role": "Bosh admin"
    },
    {
        "name": "Texnik xizmat ko'rsatish bo'limi",
        "phone": "+998 75 522 75 00",
        "role": "Bosh mutaxassis / Usta"
    },
    {
        "name": "Mijozlar bilan ishlash va to'lovlar bo'limi",
        "phone": "+998 90 999 00 11",
        "role": "Bosh operator"
    }
]

class AdminManager:
    """
    Adminlar, mas'ul xodimlar kontaktlari va xabarnomalar (Notification/Escalation) boshqaruvchisi.
    Bosh admin: @Yashnarbek_butaev
    """
    def __init__(self, config_path: str = ADMIN_CONFIG_PATH):
        self.config_path = config_path
        self.admin_ids: List[int] = []
        self.admin_usernames: List[str] = [u.lower().replace("@", "") for u in DEFAULT_ADMIN_USERNAMES]
        self.contacts: List[Dict[str, str]] = []
        self.notification_channel_id: Optional[int] = None
        self.load_config()

    def load_config(self):
        """Konfiguratsiyani yuklash (.env va JSON fayldan)"""
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # 1. .env fayldan ADMINS ni o'qish
        env_admins_raw = os.getenv("ADMINS") or os.getenv("ADMIN_ID") or ""
        env_admin_ids = []
        for part in env_admins_raw.split(","):
            part = part.strip()
            if part.isdigit():
                env_admin_ids.append(int(part))

        # 2. JSON fayldan o'qish
        loaded_from_file = False
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    file_admin_ids = data.get("admin_ids", [])
                    file_usernames = data.get("admin_usernames", DEFAULT_ADMIN_USERNAMES)
                    self.admin_usernames = list(set([u.lower().replace("@", "") for u in file_usernames] + self.admin_usernames))
                    self.contacts = data.get("contacts", DEFAULT_CONTACTS)
                    self.notification_channel_id = data.get("notification_channel_id")
                    
                    # Birlashtirish (takrorlanmas)
                    combined_admins = list(set(env_admin_ids + [int(i) for i in file_admin_ids if str(i).isdigit()]))
                    self.admin_ids = combined_admins
                    loaded_from_file = True
            except Exception as e:
                logger.error(f"Admin konfiguratsiyasini o'qishda xatolik: {e}")

        if not loaded_from_file:
            self.admin_ids = env_admin_ids
            self.contacts = DEFAULT_CONTACTS
            self.save_config()

        logger.info(f"AdminManager yuklandi: {len(self.admin_ids)} ta admin ID, {self.admin_usernames} usernames, {len(self.contacts)} ta kontakt.")

    def save_config(self):
        """Konfiguratsiyani saqlash"""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            data = {
                "admin_ids": self.admin_ids,
                "admin_usernames": self.admin_usernames,
                "contacts": self.contacts,
                "notification_channel_id": self.notification_channel_id
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Admin konfiguratsiyasini saqlashda xatolik: {e}")

    def check_and_register_username(self, user_id: int, username: Optional[str]) -> bool:
        """
        Foydalanuvchi username'i bosh admin (@Yashnarbek_butaev) ekanligini tekshirish
        va agar mos kelsa, uning ID sini avtomatik adminlar ro'yxatiga qo'shish.
        """
        if not username:
            return False
        clean_user = username.lower().replace("@", "").strip()
        if clean_user in self.admin_usernames:
            if user_id not in self.admin_ids:
                self.admin_ids.append(user_id)
                self.save_config()
                logger.info(f"Bosh admin @{username} Telegram ID {user_id} bilan avtomatik bog'landi!")
                return True
        return False

    def is_admin(self, user_id: int, username: Optional[str] = None) -> bool:
        """Foydalanuvchi admin ekanligini ID yoki username bo'yicha tekshirish"""
        if user_id in self.admin_ids:
            return True
        if username:
            clean_user = username.lower().replace("@", "").strip()
            if clean_user in self.admin_usernames:
                self.check_and_register_username(user_id, username)
                return True
        return False

    def get_admin_ids(self) -> List[int]:
        """Barcha admin Telegram ID lari"""
        return self.admin_ids

    def add_admin(self, user_id: int) -> bool:
        """Yangi admin qo'shish"""
        if user_id not in self.admin_ids:
            self.admin_ids.append(user_id)
            self.save_config()
            logger.info(f"Yangi admin qo'shildi: {user_id}")
            return True
        return False

    def remove_admin(self, user_id: int) -> bool:
        """Adminni o'chirish"""
        if user_id in self.admin_ids:
            self.admin_ids.remove(user_id)
            self.save_config()
            logger.info(f"Admin o'chirildi: {user_id}")
            return True
        return False

    def get_contacts_display(self) -> str:
        """Foydalanuvchilarga ko'rsatiladigan chiroyli formatlangan kontaktlar matni"""
        if not self.contacts:
            return "📞 <b>Bosh admin:</b> @Yashnarbek_butaev\n«Mars Elektron Texnika» servis markazi"

        lines = ["📞 <b>Mas'ul mutaxassislar kontaktlari:</b>"]
        for c in self.contacts:
            name = c.get("name", "Mutaxassis")
            phone = c.get("phone", "")
            role = c.get("role", "")
            role_str = f" <i>({role})</i>" if role else ""
            lines.append(f"▫️ <b>{name}{role_str}:</b> <code>{phone}</code>")

        lines.append("⏰ <b>Ish vaqti:</b> Dushanba - Shanba 09:00 dan 18:00 gacha")
        return "\n".join(lines)

    def add_contact(self, name: str, phone: str, role: str = "") -> bool:
        """Yangi kontakt qo'shish"""
        for c in self.contacts:
            if c.get("phone") == phone:
                c["name"] = name
                c["role"] = role
                self.save_config()
                return True
        self.contacts.append({"name": name, "phone": phone, "role": role})
        self.save_config()
        return True

    def remove_contact(self, phone: str) -> bool:
        """Kontaktni telefon raqami bo'yicha o'chirish"""
        initial_len = len(self.contacts)
        self.contacts = [c for c in self.contacts if c.get("phone") != phone]
        if len(self.contacts) < initial_len:
            self.save_config()
            return True
        return False

    async def notify_admins(
        self,
        bot: Bot,
        text: str,
        photo_file_id: Optional[str] = None,
        document_file_id: Optional[str] = None,
        reply_markup: Optional[Any] = None
    ):
        """Barcha adminlarga (shu jumladan @Yashnarbek_butaev) xabar yuborish"""
        targets = list(set(self.admin_ids))
        if self.notification_channel_id:
            targets.append(self.notification_channel_id)

        if not targets:
            logger.warning(
                "Adminga xabarnoma yuborilmadi: Hali birorta ham admin ID bog'lanmagan. "
                "@Yashnarbek_butaev botga /start bosishi yoki bir marta yozishi bilan ID avtomatik saqlanadi."
            )
            return

        for target_id in targets:
            try:
                if photo_file_id:
                    await bot.send_photo(
                        chat_id=target_id,
                        photo=photo_file_id,
                        caption=text,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                elif document_file_id:
                    await bot.send_document(
                        chat_id=target_id,
                        document=document_file_id,
                        caption=text,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                else:
                    await bot.send_message(
                        chat_id=target_id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
            except Exception as e:
                logger.warning(f"Adminga ({target_id}) xabar yetkazishda xatolik: {e}")

    async def notify_receipt_escalation(
        self,
        bot: Bot,
        user: Optional[types.User],
        chat_id: int,
        receipt_facts: Any,
        debt_status_info: Dict[str, Any],
        file_id: Optional[str] = None,
        is_photo: bool = True
    ):
        """Yangi to'lov kvitansiyasi bo'yicha @Yashnarbek_butaev va adminlarga to'liq hisobot yuborish"""
        from core.models import extract_clean_inn

        user_name = user.full_name if user else "Noma'lum"
        user_username = f"@{user.username}" if (user and user.username) else "Yo'q"
        user_id = user.id if user else 0

        org_name = debt_status_info.get("org_name") or getattr(receipt_facts, "payer_name", "") or "Aniqlanmadi"
        
        raw_inn = debt_status_info.get("inn") or getattr(receipt_facts, "payer_inn", None)
        clean_inn = extract_clean_inn(str(raw_inn)) if raw_inn else None
        is_inn_missing = bool(debt_status_info.get("inn_missing") or not clean_inn)

        paid_amount = getattr(receipt_facts, "amount", 0.0)
        prev_debt = debt_status_info.get("prev_debt", 0.0)
        remaining_debt = debt_status_info.get("remaining_debt", 0.0)
        debt_covered = debt_status_info.get("debt_covered", False)
        is_annual = debt_status_info.get("is_annual", False)

        # Tuman (Hudud) aniqlash
        tuman = debt_status_info.get("tuman", "")
        if not tuman and clean_inn:
            from excel_manager import excel_manager
            tuman = excel_manager.get_district_for_inn(clean_inn)
        tuman_line = f"📍 <b>Hudud / Tuman:</b> {tuman}\n" if tuman else ""

        # To'lov maqsadi
        purpose_label = getattr(receipt_facts, "purpose_label", "") or debt_status_info.get("purpose_label", "")
        payment_purpose = getattr(receipt_facts, "payment_purpose", "") or debt_status_info.get("payment_purpose", "")
        purpose_line = f"🎯 <b>To'lov maqsadi:</b> <b>{purpose_label}</b>\n" if (purpose_label and payment_purpose != "monthly_subscription") else ""

        # Firibgarlik, Dublikat va Eski chek ogohlantirishlari
        fraud_warnings = []
        is_dup = getattr(receipt_facts, "is_duplicate", False) or debt_status_info.get("is_duplicate", False)
        if is_dup:
            tx_id = getattr(receipt_facts, "transaction_id", "") or "-"
            fraud_warnings.append(f"🚨 <b>OGOHLANTIRISH: DUBLIKAT TRANZAKSIYA!</b>\nUshbu chek (ID: <code>{tx_id}</code>) avval ham tizimga yuborilgan!")

        is_old = getattr(receipt_facts, "is_old_receipt", False) or debt_status_info.get("is_old_receipt", False)
        old_warn_text = getattr(receipt_facts, "old_receipt_warning", "") or debt_status_info.get("old_receipt_warning", "")
        if is_old:
            fraud_warnings.append(f"⚠️ <b>OGOHLANTIRISH: ESKI SANADAGI CHEK!</b>\n{old_warn_text or 'Kvitansiya sanasi 30 kundan eski!'}")

        fraud_header = ("\n" + "\n\n".join(fraud_warnings) + "\n────────────────────\n") if fraud_warnings else ""

        # Telegram mobilda oson nusxa olish uchun pastda alohida INN bloki
        if clean_inn:
            inn_line = f"<code>{clean_inn}</code>"
            bottom_inn_block = (
                f"📋 <b>INN (nusxa olish uchun):</b>\n"
                f"<code>{clean_inn}</code>"
            )
        else:
            inn_line = "❌ Topilmadi (Chekda yo'q yoki 000)"
            bottom_inn_block = (
                f"⚠️ <b>DIQQAT: Kvitansiyadan INN topilmadi!</b>\n"
                f"<i>(Chekda INN ko'rsatilmagan yoki '000' bo'sh qoldirilgan. Mijozdan INN so'ralmoqda)</i>"
            )

        if is_annual:
            status_emoji = "🏛"
            status_text = "<b>YILLIK FISKAL MODUL TO'LOVI («Yangi Texnologiyalar» DUK)</b>"
            text = (
                f"🏛 <b>YANGI YILLIK FISKAL MODUL TO'LOVI KVITANSIYASI!</b>\n\n"
                f"{fraud_header}"
                f"👤 <b>Mijoz:</b> {user_name} ({user_username})\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code> | <b>Chat:</b> <code>{chat_id}</code>\n"
                f"────────────────────\n"
                f"🏢 <b>To'lovchi:</b> <b>{org_name}</b>\n"
                f"🔢 <b>INN / JSHSHIR:</b> {inn_line}\n"
                f"{tuman_line}"
                f"💵 <b>To'langan summa:</b> <b>{paid_amount:,.0f} so'm</b>\n"
                f"🏦 <b>Qabul qiluvchi:</b> «Yangi Texnologiyalar» DUK (<code>20210000100431200010</code>)\n"
                f"💳 <b>To'lov tizimi:</b> {getattr(receipt_facts, 'payment_system', '') or 'Elektron tolov'}\n"
                f"🔢 <b>Chek / Tranzaksiya:</b> <code>{getattr(receipt_facts, 'transaction_id', '') or '-'}</code>\n"
                f"📅 <b>To'lov vaqti:</b> {getattr(receipt_facts, 'payment_date', '') or '-'}\n"
                f"────────────────────\n"
                f"📌 <b>Holat:</b> {status_emoji} {status_text}\n"
                f"⏳ <i>Eslatma: Davlat Soliq Qo'mitasi («Yangi Texnologiyalar» DUK) to'lovni 2-24 soat ichida faollashtiradi.</i>\n\n"
                f"{bottom_inn_block}"
            )
        else:
            if is_inn_missing:
                status_emoji = "⚠️"
                status_text = "<b>KVITANSIYADA INN TOPILMADI (Mijozdan INN so'ralmoqda)</b>"
            elif debt_covered:
                status_emoji = "✅"
                status_text = "<b>QARZ TO'LIQ YOPILDI (Apparatni yoqish mumkin!)</b>"
            elif prev_debt > 0 and paid_amount < prev_debt:
                status_emoji = "⚠️"
                status_text = f"<b>QISMAN TO'LANDI</b> (Qolgan qarz: {remaining_debt:,.0f} so'm)"
            else:
                status_emoji = "🟢"
                status_text = "<b>AVANS / QARZSIZ TO'LOV</b> (Avval qarz bo'lmagan)"

            text = (
                f"🧾 <b>YANGI TO'LOV KVITANSIYASI KELIB TUSHDI!</b>\n\n"
                f"{fraud_header}"
                f"👤 <b>Mijoz:</b> {user_name} ({user_username})\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                f"💬 <b>Chat ID:</b> <code>{chat_id}</code>\n"
                f"────────────────────\n"
                f"🏢 <b>Korxona:</b> <b>{org_name}</b>\n"
                f"🔢 <b>INN / JSHSHIR:</b> {inn_line}\n"
                f"{tuman_line}"
                f"{purpose_line}"
                f"💵 <b>To'langan summa:</b> <b>{paid_amount:,.0f} so'm</b>\n"
                f"🏦 <b>Qabul qiluvchi:</b> {getattr(receipt_facts, 'recipient_account', '') or '«Mars Elektron Texnika»'}\n"
                f"💳 <b>To'lov tizimi:</b> {getattr(receipt_facts, 'payment_system', '') or 'Elektron tolov'}\n"
                f"🔢 <b>Chek / Tranzaksiya:</b> <code>{getattr(receipt_facts, 'transaction_id', '') or '-'}</code>\n"
                f"📅 <b>To'lov vaqti:</b> {getattr(receipt_facts, 'payment_date', '') or '-'}\n"
                f"────────────────────\n"
                f"📊 <b>Qarz tahlili:</b>\n"
                f"▫️ Avvalgi qarz: <b>{prev_debt:,.0f} so'm</b>\n"
                f"▫️ Holat: {status_emoji} {status_text}\n\n"
                f"{bottom_inn_block}\n\n"
                f"⚡️ <i>Mas'ul admin (@Yashnarbek_butaev): Iltimos, to'lovni tasdiqlang va tizimni yangilang.</i>"
            )

        photo_id = file_id if is_photo else None
        doc_id = file_id if not is_photo else None

        await self.notify_admins(bot, text=text, photo_file_id=photo_id, document_file_id=doc_id)

    async def notify_technical_issue(
        self,
        bot: Bot,
        user: Optional[types.User],
        chat_id: int,
        org_name: str,
        inn: str,
        issue_summary: str,
        user_comment: str = "",
        photo_file_id: Optional[str] = None
    ):
        """
        Apparatda muammo bor, internet ishlab turibdi, lekin qarz yo'q bo'lgan holatlarda
        @Yashnarbek_butaev va adminlarga zudlik bilan eskalatsiya xabari yuborish.
        """
        user_name = user.full_name if user else "Mijoz"
        user_username = f"@{user.username}" if (user and user.username) else "Mavjud emas"
        user_id = user.id if user else 0

        from excel_manager import excel_manager
        tuman = excel_manager.get_district_for_inn(inn) if inn else ""
        tuman_line = f"📍 <b>Hudud / Tuman:</b> {tuman}\n" if tuman else ""

        text = (
            f"🚨 <b>TEXNIK NOSOZLIK BO'YICHA TEZKOR ESKALATSIYA!</b>\n\n"
            f"👤 <b>Mijoz:</b> {user_name} ({user_username})\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code> | <b>Chat:</b> <code>{chat_id}</code>\n"
            f"────────────────────\n"
            f"🏢 <b>Korxona:</b> <b>{org_name or 'Aniqlanmadi'}</b>\n"
            f"🔢 <b>INN / JSHSHIR:</b> <code>{inn or 'Aniqlanmadi'}</code>\n"
            f"{tuman_line}"
            f"📶 <b>Internet aloqasi:</b> ✅ ISHLAYAPTI (Faol)\n"
            f"💳 <b>Qarzdorlik holati:</b> ✅ QARZ YO'Q (To'langan / 0 so'm)\n"
            f"────────────────────\n"
            f"⚠️ <b>Ekrandagi nosozlik:</b>\n"
            f"<b>{issue_summary}</b>\n"
        )
        if user_comment:
            text += f"\n💬 <b>Mijoz xabari:</b> <i>{user_comment}</i>\n"

        text += (
            f"\n⚡️ <i>Bosh admin (@Yashnarbek_butaev): Ushbu apparatda qarzdorlik yo'q va internet ishlayapti, "
            f"lekin texnik muammo bor. Zudlik bilan tekshirish talab etiladi!</i>"
        )

        await self.notify_admins(bot, text=text, photo_file_id=photo_file_id)

admin_manager = AdminManager()
