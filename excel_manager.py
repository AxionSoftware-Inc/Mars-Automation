import os
import re
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List
import openpyxl

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LATEST_EXCEL_PATH = os.path.join(DATA_DIR, "latest.xlsx")

class ExcelManager:
    def __init__(self, excel_path: str = LATEST_EXCEL_PATH):
        self.excel_path = excel_path
        # Xotiradagi indekslar: tezkor qidiruv uchun lug'at (dict)
        # key: stir yoki jshshir yoki terminal -> list of records
        self.stir_index: Dict[str, List[Dict[str, Any]]] = {}
        self.jshshir_index: Dict[str, List[Dict[str, Any]]] = {}
        self.terminal_index: Dict[str, List[Dict[str, Any]]] = {}
        self.records_count = 0
        self.load_data()

    def clean_digits(self, val: Any) -> str:
        """Faqat raqamlarni ajratib olish (float / string e'tiborga olingan)"""
        if val is None:
            return ""
        s = str(val).split(".")[0]  # Masalan 311790999.0 bo'lib qolmasligi uchun
        return re.sub(r"\D", "", s)

    def load_data(self) -> bool:
        """Excel faylni xotiraga tezkor yuklash (read_only + data_only)"""
        if not os.path.exists(self.excel_path):
            logger.warning(f"Excel fayli topilmadi: {self.excel_path}")
            return False

        try:
            wb = openpyxl.load_workbook(self.excel_path, read_only=True, data_only=True)
            sheet_name = wb.sheetnames[0]
            sheet = wb[sheet_name]

            # Indekslarni tozalash
            new_stir = {}
            new_jshshir = {}
            new_terminal = {}
            count = 0

            MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"]

            # 3-qatordan boshlab o'qish (1 va 2-qator sarlavhalar)
            for row in sheet.iter_rows(min_row=3, values_only=True):
                # Ustunlar:
                # 0: Telefon
                # 1: Sana
                # 2: СТИР (INN)
                # 3: ЖШШИР (JSHSHIR - YaTT uchun 14 xonali)
                # 4: Корхона номи
                # 5: Онлайн-НКМ (Terminal ID / Apparat)
                # 7..18: 2025 Hisoblandi
                # 20..31: 2025 To'lov
                # 33: Qarz 2026 yil 1-yanvar
                # 34..45: 2026 Hisoblandi
                # 47..58: 2026 To'landi
                # 60: Joriy qoldiq (Колдик)
                # 62: Tuman
                
                stir_raw = row[2] if len(row) > 2 else None
                jshshir_raw = row[3] if len(row) > 3 else None
                name_raw = row[4] if len(row) > 4 else None
                terminal_raw = row[5] if len(row) > 5 else None
                phone_raw = row[0] if len(row) > 0 else None
                debt_raw = row[60] if len(row) > 60 else None
                tuman_raw = row[62] if len(row) > 62 else None
                old_debt_raw = row[33] if len(row) > 33 else 0

                stir = self.clean_digits(stir_raw)
                jshshir = self.clean_digits(jshshir_raw)
                terminal = self.clean_digits(terminal_raw)

                if not stir and not jshshir and not terminal and not name_raw:
                    continue

                # Qarz summasi
                debt_val = 0.0
                try:
                    if debt_raw is not None:
                        debt_val = float(debt_raw)
                except (ValueError, TypeError):
                    debt_val = 0.0

                old_debt = 0.0
                try:
                    if old_debt_raw is not None:
                        old_debt = float(old_debt_raw)
                except (ValueError, TypeError):
                    old_debt = 0.0

                # 2026 yil to'lovlari (col 47..58)
                payments_2026 = {}
                charges_2026 = {}
                for m_idx, m_name in enumerate(MONTHS):
                    # To'langan
                    p_col = 47 + m_idx
                    if len(row) > p_col and row[p_col]:
                        try:
                            val = float(row[p_col])
                            if val > 0:
                                payments_2026[m_name] = val
                        except (ValueError, TypeError):
                            pass
                    # Hisoblangan
                    c_col = 34 + m_idx
                    if len(row) > c_col and row[c_col]:
                        try:
                            val = float(row[c_col])
                            if val > 0:
                                charges_2026[m_name] = val
                        except (ValueError, TypeError):
                            pass

                # 2025 yil to'lovlari (col 20..31)
                payments_2025 = {}
                for m_idx, m_name in enumerate(MONTHS):
                    p_col = 20 + m_idx
                    if len(row) > p_col and row[p_col]:
                        try:
                            val = float(row[p_col])
                            if val > 0:
                                payments_2025[m_name] = val
                        except (ValueError, TypeError):
                            pass

                record = {
                    "phone": str(phone_raw or "-").strip(),
                    "stir": stir or "-",
                    "jshshir": jshshir or "-",
                    "name": str(name_raw or "Noma'lum").strip(),
                    "terminal": terminal or "-",
                    "debt": debt_val,
                    "tuman": str(tuman_raw or "-").strip(),
                    "old_debt_2026": old_debt,
                    "payments_2026": payments_2026,
                    "charges_2026": charges_2026,
                    "payments_2025": payments_2025
                }

                if stir:
                    new_stir.setdefault(stir, []).append(record)
                if jshshir:
                    new_jshshir.setdefault(jshshir, []).append(record)
                if terminal:
                    new_terminal.setdefault(terminal, []).append(record)

                count += 1

            self.stir_index = new_stir
            self.jshshir_index = new_jshshir
            self.terminal_index = new_terminal
            self.records_count = count
            wb.close()
            logger.info(f"Excel muvaffaqiyatli yuklandi: {count} ta yozuv indekslandi.")
            return True
        except Exception as e:
            logger.error(f"Excel faylni o'qishda xatolik: {e}")
            return False

    def update_file(self, new_file_path: str) -> bool:
        """Yangi kelgan Excel faylni almashtirish va qayta yuklash"""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if new_file_path != self.excel_path:
                import shutil
                shutil.copy2(new_file_path, self.excel_path)
            return self.load_data()
        except Exception as e:
            logger.error(f"Faylni yangilashda xatolik: {e}")
            return False

    def search(self, query: str) -> List[Dict[str, Any]]:
        """INN (9 xonali), JSHSHIR (14 xonali) yoki Terminal raqami bo'yicha qidirish"""
        clean_q = re.sub(r"\D", "", query.strip())
        if not clean_q:
            return []

        # 1. INN (STIR) orqali tekshirish
        if clean_q in self.stir_index:
            return self.stir_index[clean_q]

        # 2. JSHSHIR orqali tekshirish
        if clean_q in self.jshshir_index:
            return self.jshshir_index[clean_q]

        # 3. Terminal raqami orqali tekshirish
        if clean_q in self.terminal_index:
            return self.terminal_index[clean_q]

        return []

    def format_payment_history(self, results: List[Dict[str, Any]]) -> str:
        """
        Qarzdorlik e'tirozi yoki 'nimaga qarzman' savoliga oylar kesimidagi to'lov va hisob-kitob tarixini lo'nda va aniq chiqarish.
        - To'langan oylar: ✅
        - To'lanmagan (qarzdor) oylar: ❌
        - Ko'p apparatli bo'lsa: N ta apparat x 100,000 so'm = N00,000 so'm/oy
        """
        if not results:
            return "Kechirasiz, to'lovlar tarixini ko'rish uchun avval korxona INN yoki JSHSHIR raqamini yuboring."

        first = results[0]
        name = first.get("name", "Noma'lum")
        stir = first.get("stir", "-")
        jshshir = first.get("jshshir", "-")
        device_count = len(results)
        total_debt = sum(item.get("debt", 0.0) for item in results)

        id_str = f"INN: <code>{stir}</code>" if stir != "-" else f"JSHSHIR: <code>{jshshir}</code>"

        # Barcha yozuvlardan oylik to'lovlar va hisoblarni birlashtirish
        MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"]
        
        agg_charges_2026: Dict[str, float] = {}
        agg_payments_2026: Dict[str, float] = {}
        total_old_debt_2026 = 0.0

        for rec in results:
            total_old_debt_2026 += rec.get("old_debt_2026", 0.0)
            for m, s in rec.get("charges_2026", {}).items():
                agg_charges_2026[m] = agg_charges_2026.get(m, 0.0) + s
            for m, s in rec.get("payments_2026", {}).items():
                agg_payments_2026[m] = agg_payments_2026.get(m, 0.0) + s

        # Oylik abonent narxi (agar topilsa, odatda apparat_soni * 100,000)
        sample_monthly_rate = 100000.0 * device_count
        for s in agg_charges_2026.values():
            if s > 0:
                sample_monthly_rate = s
                break

        # Oylar bo'yicha balans tahlili
        # Har bir hisoblangan oy bo'yicha to'lov yetarlimi?
        monthly_status = []
        unpaid_months = []
        paid_months_count = 0

        # Jami tushgan to'lov fondi (2026)
        payment_pool = sum(agg_payments_2026.values())
        # Eski qarzni to'lov fondidan chegirish
        effective_pool = payment_pool - max(0.0, total_old_debt_2026)

        for m in MONTHS:
            if m not in agg_charges_2026:
                continue
            charge = agg_charges_2026[m]
            paid_in_month = agg_payments_2026.get(m, 0.0)

            # Agar jami to'lov yetgan bo'lsa yoki shu oyda to'langan bo'lsa
            if effective_pool >= charge or paid_in_month >= charge:
                monthly_status.append(f"  ✅ <b>{m}:</b> to'langan ({paid_in_month:,.0f} so'm)")
                paid_months_count += 1
                effective_pool -= charge
            elif effective_pool > 0:
                # Qisman to'langan
                diff = charge - effective_pool
                monthly_status.append(f"  ⚠️ <b>{m}:</b> qisman to'langan (qarz: {diff:,.0f} so'm)")
                unpaid_months.append(f"{m} ({diff:,.0f} so'm)")
                effective_pool = 0
            else:
                monthly_status.append(f"  ❌ <b>{m}:</b> to'lanmagan (qarz: {charge:,.0f} so'm)")
                unpaid_months.append(m)

        # Xabar tuzish
        text = f"📊 <b>To'lovlar va qarzdorlik hisob-kitobi:</b>\n"
        text += f"🏢 <b>Korxona:</b> {name}\n"
        text += f"🆔 {id_str} | 📟 <b>Apparatlar soni:</b> {device_count} ta\n"
        if device_count > 1:
            text += f"ℹ️ <i>({device_count} ta apparat uchun oylik to'lov: {sample_monthly_rate:,.0f} so'm)</i>\n"
        text += f"────────────────────\n"

        # Qarz xulosasi
        if total_debt > 0:
            months_unpaid_count = len(unpaid_months)
            if months_unpaid_count > 0:
                unpaid_str = ", ".join(unpaid_months)
                text += f"🔴 <b>Qarzdorlik sababi:</b> {months_unpaid_count} oylik to'lov to'lanmagan!\n"
                text += f"📌 <b>Qarzdor oylar:</b> {unpaid_str}\n"
            elif total_old_debt_2026 > 0:
                text += f"🔴 <b>Qarzdorlik sababi:</b> 2026-yil 1-yanvardan o'tgan eski qarz ({total_old_debt_2026:,.0f} so'm) hisobiga.\n"
            text += f"💰 <b>Jami qarz summasi: {total_debt:,.0f} so'm</b>\n"
        else:
            text += "🟢 <b>Barcha oylar to'liq to'langan, qarzdorlik yo'q!</b>\n"

        text += f"────────────────────\n"
        text += "<b>2026-yil oylari holati:</b>\n"
        text += "\n".join(monthly_status) + "\n"

        if total_old_debt_2026 > 0:
            text += f"\n• <i>Eski yildan o'tgan qarz: {total_old_debt_2026:,.0f} so'm</i>\n"

        # Qarz bo'yicha to'lov tavsiyasi hisoblash (shu oy va yil oxirigacha)
        now_uzb = datetime.now(ZoneInfo("Asia/Tashkent"))
        current_month_idx = now_uzb.month  # 1..12
        current_month_name = MONTHS[current_month_idx - 1]
        remaining_months_to_year_end = max(0, 12 - current_month_idx)

        pay_current_month = max(0.0, total_debt)
        future_charges = remaining_months_to_year_end * sample_monthly_rate
        pay_year_end = pay_current_month + future_charges

        text += f"────────────────────\n"
        if total_debt > 0:
            text += f"💡 <b>Apparat uzluksiz ishlashi uchun to'lov miqdori:</b>\n"
            text += f"🔹 <b>Shu oy ({current_month_name}) ishlashi uchun:</b> <code>{pay_current_month:,.0f}</code> so'm\n"
            if remaining_months_to_year_end > 0:
                text += f"🔹 <b>Yil oxirigacha (Dekabrgacha) ishlashi uchun:</b> <code>{pay_year_end:,.0f}</code> so'm\n"
        else:
            if remaining_months_to_year_end > 0:
                prepaid_diff = abs(total_debt) if total_debt < 0 else 0.0
                year_end_needed = max(0.0, future_charges - prepaid_diff)
                text += f"💡 <b>Yil oxirigacha (Dekabrgacha) apparat uzluksiz ishlashi uchun to'lov:</b> <code>{year_end_needed:,.0f}</code> so'm\n"

        text += f"────────────────────\n"
        text += (
            "📲 <b>Click orqali to'lash:</b>\n"
            "Xizmatlar -> «Mars Elektron Texnika» -> INN kiritiladi.\n\n"
            "💬 <i>To'lov qilgan bo'lsangiz, to'lov chekini ushbu chatga tashlang. Operatorlarimiz tekshirib, tizimni yangilab berishadi.</i>"
        )
        return text

excel_manager = ExcelManager()
