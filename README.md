# arab-uzbek-vocab

Arabcha–o'zbekcha so'z boyligini oshirish uchun Telegram bot. Manba —
«Мавзулар бўйича арабча-ўзбекча луғат» (Тошкент, 2014) kitobi, 17 ta mavzu
bo'yicha tuzilgan ~1040 ta so'z (uy-ro'zg'or, oziq-ovqat, o'simliklar,
hayvonlar, qushlar, hasharotlar, baliqlar, inson a'zolari, kasblar,
qurollar, geografik nomlar, texnika va h.k.).

## Texnik stack

- Python 3.10+
- [python-telegram-bot](https://docs.python-telegram-bot.org/) v20+ (async)
- SQLite (fayl asosida)
- pypdf (faqat PDF parse qilish bosqichi uchun)

Termux'da ishlashga moslangan — og'ir kutubxonalar ishlatilmaydi.

## Loyiha tuzilishi

```
arab-uzbek-vocab/
├── parse_pdf.py                  # PDF -> SQLite parser
├── uzbek_cyrillic_to_latin.py    # kirill -> lotin transliteratsiya
├── bot.py                        # asosiy fayl, handler'lar
├── database.py                   # SQLite funksiyalari
├── data/tema-buyicha-lugat.pdf   # manba PDF
├── words.db                      # SQLite baza (gitignore'da, parse_pdf.py yaratadi)
├── .env                          # TELEGRAM_BOT_TOKEN (gitignore'da)
├── requirements.txt
└── README.md
```

## O'rnatish va ishga tushirish

### 1. Kutubxonalarni o'rnatish

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Bazani tayyorlash

PDF'ni o'qib, `words.db` bazasini yaratadi (mavzu, arabcha so'z,
o'zbekcha tarjima — lotin alifbosida):

```bash
python parse_pdf.py
```

Konsolda so'zlar/mavzular soni va 10 ta tasodifiy namuna chiqadi.

### 3. Bot tokenini olish

1. Telegram'da [@BotFather](https://t.me/BotFather) ga yozing.
2. `/newbot` → nom va username bering.
3. Berilgan tokenni nusxalang.

### 4. `.env` faylini sozlash

```bash
cp .env.example .env
```

`.env` ichida `TELEGRAM_BOT_TOKEN` qiymatini o'z tokeningizga almashtiring.

### 5. Botni ishga tushirish

```bash
python bot.py
```

Konsolda `Bot ishga tushdi (polling)` chiqsa — tayyor. Telegram'da botga
`/start` yuboring.

## Buyruqlar

| Buyruq | Vazifasi |
|--------|----------|
| `/start` | Ro'yxatdan o'tish + yordam |
| `/flashcard` | Mavzu tanlab, kartochka sessiyasi: so'zni ko'r → javobni och → «Bildim / Bilmadim» |
| `/test` | Mavzu tanlab, variantli test: 4 ta javobdan to'g'risini tanlash |
| `/stats` | Mavzular bo'yicha «bilaman» statistikasi |
| `/help` | Buyruqlar ro'yxati |

Har sessiyada shu mavzudan 10 tagacha so'z beriladi (`bot.py` → `SESSION_SIZE`).

## Progress

Foydalanuvchi progressi (`bilaman`/`bilmayman`) `progress` jadvalida
saqlanadi (user_id, word_id, status).

## Ishlab chiqish bosqichlari

- [x] 1. Muhit: venv, kutubxonalar, loyiha tuzilishi
- [x] 2. PDF parse — 1040 so'z, 17 mavzu (`parse_pdf.py`)
- [x] 2b. Kirill → lotin transliteratsiya (`uzbek_cyrillic_to_latin.py`)
- [x] 3. Telegram bot — /start, /flashcard, /test, /stats
- [ ] 4. Arabcha matndagi qoldiq harakat/bo'sh joy artefaktlarini tozalash (ixtiyoriy)
