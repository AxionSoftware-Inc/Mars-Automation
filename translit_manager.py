import re
from typing import Optional, List, Tuple

# =============================================================================
# O'ZBEK TILI LOTIN <-> KIRILL TRANSLITERATSIYA VA SKRIPT ANIQLASH MODULI
# =============================================================================

# Uzbek Cyrillic harflar to'plami
CYRILLIC_CHAR_PATTERN = re.compile(r'[а-яА-ЯёЁўЎқҚғҒҳҲ]')
LATIN_CHAR_PATTERN = re.compile(r'[a-zA-Z]')

# HTML teglari, kod bloklari, URLlar, buyruqlar, domenlar, username'lar va brend terminlarini himoyalovchi regex
PROTECTED_PATTERN = re.compile(
    r'(<code>.*?</code>|<pre>.*?</pre>|https?://[^\s<>]+|/[a-zA-Z0-9_]+|\b(?:[a-zA-Z0-9_-]+\.)+[a-zA-Z]{2,}\b|@[a-zA-Z0-9_]+|<[^>]+>|\b(?:Click|Payme|UzSmart|Pax(?:\s+[A-Za-z0-9]+)?|Sunmi|POS|Smart\s+POS|PDF|Excel)\b)',
    re.IGNORECASE | re.DOTALL
)

APOSTROPHES = "['`‘ʻ’ʼ]"

def _split_protected(text: str) -> List[Tuple[bool, str]]:
    """Matnni himoyalangan (teglar, kodlar) va ochiq matn qismlariga ajratish"""
    chunks: List[Tuple[bool, str]] = []
    last_end = 0
    for m in PROTECTED_PATTERN.finditer(text):
        if m.start() > last_end:
            chunks.append((False, text[last_end:m.start()]))
        chunks.append((True, m.group(0)))
        last_end = m.end()
    if last_end < len(text):
        chunks.append((False, text[last_end:]))
    return chunks


def detect_script(text: str) -> str:
    """
    Matn qaysi alifboda yozilganini aniqlash.
    Qaytaradi:
    - 'cyrillic': Kirill alifbosida
    - 'latin': Lotin alifbosida
    - 'unknown': Matnda harflar yo'q (raqamlar, belgilar, emojilar)
    """
    if not text:
        return "unknown"

    clean = PROTECTED_PATTERN.sub('', text)
    clean = re.sub(r'[/\\_\*#`]', '', clean)

    cyr_matches = CYRILLIC_CHAR_PATTERN.findall(clean)
    lat_matches = LATIN_CHAR_PATTERN.findall(clean)

    cyr_count = len(cyr_matches)
    lat_count = len(lat_matches)

    if cyr_count > 0 and cyr_count >= lat_count:
        return "cyrillic"
    elif lat_count > 0:
        return "latin"
    return "unknown"


# Aniq unicodeli Kirill -> Lotin lug'ati
CYR_TO_LAT_MAP = {
    # Kichik harflar
    chr(1072): 'a',   # а
    chr(1073): 'b',   # б
    chr(1074): 'v',   # в
    chr(1075): 'g',   # г
    chr(1076): 'd',   # д
    chr(1077): 'e',   # е
    chr(1078): 'j',   # ж
    chr(1079): 'z',   # з
    chr(1080): 'i',   # и
    chr(1081): 'y',   # й
    chr(1082): 'k',   # к
    chr(1083): 'l',   # л
    chr(1084): 'm',   # м
    chr(1085): 'n',   # н
    chr(1086): 'o',   # о
    chr(1087): 'p',   # п
    chr(1088): 'r',   # р
    chr(1089): 's',   # с
    chr(1090): 't',   # т
    chr(1091): 'u',   # у
    chr(1092): 'f',   # ф
    chr(1093): 'x',   # х
    chr(1094): 's',   # ц -> s (kvitansiya, sirk)
    chr(1095): 'ch',  # ч
    chr(1096): 'sh',  # ш
    chr(1097): 'sh',  # щ
    chr(1098): "'",   # ъ
    chr(1099): 'i',   # ы
    chr(1100): '',    # ь
    chr(1101): 'e',   # э
    chr(1102): 'yu',  # ю
    chr(1103): 'ya',  # я
    chr(1105): 'yo',  # ё
    chr(1118): "o'",  # ў
    chr(1179): 'q',   # қ
    chr(1171): "g'",  # ғ
    chr(1203): 'h',   # ҳ
    # Katta harflar
    chr(1040): 'A',   # А
    chr(1041): 'B',   # Б
    chr(1042): 'V',   # В
    chr(1043): 'G',   # Г
    chr(1044): 'D',   # Д
    chr(1045): 'E',   # Е
    chr(1046): 'J',   # Ж
    chr(1047): 'Z',   # З
    chr(1048): 'I',   # И
    chr(1049): 'Y',   # Й
    chr(1050): 'K',   # К
    chr(1051): 'L',   # Л
    chr(1052): 'M',   # М
    chr(1053): 'N',   # Н
    chr(1054): 'O',   # О
    chr(1055): 'P',   # П
    chr(1056): 'R',   # Р
    chr(1057): 'S',   # С
    chr(1058): 'T',   # Т
    chr(1059): 'U',   # У
    chr(1060): 'F',   # Ф
    chr(1061): 'X',   # Х
    chr(1062): 'S',   # Ц
    chr(1063): 'Ch',  # Ч
    chr(1064): 'Sh',  # Ш
    chr(1065): 'Sh',  # Щ
    chr(1066): "'",   # Ъ
    chr(1067): 'I',   # Ы
    chr(1068): '',    # Ь
    chr(1069): 'E',   # Э
    chr(1070): 'Yu',  # Ю
    chr(1071): 'Ya',  # Я
    chr(1025): 'Yo',  # Ё
    chr(1038): "O'",  # Ў
    chr(1178): 'Q',   # Қ
    chr(1170): "G'",  # Ғ
    chr(1202): 'H',   # Ҳ
}


def _translit_lat_to_cyr_chunk(s: str) -> str:
    # 0. Kvitansiya maxsus so'zi
    s = re.sub(r'\bKvitansi', 'Квитанци', s)
    s = re.sub(r'\bkvitansi', 'квитанци', s)

    # 1. O' va G'
    s = re.sub(r'O' + APOSTROPHES, 'Ў', s)
    s = re.sub(r'o' + APOSTROPHES, 'ў', s)
    s = re.sub(r'G' + APOSTROPHES, 'Ғ', s)
    s = re.sub(r'g' + APOSTROPHES, 'ғ', s)

    # 2. 2 ta harfli birikmalar
    compounds = [
        ('SH', 'Ш'), ('Sh', 'Ш'), ('sh', 'ш'),
        ('CH', 'Ч'), ('Ch', 'Ч'), ('ch', 'ч'),
        ('YO', 'Ё'), ('Yo', 'Ё'), ('yo', 'ё'),
        ('YU', 'Ю'), ('Yu', 'Ю'), ('yu', 'ю'),
        ('YA', 'Я'), ('Ya', 'Я'), ('ya', 'я'),
        ('YE', 'Е'), ('Ye', 'Е'), ('ye', 'е'),
        ('TS', 'Ц'), ('Ts', 'Ц'), ('ts', 'ц'),
    ]
    for lat, cyr in compounds:
        s = s.replace(lat, cyr)

    # 3. So'z boshidagi 'E' / 'e' -> 'Э' / 'э'
    s = re.sub(r'(^|[\s\(\[\{\'\"«“,\.\?!;:\-])E', r'\1Э', s)
    s = re.sub(r'(^|[\s\(\[\{\'\"«“,\.\?!;:\-])e', r'\1э', s)

    # 4. Tutuq belgisi (apostrof -> ъ)
    s = re.sub(r'([a-zA-Zа-яА-ЯёЁўЎқҚғҒҳҲ])' + APOSTROPHES, r'\1ъ', s)

    # 5. Yagona harflar
    single_map = {
        'A': 'А', 'a': 'а',
        'B': 'Б', 'b': 'б',
        'D': 'Д', 'd': 'д',
        'E': 'е', 'e': 'е',
        'F': 'Ф', 'f': 'ф',
        'G': 'Г', 'g': 'г',
        'H': 'Ҳ', 'h': 'ҳ',
        'I': 'И', 'i': 'и',
        'J': 'Ж', 'j': 'ж',
        'K': 'К', 'k': 'к',
        'L': 'Л', 'l': 'л',
        'M': 'М', 'm': 'м',
        'N': 'Н', 'n': 'н',
        'O': 'О', 'o': 'о',
        'P': 'П', 'p': 'п',
        'Q': 'Қ', 'q': 'қ',
        'R': 'Р', 'r': 'р',
        'S': 'С', 's': 'с',
        'T': 'Т', 't': 'т',
        'U': 'У', 'u': 'у',
        'V': 'В', 'v': 'в',
        'X': 'Х', 'x': 'х',
        'Y': 'Й', 'y': 'й',
        'Z': 'З', 'z': 'з',
        'C': 'Ц', 'c': 'ц',
    }
    return "".join(single_map.get(ch, ch) for ch in s)


def latin_to_cyrillic(text: str) -> str:
    """
    O'zbekcha Lotin matnini Kirill alifbosiga o'girish.
    HTML teglari, <code> bloklari, havolalar, brendlar (@, Click, Pax va h.k.) saqlanadi.
    """
    if not text:
        return text

    chunks = _split_protected(text)
    result = []
    for is_prot, c in chunks:
        if is_prot:
            result.append(c)
        else:
            result.append(_translit_lat_to_cyr_chunk(c))
    return "".join(result)


def _translit_cyr_to_lat_chunk(s: str) -> str:
    vowels = "аоуиеёюяэўАОУИЕЁЮЯЭЎ"
    # So'z boshida yoki unlidan keyingi Е/е -> Ye/ye
    s = re.sub(r'(^|[\s\(\[\{\'\"«“,\.\?!;:\-])Е', r'\1Ye', s)
    s = re.sub(r'(^|[\s\(\[\{\'\"«“,\.\?!;:\-])е', r'\1ye', s)
    s = re.sub(rf'([{vowels}])Е', r'\1Ye', s)
    s = re.sub(rf'([{vowels}])е', r'\1ye', s)

    return "".join(CYR_TO_LAT_MAP.get(ch, ch) for ch in s)


def cyrillic_to_latin(text: str) -> str:
    """
    O'zbekcha Kirill matnini Lotin alifbosiga o'girish.
    HTML teglari, <code> bloklari, havolalar, brendlar saqlanadi.
    """
    if not text:
        return text

    chunks = _split_protected(text)
    result = []
    for is_prot, c in chunks:
        if is_prot:
            result.append(c)
        else:
            result.append(_translit_cyr_to_lat_chunk(c))
    return "".join(result)


def adapt_to_user_script(reply_text: str, target_script: str) -> str:
    """
    Bot javobini foydalanuvchining alifbosiga (lotin yoki kirill) moslashtiruvchi universal adapter.
    target_script: 'cyrillic' yoki 'latin'
    """
    if not reply_text:
        return reply_text

    current_script = detect_script(reply_text)

    if target_script == "cyrillic":
        if current_script != "cyrillic":
            return latin_to_cyrillic(reply_text)
        return reply_text
    elif target_script == "latin":
        if current_script == "cyrillic":
            return cyrillic_to_latin(reply_text)
        return reply_text

    return reply_text
