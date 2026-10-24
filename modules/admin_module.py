"""
modules/admin_module.py
=======================
Mars Smart POS — Hududiy (Regional) Admin va Eskalatsiya Moduli.

Ushbu modul:
1. `data/regional_admins.json` orqali viloyatdagi 14+ shahar va tumanlarning har biriga
   alohida mas'ul admin/ustani biriktiradi.
2. Excel bazadagi korxona INN raqami orqali uning qaysi hudud (tuman/shahar) ekanini
   avtomatik aniqlaydi (Kirill, Lotin, katta-kichik harflar va «ТУМАНИ» qo'shimchalaridan qat'i nazar).
3. Mijozga aynan o'z hududidagi mas'ul adminning ismi, telefon raqami va Telegram profiliga
   to'g'ridan-to'g'ri o'tish tugmasini (`InlineKeyboardMarkup`) chiqarib beradi.
4. Mijozning barcha ma'lumotlari (Ism, @username, Telefon, INN, Korxona nomi, Hudud,
   Apparat modeli, Fiskal modul, Qarz holati) hamda APPARAT RASMINI (yoki kvitansiyani)
   aynan o'sha hudud adminiga + Bosh adminlarga yuboradi.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.module_registry import BaseBotModule

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
REGIONAL_ADMINS_PATH = os.path.join(DATA_DIR, "regional_admins.json")


def _normalize_region_str(val: str) -> str:
    """Hudud nomini solishtirish uchun yagona standart shaklga keltirish"""
    if not val:
        return ""
    s = str(val).lower().strip()
    s = s.replace("ʻ", "'").replace("ʼ", "'").replace("‘", "'").replace("’", "'").replace("`", "'")
    # Qo'shimcha so'zlarni tozalab ham tekshirish oson bo'lishi uchun
    return s


class RegionalAdminRouterService:
    """
    Hududlar (tuman/shahar) bo'yicha mas'ul adminlarni boshqarish va
    murojaatlarni (rasm + to'liq ma'lumotlar bilan) tegishli hudud adminiga yo'naltirish xizmati.
    """

    def __init__(self, json_path: str = REGIONAL_ADMINS_PATH):
        self.json_path = json_path
        self.super_admins: List[Dict[str, Any]] = []
        self.regional_admins: List[Dict[str, Any]] = []
        self.load()

    def load(self):
        """data/regional_admins.json faylidan hududiy adminlar ro'yxatini yuklash"""
        if not os.path.exists(self.json_path):
            logger.warning(f"Hududiy adminlar fayli topilmadi: {self.json_path}")
            return
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.super_admins = data.get("default_super_admins", [])
                self.regional_admins = data.get("regional_admins", [])
            logger.info(
                f"RegionalAdminRouterService yuklandi: {len(self.regional_admins)} ta hudud, "
                f"{len(self.super_admins)} ta super-admin."
            )
        except Exception as e:
            logger.error(f"regional_admins.json o'qishda xatolik: {e}")

    def save(self):
        """O'zgarishlarni data/regional_admins.json fayliga saqlash"""
        try:
            os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
            data = {
                "default_super_admins": self.super_admins,
                "regional_admins": self.regional_admins
            }
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"regional_admins.json saqlashda xatolik: {e}")

    def find_region_admin(self, tuman_raw: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Excel'dan kelgan `tuman` (masalan: 'шахрисабз', 'ҚАРШИ ШАҲАР', 'КИТОБ ТУМАНИ', 'гузор')
        qiymati bo'yicha `regional_admins.json` dan mos hudud adminini topish.
        """
        if not tuman_raw or str(tuman_raw).strip() in ("", "-", "None"):
            return None

        norm = _normalize_region_str(tuman_raw)
        # 1. To'g'ridan-to'g'ri kalit so'z mosligi
        for reg in self.regional_admins:
            if not reg.get("active", True):
                continue
            if norm == reg.get("region_id", "").lower():
                return reg
            for kw in reg.get("keywords", []):
                kw_norm = _normalize_region_str(kw)
                if kw_norm and (norm == kw_norm or kw_norm in norm or norm in kw_norm):
                    return reg

        # 2. Agar Excelda tuman bor bo'lsa-yu (masalan: 'миробод'), asosiy ro'yxatdan topilmasa -> 'other_regions' fallback
        for reg in self.regional_admins:
            if reg.get("region_id") == "other_regions" and reg.get("active", True):
                return reg

        return None

    def find_region_admin_by_inn(self, inn: Optional[str]) -> Optional[Dict[str, Any]]:
        """Korxona INN / JSHSHIR raqami orqali Excel'dan hududni topib, o'sha hudud adminini qaytarish"""
        if not inn or str(inn).strip() in ("", "-"):
            return None
        try:
            from excel_manager import excel_manager
            tuman = excel_manager.get_district_for_inn(str(inn).strip())
            if tuman:
                return self.find_region_admin(tuman)
        except Exception as e:
            logger.warning(f"INN ({inn}) bo'yicha hudud adminini topishda xatolik: {e}")
        return None

    def get_all_regions(self) -> List[Dict[str, Any]]:
        """Barcha hududlar ro'yxatini qaytarish"""
        return self.regional_admins

    def get_all_regions_summary(self) -> str:
        """Admin panel (/hududlar) uchun barcha hududlar va biriktirilgan adminlar ro'yxatini matn ko'rinishida qaytarish"""
        lines = ["🗺 <b>Viloyat va tumanlar bo'yicha Hududiy Adminlar (`data/regional_admins.json`):</b>\n"]
        for idx, reg in enumerate(self.regional_admins, 1):
            r_id = reg.get("region_id", "")
            r_name = reg.get("region_name", "")
            a_name = reg.get("admin_name", "")
            a_user = (reg.get("username") or "").lstrip("@")
            a_id = reg.get("telegram_id") or 0
            a_phone = reg.get("phone") or "-"
            status = "🟢" if reg.get("active", True) else "🔴"
            lines.append(
                f"{idx}. {status} <b>{r_name}</b> [<code>{r_id}</code>]\n"
                f"   👤 {a_name} | @{a_user} (ID: <code>{a_id}</code>) | 📞 {a_phone}"
            )
        lines.append(
            "\n✏️ <b>O'zgartirish:</b>\n"
            "1) Serverdagi <code>data/regional_admins.json</code> faylini tahrirlash orqali;\n"
            "2) Yoki botning o'zida:\n"
            "<code>/set_hudud_admin shahrisabz | Ism | @username | telegram_id | +998901234567</code>"
        )
        return "\n".join(lines)

    def update_region_admin(
        self,
        region_id: str,
        admin_name: str,
        username: str,
        telegram_id: Optional[int] = None,
        phone: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Berilgan region_id uchun mas'ul admin ma'lumotlarini yangilash yoki yangi hudud qo'shish"""
        clean_id = region_id.strip().lower()
        clean_username = username.strip().replace("@", "")
        for reg in self.regional_admins:
            if reg.get("region_id", "").lower() == clean_id:
                reg["admin_name"] = admin_name.strip()
                reg["username"] = clean_username
                if telegram_id is not None:
                    reg["telegram_id"] = int(telegram_id)
                if phone:
                    reg["phone"] = phone.strip()
                self.save()
                return reg

        # Agar bunday region_id topilmasa, yangi hudud sifatida qo'shamiz
        new_reg = {
            "region_id": clean_id,
            "region_name": f"{region_id.capitalize()} hududi",
            "keywords": [clean_id],
            "admin_name": admin_name.strip(),
            "username": clean_username,
            "telegram_id": int(telegram_id) if telegram_id else 0,
            "phone": phone.strip(),
            "active": True
        }
        self.regional_admins.append(new_reg)
        self.save()
        return new_reg

    def get_all_admin_telegram_ids(self) -> List[int]:
        """Tizimdagi barcha super-admin va hududiy adminlarning Telegram ID lari"""
        ids = set()
        for sa in self.super_admins:
            tid = sa.get("telegram_id")
            if tid and str(tid).isdigit() and int(tid) > 0:
                ids.add(int(tid))
        for ra in self.regional_admins:
            if not ra.get("active", True):
                continue
            tid = ra.get("telegram_id")
            if tid and str(tid).isdigit() and int(tid) > 0:
                ids.add(int(tid))
        return list(ids)

    def get_all_admin_usernames(self) -> List[str]:
        """Tizimdagi barcha super-admin va hududiy adminlarning Telegram username lari"""
        usernames = set()
        for sa in self.super_admins:
            u = (sa.get("username") or "").strip().lower().replace("@", "")
            if u:
                usernames.add(u)
        for ra in self.regional_admins:
            if not ra.get("active", True):
                continue
            u = (ra.get("username") or "").strip().lower().replace("@", "")
            if u:
                usernames.add(u)
        return list(usernames)

    def register_user_id_by_username(self, user_id: int, username: str) -> bool:
        """
        Agar hududiy admin botga yozsa yoki guruhda xabar yozsa va uning telegram_id si
        hali 0/mock bo'lsa, username orqali avtomatik ravishda haqiqiy telegram_id ni yozib qo'yadi!
        """
        if not username or not user_id:
            return False
        clean_u = username.strip().lower().replace("@", "")
        updated = False
        for sa in self.super_admins:
            if (sa.get("username") or "").strip().lower().replace("@", "") == clean_u:
                if sa.get("telegram_id") != user_id:
                    sa["telegram_id"] = user_id
                    updated = True
        for ra in self.regional_admins:
            if (ra.get("username") or "").strip().lower().replace("@", "") == clean_u:
                if ra.get("telegram_id") != user_id:
                    ra["telegram_id"] = user_id
                    updated = True
        if updated:
            self.save()
            logger.info(f"Hududiy admin (@{clean_u}) Telegram ID si avtomatik yangilandi: {user_id}")
        return updated

    def format_user_facing_admin_info(
        self,
        inn: Optional[str] = None,
        tuman: Optional[str] = None
    ) -> str:
        """
        Mijozga ko'rsatiladigan xabar ichida aynan uning hududiga biriktirilgan
        mas'ul admin (Ism, @username, Telefon) haqida chiroyli blok qaytarish.
        """
        reg_admin = None
        if tuman:
            reg_admin = self.find_region_admin(tuman)
        if not reg_admin and inn:
            reg_admin = self.find_region_admin_by_inn(inn)

        if reg_admin:
            r_name = reg_admin.get("region_name", tuman or "Hudud")
            a_name = reg_admin.get("admin_name", "Hududiy mas'ul usta")
            a_user = (reg_admin.get("username") or "").replace("@", "")
            a_phone = reg_admin.get("phone") or ""
            user_str = f" (@{a_user})" if a_user else ""
            phone_str = f"\n📞 <b>Telefon:</b> <code>{a_phone}</code>" if a_phone else ""
            return (
                f"📍 <b>Hudud:</b> {r_name}\n"
                f"👨‍💻 <b>Hududiy mas'ul mutaxassis:</b> {a_name}{user_str}"
                f"{phone_str}"
            )

        # Fallback: Agar INN yoki hudud hali noma'lum bo'lsa -> Umumiy mas'ullar
        return (
            "👨‍💻 <b>Hududiy THKM texnik xizmat ko'rsatish mas'ul xodimlari:</b>\n"
            "• Mas'ul xodim: @quvonchbek_admin (+998 91 945 32 89)\n"
            "• Bosh usta: @Yashnarbek_butaev (+998 94 299 77 99)"
        )

    def build_contact_keyboard(
        self,
        inn: Optional[str] = None,
        tuman: Optional[str] = None
    ) -> InlineKeyboardMarkup:
        """
        Mijozga chiqadigan interaktiv tugmalar:
        1. Agar hudud aniqlansa -> 1-qatorga aynan o'sha hudud adminining tugmasi chiqadi!
        2. Pastidan Bosh admin / Viloyat mas'uli tugmasi chiqadi.
        """
        buttons = []
        reg_admin = None
        if tuman:
            reg_admin = self.find_region_admin(tuman)
        if not reg_admin and inn:
            reg_admin = self.find_region_admin_by_inn(inn)

        added_usernames = set()

        if reg_admin:
            r_name = reg_admin.get("region_name", "Hudud")
            a_name = reg_admin.get("admin_name", "Mas'ul usta")
            a_user = (reg_admin.get("username") or "").strip().replace("@", "")
            if a_user:
                added_usernames.add(a_user.lower())
                buttons.append([
                    InlineKeyboardButton(
                        text=f"📍 {r_name}: {a_name} (@{a_user})",
                        url=f"https://t.me/{a_user}"
                    )
                ])

        # Super-adminlarni ham zaxira / nazorat uchun qo'shamiz
        for sa in self.super_admins:
            su = (sa.get("username") or "").strip().replace("@", "")
            s_role = sa.get("role", "Hududiy THKM mas'ul xodimi")
            if su and su.lower() not in added_usernames:
                added_usernames.add(su.lower())
                buttons.append([
                    InlineKeyboardButton(
                        text=f"👨‍💻 {s_role} (@{su})",
                        url=f"https://t.me/{su}"
                    )
                ])

        if not buttons:
            buttons = [
                [InlineKeyboardButton(text="👨‍💻 Hududiy THKM mas'ul xodimi (@quvonchbek_admin)", url="https://t.me/quvonchbek_admin")],
                [InlineKeyboardButton(text="🛠 Bosh administrator (@Yashnarbek_butaev)", url="https://t.me/Yashnarbek_butaev")]
            ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def get_target_admin_ids_for_escalation(
        self,
        inn: Optional[str] = None,
        tuman: Optional[str] = None,
        fallback_admin_ids: Optional[List[int]] = None,
        notification_channel_id: Optional[int] = None
    ) -> List[int]:
        """
        Murojaat yuborilishi kerak bo'lgan Telegram ID larni aniqlash:
        1. Aynan o'sha hududning mas'ul admini (agar telegram_id > 0 bo'lsa)
        2. Barcha `receive_all_escalations: true` bo'lgan Bosh adminlar
        3. Bildirishnoma kanali (agar sozlangan bo'lsa)
        """
        targets = []

        reg_admin = None
        if tuman:
            reg_admin = self.find_region_admin(tuman)
        if not reg_admin and inn:
            reg_admin = self.find_region_admin_by_inn(inn)

        if reg_admin:
            rtid = reg_admin.get("telegram_id")
            if rtid and str(rtid).isdigit() and int(rtid) > 0:
                targets.append(int(rtid))

        for sa in self.super_admins:
            if sa.get("receive_all_escalations", True):
                stid = sa.get("telegram_id")
                if stid and str(stid).isdigit() and int(stid) > 0 and int(stid) not in targets:
                    targets.append(int(stid))

        if fallback_admin_ids:
            for fid in fallback_admin_ids:
                if fid and int(fid) not in targets:
                    targets.append(int(fid))

        if notification_channel_id and notification_channel_id not in targets:
            targets.append(notification_channel_id)

        return targets

    def build_user_contact_keyboard_for_admin(
        self,
        user: Optional[types.User],
        phone: Optional[str] = None
    ) -> Optional[InlineKeyboardMarkup]:
        """
        Adminga borgan xabarnoma ostida mijozning profiliga 1-klik bilan o'tish tugmasini yaratish.
        Shunda admin mijozni qidirib o'tirmasdan darhol bog'lana oladi!
        """
        if not user:
            return None
        buttons = []
        if user.username:
            buttons.append([
                InlineKeyboardButton(
                    text=f"✉️ Mijozga yozish (@{user.username})",
                    url=f"https://t.me/{user.username}"
                )
            ])
        elif user.id:
            buttons.append([
                InlineKeyboardButton(
                    text=f"👤 Mijoz profili (ID: {user.id})",
                    url=f"tg://user?id={user.id}"
                )
            ])
        if phone and phone != "-" and len(phone.replace("+", "").strip()) >= 7:
            clean_p = phone.strip()
            buttons.append([
                InlineKeyboardButton(
                    text=f"📞 Korxonaga qo'ng'iroq ({clean_p})",
                    url=f"tel:{clean_p}"
                )
            ])
        return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


regional_admin_service = RegionalAdminRouterService()


class AdminModule(BaseBotModule):
    """
    Tashqi va ichki tizimlar uchun mustaqil Admin Moduli (`modules/admin_module.py`).
    """
    name = "admin_module"
    version = "2.1.0"
    description = "Viloyat va shahar/tumanlar bo'yicha hududiy adminlar, eskalatsiya va statistika moduli"
    priority = 100

    def get_router(self):
        from handlers.admin import router as admin_router
        return admin_router

    def get_services(self) -> Dict[str, Any]:
        from admin_manager import admin_manager
        return {
            "regional_admin_service": regional_admin_service,
            "admin_manager": admin_manager
        }

