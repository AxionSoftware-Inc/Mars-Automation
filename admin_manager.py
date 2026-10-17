import os
import json
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ADMIN_CONFIG_PATH = os.path.join(DATA_DIR, "admin_config.json")

DEFAULT_ADMIN_USERNAMES = ["quvonchbek_admin", "yashnarbek_butaev", "bim_project_manager"]
DEFAULT_ADMIN_IDS = [1966874161, 6436610869]

DEFAULT_CONTACTS = [
    {
        "name": "@quvonchbek_admin",
        "phone": "@quvonchbek_admin",
        "role": "Hududiy THKM texnik xizmat ko'rsatish mas'ul xodimi"
    },
    {
        "name": "@Yashnarbek_butaev",
        "phone": "@Yashnarbek_butaev",
        "role": "Hududiy THKM texnik xizmat ko'rsatish mas'ul xodimi"
    }
]

class AdminManager:
    """
    Adminlar, mas'ul xodimlar kontaktlari va xabarnomalar (Notification/Escalation) boshqaruvchisi.
    Mas'ul adminlar / texniklar: @quvonchbek_admin va @Yashnarbek_butaev
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
                    
                    # Birlashtirish (har doim DEFAULT_ADMIN_IDS ning ikkalasi ham bo'lishi shart)
                    combined_admins = list(set(DEFAULT_ADMIN_IDS + env_admin_ids + [int(i) for i in file_admin_ids if str(i).isdigit()]))
                    self.admin_ids = combined_admins
                    loaded_from_file = True
            except Exception as e:
                logger.error(f"Admin konfiguratsiyasini o'qishda xatolik: {e}")

        if not loaded_from_file:
            self.admin_ids = list(set(DEFAULT_ADMIN_IDS + env_admin_ids))
            self.contacts = DEFAULT_CONTACTS
            self.save_config()

        logger.info(f"AdminManager yuklandi: {len(self.admin_ids)} ta admin ID ({self.admin_ids}), {self.admin_usernames} usernames, {len(self.contacts)} ta kontakt.")

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

    def get_admin_ids(self) -> List[int]:
        """Admin ID lar ro'yxatini qaytarish"""
        return self.admin_ids

    def is_admin(self, user_id: int, username: Optional[str] = None) -> bool:
        """Foydalanuvchi admin yoki hududiy texnik ekanligini tekshirish"""
        from modules.admin_module import regional_admin_service
        if user_id in self.admin_ids or user_id in regional_admin_service.get_all_admin_telegram_ids():
            return True
        if username:
            clean_u = username.lower().replace("@", "")
            if clean_u in self.admin_usernames or clean_u in regional_admin_service.get_all_admin_usernames():
                self.check_and_register_username(user_id, username)
                regional_admin_service.register_user_id_by_username(user_id, username)
                return True
        return False

    def check_and_register_username(self, user_id: int, username: str):
        """Agar xabar yozgan user admin username laridan biri bo'lsa, uning ID sini avtomatik saqlash"""
        if not username:
            return
        from modules.admin_module import regional_admin_service
        regional_admin_service.register_user_id_by_username(user_id, username)
        clean_u = username.lower().replace("@", "")
        if clean_u in self.admin_usernames and user_id not in self.admin_ids:
            self.admin_ids.append(user_id)
            self.save_config()
            logger.info(f"Yangi admin ID avtomatik ro'yxatga olindi: {user_id} (@{username})")

    def add_admin(self, admin_id: int) -> bool:
        """Yangi admin ID qo'shish"""
        if admin_id not in self.admin_ids:
            self.admin_ids.append(admin_id)
            self.save_config()
            return True
        return False

    def remove_admin(self, admin_id: int) -> bool:
        """Adminni o'chirish"""
        if admin_id in self.admin_ids:
            self.admin_ids.remove(admin_id)
            self.save_config()
            return True
        return False

    def add_contact(self, name: str, phone: str, role: str = ""):
        """Yangi kontakt qo'shish"""
        self.contacts.append({"name": name, "phone": phone, "role": role})
        self.save_config()

    def remove_contact(self, phone: str):
        """Kontaktni telefon bo'yicha o'chirish"""
        self.contacts = [c for c in self.contacts if c.get("phone") != phone]
        self.save_config()

    def get_contacts_display(self, inn: Optional[str] = None, tuman: Optional[str] = None) -> str:
        """Foydalanuvchilarga ko'rsatish uchun hududiy mas'ul xodim va kontaktlar matni"""
        from modules.admin_module import regional_admin_service
        return regional_admin_service.format_user_facing_admin_info(inn=inn, tuman=tuman)

    def get_region_admin_info(self, inn: Optional[str] = None, tuman: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Berilgan INN yoki tuman bo'yicha hududiy admin ma'lumotlarini olish"""
        from modules.admin_module import regional_admin_service
        if tuman:
            reg = regional_admin_service.find_region_admin(tuman)
            if reg:
                return reg
        if inn:
            return regional_admin_service.find_region_admin_by_inn(inn)
        return None

    async def notify_admins(
        self,
        bot: Bot,
        text: str,
        photo_file_id: Optional[str] = None,
        document_file_id: Optional[str] = None,
        short_caption: Optional[str] = None,
        inn: Optional[str] = None,
        tuman: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None
    ):
        """Hududiy mas'ul adminga, bosh adminlarga va bildirishnoma kanaliga xabar (rasmi bilan) yuborish"""
        from modules.admin_module import regional_admin_service
        caption_text = short_caption or text
        if len(caption_text) > 1024:
            caption_text = caption_text[:1020] + "..."

        targets = regional_admin_service.get_target_admin_ids_for_escalation(
            inn=inn,
            tuman=tuman,
            fallback_admin_ids=self.admin_ids,
            notification_channel_id=self.notification_channel_id
        )

        for target_id in targets:
            try:
                if photo_file_id:
                    await bot.send_photo(
                        chat_id=target_id,
                        photo=photo_file_id,
                        caption=caption_text,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                elif document_file_id:
                    await bot.send_document(
                        chat_id=target_id,
                        document=document_file_id,
                        caption=caption_text,
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
                logger.warning(f"Adminga ({target_id}) xabarnoma yuborishda xatolik: {e}")

    async def notify_receipt_escalation(
        self,
        bot: Bot,
        user: Optional[types.User],
        chat_id: int,
        receipt_facts: Any,
        debt_status_info: Dict[str, Any],
        file_id: Optional[str] = None,
        is_photo: bool = True,
        user_comment: str = ""
    ):
        """To'lov kvitansiyasi kelganda hududiy va bosh adminlarga to'liq hisobot yuborish"""
        from modules.admin_module import regional_admin_service
        user_name = user.full_name if user else "Mijoz"
        user_username = f"@{user.username}" if (user and user.username) else "Mavjud emas"
        user_id = user.id if user else 0

        paid_amount = getattr(receipt_facts, "amount", 0.0) or 0.0
        prev_debt = debt_status_info.get("previous_debt", debt_status_info.get("prev_debt", 0.0))
        remaining_debt = debt_status_info.get("remaining_debt", 0.0)
        org_name = debt_status_info.get("org_name") or getattr(receipt_facts, "payer_name", "") or "Aniqlanmadi"
        inn = getattr(receipt_facts, "payer_inn", "") or debt_status_info.get("inn", "")
        debt_covered = debt_status_info.get("debt_covered", False)
        is_inn_missing = debt_status_info.get("is_inn_missing", False)
        is_annual = getattr(receipt_facts, "is_annual_fiscal_fee", False) or debt_status_info.get("is_annual", False)
        is_old = getattr(receipt_facts, "is_old_receipt", False) or debt_status_info.get("is_old_receipt", False)
        is_dup = getattr(receipt_facts, "is_duplicate", False) or debt_status_info.get("is_duplicate", False)

        from excel_manager import excel_manager
        tuman = debt_status_info.get("tuman") or (excel_manager.get_district_for_inn(inn) if inn else "")
        reg_admin = self.get_region_admin_info(inn=inn, tuman=tuman)
        reg_admin_line = ""
        if reg_admin:
            ra_user = (reg_admin.get("username") or "").replace("@", "")
            reg_admin_line = f"👨‍💻 <b>Hududiy mas'ul:</b> {reg_admin.get('admin_name')} (@{ra_user})\n"

        tuman_line = f"📍 <b>Hudud / Tuman:</b> {tuman}\n" if tuman else ""

        purpose_label = getattr(receipt_facts, "purpose_label", None) or debt_status_info.get("purpose_label") or "Oylik abonent to'lovi"
        payment_purpose = getattr(receipt_facts, "payment_purpose", None) or debt_status_info.get("payment_purpose", "monthly_subscription")
        purpose_line = f"🎯 <b>To'lov maqsadi:</b> <b>{purpose_label}</b>\n" if (purpose_label and payment_purpose != "monthly_subscription") else ""

        fraud_header = ""
        if is_dup:
            tx_id = getattr(receipt_facts, "transaction_id", "") or "-"
            fraud_header += f"🚨 <b>OGOHLANTIRISH: DUBLIKAT TRANZAKSIYA!</b>\nUshbu chek (ID: <code>{tx_id}</code>) avval ham tizimga yuborilgan!\n\n"
        if is_old:
            warn = getattr(receipt_facts, "old_receipt_warning", "") or debt_status_info.get("old_receipt_warning", "") or "Eski sana"
            fraud_header += f"⚠️ <b>DIQQAT: KVITANSIYA SANASI ESKI ({warn})!</b>\n\n"

        summa_line = f"💵 <b>To'langan summa:</b> <b>{paid_amount:,.0f} so'm</b>\n"
        pay_date = getattr(receipt_facts, "payment_date", "")
        date_line = f"📅 <b>To'lov vaqti:</b> {pay_date}\n" if pay_date else ""
        user_comment_str = f"💬 <b>Mijoz izohi:</b> <i>{user_comment}</i>\n" if user_comment else ""

        if inn and inn != "000":
            inn_line = f"<code>{inn}</code>"
            bottom_inn_block = (
                f"📋 <b>INN (nusxa olish uchun):</b>\n"
                f"<code>{inn}</code>"
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
                f"{summa_line}"
                f"{date_line}"
                f"🔢 <b>INN / JSHSHIR:</b> {inn_line}\n"
                f"🏢 <b>To'lovchi:</b> <b>{org_name}</b>\n"
                f"{tuman_line}"
                f"{reg_admin_line}"
                f"🏦 <b>Qabul qiluvchi:</b> «Yangi Texnologiyalar» DUK (<code>20210000100431200010</code>)\n"
                f"────────────────────\n"
                f"📌 <b>Holat:</b> {status_emoji} {status_text}\n"
                f"💳 <b>To'lov tizimi:</b> {getattr(receipt_facts, 'payment_system', '') or 'Elektron tolov'}\n"
                f"🔢 <b>Chek / Tranzaksiya:</b> <code>{getattr(receipt_facts, 'transaction_id', '') or '-'}</code>\n"
                f"👤 <b>Mijoz:</b> {user_name} ({user_username})\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code> | <b>Chat:</b> <code>{chat_id}</code>\n"
                f"{user_comment_str}"
                f"⏳ <i>Eslatma: Davlat Soliq Qo'mitasi («Yangi Texnologiyalar» DUK) to'lovni 2-24 soat ichida faollashtiradi.</i>\n\n"
                f"{bottom_inn_block}"
            )
            short_caption = (
                f"🏛 <b>YILLIK FISKAL MODUL TO'LOVI KVITANSIYASI!</b>\n\n"
                f"👤 <b>Mijoz:</b> {user_name} ({user_username})\n"
                f"{summa_line}"
                f"{date_line}"
                f"🔢 <b>INN / JSHSHIR:</b> {inn_line}\n"
                f"🏢 <b>To'lovchi:</b> <b>{org_name}</b>\n"
                f"{tuman_line}"
                f"{reg_admin_line}"
                f"📌 <b>Holat:</b> {status_emoji} {status_text}\n\n"
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
                f"{summa_line}"
                f"{date_line}"
                f"🔢 <b>INN / JSHSHIR:</b> {inn_line}\n"
                f"🏢 <b>Korxona:</b> <b>{org_name}</b>\n"
                f"{tuman_line}"
                f"{reg_admin_line}"
                f"{purpose_line}"
                f"────────────────────\n"
                f"📊 <b>Qarz tahlili:</b>\n"
                f"▫️ Avvalgi qarz: <b>{prev_debt:,.0f} so'm</b>\n"
                f"▫️ Holat: {status_emoji} {status_text}\n"
                f"🏦 <b>Qabul qiluvchi:</b> {getattr(receipt_facts, 'recipient_account', '') or '«Mars Elektron Texnika»'}\n"
                f"💳 <b>To'lov tizimi:</b> {getattr(receipt_facts, 'payment_system', '') or 'Elektron tolov'}\n"
                f"🔢 <b>Chek / Tranzaksiya:</b> <code>{getattr(receipt_facts, 'transaction_id', '') or '-'}</code>\n"
                f"👤 <b>Mijoz:</b> {user_name} ({user_username})\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code> | <b>Chat:</b> <code>{chat_id}</code>\n"
                f"{user_comment_str}\n"
                f"{bottom_inn_block}\n\n"
                f"⚡️ <i>Iltimos, to'lovni tasdiqlang va tizimni yangilang.</i>"
            )
            short_caption = (
                f"🧾 <b>YANGI TO'LOV KVITANSIYASI!</b>\n\n"
                f"👤 <b>Mijoz:</b> {user_name} ({user_username})\n"
                f"{summa_line}"
                f"{date_line}"
                f"🔢 <b>INN / JSHSHIR:</b> {inn_line}\n"
                f"🏢 <b>Korxona:</b> <b>{org_name}</b>\n"
                f"{tuman_line}"
                f"{reg_admin_line}"
                f"📌 <b>Holat:</b> {status_emoji} {status_text}\n\n"
                f"{bottom_inn_block}"
            )

        photo_id = file_id if is_photo else None
        doc_id = file_id if not is_photo else None
        admin_kb = regional_admin_service.build_user_contact_keyboard_for_admin(user)

        await self.notify_admins(
            bot=bot,
            text=text,
            photo_file_id=photo_id,
            document_file_id=doc_id,
            short_caption=short_caption,
            inn=inn,
            tuman=tuman,
            reply_markup=admin_kb
        )

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
        aynan o'sha hududdagi mas'ul adminga (va bosh adminlarga) rasmi bilan tezkor eskalatsiya yuborish.
        """
        from modules.admin_module import regional_admin_service
        user_name = user.full_name if user else "Mijoz"
        user_username = f"@{user.username}" if (user and user.username) else "Mavjud emas"
        user_id = user.id if user else 0

        from excel_manager import excel_manager
        tuman = excel_manager.get_district_for_inn(inn) if inn else ""
        records = excel_manager.search(inn) if inn else []
        comp_phone = records[0].get("phone", "") if records else ""
        model_str = excel_manager.get_device_model_summary(records) if records else ""

        reg_admin = self.get_region_admin_info(inn=inn, tuman=tuman)
        reg_admin_line = ""
        target_mention = "@quvonchbek_admin, @Yashnarbek_butaev"
        if reg_admin:
            ra_user = (reg_admin.get("username") or "").replace("@", "")
            reg_admin_line = f"👨‍💻 <b>Hududiy mas'ul:</b> {reg_admin.get('admin_name')} (@{ra_user})\n"
            target_mention = f"@{ra_user}"

        tuman_line = f"📍 <b>Hudud / Tuman:</b> {tuman}\n" if tuman else ""
        phone_line = f"📞 <b>Korxona telefoni:</b> <code>{comp_phone}</code>\n" if (comp_phone and comp_phone != "-") else ""
        model_line = f"📟 <b>Apparat modeli:</b> {model_str}\n" if model_str else ""

        text = (
            f"🚨 <b>TEXNIK NOSOZLIK BO'YICHA HUDUDIY ESKALATSIYA!</b>\n\n"
            f"👤 <b>Mijoz:</b> {user_name} ({user_username})\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code> | <b>Chat:</b> <code>{chat_id}</code>\n"
            f"{phone_line}"
            f"────────────────────\n"
            f"🏢 <b>Korxona:</b> <b>{org_name or 'Aniqlanmadi'}</b>\n"
            f"🔢 <b>INN / JSHSHIR:</b> <code>{inn or 'Aniqlanmadi'}</code>\n"
            f"{tuman_line}"
            f"{reg_admin_line}"
            f"{model_line}"
            f"📶 <b>Internet aloqasi:</b> ✅ ISHLAYAPTI (Faol)\n"
            f"💳 <b>Qarzdorlik holati:</b> ✅ QARZ YO'Q (To'langan / 0 so'm)\n"
            f"────────────────────\n"
            f"⚠️ <b>Ekrandagi nosozlik:</b>\n"
            f"<b>{issue_summary}</b>\n"
        )
        if user_comment:
            text += f"\n💬 <b>Mijoz xabari:</b> <i>{user_comment}</i>\n"

        text += (
            f"\n⚡️ <i>Mas'ul mutaxassis ({target_mention}): Mijozga sizning kontaktingiz berildi, "
            f"iltimos mijoz bilan bog'lanib amaliy yordam bering!</i>"
        )

        admin_kb = regional_admin_service.build_user_contact_keyboard_for_admin(user)
        await self.notify_admins(
            bot,
            text=text,
            photo_file_id=photo_file_id,
            inn=inn,
            tuman=tuman,
            reply_markup=admin_kb
        )

    async def notify_user_query_escalation(
        self,
        bot: Bot,
        user: Optional[types.User],
        chat_id: int,
        query_text: str,
        reason: str = "Foydalanuvchi adminga/texnikka murojaat qildi",
        inn: Optional[str] = None,
        org_name: Optional[str] = None,
        photo_file_id: Optional[str] = None
    ):
        """
        Foydalanuvchi adminga murojaat qilganda yoki yordam talab qilganda
        hududiy adminga (va bosh adminlarga) mijoz ma'lumotlari va rasmi bilan xabar yuborish.
        """
        from modules.admin_module import regional_admin_service
        user_name = user.full_name if user else "Mijoz"
        user_username = f"@{user.username}" if (user and user.username) else "Yo'q"
        user_id = user.id if user else 0

        tuman = ""
        comp_phone = ""
        model_str = ""
        if inn:
            from excel_manager import excel_manager
            tuman = excel_manager.get_district_for_inn(inn)
            records = excel_manager.search(inn)
            if records:
                comp_phone = records[0].get("phone", "")
                model_str = excel_manager.get_device_model_summary(records)
                if not org_name:
                    org_name = records[0].get("name", "")

        reg_admin = self.get_region_admin_info(inn=inn, tuman=tuman)
        reg_admin_line = ""
        target_mention = "@quvonchbek_admin, @Yashnarbek_butaev"
        if reg_admin:
            ra_user = (reg_admin.get("username") or "").replace("@", "")
            reg_admin_line = f"👨‍💻 <b>Hududiy mas'ul:</b> {reg_admin.get('admin_name')} (@{ra_user})\n"
            target_mention = f"@{ra_user}"

        tuman_line = f"📍 <b>Hudud / Tuman:</b> {tuman}\n" if tuman else ""
        inn_line = f"🔢 <b>INN:</b> <code>{inn}</code>\n" if inn else ""
        org_line = f"🏢 <b>Korxona:</b> <b>{org_name}</b>\n" if org_name else ""
        phone_line = f"📞 <b>Korxona telefoni:</b> <code>{comp_phone}</code>\n" if (comp_phone and comp_phone != "-") else ""
        model_line = f"📟 <b>Apparat modeli:</b> {model_str}\n" if model_str else ""

        text = (
            f"🔔 <b>YANGI HUDUDIY MUROJAAT / TEXNIK YORDAM SO'ROVI!</b>\n\n"
            f"📌 <b>Holat:</b> {reason}\n"
            f"👤 <b>Mijoz:</b> {user_name} ({user_username})\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code> | <b>Chat ID:</b> <code>{chat_id}</code>\n"
            f"{phone_line}"
            f"{inn_line}"
            f"{org_line}"
            f"{tuman_line}"
            f"{reg_admin_line}"
            f"{model_line}"
            f"────────────────────\n"
            f"💬 <b>Mijoz xabari:</b>\n"
            f"<i>{query_text}</i>\n\n"
            f"⚡️ <i>Mas'ul mutaxassis ({target_mention}): "
            f"Foydalanuvchi siz bilan bog'lanishni kutmoqda. Quyidagi tugma orqali mijozga yozishingiz mumkin.</i>"
        )
        admin_kb = regional_admin_service.build_user_contact_keyboard_for_admin(user)
        await self.notify_admins(
            bot,
            text=text,
            photo_file_id=photo_file_id,
            inn=inn,
            tuman=tuman,
            reply_markup=admin_kb
        )

    async def notify_debt_free_device_issue(
        self,
        bot: Bot,
        user: Optional[types.User],
        chat_id: int,
        org_name: str,
        inn: str,
        issue_summary: str,
        user_comment: str = "",
        photo_file_id: Optional[str] = None,
        fiscal_module: Optional[str] = None,
        device_model: Optional[str] = None
    ):
        """
        To'lovlardan qarzdorlik bo'lmaganda (oylik 0 so'm, yillik 0 so'm/faol),
        apparat nosozligi bo'yicha barcha to'plangan ma'lumotlar va rasmlarni
        zudlik bilan mijozning hududiy adminiga (@username) va bosh adminlarga uzatish.
        """
        from modules.admin_module import regional_admin_service
        user_name = user.full_name if user else "Mijoz"
        user_username = f"@{user.username}" if (user and user.username) else "Yo'q"
        user_id = user.id if user else 0

        from excel_manager import excel_manager
        tuman = excel_manager.get_district_for_inn(inn) if inn else ""
        records = excel_manager.search(inn) if inn else []
        comp_phone = records[0].get("phone", "") if records else ""
        if not device_model and records:
            device_model = excel_manager.get_device_model_summary(records)

        reg_admin = self.get_region_admin_info(inn=inn, tuman=tuman)
        reg_admin_line = ""
        target_mention = "@quvonchbek_admin, @Yashnarbek_butaev"
        if reg_admin:
            ra_user = (reg_admin.get("username") or "").replace("@", "")
            reg_admin_line = f"👨‍💻 <b>Hududiy mas'ul:</b> {reg_admin.get('admin_name')} (@{ra_user})\n"
            target_mention = f"@{ra_user}"

        tuman_line = f"📍 <b>Hudud / Tuman:</b> {tuman}\n" if tuman else ""
        phone_line = f"📞 <b>Korxona telefoni:</b> <code>{comp_phone}</code>\n" if (comp_phone and comp_phone != "-") else ""
        fm_line = f"🏛 <b>Fiskal modul:</b> <code>{fiscal_module}</code>\n" if fiscal_module else ""
        model_line = f"📱 <b>Apparat modeli:</b> {device_model}\n" if device_model else ""

        text = (
            f"🚨 <b>QARZDORLIKSIZ APPARAT NOSOZLIGI (HUDUDIY ESKALATSIYA)!</b>\n\n"
            f"👤 <b>Mijoz:</b> {user_name} ({user_username})\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code> | <b>Chat ID:</b> <code>{chat_id}</code>\n"
            f"{phone_line}"
            f"────────────────────\n"
            f"🏢 <b>Korxona:</b> <b>{org_name or 'Aniqlanmadi'}</b>\n"
            f"🔢 <b>INN / СТИР:</b> <code>{inn or 'Aniqlanmadi'}</code>\n"
            f"{tuman_line}"
            f"{reg_admin_line}"
            f"{model_line}"
            f"{fm_line}"
            f"────────────────────\n"
            f"📊 <b>To'lovlar tekshiruvi:</b>\n"
            f"▫️ «Mars» oylik to'lovi: ✅ <b>0 so'm (To'langan / Qarz yo'q)</b>\n"
            f"▫️ Davlat Soliq (OFD) yillik to'lovi: ✅ <b>Faol (To'langan / Qarz yo'q)</b>\n"
            f"────────────────────\n"
            f"⚠️ <b>Muammo / Xatolik:</b>\n"
            f"<b>{issue_summary}</b>\n"
        )
        if user_comment:
            text += f"\n💬 <b>Mijoz xabari:</b> <i>{user_comment}</i>\n"

        if photo_file_id:
            text += f"\n📸 <b>Apparat ekrani / xatolik fotosurati ilova qilindi.</b>\n"

        text += (
            f"\n⚡️ <i>Mas'ul mutaxassis ({target_mention}): "
            f"Mijozda hech qanday qarzdorlik yo'q! Apparatida texnik muammo mavjud, "
            f"mijoz siz bilan bog'lanishni kutmoqda. Zudlik bilan bog'laning!</i>"
        )

        short_caption = (
            f"🚨 <b>QARZDORLIKSIZ APPARAT NOSOZLIGI!</b>\n\n"
            f"🏢 <b>{org_name or 'Korxona'}</b> (INN: <code>{inn or '-'}</code>)\n"
            f"{tuman_line}"
            f"{phone_line}"
            f"{reg_admin_line}"
            f"{fm_line}"
            f"👤 <b>Mijoz:</b> {user_name} ({user_username})\n"
            f"✅ To'lovlar: Qarz yo'q (0 so'm)\n"
            f"⚠️ Muammo: {issue_summary[:140]}\n\n"
            f"⚡️ Mas'ul: {target_mention}"
        )

        admin_kb = regional_admin_service.build_user_contact_keyboard_for_admin(user)
        await self.notify_admins(
            bot=bot,
            text=text,
            photo_file_id=photo_file_id,
            short_caption=short_caption,
            inn=inn,
            tuman=tuman,
            reply_markup=admin_kb
        )


def get_admin_contact_keyboard(inn: Optional[str] = None, tuman: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Foydalanuvchini aynan o'z hududidagi mas'ul mutaxassis (va bosh adminlar)
    bilan to'g'ridan-to'g'ri bog'lovchi interaktiv tugmalar.
    """
    from modules.admin_module import regional_admin_service
    return regional_admin_service.build_contact_keyboard(inn=inn, tuman=tuman)


admin_manager = AdminManager()
