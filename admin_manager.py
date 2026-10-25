import os
import json
import html
import logging
from typing import Optional, Dict, Any, List, Tuple
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
        if username:
            clean_u = username.lower().replace("@", "")
            if clean_u in self.admin_usernames or clean_u in regional_admin_service.get_all_admin_usernames():
                self.check_and_register_username(user_id, username)
                regional_admin_service.register_user_id_by_username(user_id, username)
                return True
        if user_id in self.admin_ids or user_id in regional_admin_service.get_all_admin_telegram_ids():
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
        base_info = regional_admin_service.format_user_facing_admin_info(inn=inn, tuman=tuman)
        if self.contacts:
            extra = "\n".join(f"👨‍💻 {c['name']} ({c.get('role', 'Mutaxassis')}): {c['phone']}" for c in self.contacts)
            return f"{base_info}\n\n{extra}"
        return base_info

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
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        photos: Optional[List[str]] = None
    ):
        """Hududiy mas'ul adminga, bosh adminlarga va bildirishnoma kanaliga xabar (barcha rasmlari bilan) yuborish"""
        from modules.admin_module import regional_admin_service
        raw_caption = short_caption or text

        targets = regional_admin_service.get_target_admin_ids_for_escalation(
            inn=inn,
            tuman=tuman,
            fallback_admin_ids=self.admin_ids,
            notification_channel_id=self.notification_channel_id
        )

        # Barcha noyob rasmlarni tartibli yig'ish
        all_photos: List[str] = []
        if photos:
            for p in photos:
                if p and p not in all_photos:
                    all_photos.append(p)
        if photo_file_id and photo_file_id not in all_photos:
            all_photos.insert(0, photo_file_id)

        for target_id in targets:
            try:
                if all_photos:
                    primary_photo = all_photos[0]
                    if len(raw_caption) <= 1000:
                        await bot.send_photo(
                            chat_id=target_id,
                            photo=primary_photo,
                            caption=raw_caption,
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )
                    else:
                        # Rasm va uzun matnni ajratib yuborish (HTML buzilmasligi uchun)
                        await bot.send_photo(chat_id=target_id, photo=primary_photo)
                        await bot.send_message(
                            chat_id=target_id,
                            text=text,
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )

                    # Agar mijoz bir nechta rasm yuborgan bo'lsa, qolgan barcha rasmlarni ham uzatish
                    for extra_p in all_photos[1:]:
                        try:
                            await bot.send_photo(
                                chat_id=target_id,
                                photo=extra_p,
                                caption="📸 <i>Mijoz yuborgan qo'shimcha fotosurat</i>",
                                parse_mode="HTML"
                            )
                        except Exception as ep_err:
                            logger.warning(f"Qo'shimcha rasmni adminga ({target_id}) yuborishda xato: {ep_err}")
                elif document_file_id:
                    if len(raw_caption) <= 1000:
                        await bot.send_document(
                            chat_id=target_id,
                            document=document_file_id,
                            caption=raw_caption,
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )
                    else:
                        await bot.send_document(chat_id=target_id, document=document_file_id)
                        await bot.send_message(
                            chat_id=target_id,
                            text=text,
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
                logger.warning(f"Adminga ({target_id}) xabarnoma yuborishda xatolik: {e}. Qayta urinish (plain text)...")
                try:
                    # Agar HTML entity parsing xatolik bersa, oddiy matn sifatida yuborish
                    clean_text = text.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<i>", "").replace("</i>", "")
                    await bot.send_message(
                        chat_id=target_id,
                        text=clean_text[:4000],
                        reply_markup=reply_markup
                    )
                except Exception as e2:
                    logger.error(f"Adminga ({target_id}) xabar umuman yetib bormadi: {e2}")

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
        is_inn_missing = bool(debt_status_info.get("is_inn_missing", False) or debt_status_info.get("inn_missing", False))
        is_annual = getattr(receipt_facts, "is_annual_fiscal_fee", False) or debt_status_info.get("is_annual", False)
        is_old = getattr(receipt_facts, "is_old_receipt", False) or debt_status_info.get("is_old_receipt", False)
        is_dup = getattr(receipt_facts, "is_duplicate", False) or debt_status_info.get("is_duplicate", False)

        inn_mismatch = bool(debt_status_info.get("inn_mismatch", False))
        session_inn = debt_status_info.get("session_inn") or ""
        session_org_name = debt_status_info.get("session_org_name") or ""
        session_debt = float(debt_status_info.get("session_debt", 0.0) or 0.0)
        inn_in_db = bool(debt_status_info.get("inn_in_db", True))

        from excel_manager import excel_manager
        tuman = debt_status_info.get("tuman") or (excel_manager.get_district_for_inn(inn) if inn else "")
        reg_admin = self.get_region_admin_info(inn=session_inn or inn, tuman=tuman)
        reg_admin_line = ""
        if reg_admin:
            ra_user = (reg_admin.get("username") or "").replace("@", "")
            reg_admin_line = f"👨‍💻 <b>Hududiy mas'ul:</b> {reg_admin.get('admin_name')} (@{ra_user})\n"

        tuman_line = f"📍 <b>Hudud / Tuman:</b> {tuman}\n" if tuman else ""

        purpose_label = getattr(receipt_facts, "purpose_label", None) or debt_status_info.get("purpose_label") or "Oylik abonent to'lovi"
        payment_purpose = getattr(receipt_facts, "payment_purpose", None) or debt_status_info.get("payment_purpose", "monthly_subscription")
        purpose_line = f"🎯 <b>To'lov maqsadi:</b> <b>{purpose_label}</b>\n" if (purpose_label and payment_purpose != "monthly_subscription") else ""

        warn = getattr(receipt_facts, "old_receipt_warning", "") or debt_status_info.get("old_receipt_warning", "") or "Kvitansiya sanasi bugungi emas"
        fraud_header = ""
        if is_dup:
            tx_id = getattr(receipt_facts, "transaction_id", "") or "-"
            fraud_header += f"🚨 <b>DUBLIKAT TRANZAKSIYA (ID: <code>{tx_id}</code>)</b>\nUshbu chek avval ham tizimga yuborilgan!\n\n"
        if is_old:
            fraud_header += f"⚠️ <b>DIQQAT: ESKI KVITANSIYA! ({warn})</b>\n\n"
        if inn_mismatch:
            fraud_header += (
                f"🚨 <b>DIQQAT: INN MOS EMAS!</b>\n"
                f"Mijoz suhbatda <b>{session_org_name or 'Korxona'}</b> (INN: <code>{session_inn}</code>, qarzi: <b>{session_debt:,.0f} so'm</b>) bo'yicha yozayotgan edi, "
                f"lekin kvitansiyada boshqa INN (<code>{inn}</code>) ko'rsatilgan!\n\n"
            )

        summa_line = f"💵 <b>To'langan summa:</b> <b>{paid_amount:,.0f} so'm</b>\n"
        pay_date = getattr(receipt_facts, "payment_date", "")
        date_tag = " <i>(ESKI SANA)</i>" if is_old else " <i>(Bugungi)</i>"
        date_line = f"📅 <b>Kvitansiya sanasi:</b> {pay_date}{date_tag}\n" if pay_date else "📅 <b>Kvitansiya sanasi:</b> Ko'rsatilmagan\n"
        user_comment_str = f"💬 <b>Mijoz izohi:</b> <i>{user_comment}</i>\n" if user_comment else ""

        if inn and inn != "000":
            inn_line = f"<code>{inn}</code>"
            bottom_inn_block = (
                f"📋 <b>INN (nusxa olish uchun):</b>\n"
                f"<code>{session_inn if (inn_mismatch and session_inn) else inn}</code>"
            )
        else:
            inn_line = "❌ Topilmadi (Chekda yo'q yoki 000)"
            bottom_inn_block = (
                f"⚠️ <b>DIQQAT: Kvitansiyadan INN topilmadi!</b>\n"
                f"<i>(Chekda INN ko'rsatilmagan yoki '000' bo'sh qoldirilgan. Mijozdan INN so'ralmoqda)</i>"
            )

        import html
        user_name_esc = html.escape(user_name)
        org_name_esc = html.escape(org_name)
        session_org_esc = html.escape(session_org_name)
        comment_esc = html.escape(user_comment) if user_comment else ""

        target_fm = debt_status_info.get("fiscal_module")
        fm_admin_line = f"🏛 <b>FM:</b> <code>{target_fm}</code>\n" if target_fm else ""
        bank_caution = "⚠️ <i>Apparatni yoqishdan oldin bank hisobini tekshiring!</i>\n" if (not is_old and debt_covered) else ""

        fraud_header = ""
        if is_dup:
            tx_id = getattr(receipt_facts, "transaction_id", "") or "-"
            fraud_header += f"🚨 <b>DUBLIKAT TRANZAKSIYA (ID: <code>{tx_id}</code>)</b>\n"
        if is_old:
            fraud_header += f"⚠️ <b>ESKI KVITANSIYA ({warn})</b>\n"
        if inn_mismatch:
            fraud_header += f"🚨 <b>INN MOS EMAS:</b> Suhbatda <code>{session_inn}</code> ({session_debt:,.0f} so'm), chekda <code>{inn}</code>\n"

        pay_date = getattr(receipt_facts, "payment_date", "")
        date_line = f"📅 <b>Sana:</b> {pay_date}{' (ESKI)' if is_old else ''}\n" if pay_date else ""
        user_comment_str = f"💬 <b>Izoh:</b> <i>{comment_esc}</i>\n" if comment_esc else ""

        if inn and inn != "000":
            inn_line = f"<code>{inn}</code>"
            bottom_inn_block = f"📋 <code>{session_inn if (inn_mismatch and session_inn) else inn}</code>"
        else:
            inn_line = "❌ Topilmadi"
            bottom_inn_block = "⚠️ <i>INN topilmadi, mijozdan so'ralmoqda</i>"

        from user_memory import user_memory
        user_link = f'<a href="tg://user?id={user_id}">{user_name_esc}</a>' if user_id else user_name_esc

        if is_annual:
            status_text = f"ESKI ({warn})" if is_old else "YILLIK TO'LOV"
            title = "⚠️ <b>ESKI YILLIK TO'LOV!</b>" if is_old else "🏛 <b>YILLIK TO'LOV KVITANSIYASI!</b>"
            
            compact_msg = (
                f"{title}\n"
                f"{fraud_header}"
                f"👤 {user_link} ({user_username})\n"
                f"💵 <b>{paid_amount:,.0f} so'm</b> | {date_line}"
                f"🏢 <b>{org_name_esc}</b> (INN: {inn_line})\n"
                f"{fm_admin_line}"
                f"{tuman_line}"
                f"{reg_admin_line}"
                f"📌 <b>Holat:</b> {status_text}\n"
                f"🔢 <b>Chek:</b> <code>{getattr(receipt_facts, 'transaction_id', '') or '-'}</code> ({getattr(receipt_facts, 'payment_system', '') or 'Bank'})\n"
                f"{user_comment_str}"
                f"📋 <b>INN:</b> {bottom_inn_block}"
            )
            text = compact_msg
            short_caption = compact_msg
        else:
            if is_inn_missing:
                status_text = "⚠️ INN TOPILMADI (so'ralmoqda)"
                if is_old:
                    status_text += f" | ESKI ({warn})"
            elif is_old:
                status_text = f"⚠️ ESKI (Qarz: {prev_debt:,.0f} so'm)"
            elif inn_mismatch:
                status_text = f"🚨 INN MOS EMAS (Suhbatda: {session_inn})"
            elif not inn_in_db:
                status_text = "⚠️ INN BAZADA YO'Q"
            elif debt_covered and prev_debt > 0:
                status_text = f"✅ QARZNI YOPADI (Qarz: {prev_debt:,.0f} so'm)"
            elif prev_debt > 0 and paid_amount < prev_debt:
                status_text = f"⚠️ QARZNI YOPMAYDI (Qoldiq: {remaining_debt:,.0f} so'm)"
            else:
                status_text = "🟢 BAZADA QARZ YO'Q (0 so'm)"

            title = "⚠️ <b>ESKI TO'LOV!</b>" if is_old else "🧾 <b>YANGI TO'LOV KVITANSIYASI!</b>"

            compact_msg = (
                f"{title}\n"
                f"{fraud_header}"
                f"👤 {user_link} ({user_username})\n"
                f"💵 <b>To'langan:</b> <b>{paid_amount:,.0f} so'm</b>\n"
                f"{purpose_line}"
                f"{date_line}"
                f"🏢 <b>{org_name_esc}</b> (INN: {inn_line})\n"
                f"{tuman_line}"
                f"{reg_admin_line}"
                f"📊 <b>Qarz:</b> <b>{prev_debt:,.0f} so'm</b> | <b>Xulosa:</b> {status_text}\n"
                f"{bank_caution}"
                f"🔢 <b>Chek ID:</b> <code>{getattr(receipt_facts, 'transaction_id', '') or '-'}</code> ({getattr(receipt_facts, 'payment_system', '') or 'Bank'})\n"
                f"{user_comment_str}"
                f"📋 <b>INN nusxa:</b> {bottom_inn_block}"
            )
            text = compact_msg
            short_caption = compact_msg

        photo_id = file_id if is_photo else None
        doc_id = file_id if not is_photo else None

        all_user_photos = user_memory.get_all_photos(chat_id, user_id) if (chat_id and user_id) else []
        if photo_id and photo_id not in all_user_photos:
            all_user_photos.insert(0, photo_id)

        target_check_inn = session_inn if (inn_mismatch and session_inn) else inn
        comp_phone = ""
        if target_check_inn and target_check_inn != "000":
            from excel_manager import excel_manager
            rec_matches = excel_manager.search(target_check_inn)
            if rec_matches:
                comp_phone = rec_matches[0].get("phone", "")

        admin_kb = regional_admin_service.build_user_contact_keyboard_for_admin(user, phone=comp_phone)

        await self.notify_admins(
            bot=bot,
            text=text,
            photo_file_id=photo_id,
            document_file_id=doc_id,
            short_caption=short_caption,
            inn=session_inn if (inn_mismatch and session_inn) else inn,
            tuman=tuman,
            reply_markup=admin_kb,
            photos=all_user_photos if is_photo else None
        )

    def _build_escalation_card(
        self,
        title: str,
        reason: str,
        user: Optional[types.User],
        chat_id: int,
        inn: Optional[str] = None,
        org_name: Optional[str] = None,
        fiscal_module: Optional[str] = None,
        device_model: Optional[str] = None,
        issue_summary: Optional[str] = None,
        user_comment: Optional[str] = None,
        query_text: Optional[str] = None,
        photo_file_id: Optional[str] = None,
        override_monthly_debt: Optional[float] = None,
        override_annual_status: Optional[str] = None,
        internet_status: Optional[str] = None
    ) -> Tuple[str, str, str, str, List[str], Optional[InlineKeyboardMarkup]]:
        """Adminga eskalatsiya uchun ixcham, to'liq va tushunarli kartochka yaratuvchi markaziy funksiya"""
        from modules.admin_module import regional_admin_service
        from user_memory import user_memory
        from excel_manager import excel_manager

        user_id = getattr(user, "id", 0) if user else 0
        user_name = getattr(user, "full_name", None) or getattr(user, "first_name", "Mijoz")
        user_name_esc = html.escape(user_name)
        user_username = f"@{user.username}" if (user and getattr(user, "username", None)) else "Mavjud emas"
        user_link = f'<a href="tg://user?id={user_id}">{user_name_esc}</a>' if user_id else user_name_esc

        # Sessiyadan yetishmayotgan ma'lumotlarni to'ldirish
        session_inn = user_memory.get_last_id(chat_id, user_id) if (chat_id and user_id) else None
        effective_inn = inn or session_inn or ""
        session_fm = fiscal_module or (user_memory.get_last_fm(chat_id, user_id) if (chat_id and user_id) else None)

        tuman = ""
        comp_phone = ""
        model_str = device_model or ""
        monthly_debt = override_monthly_debt
        records = []
        if effective_inn:
            records = excel_manager.search(effective_inn)
            tuman = excel_manager.get_district_for_inn(effective_inn)
            if records:
                if not comp_phone:
                    comp_phone = records[0].get("phone", "")
                if not model_str:
                    model_str = excel_manager.get_device_model_summary(records)
                if monthly_debt is None:
                    monthly_debt = sum(item.get("debt", 0.0) for item in records)
                if not org_name:
                    org_name = records[0].get("name", "")

        if not org_name and chat_id and user_id:
            org_name = user_memory.get_org_name(chat_id, user_id) or ""
        if not model_str and chat_id and user_id:
            model_str = user_memory.get_device_models(chat_id, user_id) or ""

        # Hududiy mas'ul xodim
        reg_admin = self.get_region_admin_info(inn=effective_inn, tuman=tuman)
        reg_admin_line = ""
        target_mention = "@quvonchbek_admin, @Yashnarbek_butaev"
        if reg_admin:
            ra_user = (reg_admin.get("username") or "").replace("@", "")
            reg_admin_line = f"▫️ Mas'ul mutaxassis: {reg_admin.get('admin_name')} (@{ra_user})"
            target_mention = f"@{ra_user}"

        # 1. Aniqlangan ma'lumotlar
        id_lines = []
        if org_name:
            id_lines.append(f"▫️ Korxona: <b>{html.escape(org_name)}</b>")
        if effective_inn:
            id_lines.append(f"▫️ STIR (INN): <code>{effective_inn}</code>")
        if session_fm:
            id_lines.append(f"▫️ Fiskal modul: <code>{session_fm}</code>")
        if tuman:
            id_lines.append(f"▫️ Hudud / Tuman: {tuman}")
        if model_str:
            id_lines.append(f"▫️ Apparat modeli: {model_str}")
        if comp_phone and comp_phone != "-":
            id_lines.append(f"▫️ Korxona telefoni: <code>{comp_phone}</code>")
        if internet_status:
            id_lines.append(f"▫️ Internet aloqasi: {internet_status}")
        if reg_admin_line:
            id_lines.append(reg_admin_line)

        id_block = "\n".join(id_lines) if id_lines else "▫️ Korxona ma'lumotlari kiritilmagan"

        # 2. Qarzdorlik holati
        debt_lines = []
        if monthly_debt is not None:
            if monthly_debt > 0:
                debt_lines.append(f"▫️ «Mars» oylik to'lovi: 🔴 <b>{monthly_debt:,.0f} so'm QARZ MAVJUD</b>")
            else:
                debt_lines.append("▫️ «Mars» oylik to'lovi: ✅ <b>0 so'm (To'langan / Qarz yo'q)</b>")
        else:
            debt_lines.append("▫️ «Mars» oylik to'lovi: ❓ <i>Noma'lum (INN yo'q)</i>")

        if override_annual_status:
            debt_lines.append(f"▫️ Davlat Soliq (OFD) yillik: {override_annual_status}")
        else:
            ann_st = user_memory.get_annual_status(chat_id, user_id) if (chat_id and user_id) else None
            if ann_st:
                if ann_st.get("has_debt"):
                    debt_lines.append("▫️ Davlat Soliq (OFD) yillik: 🔴 <b>440 000 so'm QARZ MAVJUD</b>")
                elif not ann_st.get("unavailable"):
                    debt_lines.append("▫️ Davlat Soliq (OFD) yillik: ✅ <b>Faol (Muddati joyida)</b>")
                else:
                    debt_lines.append("▫️ Davlat Soliq (OFD) yillik: ⚠️ <i>Tizim javob bermadi</i>")
            else:
                debt_lines.append("▫️ Davlat Soliq (OFD) yillik: ❓ <i>Tekshirilmagan</i>")

        last_receipt = user_memory.get_last_receipt(chat_id, user_id) if (chat_id and user_id) else None
        if last_receipt:
            amt = last_receipt.get("amount", 0.0)
            if amt > 0:
                debt_lines.append(f"▫️ Yaqinda to'langan: 💵 <b>{amt:,.0f} so'm</b> (Kvitansiya tekshiruvda)")

        debt_block = "\n".join(debt_lines)

        # 3. Aniqlanmagan ma'lumotlar
        all_photos = user_memory.get_all_photos(chat_id, user_id) if (chat_id and user_id) else []
        if photo_file_id and photo_file_id not in all_photos:
            all_photos.append(photo_file_id)

        missing_lines = []
        if not effective_inn:
            missing_lines.append("▫️ Korxona STIR (INN) kiritilmagan")
        if not session_fm:
            missing_lines.append("▫️ Kassa Fiskal moduli (LG/YG) ma'lum emas")
        if not all_photos:
            missing_lines.append("▫️ Apparat ekrani / nosozlik fotosurati tashlanmagan")
        if not missing_lines:
            missing_lines.append("▫️ Barcha asosiy ma'lumotlar to'liq aniqlangan ✅")

        missing_block = "\n".join(missing_lines)

        # 4. Suhbat mazmuni
        chat_summary = user_memory.get_short_conversation_summary(chat_id, user_id, max_messages=4) if (chat_id and user_id) else ""
        msg_body = query_text or user_comment or issue_summary or ""
        if not chat_summary and msg_body:
            chat_summary = f"▫️ <i>Mijoz:</i> {html.escape(msg_body[:120])}"
        elif msg_body and msg_body not in chat_summary:
            clean_body = html.escape(msg_body[:90])
            chat_summary += f"\n▫️ <i>Oxirgi xabar:</i> {clean_body}"

        # Muammo / Nosozlik tafsiloti
        issue_block = ""
        if issue_summary:
            issue_block = f"⚠️ <b>Muammo / Nosozlik:</b>\n<b>{html.escape(issue_summary)}</b>\n────────────────────\n"

        full_text = (
            f"{title}\n\n"
            f"📌 <b>Holat:</b> {reason}\n"
            f"👤 <b>Mijoz:</b> {user_link} ({user_username}) | ID: <code>{user_id}</code> | Chat: <code>{chat_id}</code>\n"
            f"────────────────────\n"
            f"🏢 <b>Aniqlangan ma'lumotlar:</b>\n"
            f"{id_block}\n"
            f"────────────────────\n"
            f"📊 <b>Qarzdorlik holati:</b>\n"
            f"{debt_block}\n"
            f"────────────────────\n"
            f"⚠️ <b>Aniqlanmagan ma'lumotlar:</b>\n"
            f"{missing_block}\n"
            f"────────────────────\n"
            f"{issue_block}"
            f"💬 <b>Suhbat mazmuni:</b>\n"
            f"{chat_summary}\n\n"
            f"⚡️ <i>Mas'ul mutaxassis ({target_mention}): Mijoz siz bilan bog'lanishni kutmoqda.</i>"
        )

        monthly_status_short = f"{monthly_debt:,.0f} so'm qarz" if (monthly_debt and monthly_debt > 0) else "0 so'm (qarz yo'q)"
        missing_short = ", ".join(m.replace("▫️ ", "") for m in missing_lines[:2])
        tuman_line_short = f"📍 {tuman}\n" if tuman else ""
        short_caption = (
            f"{title}\n"
            f"📌 {reason[:80]}\n"
            f"👤 {user_link} ({user_username})\n"
            f"🏢 <b>{html.escape(org_name or 'Aniqlanmagan')}</b> (INN: <code>{effective_inn or '-'}</code>)\n"
            f"{tuman_line_short}"
            f"📊 Qarz: {monthly_status_short}\n"
            f"⚠️ Yetishmaydi: {missing_short}\n"
            f"💬 <i>{html.escape(msg_body[:80], quote=False)}</i>\n"
            f"⚡️ Mas'ul: {target_mention}"
        )

        admin_kb = regional_admin_service.build_user_contact_keyboard_for_admin(user, phone=comp_phone)
        return full_text, short_caption, effective_inn, tuman, all_photos, admin_kb

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
        full_text, short_caption, eff_inn, tuman, all_photos, admin_kb = self._build_escalation_card(
            title="🚨 <b>TEXNIK NOSOZLIK BO'YICHA HUDUDIY ESKALATSIYA!</b>",
            reason=issue_summary,
            user=user,
            chat_id=chat_id,
            inn=inn,
            org_name=org_name,
            issue_summary=issue_summary,
            user_comment=user_comment,
            photo_file_id=photo_file_id,
            override_monthly_debt=0.0,
            internet_status="✅ ISHLAYAPTI (Faol)"
        )

        await self.notify_admins(
            bot=bot,
            text=full_text,
            photo_file_id=photo_file_id,
            short_caption=short_caption,
            inn=eff_inn,
            tuman=tuman,
            reply_markup=admin_kb,
            photos=all_photos
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
        hududiy adminga (va bosh adminlarga) mijoz ma'lumotlari, suhbat xulosasi va rasmlari bilan xabar yuborish.
        """
        full_text, short_caption, eff_inn, tuman, all_photos, admin_kb = self._build_escalation_card(
            title="🔔 <b>YANGI HUDUDIY ESKALATSIYA!</b>",
            reason=reason,
            user=user,
            chat_id=chat_id,
            inn=inn,
            org_name=org_name,
            query_text=query_text,
            photo_file_id=photo_file_id
        )

        await self.notify_admins(
            bot=bot,
            text=full_text,
            photo_file_id=photo_file_id,
            short_caption=short_caption,
            inn=eff_inn,
            tuman=tuman,
            reply_markup=admin_kb,
            photos=all_photos
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
        apparat nosozligi bo'yicha barcha to'plangan ma'lumotlar, suhbat mazmuni va rasmlarni
        zudlik bilan mijozning hududiy adminiga (@username) va bosh adminlarga uzatish.
        """
        full_text, short_caption, eff_inn, tuman, all_photos, admin_kb = self._build_escalation_card(
            title="🚨 <b>QARZDORLIKSIZ APPARAT NOSOZLIGI (HUDUDIY ESKALATSIYA)!</b>",
            reason="To'lovlar bo'yicha qarzdorlik yo'q (to'langan), apparatda nosozlik mavjud",
            user=user,
            chat_id=chat_id,
            inn=inn,
            org_name=org_name,
            fiscal_module=fiscal_module,
            device_model=device_model,
            issue_summary=issue_summary,
            user_comment=user_comment,
            photo_file_id=photo_file_id,
            override_monthly_debt=0.0,
            override_annual_status="✅ <b>Faol (To'langan / Qarz yo'q)</b>"
        )

        await self.notify_admins(
            bot=bot,
            text=full_text,
            photo_file_id=photo_file_id,
            short_caption=short_caption,
            inn=eff_inn,
            tuman=tuman,
            reply_markup=admin_kb,
            photos=all_photos
        )


def get_admin_contact_keyboard(inn: Optional[str] = None, tuman: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Foydalanuvchini aynan o'z hududidagi mas'ul mutaxassis (va bosh adminlar)
    bilan to'g'ridan-to'g'ri bog'lovchi interaktiv tugmalar.
    """
    from modules.admin_module import regional_admin_service
    return regional_admin_service.build_contact_keyboard(inn=inn, tuman=tuman)


admin_manager = AdminManager()
