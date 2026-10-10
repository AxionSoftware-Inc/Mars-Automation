import logging
from aiogram import Router, types, Bot, F
from aiogram.filters import Command
from aiogram.enums import ChatType

from admin_manager import admin_manager
from excel_manager import excel_manager
from user_memory import user_memory

logger = logging.getLogger(__name__)

router = Router(name="admin_router")

def is_admin_filter(message: types.Message) -> bool:
    """Faqat adminlarga ruxsat beruvchi filtr"""
    user_id = message.from_user.id if message.from_user else 0
    # Agar adminlar ro'yxati bo'sh bo'lsa, istalgan dastlabki kishiga sozlashga ruxsat
    admin_ids = admin_manager.get_admin_ids()
    if not admin_ids:
        return True
    return admin_manager.is_admin(user_id)

@router.message(Command("admin"), is_admin_filter)
async def cmd_admin_panel(message: types.Message):
    """Admin boshqaruv paneli"""
    admin_ids = admin_manager.get_admin_ids()
    contacts = admin_manager.contacts

    text = (
        "⚙️ <b>«Mars POS» Admin Boshqaruv Paneli</b>\n\n"
        f"📊 <b>Excel bazasi:</b> {excel_manager.records_count} ta yozuv indekslangan\n"
        f"👥 <b>Adminlar soni:</b> {len(admin_ids)} ta\n"
        f"📞 <b>Mas'ul kontaktlar:</b> {len(contacts)} ta\n"
        f"💾 <b>Faol sessiyalar:</b> {len(user_memory.sessions)} ta foydalanuvchi\n\n"
        "<b>Mavjud buyruqlar:</b>\n"
        "🔹 /statistika — Kengaytirilgan qarz va baza statistikasi\n"
        "🔹 /admins — Barcha adminlar ro'yxati\n"
        "🔹 /add_admin <code>&lt;user_id&gt;</code> — Yangi admin qo'shish\n"
        "🔹 /del_admin <code>&lt;user_id&gt;</code> — Adminni o'chirish\n"
        "🔹 /contacts — Mas'ul xodimlar kontaktlari\n"
        "🔹 /add_contact <code>Ism | Telefon | Lavozim</code> — Yangi kontakt qo'shish\n"
        "🔹 /del_contact <code>Telefon</code> — Kontaktni o'chirish"
    )
    await message.reply(text, parse_mode="HTML")

@router.message(Command("statistika"), is_admin_filter)
async def cmd_statistika(message: types.Message):
    """Batafsil qarzdorlik va tizim statistikasi"""
    total_records = excel_manager.records_count

    debtors_count = 0
    total_debt_sum = 0.0

    for records in excel_manager.stir_index.values():
        for r in records:
            d = r.get("debt", 0.0)
            if d > 0:
                debtors_count += 1
                total_debt_sum += d

    text = (
        "📊 <b>Mars Elektron Texnika — Tizim Statistikasi</b>\n\n"
        f"📁 <b>Jami ro'yxatga olingan apparatlar:</b> {total_records} ta\n"
        f"🔴 <b>Qarzdor korxonalar/apparatlar soni:</b> {debtors_count} ta\n"
        f"💰 <b>Jami qarzdorlik summasi:</b> {total_debt_sum:,.0f} so'm\n"
        f"👥 <b>Botdagi faol xotira sessiyalari:</b> {len(user_memory.sessions)} ta\n"
    )
    await message.reply(text, parse_mode="HTML")

@router.message(Command("admins"), is_admin_filter)
async def cmd_list_admins(message: types.Message):
    """Adminlar ro'yxati"""
    admin_ids = admin_manager.get_admin_ids()
    if not admin_ids:
        await message.reply("Hozircha birorta ham admin kiritilmagan. /add_admin orqali qo'shing.")
        return

    lines = ["👥 <b>Ro'yxatdan o'tgan Adminlar:</b>"]
    for idx, aid in enumerate(admin_ids, 1):
        lines.append(f"{idx}. <code>{aid}</code>")

    lines.append("\nAdmin qo'shish: <code>/add_admin &lt;id&gt;</code>\nO'chirish: <code>/del_admin &lt;id&gt;</code>")
    await message.reply("\n".join(lines), parse_mode="HTML")

@router.message(Command("add_admin"), is_admin_filter)
async def cmd_add_admin(message: types.Message):
    """Yangi admin qo'shish: /add_admin 123456789"""
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("Noto'g'ri format. Misol: <code>/add_admin 123456789</code>", parse_mode="HTML")
        return

    new_id = int(parts[1])
    success = admin_manager.add_admin(new_id)
    if success:
        await message.reply(f"✅ Yangi admin qo'shildi: <code>{new_id}</code>", parse_mode="HTML")
    else:
        await message.reply(f"Ushbu ID (<code>{new_id}</code>) allaqachon adminlar ro'yxatida bor.", parse_mode="HTML")

@router.message(Command("del_admin"), is_admin_filter)
async def cmd_del_admin(message: types.Message):
    """Adminni o'chirish: /del_admin 123456789"""
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("Noto'g'ri format. Misol: <code>/del_admin 123456789</code>", parse_mode="HTML")
        return

    target_id = int(parts[1])
    success = admin_manager.remove_admin(target_id)
    if success:
        await message.reply(f"✅ Admin o'chirildi: <code>{target_id}</code>", parse_mode="HTML")
    else:
        await message.reply(f"Ushbu ID (<code>{target_id}</code>) topilmadi.", parse_mode="HTML")

@router.message(Command("contacts"), is_admin_filter)
async def cmd_contacts(message: types.Message):
    """Kontaktlar ro'yxati"""
    text = admin_manager.get_contacts_display()
    text += (
        "\n\n<b>Kontakt qo'shish:</b>\n"
        "<code>/add_contact Ism | +998901234567 | Lavozim</code>\n"
        "<b>O'chirish:</b>\n"
        "<code>/del_contact +998901234567</code>"
    )
    await message.reply(text, parse_mode="HTML")

@router.message(Command("add_contact"), is_admin_filter)
async def cmd_add_contact(message: types.Message):
    """Kontakt qo'shish: /add_contact Ali | +998901234567 | Usta"""
    raw_args = message.text[len("/add_contact"):].strip()
    parts = [p.strip() for p in raw_args.split("|")]
    if len(parts) < 2:
        await message.reply(
            "Format xato. Misol:\n<code>/add_contact Anvar Aka | +998901234567 | Kassa ustasi</code>",
            parse_mode="HTML"
        )
        return

    name = parts[0]
    phone = parts[1]
    role = parts[2] if len(parts) > 2 else ""

    admin_manager.add_contact(name=name, phone=phone, role=role)
    await message.reply(
        f"✅ <b>Yangi kontakt saqlandi!</b>\n"
        f"👤 <b>Ism:</b> {name}\n"
        f"📞 <b>Telefon:</b> {phone}\n"
        f"💼 <b>Lavozim:</b> {role}",
        parse_mode="HTML"
    )

@router.message(Command("del_contact"), is_admin_filter)
async def cmd_del_contact(message: types.Message):
    """Kontaktni o'chirish: /del_contact +998901234567"""
    phone = message.text[len("/del_contact"):].strip()
    if not phone:
        await message.reply("Telefon raqamini kiriting. Misol: <code>/del_contact +998901234567</code>", parse_mode="HTML")
        return

    success = admin_manager.remove_contact(phone)
    if success:
        await message.reply(f"✅ Kontakt o'chirildi: <code>{phone}</code>", parse_mode="HTML")
    else:
        await message.reply(f"Telefon raqam topilmadi: <code>{phone}</code>", parse_mode="HTML")
