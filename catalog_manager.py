import os
import re
import json
import logging
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

from openrouter_client import openrouter_client

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CATALOG_FILE = os.path.join(DATA_DIR, "video_catalog.json")

class CatalogManager:
    def __init__(self, catalog_path: str = CATALOG_FILE):
        self.catalog_path = catalog_path
        self.posts: List[Dict[str, Any]] = []
        self.load_catalog()

    def load_catalog(self):
        """Katalog faylini yuklash"""
        if os.path.exists(self.catalog_path):
            try:
                with open(self.catalog_path, "r", encoding="utf-8") as f:
                    self.posts = json.load(f)
                logger.info(f"Video katalog yuklandi: {len(self.posts)} ta post.")
            except Exception as e:
                logger.error(f"Katalog faylini o'qishda xatolik: {e}")
                self.posts = []
        else:
            self.posts = []

    def save_catalog(self):
        """Katalog faylini saqlash"""
        try:
            os.makedirs(os.path.dirname(self.catalog_path), exist_ok=True)
            with open(self.catalog_path, "w", encoding="utf-8") as f:
                json.dump(self.posts, f, ensure_ascii=False, indent=2)
            logger.info("Video katalog muvaffaqiyatli saqlandi.")
        except Exception as e:
            logger.error(f"Katalogni saqlashda xatolik: {e}")

    def normalize(self, text: str) -> str:
        """Matnni tozalash va shevalarni yaqinlashtirish"""
        if not text:
            return ""
        t = text.lower()
        t = re.sub(r"[’‘`ʻʼ'\"]", "", t)
        
        # Kirill harflarini lotinga
        cyr_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
            'ж': 'j', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'x', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sh', 'ъ': '',
            'ы': 'i', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya', 'ў': 'o', 'қ': 'q',
            'ғ': 'g', 'ҳ': 'x'
        }
        for c, l in cyr_map.items():
            t = t.replace(c, l)

        # Ommaviy so'zlar yaqinlashuvi
        t = re.sub(r"ishlam[aei]+[p]?[d]?[i]?", "ishlamay", t)
        t = t.replace("karz", "qarz")
        t = t.replace("tulov", "tolov").replace("tulash", "tolash")
        return t

    def find_post_by_keywords(self, text: str) -> Optional[int]:
        """Tezkor kalit so'zlar bo'yicha qidirish"""
        t = self.normalize(text)

        # Qarz yoki apparat ishlamay qolgan shikoyatlarga video berilmaydi (INN so'ralishi kerak)
        if any(w in t for w in ["qarzim bormi", "qarz bormi", "qarzdorlik bormi", "ishlamayapti", "ochib qoldi", "blok boldi"]):
            return None

        # Eng yuqori moslikdagi postni topish
        best_post_id = None
        best_match_score = 0

        for post in self.posts:
            pid = post.get("id")
            keywords = post.get("keywords", [])
            for kw in keywords:
                kw_norm = self.normalize(kw)
                if kw_norm and kw_norm in t:
                    score = len(kw_norm)
                    if score > best_match_score:
                        best_match_score = score
                        best_post_id = pid

        return best_post_id

    def find_matching_post(self, user_text: str) -> Optional[int]:
        """
        Gibrid qidiruv:
        1-bosqich: Tezkor kalit so'zlar orqali;
        2-bosqich: Agar topilmasa, Gemini AI orqali butun indeks ichidan eng mosini topish.
        """
        # 1-bosqich: Tezkor kalit so'zlar bo'yicha
        kw_match = self.find_post_by_keywords(user_text)
        if kw_match:
            return kw_match

        t = self.normalize(user_text)
        # Agar apparat ishlamay qolganini bildirayotgan bo'lsa -> INN so'rash uchun video bermaymiz
        if any(w in t for w in ["ishlamay", "ishlamadi", "ishlamas", "ochib qol", "ochiq qol", "ochilmay", "blok", "qarzim", "qarz"]):
            # Faqat aynan o'chish sanasi so'ralgan bo'lsa
            if not any(w in t for w in ["qachon", "nechanchi", "qaysi sana"]):
                return None

        # 2-bosqich: AI yordamida chuqur semantik moslashtirish
        if not openrouter_client or len(user_text.strip()) < 4:
            return None

        try:
            catalog_summary = "\n".join([
                f"- ID {p['id']}: {p['title']} ({', '.join(p.get('keywords', [])[:4])})"
                for p in self.posts
            ])

            prompt = f"""
Siz "Mars" Smart POS kassa apparatlari kanali videolari dispetchersiz.
Foydalanuvchi quyidagi murojaatni yozdi:
"{user_text.strip()}"

Kanalda mavjud video-qo'llanmalar katalogi:
{catalog_summary}

VAZIFA:
Agar foydalanuvchining savoli yuqoridagi videolardan birontasiga to'g'ri kelsa, FAQAT o'sha postning ID raqamini (masalan: 140 yoki 2 yoki 148) bitta son qilib qaytaring.
Agar foydalanuvchi shunchaki salomlashgan bo'lsa, apparati ishlamay qolgani bo'yicha qarzini tekshirmoqchi bo'lsa, yoki mos video bo'lmasa, FAQAT 0 raqamini qaytaring.

Javob: FAQAT bitta son (masalan 140 yoki 0):
"""
            result_str = openrouter_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            ) or ""
            matched = re.search(r"\b(\d+)\b", result_str.strip())
            if matched:
                val = int(matched.group(1))
                if val > 0 and any(p["id"] == val for p in self.posts):
                    return val
        except Exception as e:
            logger.error(f"Catalog AI search error: {e}")

        return None

    def auto_index_new_post(self, post_id: int, post_text: str) -> bool:
        """
        Kanalga yangi post qo'shilganda uni AI orqali avtomatik tahlil qilib,
        katalogga yangi element sifatida qo'shib saqlash
        """
        if not post_text or len(post_text.strip()) < 10:
            return False

        # Agar allaqachon mavjud bo'lsa, yangilash yoki o'tkazib yuborish
        existing = [p for p in self.posts if p["id"] == post_id]
        if existing:
            logger.info(f"Post {post_id} allaqachon katalogda bor.")
            return False

        try:
            prompt = f"""
Siz POS kassa apparatlari kanali (@POS_Terminal_UzSmart_Bank) uchun yangi postni indekslovchisiz.
Yangi kelgan post matni:
"{post_text.strip()}"

Vazifa: Ushbu post uchun quyidagi JSON formatida qisqa ma'lumot tayyorlang:
{{
  "id": {post_id},
  "title": "Qisqa tushunarli sarlavha (o'zbek tilida)",
  "description": "Nima haqidaligi haqida 1 qisqa gap",
  "keywords": ["kamida 5 ta asosiy kalit so'z, shevalar va sinonimlar"]
}}
Javobingiz FAQAT toza JSON bo'lsin:
"""
            resp_str = openrouter_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            ) or "{}"
            new_entry = json.loads(resp_str)
            self.posts.append(new_entry)
            self.save_catalog()
            logger.info(f"✅ Yangi post avtomatik indekslandi: ID={post_id}, Title='{new_entry.get('title')}'")
            return True
        except Exception as e:
            logger.error(f"Yangi postni avto-indekslashda xatolik: {e}")
            return False

catalog_manager = CatalogManager()
