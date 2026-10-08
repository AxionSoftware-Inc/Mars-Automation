import os
import re
import logging
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

            # 3-qatordan boshlab o'qish (1 va 2-qator sarlavhalar)
            for row in sheet.iter_rows(min_row=3, values_only=True):
                # Ustunlar:
                # 0: Telefon
                # 1: Sana
                # 2: СТИР (INN)
                # 3: ЖШШИР (JSHSHIR - YaTT uchun 14 xonali)
                # 4: Корхона номи
                # 5: Онлайн-НКМ (Terminal ID / Apparat)
                # 33: Qarz 2026 yil 1-yanvar
                # 60: Joriy qoldiq (Колдик)
                # 62: Tuman
                
                stir_raw = row[2] if len(row) > 2 else None
                jshshir_raw = row[3] if len(row) > 3 else None
                name_raw = row[4] if len(row) > 4 else None
                terminal_raw = row[5] if len(row) > 5 else None
                phone_raw = row[0] if len(row) > 0 else None
                debt_raw = row[60] if len(row) > 60 else None
                tuman_raw = row[62] if len(row) > 62 else None

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

                record = {
                    "phone": str(phone_raw or "-").strip(),
                    "stir": stir or "-",
                    "jshshir": jshshir or "-",
                    "name": str(name_raw or "Noma'lum").strip(),
                    "terminal": terminal or "-",
                    "debt": debt_val,
                    "tuman": str(tuman_raw or "-").strip()
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

excel_manager = ExcelManager()
