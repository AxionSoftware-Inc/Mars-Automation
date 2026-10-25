"""
templates.py
============
Barcha bot xabarlari, javob matnlari va to'lov rekvizitlarining yagona markazlashtirilgan moduli.
Barcha shablonlar ortiqcha gap-so'zlardan tozalangan, ixcham va lo'nda qilib tuzilgan.
"""

from typing import Optional, List, Dict, Any, Tuple
from translit_manager import adapt_to_user_script
from excel_manager import excel_manager


# =============================================================================
# 1. ASOSIY BUYRUQLAR (/start, /help)
# =============================================================================

def get_start_template(script: str = "latin") -> str:
    """Start buyrug'i uchun ixcham boshlanish matni"""
    text = (
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "Qarzdorlikni tekshirish uchun <b>INN</b> yoki <b>JSHSHIR</b> raqamingizni yuboring.\n\n"
        "• /tolov — To'lov rekvizitlari\n"
        "• /help — Buyruqlar ro'yxati\n\n"
        "<i>Savolingiz yoki apparat ekranidagi xatolik rasmini to'g'ridan-to'g'ri yuborishingiz mumkin.</i>"
    )
    return adapt_to_user_script(text, script)


def get_help_template(script: str = "latin") -> str:
    """Buyruqlar ro'yxati va qisqa yo'riqnoma"""
    text = (
        "📖 <b>Buyruqlar ro'yxati:</b>\n\n"
        "• /start — Bosh menyu\n"
        "• /tekshir <code>[INN]</code> — Qarzdorlikni tekshirish\n"
        "• /tolov — To'lov rekvizitlari\n"
        "• /tarix — Oxirgi korxona to'lov tarixi\n"
        "• /help — Yordam"
    )
    return adapt_to_user_script(text, script)


# =============================================================================
# 2. TO'LOV REKVIZITLARI VA HISOB RAQAMLAR
# =============================================================================

def get_monthly_payment_card(script: str = "latin") -> str:
    """Oylik abonent to'lovi (Mars Elektron Texnika) uchun aniq rekvizitlar"""
    text = (
        "💳 <b>OYLIK ABONENT TO'LOVI REKVIZITLARI:</b>\n"
        "• <b>Tashkilot:</b> «MARS ELEKTRON TEXNIKA» MCHJ\n"
        "• <b>Hisob raqam:</b> <code>20208000800208044003</code>\n"
        "• <b>Bank:</b> «Ipak Yo'li» AITB Shahrisabz, MFO: <code>01048</code>\n"
        "• <b>INN (STIR):</b> <code>302568138</code>\n"
        "• <b>Summa:</b> 100 000 so'm (har oyning 6-sanasigacha)\n"
        "• <b>To'lov maqsadi:</b> <code>INN [korxona INN] abonent to'lovi</code>\n\n"
        "📲 <i>Click -> To'lovlar -> Rekvizit bo'yicha to'lov</i>"
    )
    return adapt_to_user_script(text, script)


def get_annual_payment_card(script: str = "latin") -> str:
    """Yillik fiskal modul to'lovi (Yangi Texnologiyalar DUK) uchun aniq rekvizitlar"""
    text = (
        "🏛 <b>YILLIK FISKAL MODUL TO'LOVI REKVIZITLARI:</b>\n"
        "• <b>Tashkilot:</b> «Yangi Texnologiyalar» DUK (Davlat Soliq Qo'mitasi)\n"
        "• <b>Hisob raqam:</b> <code>20210000100431200010</code>\n"
        "• <b>Bank:</b> ATB «Kapitalbank» Toshkent, MFO: <code>01018</code>\n"
        "• <b>INN:</b> <code>201589463</code> | <b>To'lov kodi:</b> <code>00668</code>\n"
        "• <b>Summa:</b> 440 000 so'm (1 yilga)\n"
        "• <b>To'lov maqsadi:</b> <code>INN [korxona INN] fiskal modulning yillik to'lovi</code>\n\n"
        "⏳ <i>To'lovdan so'ng 2-24 soat ichida Soliq tizimida avtomatik uzaytiriladi.</i>\n"
        "⚠️ <i>Oylik to'lovdan mutlaqo alohidadir.</i>"
    )
    return adapt_to_user_script(text, script)


def get_all_payment_accounts_card(script: str = "latin") -> str:
    """Ikkala hisob raqamni aniq va lo'nda ko'rsatuvchi karta"""
    text = (
        "💳 <b>SMART POS KASSA APPARATLARI UCHUN TO'LOV REKVIZITLARI:</b>\n\n"
        "1️⃣ <b>OYLIK ABONENT TO'LOVI (Har oyning 6-sanasigacha):</b>\n"
        "• <b>Tashkilot:</b> «MARS ELEKTRON TEXNIKA» MCHJ\n"
        "• <b>Hisob raqam:</b> <code>20208000800208044003</code>\n"
        "• <b>MFO:</b> <code>01048</code> | <b>INN:</b> <code>302568138</code>\n"
        "• <b>Summa:</b> 100 000 so'm/oy\n"
        "• <b>Maqsadi:</b> <code>INN [korxonangiz INN] abonent to'lov</code>\n\n"
        "────────────────────\n"
        "2️⃣ <b>YILLIK FISKAL MODUL TO'LOVI (Yilda 1 marta):</b>\n"
        "• <b>Tashkilot:</b> «Yangi Texnologiyalar» DUK (Davlat Soliq Qo'mitasi)\n"
        "• <b>Hisob raqam:</b> <code>20210000100431200010</code>\n"
        "• <b>MFO:</b> <code>01018</code> | <b>INN:</b> <code>201589463</code> | <b>Kodi:</b> <code>00668</code>\n"
        "• <b>Summa:</b> 440 000 so'm (1 yillik sertifikat)\n"
        "• <b>Maqsadi:</b> <code>INN [korxonangiz INN] fiskal modulning yillik to'lovi</code>\n\n"
        "⚠️ <i>Oylik va yillik to'lovlarni adashtirmaslik lozim (2 xil tashkilot).</i>"
    )
    return adapt_to_user_script(text, script)


def get_both_posts_intro(script: str = "latin") -> str:
    """Ikkala post uzatilishidan oldingi qisqa ogohlantirish"""
    text = (
        "⚠️ <b>To'lovlar 2 xil tashkilotga to'lanadi (ularni adashtirmaslik lozim):</b>\n\n"
        "1️⃣ <b>Oylik abonent to'lovi (100 000 so'm)</b> — «MARS ELEKTRON TEXNIKA» MCHJ ga\n"
        "2️⃣ <b>Yillik fiskal modul to'lovi (440 000 so'm)</b> — «Yangi Texnologiyalar» DUK ga\n\n"
        "👇 <i>Quyida rasmiy hisob raqamlar uzatilmoqda:</i>"
    )
    return adapt_to_user_script(text, script)


def get_monthly_post_note(script: str = "latin") -> str:
    """Oylik to'lov posti ostidagi eslatma"""
    text = (
        "💡 <b>«Mars» oylik abonent to'lovi (100 000 so'm/oy):</b>\n"
        "Har oyning <b>6-sanasigacha</b> to'lanishi lozim."
    )
    return adapt_to_user_script(text, script)


def get_annual_post_note(script: str = "latin") -> str:
    """Yillik to'lov posti ostidagi eslatma"""
    text = (
        "💡 <b>Yillik fiskal modul litsenziyasi (440 000 so'm/yil):</b>\n"
        "«Yangi Texnologiyalar» DUK ga to'lanadi (2-24 soatda faollashadi)."
    )
    return adapt_to_user_script(text, script)


def get_fiscal_module_request_prompt(script: str = "latin") -> str:
    """Fiskal modul so'rash shabloni"""
    text = (
        "🏛 <b>Yillik Soliq (OFD) to'lovini tekshirish uchun:</b>\n"
        "Kassa chekining pastki qismidagi <b>Fiskal modul seriya raqamini (LG... yoki YG...)</b> yuboring (masalan: <code>LG420210630789</code>).\n"
        "Chek bo'lmasa, apparat orqasidagi nakleyka (yorliq) yoki ekranni <b>rasmga olib</b> tashlang."
    )
    return adapt_to_user_script(text, script)


def get_single_account_warning(script: str = "latin") -> str:
    """Bitta hisob raqamga to'lash mumkinmi deyilganda qat'iy va qisqa javob"""
    text = (
        "❌ <b>Yo'q, mutlaqo bo'lmaydi! To'lovlar 2 ta alohida tashkilotga to'lanadi:</b>\n\n"
        "1️⃣ <b>Oylik abonent (100 000 so'm)</b> — «Mars Elektron Texnika»ga\n"
        "2️⃣ <b>Yillik litsenziya (440 000 so'm)</b> — «Yangi Texnologiyalar» DUKga\n\n"
        "<i>Bitta hisobga to'lasangiz, Soliq tizimi litsenziyangizni uzaytirmaydi.</i>"
    )
    return adapt_to_user_script(text, script)


def get_p2p_warning(card_num: str = "", script: str = "latin") -> str:
    """Plastik karta yuborilganda P2P qabul qilinmasligi haqida ogohlantirish"""
    num_str = f" <code>{card_num}</code>" if card_num else ""
    text = (
        f"💳{num_str}\n"
        "⚠️ <b>To'lovlar kartadan-kartaga (P2P) qabul qilinmaydi.</b>\n"
        "To'lov faqat rasmiy 20 xonali hisob raqamga qilinadi. Rekvizitlar uchun: /tolov"
    )
    return adapt_to_user_script(text, script)


def get_due_date_template(script: str = "latin") -> str:
    """To'lov muddatlari haqida javob"""
    text = (
        "📅 <b>To'lov muddatlari:</b>\n\n"
        "• <b>Oylik abonent:</b> Har oyning <b>6-sanasigacha</b> (100 000 so'm)\n"
        "• <b>Yillik litsenziya:</b> Yilda 1 marta (440 000 so'm)"
    )
    return adapt_to_user_script(text, script)


# =============================================================================
# 3. QARZDORLIK VA KORXONANI TEKSHIRISH
# =============================================================================

def format_debt_response_template(
    results: list,
    checked_fm: Optional[str] = None,
    annual_status: Optional[dict] = None,
    chat_id: int = 0,
    user_id: int = 0,
    script: str = "latin"
) -> str:
    """Excel tekshiruvi natijasi: apparat soni va qarz summasi (ixcham)"""
    if not results:
        text = (
            "❌ <b>Bazada ushbu raqam bo'yicha ma'lumot topilmadi.</b>\n\n"
            "СТИР (INN) yoki JSHSHIR raqamini to'g'ri kiritganingizni tekshirib qayta yuboring."
        )
        return adapt_to_user_script(text, script)

    first = results[0]
    org_name = first.get("name", "-")
    inn = first.get("stir", "-")
    jshshir = first.get("jshshir", "-")
    tuman = first.get("tuman", "-")
    device_count = len(results)

    lines = [f"🏢 <b>Korxona:</b> {org_name}"]
    if inn != "-":
        lines.append(f"🆔 <b>СТИР (INN):</b> <code>{inn}</code>")
    if jshshir != "-":
        lines.append(f"🆔 <b>ЖШSHIR:</b> <code>{jshshir}</code>")
    if tuman != "-":
        lines.append(f"📍 <b>Hudud / Tuman:</b> {tuman}")

    p3_items = [item for item in results if item.get("is_p3", False)]
    smart_items = [item for item in results if not item.get("is_p3", False)]

    if device_count == 1:
        single_model = "P3 Humo" if p3_items else "Smart One"
        lines.append(f"📟 <b>Apparat modeli:</b> {single_model}")
        terminal_id = results[0].get("terminal", "-")
        if terminal_id and terminal_id != "-":
            lines.append(f"🔢 <b>Terminal ID:</b> <code>{terminal_id}</code>")
    else:
        lines.append(f"📟 <b>Biriktirilgan apparatlar soni:</b> {device_count} ta")
        if p3_items and smart_items:
            lines.append(f"   • <b>P3 Humo:</b> {len(p3_items)} ta | <b>Smart One:</b> {len(smart_items)} ta")
        elif p3_items:
            lines.append(f"   • <b>Modeli:</b> P3 Humo ({len(p3_items)} ta)")
        elif smart_items:
            lines.append(f"   • <b>Modeli:</b> Smart One ({len(smart_items)} ta)")

    decom_items = excel_manager.get_decommissioned(inn) if inn != "-" else []
    if decom_items:
        lines.append(f"ℹ️ <i>Korxonaning {len(decom_items)} ta apparati avval hisobdan chiqarilgan (qarz hisoblanmaydi).</i>")

    lines.append("────────────────────")

    total_debt = sum(item.get("debt", 0.0) for item in results)
    if total_debt > 0:
        lines.append(f"🔴 <b>JAMI QARZDORLIK: {total_debt:,.0f} so'm</b>")
        lines.append("\n💳 <i>To'lov uchun rekvizitlar quyida keltirildi.</i>")
    elif total_debt < 0:
        lines.append(f"🟢 <b>Ortiqcha to'lov:</b> {abs(total_debt):,.0f} so'm")
        lines.append("✅ <b>Abonent to'lovidan qarzdorlik yo'q.</b>")
    else:
        lines.append("✅ <b>«Mars» oylik abonent to'lovidan qarzdorlik yo'q (0 so'm).</b>")

    # Yillik Soliq (OFD) litsenziyasi holati
    if checked_fm and annual_status is not None:
        if annual_status.get("unavailable"):
            lines.append(f"⏳ <b>Yillik Soliq litsenziyasi ({checked_fm}):</b> Tizim vaqtincha javob bermadi.")
        elif annual_status.get("has_debt"):
            lines.append(f"🔴 <b>Yillik Soliq litsenziyasi ({checked_fm}):</b> Qarzdorlik mavjud (440 000 so'm).")
        else:
            lines.append(f"✅ <b>Yillik Soliq litsenziyasi ({checked_fm}):</b> Faol (Litsenziya muddati joyida).")
    elif total_debt <= 0:
        lines.append(
            "\n🏛 <b>Yillik Soliq (OFD) litsenziyasini tekshirish uchun:</b>\n"
            "Kassa chekining pastki qismidagi <b>Fiskal modul raqamini (LG... yoki YG...)</b> yuboring."
        )

    if inn == "302568138":
        lines.append(
            "\n💡 <i><code>302568138</code> — «Mars Elektron Texnika» MCHJ STIR raqami. "
            "O'z korxonangiz qarzini tekshirish uchun korxonangiz STIR raqamini yuboring.</i>"
        )

    text = "\n".join(lines)
    return adapt_to_user_script(text, script)


def get_decommissioned_template(org_name: str, query_num: str = "", tuman: str = "", script: str = "latin") -> str:
    """Hisobdan chiqarilgan (o'chirilgan) korxona uchun ixcham javob"""
    lines = [f"🏢 <b>Korxona:</b> {org_name}"]
    if query_num:
        lines.append(f"🆔 <b>Qidiruv raqami:</b> <code>{query_num}</code>")
    if tuman and tuman != "-":
        lines.append(f"📍 <b>Hudud / Tuman:</b> {tuman}")
    lines.append("────────────────────")
    lines.append("ℹ️ <b>Holati:</b> Hisobdan chiqarilgan (o'chirilgan)")
    lines.append("✅ <b>Qarzdorlik:</b> 0 so'm")
    text = "\n".join(lines)
    return adapt_to_user_script(text, script)


def get_yt_inn_warning(inn: str = "201589463", script: str = "latin") -> str:
    """Yangi Texnologiyalar DUK STIR raqami kiritilganda ogohlantirish"""
    text = (
        f"⚠️ <b>Kiritilgan СТИР (<code>{inn}</code>) — «Yangi Texnologiyalar» DUK raqami.</b>\n\n"
        "• O'z korxonangiz qarzini tekshirish uchun: <b>9 xonali INN</b> raqamingizni yuboring;\n"
        "• Yillik litsenziyani tekshirish uchun: Chekdagi <b>Fiskal modul (LG/YG)</b> raqamini yuboring."
    )
    return adapt_to_user_script(text, script)


def get_incomplete_inn_template(script: str = "latin") -> str:
    """To'liq kiritilmagan INN uchun eslatma"""
    text = (
        "⚠️ <b>Korxona INN raqami 9 xonali (JSHSHIR 14 xonali) bo'lishi kerak.</b>\n"
        "Masalan: <code>302568138</code>"
    )
    return adapt_to_user_script(text, script)


def get_invalid_digits_template(length: int, script: str = "latin") -> str:
    """Noto'g'ri xonali raqam kiritilganda xabar"""
    text = (
        f"⚠️ <b>Kiritilgan raqam ({length} xonali) standart formatga mos emas.</b>\n"
        "• <b>СТИР (INN):</b> 9 xonali son\n"
        "• <b>JSHSHIR:</b> 14 xonali son\n"
        "• <b>Fiskal modul:</b> LG... / YG..."
    )
    return adapt_to_user_script(text, script)


# =============================================================================
# 4. OFD YILLIK LITSENZIYA HOLATI
# =============================================================================

def format_ofd_status_template(fm_code: str, ofd_text: Optional[str], script: str = "latin") -> str:
    """OFD litsenziya holatini qisqa va lo'nda ko'rsatish"""
    clean_code = str(fm_code).strip()
    is_inn = len(clean_code) in (9, 14) and clean_code.isdigit()
    code_label = f"🔢 <b>СТИР (INN):</b> <code>{clean_code}</code>" if is_inn else f"🏛 <b>Fiskal modul:</b> <code>{clean_code}</code>"

    from payment_accounts import parse_ofd_reply_status
    status = parse_ofd_reply_status(ofd_text)

    if status == "unavailable":
        text = (
            f"{code_label}\n"
            f"⏳ <b>Davlat Soliq (OFD) tizimi vaqtincha javob bermayapti.</b>\n"
            f"Birozdan so'ng qayta urinib ko'ring."
        )
    elif status == "not_found":
        text = (
            f"❌ <b>Fiskal modul topilmadi:</b> <code>{clean_code}</code>\n"
            f"Chekdagi seriya raqamini tekshirib qayta yuboring (masalan: <code>LG420210630789</code>)."
        )
    elif status == "debt":
        text = (
            f"🔴 <b>Yillik Soliq (OFD) to'lovidan QARZDORLIK MAVJUD!</b>\n\n"
            f"{code_label}\n"
            f"💰 <b>Summa:</b> <b>440 000 so'm</b> (1 yilga)\n\n"
            f"💳 <i>To'lov rekvizitlari quyida uzatildi (yoki «To'layman» deb yozing).</i>"
        )
    else:
        text = (
            f"🟢 <b>Yillik Soliq (OFD) to'lovidan QARZDORLIK YO'Q!</b>\n\n"
            f"{code_label}\n"
            f"✅ <b>Holati:</b> Faol (Litsenziya muddati joyida)."
        )
    return adapt_to_user_script(text, script)


# =============================================================================
# 5. KVITANSIYA VA TO'LOV E'TIROZLARI
# =============================================================================

def get_payment_claim_template(has_receipt: bool = False, script: str = "latin") -> str:
    """«To'ladim / Pul o'tkazdim» deyilganda qaytariladigan qisqa javob"""
    if has_receipt:
        text = "ℹ️ <b>Kvitansiyangiz adminga yetkazilgan, tez orada apparatingiz yoqiladi.</b>"
    else:
        text = "🧾 <b>To'lov kvitansiyasini (rasm yoki PDF) yuboring.</b>"
    return adapt_to_user_script(text, script)


def get_receipt_ack_template(is_recent_dup: bool = False, missing_inn: bool = False, script: str = "latin") -> str:
    """Kvitansiya qabul qilinganda foydalanuvchiga bildirishnoma"""
    if is_recent_dup:
        text = "ℹ️ <b>Ushbu kvitansiya avval qabul qilingan va adminga yuborilgan.</b>"
    elif missing_inn:
        text = (
            "🧾 <b>Kvitansiyangiz qabul qilindi.</b>\n\n"
            "Iltimos, korxonangiz <b>INN</b> raqamini yuboring."
        )
    else:
        text = "🧾 <b>Kvitansiyangiz qabul qilindi va tekshirish uchun mas'ul adminga yuborildi.</b>"
    return adapt_to_user_script(text, script)


# =============================================================================
# 6. APPARAT NOSOZLIGI (HARDWARE ISSUE FLOW)
# =============================================================================

def get_hardware_step1_inn_template(script: str = "latin") -> str:
    """1-bosqich: INN so'rash"""
    text = "🔍 <b>Kassa apparati holatini tekshirish uchun korxonangiz СТИР (INN) raqamini yuboring.</b>"
    return adapt_to_user_script(text, script)


def get_hardware_step2_fm_template(org_name: str, inn: str, script: str = "latin") -> str:
    """2-bosqich: Oylik qarz yo'q bo'lsa, Fiskal modul so'rash"""
    text = (
        f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{inn}</code>)\n"
        f"✅ «Mars» oylik to'lovidan qarzdorlik yo'q (0 so'm).\n\n"
        f"🏛 Yillik Soliq litsenziyasini tekshirish uchun chekdagi <b>Fiskal modul raqamini (LG... yoki YG...)</b> yuboring."
    )
    return adapt_to_user_script(text, script)


def get_hardware_step3_clear_template(
    org_name: str,
    inn: str,
    fm: str,
    contacts_block: str = "",
    has_photo: bool = False,
    script: str = "latin"
) -> str:
    """3-bosqich: Qarzdorlik yo'q bo'lganda apparatni tekshirish va eskalatsiya"""
    lines = [
        "🟢 <b>To'lovlar bo'yicha qarzdorlik yo'q!</b>\n",
        f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{inn}</code>)",
        f"🏛 <b>Fiskal modul:</b> <code>{fm}</code>",
        "✅ <b>Oylik to'lov:</b> 0 so'm",
        "✅ <b>Yillik litsenziya:</b> Faol (Litsenziya muddati joyida)\n"
    ]
    if contacts_block:
        lines.append(contacts_block + "\n")

    if has_photo:
        lines.append("👨‍💻 <i>Ma'lumotlar va apparat rasmi mas'ul adminga yetkazildi.</i>")
    else:
        lines.extend([
            "📌 <b>Tekshiring:</b>",
            "1. <b>Internet aloqasi:</b> Wi-Fi yoki SIM tarmog'i",
            "2. <b>Soat va sana:</b> Aniq vaqt to'g'riligi",
            "3. <b>Qayta yoqish:</b> Apparatni o'chirib yoqing (Перезагрузка / Reboot)\n",
            "📸 <i>Ishlamasa, ekrandagi xatolikni rasmga olib yuboring yoki «Usta kerak» deb yozing.</i>"
        ])
    text = "\n".join(lines)
    return adapt_to_user_script(text, script)


def get_hardware_no_receipt_template(org_name: str, inn: str, script: str = "latin") -> str:
    """Chek chiqmayotganda fiskal modulni topish bo'yicha ixcham qo'llanma"""
    text = (
        f"🏢 <b>Korxona:</b> {org_name} (INN: <code>{inn}</code>)\n"
        f"✅ «Mars» oylik to'lovidan qarzdorlik yo'q (0 so'm).\n\n"
        f"📌 <b>Fiskal modul raqamini topish:</b>\n"
        f"1. Istalgan <b>eski kassa chekining eng pastki qismi</b>dan;\n"
        f"2. Apparatning <b>orqa qismidagi yorliq (nakleyka)</b>dan topishingiz mumkin.\n\n"
        f"📸 <i>Yoki apparat orqasini rasmga olib yuboring.</i>"
    )
    return adapt_to_user_script(text, script)


# =============================================================================
# 7. ADMINGA ESKALATSIYA VA OPERATOR
# =============================================================================

def get_escalate_admin_template(contacts_block: str = "", script: str = "latin") -> str:
    """Operator yoki usta chaqirilganda qisqa xabar"""
    text = "👨‍💻 <b>Murojaatingiz qabul qilindi va operator / adminga yetkazildi.</b> Tez orada siz bilan bog'lanishadi:"
    if contacts_block:
        text += f"\n\n{contacts_block}"
    return adapt_to_user_script(text, script)


def get_escalate_with_photo_template(
    org_name: str,
    inn: str,
    fm: str = "",
    contacts_block: str = "",
    script: str = "latin"
) -> str:
    """Rasm adminga uzatilganda qisqa tasdiq xabari"""
    lines = [
        "👨‍💻 <b>Ma'lumotlar adminga yuborildi:</b>\n",
        f"🏢 <b>Korxona:</b> {org_name}",
        f"🆔 <b>INN:</b> <code>{inn}</code>"
    ]
    if fm:
        lines.append(f"🏛 <b>Fiskal modul:</b> <code>{fm}</code>")
    if contacts_block:
        lines.append(f"\n{contacts_block}")
    text = "\n".join(lines)
    return adapt_to_user_script(text, script)


def get_unrecognized_image_template(script: str = "latin") -> str:
    """Noma'lum rasm yuborilganda ixcham yo'riqnoma"""
    text = (
        "📸 <b>Tasvirdan kassa ekrani yoki chekni aniqlab bo'lmadi.</b>\n"
        "Ekrandagi xatolikni yaqinroqdan rasmga oling yoki korxona <b>INN</b> raqamini yozing."
    )
    return adapt_to_user_script(text, script)


def get_receipt_missing_inn_or_fm_template(script: str = "latin") -> str:
    """Chek rasmida na INN, na FM o'qilganda qaytadigan xabar"""
    text = (
        "🧾 <b>Chekdan INN yoki Fiskal modul raqamini aniq o'qib bo'lmadi.</b>\n"
        "Chekni yaqinroqdan aniq rasmga oling yoki <b>9 xonali INN</b> raqamingizni yozib yuboring."
    )
    return adapt_to_user_script(text, script)


# =============================================================================
# 8. MXIK QO'LLANMALARI
# =============================================================================

def get_mxik_guidance_template(query: str = "") -> Tuple[str, int]:
    """MXIK (IKPU / Tasnif / Soliq) bo'yicha ixcham va aniq yo'riqnoma"""
    q = query.lower()

    if any(w in q for w in ["baza yuklash", "baza yuklasa", "baza kiritish", "excel", "exceldan", "tovarlar bazasi", "tovar bazasi", "baza", "база", "база юклаш", "эксель", "эксел"]):
        return (
            "📥 <b>Kassa apparatiga tovarlar bazasini yuklash:</b>\n"
            "Excel fayli orqali tovarlar nomi, narxi va MXIK kodlarini bir vaqtning o'zida ommaviy yuklash mumkin.",
            138
        )
    if any(w in q for w in ["otkaz", "bekor qilish", "bekor qilsa", "bekor", "qaytadan urish", "qaytadan to'g'rilab", "chekni bekor", "tovarni bekor", "отказ", "бекор", "бекор қилиш", "қайтадан уриш"]):
        return (
            "🔄 <b>Tovarni bekor qilish (Otkaz):</b>\n"
            "Savatchadagi tovar ustiga bosib «Otkaz»ni tanlang. Chek chiqib bo'lgan bo'lsa, qaytarish (vozvrat) cheki uriladi.",
            53
        )
    if any(w in q for w in ["qqs", "nds", "soliq stavka", "qqs stavka", "12%", "stavka", "ққс", "ндс", "ставка"]):
        return (
            "📊 <b>QQS stavkasi va MXIK:</b>\n"
            "QQS to'lovchilar tovar qo'shishda soliq stavkasini (12% yoki QQSsiz) to'g'ri belgilashlari shart (VMQ-943).",
            89
        )
    if any(w in q for w in ["zapravka", "alkogol", "tamaki", "naqd", "naqt", "bloklab urish", "заправка", "алкогол", "тамаки", "нақд", "накт"]):
        return (
            "🚫 <b>Naqd pulga savdo qilib bo'lmaydigan tovarlar:</b>\n"
            "Zapravkalar, alkogol va tamaki mahsulotlariga qonun bo'yicha faqat bank kartasi orqali chek uriladi.",
            133
        )
    if any(w in q for w in ["tekshirish", "jarima", "soliq jarima", "xato kod", "to'g'rilash", "togrilash", "tekshir", "текшириш", "жарима", "солиқ жарима", "солик жарима", "хато код", "тўғрилаш", "тогрилаш"]):
        return (
            "⚠️ <b>MXIK tekshiruvi va jarimalar:</b>\n"
            "Chekda noto'g'ri MXIK yoki o'lchov birligi ko'rsatilsa, soliq jarimasi qo'llanadi. Kodlarni tasnif.soliq.uz orqali tekshiring.",
            17
        )
    if any(w in q for w in ["tasnif", "soliq sayt", "soliqdan", "sayt", "qidirish", "topish", "qayerdan", "qayerdan olaman", "qanday olinadi", "soliq portali", "kodini", "kodi qanaqa", "kodi nima", "kod bering", "kod tashlang", "тасниф", "солиқ сайт", "солик сайт", "сайт", "қидириш", "кидириш", "топиш", "қаердан", "каердан", "қандай олинади", "коди қанақа", "коди нима"]):
        return (
            "🔍 <b>MXIK kodlarni Tasnif.soliq.uz saytidan qidirish:</b>\n"
            "Rasmiy <a href='https://tasnif.soliq.uz'>tasnif.soliq.uz</a> saytidan tovar nomini yozib, 17 xonali kodni oling.",
            28
        )
    return (
        "📦 <b>Tovar qo'shish va MXIK (ИКПУ) kod:</b>\n"
        "Kassa dasturida «Tovar qo'shish»ga kiring, tovar nomi, narxi va Tasnif.soliq.uz dan olingan 17 xonali MXIK kodni kiriting.",
        15
    )
