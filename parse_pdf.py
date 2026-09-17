"""«Мавзулар бўйича арабча-ўзбекча луғат» PDF faylini o'qib, SQLite bazasiga yozadi.

PDF format tuzilishi (tema-buyicha-lugat.pdf):
  * Har bir mavzu (masalan "УЙ ВА УЙГА ТЕГИШЛИ УСКУНАЛАР") — butunlay katta
    harfli kirill sarlavha qatori. Undan oldin ko'pincha arabcha mavzu nomi
    keladi (uni e'tiborsiz qoldiramiz).
  * Har bir so'z yozuvi bitta qatorda: arabcha so'z (harakatlar bilan,
    ba'zan qavs ichida ko'plik shakli) + tire (- yoki –) + o'zbekcha tarjima
    (kirillcha).

Muammo: PDF matn ekstraktsiyasida arab (RTL) va o'zbek (LTR) qismlar bir xil
qatorda vizual joylashuvi bo'yicha aralashib chiqadi (masalan tire so'z
oxiriga chiqib qoladi, o'zbekcha tarjima esa arabcha qavslar orasida paydo
bo'lishi mumkin). Buni hal qilish uchun tire pozitsiyasiga emas, balki har
bir belgining Unicode blokiga (arab yoki kirill) qaraladi: arab-blok
belgilari o'z navbatini saqlagan holda bitta "arabcha" bufer'ga, kirill-blok
belgilari o'z navbatini saqlagan holda "o'zbekcha" bufer'ga yig'iladi.
Bo'sh joy, qavs, tire, vergul kabi neytral belgilar oxirgi faol
buferga qo'shiladi.
"""

from __future__ import annotations

import random
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from uzbek_cyrillic_to_latin import cyrillic_to_latin

BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = BASE_DIR / "data" / "tema-buyicha-lugat.pdf"
DB_PATH = BASE_DIR / "words.db"

ARABIC_RANGES = [(0x0600, 0x06FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)]
CYRILLIC_RANGES = [(0x0400, 0x04FF), (0x0500, 0x052F)]

SKIP_LINE_RE = re.compile(r"^(www\.arabic\.uz|\d+)$")


def _in_ranges(ch: str, ranges: list[tuple[int, int]]) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in ranges)


def is_arabic_char(ch: str) -> bool:
    return _in_ranges(ch, ARABIC_RANGES)


def is_cyrillic_char(ch: str) -> bool:
    return _in_ranges(ch, CYRILLIC_RANGES)


def split_scripts(line: str) -> tuple[str, str]:
    """Qatorni arabcha va o'zbekcha (kirill) buferlarga ajratadi.

    Belgi arab yoki kirill blokida bo'lsa — mos buferga, aks holda (bo'sh
    joy, tire, qavs, vergul, raqam) — oxirgi faol buferga qo'shiladi.
    """
    arabic: list[str] = []
    uzbek: list[str] = []
    mode = "ar"  # standart: qator arabcha so'z bilan boshlanadi
    for ch in line:
        if is_arabic_char(ch):
            mode = "ar"
            arabic.append(ch)
        elif is_cyrillic_char(ch):
            mode = "uz"
            uzbek.append(ch)
        else:
            (arabic if mode == "ar" else uzbek).append(ch)
    return "".join(arabic), "".join(uzbek)


def clean_arabic(text: str) -> str:
    text = re.sub(r"[-–—,]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_uzbek(text: str) -> str:
    text = re.sub(r"^[\s\-–—,]+", "", text)
    text = re.sub(r"[\s\-–—]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def is_category_header(line: str) -> bool:
    """Butunlay katta harfli kirill sarlavha (tire, arab belgisi yo'q)."""
    letters = [ch for ch in line if ch.isalpha()]
    if not letters:
        return False
    if any(is_arabic_char(ch) for ch in line):
        return False
    if "-" in line or "–" in line:
        return False
    if not all(is_cyrillic_char(ch) for ch in letters):
        return False
    return all(ch == ch.upper() for ch in letters)


@dataclass
class Entry:
    category: str
    arabic: str
    uzbek: str


def extract_lines() -> list[str]:
    reader = PdfReader(str(PDF_PATH))
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for raw in text.split("\n"):
            line = raw.strip()
            if not line or SKIP_LINE_RE.match(line):
                continue
            lines.append(line)
    return lines


def parse_entries(lines: list[str]) -> list[Entry]:
    entries: list[Entry] = []
    pending_headers: list[str] = []
    current_category = "Umumiy"

    for line in lines:
        if is_category_header(line):
            pending_headers.append(line)
            continue

        if pending_headers:
            current_category = " — ".join(pending_headers)
            pending_headers = []

        arabic_raw, uzbek_raw = split_scripts(line)
        arabic = clean_arabic(arabic_raw)
        uzbek = clean_uzbek(uzbek_raw)

        if not uzbek:
            # Kirillcha tarjimasi bo'lmagan qator (masalan bismillah satri) — o'tkazib yuboriladi
            continue

        if not arabic and entries:
            # Faqat davomi (oldingi tarjimaning davomi, arabcha yo'q)
            entries[-1].uzbek = clean_uzbek(entries[-1].uzbek + " " + uzbek)
            continue

        if not arabic:
            continue

        entries.append(Entry(category=current_category, arabic=arabic, uzbek=uzbek))

    for e in entries:
        e.uzbek = cyrillic_to_latin(e.uzbek)

    return entries


SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id                INTEGER PRIMARY KEY,
    mavzu             TEXT NOT NULL,
    arabcha_soz       TEXT NOT NULL,
    ozbekcha_tarjima  TEXT NOT NULL
);
"""


def save_to_db(entries: list[Entry]) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM words")
        conn.executemany(
            "INSERT INTO words (mavzu, arabcha_soz, ozbekcha_tarjima) VALUES (?, ?, ?)",
            [(e.category, e.arabic, e.uzbek) for e in entries],
        )


def main() -> None:
    lines = extract_lines()
    entries = parse_entries(lines)
    save_to_db(entries)

    categories = sorted({e.category for e in entries})
    print(f"Jami so'zlar: {len(entries)}")
    print(f"Jami mavzular: {len(categories)}\n")
    print("Mavzular ro'yxati:")
    for c in categories:
        count = sum(1 for e in entries if e.category == c)
        print(f"  - {c}  ({count} ta)")

    print("\n10 ta tasodifiy namuna:")
    for e in random.sample(entries, min(10, len(entries))):
        print(f"  [{e.category}] {e.arabic}  -  {e.uzbek}")


if __name__ == "__main__":
    main()
