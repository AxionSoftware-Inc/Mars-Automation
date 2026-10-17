import logging
from aiogram import Router, types, Bot, F
from aiogram.filters import Command
from aiogram.enums import ChatType

from admin_manager import admin_manager
from excel_manager import excel_manager
from user_memory import user_memory
from error_manager import error_manager
from ofd_bridge import ofd_bridge

logger = logging.getLogger(__name__)

router = Router(name="admin_router")

def is_admin_filter(message: types.Message) -> bool:
    """Faqat adminlarga ruxsat beruvchi filtr"""
    user_id = message.from_user.id if message.from_user else 0
    admin_ids = admin_manager.get_admin_ids()
    if not admin_ids:
        return True
    return admin_manager.is_admin(user_id)

@router.message(Command("admin"), is_admin_filter)
async def cmd_admin_panel(message: types.Message):
    """Admin boshqaruv paneli"""
    admin_ids = admin_manager.get_admin_ids()
    contacts = admin_manager.contacts
    rules_count = len(error_manager.rules)
    ofd_status_text = "✅ Ulangan" if ofd_bridge.is_configured() else "⚠️ Ulanmagan"

    text = (
        "⚙️ <b>«Mars POS» Admin Boshqaruv Paneli</b>\n\n"
        f"📊 <b>Excel bazasi:</b> {excel_manager.records_count} ta yozuv indekslangan\n"
        f"🛠 <b>Ekran nosozliklari bazasi:</b> {rules_count} ta xatolik kiritilgan\n"
        f"🏛 <b>OFD ko'prigi:</b> {ofd_status_text} (ID: <code>{ofd_bridge.ofd_group_id}</code>)\n"
        f"👥 <b>Adminlar soni:</b> {len(admin_ids)} ta\n"
        f"📞 <b>Mas'ul kontaktlar:</b> {len(contacts)} ta\n"
        f"💾 <b>Faol sessiyalar:</b> {len(user_memory.sessions)} ta foydalanuvchi\n\n"
        "<b>Mavjud buyruqlar:</b>\n"
        "🔹 /statistika — Qarz va tizim statistikasi\n"
        "🔹 /ofd — OFD (@ofd943_bot) holati va diagnostika\n"
        "🔹 /set_ofd_channel <code>&lt;chat_id&gt;</code> — OFD ko'prik kanalini sozlash\n"
        "🔹 /test_ofd <code>[FM]</code> — Jonli OFD tekshiruvini sinab ko'rish\n"
        "🔹 /errors — Barcha 20+ ta kassa xatoliklari qoidalari\n"
        "🔹 /add_error <code>id | nom | kalit_sozlar | yechim | video_id</code>\n"
        "🔹 /del_error <code>&lt;id&gt;</code> — Xatolik qoidasini o'chirish\n"
        "🔹 /admins — Barcha adminlar ro'yxati\n"
        "🔹 /add_admin <code>&lt;user_id&gt;</code> — Yangi admin qo'shish\n"
        "🔹 /del_admin <code>&lt;user_id&gt;</code> — Adminni o'chirish\n"
        "🔹 /contacts — Mas'ul xodimlar kontaktlari\n"
        "🔹 /add_contact <code>Ism | Telefon | Lavozim</code> — Yangi kontakt qo'shish\n"
        "🔹 /del_contact <code>Telefon</code> — Kontaktni o'chirish\n"
        "🔹 /hududlar — Viloyat va tumanlar bo'yicha hududiy adminlar ro'yxati\n"
        "🔹 /set_hudud_admin <code>region_id | Ism | @user | tg_id | tel</code> — Hudud adminini yangilash\n"
        "🔹 /modules — Ulangan tizim modullari ro'yxati\n"
        "🔹 /patches — Dinamik qoidalar (Plug & Play) ro'yxati\n"
        "🔹 /add_patch <code>id | so'z1, so'z2 | Javob | video_id</code> — Yangi qoida qo'shish\n"
        "🔹 /del_patch <code>id</code> — Dinamik qoidani o'chirish"
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
        f"🛠 <b>Ekran nosozliklari qoidalari:</b> {len(error_manager.rules)} ta\n"
        f"👥 <b>Botdagi faol xotira sessiyalari:</b> {len(user_memory.sessions)} ta\n"
    )
    await message.reply(text, parse_mode="HTML")

@router.message(Command("errors"), is_admin_filter)
async def cmd_list_errors(message: types.Message):
    """Barcha kiritilgan 20+ ekran xatoliklarini ro'yxatini ko'rish"""
    rules = error_manager.get_all_rules()
    if not rules:
        await message.reply("Hozircha xatoliklar qoidalari bo'sh.")
        return

    lines = [f"🛠 <b>Kassa Apparatlari Ekran Nosozliklari ({len(rules)} ta):</b>\n"]
    for idx, r in enumerate(rules, 1):
        vid = f" (🎬 Video {r.get('video_id')})" if r.get('video_id') else ""
        lines.append(f"<b>{idx}. {r.get('name')}</b> [<code>{r.get('id')}</code>]{vid}")

    lines.append("\nQo'shish: <code>/add_error id | Nomi | so'z1, so'z2 | Yechim matni | video_id</code>")
    lines.append("O'chirish: <code>/del_error id</code>")

    full_text = "\n".join(lines)
    # Agar xabar 4000 belgidan oshsa, bo'lib jo'natish
    if len(full_text) > 4000:
        for x in range(0, len(full_text), 4000):
            await message.reply(full_text[x:x+4000], parse_mode="HTML")
    else:
        await message.reply(full_text, parse_mode="HTML")

@router.message(Command("add_error"), is_admin_filter)
async def cmd_add_error(message: types.Message):
    """
    Yangi xatolik qo'shish yoki mavjudini yangilash:
    /add_error id | Nomi | kalit1, kalit2 | Yechim matni | video_id
    """
    raw_args = message.text[len("/add_error"):].strip()
    parts = [p.strip() for p in raw_args.split("|")]
    if len(parts) < 4:
        await message.reply(
            "Format xato. Misol:\n"
            "<code>/add_error pin_error | PIN-pad xatosi | pinpad xato, pin xato | PIN-pad kabelini tekshiring | 101</code>",
            parse_mode="HTML"
        )
        return

    rule_id = parts[0]
    name = parts[1]
    keywords = [k.strip() for k in parts[2].split(",") if k.strip()]
    response_text = parts[3]
    video_id = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None

    error_manager.add_or_update_rule(
        rule_id=rule_id,
        name=name,
        screen_keywords=keywords,
        response_text=response_text,
        video_id=video_id
    )

    vid_str = str(video_id) if video_id else "Mavjud emas"
    await message.reply(
        f"✅ <b>Yangi xatolik qoidasi saqlandi!</b>\n\n"
        f"🆔 ID: <code>{rule_id}</code>\n"
        f"📌 Nomi: <b>{name}</b>\n"
        f"🔑 Kalit so'zlar: <code>{', '.join(keywords)}</code>\n"
        f"🎬 Video: {vid_str}",
        parse_mode="HTML"
    )

@router.message(Command("del_error"), is_admin_filter)
async def cmd_del_error(message: types.Message):
    """Xatolik qoidasini o'chirish: /del_error rule_id"""
    rule_id = message.text[len("/del_error"):].strip()
    if not rule_id:
        await message.reply("ID ni kiriting. Misol: <code>/del_error time_error</code>", parse_mode="HTML")
        return

    success = error_manager.delete_rule(rule_id)
    if success:
        await message.reply(f"✅ Xatolik qoidasi o'chirildi: <code>{rule_id}</code>", parse_mode="HTML")
    else:
        await message.reply(f"Bunday ID li qoida topilmadi: <code>{rule_id}</code>", parse_mode="HTML")

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

# =============================================================================
# OFD (@ofd943_bot) KO'PRIGI BOSHQARUVI VA DIAGNOSTIKASI
# =============================================================================

@router.message(Command("ofd", "ofd_status"), is_admin_filter)
async def cmd_ofd_status(message: types.Message, bot: Bot):
    """OFD ko'prigi (@ofd943_bot) holati va sozlamalarini ko'rsatish"""
    st = await ofd_bridge.get_status_info(bot=bot)

    configured_emoji = "✅ Ulangan" if st["configured"] else "⚠️ Ulanmagan"
    chat_id = st["chat_id"] or "Mavjud emas"
    chat_title = st["chat_title"] or "Noma'lum"
    chat_type = st["chat_type"] or "Noma'lum"

    our_bot_badge = "✅ Mavjud" if st["our_bot_present"] else "❌ Yo'q / Aniqlanmadi"
    ofd_bot_badge = "✅ Mavjud" if st["ofd_bot_present"] else "❌ Yo'q / Aniqlanmadi"
    can_post = "✅ Ruxsat berilgan" if st.get("can_post_messages") else ("ℹ️ Noma'lum" if st.get("can_post_messages") is None else "❌ Ruxsat yo'q")

    text = (
        "🏛 <b>Davlat Soliq (OFD) Ko'prigi Holati</b>\n\n"
        f"🔘 <b>Holat:</b> {configured_emoji}\n"
        f"🆔 <b>Ko'prik Chat ID:</b> <code>{chat_id}</code>\n"
        f"📛 <b>Chat nomi:</b> {chat_title} ({chat_type})\n"
        f"🤖 <b>Bizning bot (@marselektrontexnikamchj_bot):</b> {our_bot_badge}\n"
        f"📝 <b>Post yozish huquqi:</b> {can_post}\n"
        f"🤖 <b>OFD bot (@{st['ofd_username']}):</b> {ofd_bot_badge}\n"
        f"💾 <b>Keshdagi FM lar:</b> {st['cached_keys_count']} ta\n"
        f"👤 <b>Telethon Userbot sessiyasi:</b> {'✅ Faol' if st['has_user_session'] else '❌ Yo\'q (Bot API ishlamoqda)'}\n"
    )

    if st.get("error"):
        text += f"\n⚠️ <b>Xatolik:</b> <code>{st['error']}</code>\n"

    text += (
        "\n<b>Buyruqlar:</b>\n"
        "🔹 /set_ofd_channel <code>&lt;chat_id&gt;</code> — Yangi kanal/guruh ID sini ulash\n"
        "🔹 /test_ofd <code>[FM_KOD]</code> — Jonli tekshirish (masalan: <code>/test_ofd LG420230615712</code>)\n\n"
        "💡 <i>Eslatma: Botimiz va @ofd943_bot admin bo'lgan kanalga post yuborilsa yoki shu kanalda /set_ofd_channel yozilsa, ko'prik avtomatik ulanadi.</i>"
    )

    await message.reply(text, parse_mode="HTML")

@router.message(Command("set_ofd_channel", "set_ofd_group"), is_admin_filter)
async def cmd_set_ofd_channel(message: types.Message, bot: Bot):
    """OFD kanali yoki guruhini qo'lda sozlash"""
    raw_args = message.text.split()
    target_chat_id = None

    if len(raw_args) > 1:
        target_arg = raw_args[1].strip()
        if target_arg.startswith("https://t.me/"):
            target_arg = "@" + target_arg.replace("https://t.me/", "").strip("/")
        try:
            target_chat_id = int(target_arg)
        except ValueError:
            target_chat_id = target_arg
    else:
        target_chat_id = message.chat.id

    try:
        chat = await bot.get_chat(target_chat_id)
        chat_title = chat.title or chat.first_name or "Nomsiz"
        chat_type = chat.type
        real_chat_id = chat.id
    except Exception as e:
        await message.reply(
            f"❌ Chatni topib bo'lmadi: <code>{target_chat_id}</code>\n"
            f"Sabab: <i>{e}</i>\n\n"
            f"Bot avval ushbu chat/kanalga admin qilib qo'shilganiga ishonch hosil qiling.",
            parse_mode="HTML"
        )
        return

    ofd_bridge.set_ofd_group(real_chat_id)

    # Adminlarni tekshirish
    admins_text = ""
    try:
        admins = await bot.get_chat_administrators(target_chat_id)
        ofd_found = any(ofd_bridge.is_ofd_user(a.user) for a in admins)
        admins_text = (
            f"\n🤖 <b>@{ofd_bridge.ofd_username}:</b> {'✅ Chatda admin sifatida topildi!' if ofd_found else '⚠️ Chatda adminlar ro\'yxatida ko\'rinmadi (OFD botni ham kanalga admin qilib qo\'shing!)'}"
        )
    except Exception:
        pass

    await message.reply(
        f"✅ <b>OFD ko'prik kanali muvaffaqiyatli saqlandi!</b>\n\n"
        f"🆔 <b>Chat ID:</b> <code>{target_chat_id}</code>\n"
        f"📛 <b>Nomi:</b> {chat_title} ({chat_type})"
        f"{admins_text}\n\n"
        f"Endi <code>/test_ofd</code> buyrug'i orqali tekshirib ko'rishingiz mumkin.",
        parse_mode="HTML"
    )

@router.message(Command("test_ofd"), is_admin_filter)
async def cmd_test_ofd(message: types.Message, bot: Bot):
    """Jonli OFD so'rovini yuborib tekshirish: /test_ofd LG420230615712"""
    raw_args = message.text.split()
    test_code = raw_args[1].strip() if len(raw_args) > 1 else "LG420230615712"

    if not ofd_bridge.is_configured():
        await message.reply(
            "⚠️ <b>OFD ko'prigi hali ulanmagan!</b>\n\n"
            "Avval <code>/set_ofd_channel &lt;chat_id&gt;</code> buyrug'i orqali kanalni sozlang yoki /ofd ni bosing.",
            parse_mode="HTML"
        )
        return

    wait_msg = await message.reply(
        f"⏳ @{ofd_bridge.ofd_username} tizimiga so'rov yuborilmoqda...\n"
        f"📟 <b>Fiskal modul:</b> <code>{test_code}</code>\n"
        f"🆔 <b>Kanal:</b> <code>{ofd_bridge.ofd_group_id}</code>",
        parse_mode="HTML"
    )

    res = await ofd_bridge.test_connection(bot=bot, test_code=test_code, timeout=9.0)

    if res["success"]:
        from payment_accounts import format_ofd_annual_status
        formatted = format_ofd_annual_status(res["code"], res["reply"])
        resp_text = (
            f"✅ <b>OFD TIZIMI MUVAFFAQIYATLI JAVOB BERDI!</b>\n"
            f"⏱ <b>Javob tezligi:</b> {res['duration_sec']} soniya\n\n"
            f"📥 <b>Xom javob matni:</b>\n<i>{res['reply']}</i>\n\n"
            f"────────────────────\n"
            f"<b>Mijozga ko'rsatiladigan format:</b>\n{formatted}"
        )
    else:
        resp_text = (
            f"❌ <b>OFD TIZIMIDAN JAVOB OLINMADI! (Timeout {res['duration_sec']}s)</b>\n\n"
            f"📌 <b>Mumkin bo'lgan sabablar:</b>\n"
            f"1️⃣ @{ofd_bridge.ofd_username} kanalda/guruhda admin emas yoki xabar yozish ruxsati yo'q;\n"
            f"2️⃣ Bizning botga kanalda xabar yozish ruxsati (Post messages) berilmagan;\n"
            f"3️⃣ Soliq tizimi (@ofd943_bot) serverida vaqtinchalik uzilish mavjud."
        )

    try:
        await wait_msg.edit_text(resp_text, parse_mode="HTML")
    except Exception:
        await message.reply(resp_text)


# =============================================================================
# MODULLAR VA DINAMIK QOIDALAR (PLUG & PLAY RULE ENGINE) BOSHQARUVI
# =============================================================================

@router.message(Command("modules"), is_admin_filter)
async def cmd_list_modules(message: types.Message):
    """Tizimga ulangan barcha modullar holatini ko'rish"""
    from core.module_registry import module_registry
    mods = module_registry.list_modules_info()
    lines = [f"🧩 <b>Ulangan Tizim Modullari ({len(mods)} ta):</b>\n"]
    for idx, m in enumerate(mods, 1):
        status = "🟢 Faol" if m.get("enabled") else "🔴 O'chiq"
        lines.append(
            f"<b>{idx}. {m['name']}</b> (v{m['version']}) — {status} [Priority: {m['priority']}]\n"
            f"   <i>{m.get('description', '')}</i>"
        )
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("patches"), is_admin_filter)
async def cmd_list_patches(message: types.Message):
    """data/custom_patches.json dagi barcha dinamik qoidalarni ko'rish"""
    from core.rule_engine import rule_engine
    rules = rule_engine.get_rules_summary()
    if not rules:
        await message.reply(
            "📑 Hozircha dinamik patchlar (qoidalar) yo'q.\n\n"
            "Qo'shish: <code>/add_patch id | kalit1, kalit2 | Javob matni | video_id</code>",
            parse_mode="HTML"
        )
        return

    lines = [f"📑 <b>Faol Dinamik Qoidalar ({len(rules)} ta):</b>\n"]
    for idx, r in enumerate(rules, 1):
        lines.append(f"{idx}. <code>{r['name']}</code> (priority={r['priority']}, enabled={r['enabled']})")

    lines.append("\nQo'shish: <code>/add_patch id | kalit1, kalit2 | Javob matni | video_id</code>")
    lines.append("O'chirish: <code>/del_patch id</code>")
    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("add_patch"), is_admin_filter)
async def cmd_add_patch(message: types.Message):
    """
    Kodga tegmasdan yangi qoida qo'shish:
    /add_patch id | kalit1, kalit2 | Javob matni | video_id
    """
    from core.rule_engine import rule_engine
    raw_args = message.text[len("/add_patch"):].strip()
    parts = [p.strip() for p in raw_args.split("|")]
    if len(parts) < 3:
        await message.reply(
            "Format: <code>/add_patch id | kalit1, kalit2 | Javob matni | [video_id]</code>",
            parse_mode="HTML"
        )
        return

    patch_id = parts[0]
    keywords = [k.strip() for k in parts[1].split(",") if k.strip()]
    reply_text = parts[2]
    video_id = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None

    ok = rule_engine.add_patch(
        patch_id=patch_id,
        keywords=keywords,
        reply_text=reply_text,
        video_id=video_id
    )
    if ok:
        await message.reply(
            f"✅ <b>Yangi dinamik qoida qo'shildi va darhol ishga tushdi!</b>\n"
            f"🆔 ID: <code>{patch_id}</code>\n"
            f"🔑 Kalit so'zlar: <code>{', '.join(keywords)}</code>",
            parse_mode="HTML"
        )
    else:
        await message.reply("❌ Qoidani saqlashda xatolik yuz berdi.")


@router.message(Command("del_patch"), is_admin_filter)
async def cmd_del_patch(message: types.Message):
    """Dinamik qoidani o'chirish: /del_patch id"""
    from core.rule_engine import rule_engine
    patch_id = message.text[len("/del_patch"):].strip()
    if not patch_id:
        await message.reply("Format: <code>/del_patch id</code>", parse_mode="HTML")
        return

    if rule_engine.remove_patch(patch_id):
        await message.reply(f"✅ Qoida o'chirildi: <code>{patch_id}</code>", parse_mode="HTML")
    else:
        await message.reply(f"❌ Qoida topilmadi: <code>{patch_id}</code>", parse_mode="HTML")


# =============================================================================
# HUDUDIY ADMINLAR MODULI BOSHQARUVI (data/regional_admins.json)
# =============================================================================

@router.message(Command("hududlar", "regional_admins"), is_admin_filter)
async def cmd_list_hududlar(message: types.Message):
    """Viloyat va tumanlar bo'yicha biriktirilgan hududiy adminlar ro'yxatini ko'rsatish"""
    from modules.admin_module import regional_admin_service
    text = regional_admin_service.get_all_regions_summary()
    await message.reply(text, parse_mode="HTML")


@router.message(Command("set_hudud_admin"), is_admin_filter)
async def cmd_set_hudud_admin(message: types.Message):
    """
    Hududiy admin ma'lumotlarini yangilash:
    /set_hudud_admin qarshi | Quvonchbek (Qarshi) | @quvonchbek_admin | 7516266624 | +998 97 383 22 25
    """
    from modules.admin_module import regional_admin_service
    raw_args = message.text[len("/set_hudud_admin"):].strip()
    parts = [p.strip() for p in raw_args.split("|")]
    if len(parts) < 3:
        await message.reply(
            "Format xato. Misol:\n"
            "<code>/set_hudud_admin shahrisabz | Anvar Aka | @anvar_admin | 123456789 | +998 90 123 45 67</code>\n\n"
            "Barcha hudud kodlarini ko'rish uchun: /hududlar",
            parse_mode="HTML"
        )
        return

    region_id = parts[0].lower()
    admin_name = parts[1]
    username = parts[2]
    tg_id = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
    phone = parts[4] if len(parts) > 4 else None

    ok = regional_admin_service.update_region_admin(
        region_id=region_id,
        admin_name=admin_name,
        username=username,
        telegram_id=tg_id,
        phone=phone
    )
    if ok:
        await message.reply(
            f"✅ <b>Hududiy admin muvaffaqiyatli yangilandi!</b>\n\n"
            f"📍 <b>Hudud kodi:</b> <code>{region_id}</code>\n"
            f"👤 <b>Mas'ul:</b> {admin_name}\n"
            f"💬 <b>Telegram:</b> @{username.lstrip('@')}\n"
            f"🆔 <b>Telegram ID:</b> <code>{tg_id or 'Avto-aniqlanadi'}</code>\n"
            f"📞 <b>Telefon:</b> {phone or 'Kiritilmagan'}",
            parse_mode="HTML"
        )
    else:
        await message.reply(
            f"❌ Bunday hudud kodi topilmadi: <code>{region_id}</code>\n"
            f"Mavjud hudud kodlarini ko'rish uchun /hududlar buyrug'ini yuboring.",
            parse_mode="HTML"
        )


