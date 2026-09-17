"""Arabcha–o'zbekcha so'z boyligi boti — handler'lar va ishga tushirish.

Buyruqlar:
    /start      — ro'yxatdan o'tish, mavzular ro'yxati
    /flashcard  — mavzu tanlab, kartochka sessiyasi
    /test       — mavzu tanlab, variantli test
    /stats      — o'rganish statistikasi
    /help       — buyruqlar ro'yxati
"""

from __future__ import annotations

import logging
import os
import random

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import database as db

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("arab-vocab-bot")

SESSION_SIZE = 10
TEST_OPTIONS = 4

BTN_FLASHCARD = "📇 Kartochka"
BTN_TEST = "🧩 Test"
BTN_STATS = "📊 Statistika"
MAIN_KB = ReplyKeyboardMarkup(
    [[BTN_FLASHCARD, BTN_TEST], [BTN_STATS]],
    resize_keyboard=True,
)

BOT_COMMANDS = [
    BotCommand("flashcard", "Kartochka sessiyasi"),
    BotCommand("test", "Variantli test"),
    BotCommand("stats", "O'rganish statistikasi"),
    BotCommand("help", "Yordam"),
]

HELP_TEXT = (
    "🇦🇪🇺🇿 <b>Arabcha–o'zbekcha so'z boti</b>\n\n"
    "/flashcard — mavzu tanlab, kartochka sessiyasi\n"
    "/test — mavzu tanlab, variantli test\n"
    "/stats — o'rganish statistikasi\n"
    "/help — shu yordam\n\n"
    "Pastdagi tugmalardan ham foydalanishingiz mumkin. "
    f"Har sessiyada {SESSION_SIZE} tagacha so'z."
)


# --------------------------------------------------------------------------- #
#  Yordamchilar
# --------------------------------------------------------------------------- #
_ALL_WORDS_CACHE: list[dict] = []


def db_all_words() -> list[dict]:
    global _ALL_WORDS_CACHE
    if not _ALL_WORDS_CACHE:
        cats = db.get_categories()
        for c in cats:
            _ALL_WORDS_CACHE.extend(db.get_words_by_category(c["mavzu"]))
    return _ALL_WORDS_CACHE


def _card_text(word: dict, idx: int, total: int, revealed: bool) -> str:
    head = f"📇 Kartochka {idx}/{total}  <i>({word['mavzu'].title()})</i>\n\n🇦🇪 <b>{word['arabcha_soz']}</b>"
    if not revealed:
        return head
    return f"{head}\n\n🇺🇿 <b>{word['ozbekcha_tarjima']}</b>"


def _summary_text(session: dict) -> str:
    done = session["correct"] + session["wrong"]
    acc = round(session["correct"] / done * 100) if done else 0
    kind = "Kartochka" if session["mode"] == "flashcard" else "Test"
    return (
        f"🎉 <b>{kind} sessiyasi tugadi!</b>\n\n"
        f"✅ To'g'ri/Bildim: {session['correct']}\n"
        f"❌ Xato/Bilmadim: {session['wrong']}\n"
        f"🎯 Aniqlik: {acc}%\n\n"
        "Yana mashq qilish uchun /flashcard yoki /test.\n"
        "Umumiy holat — /stats."
    )


def _build_test_options(word: dict) -> list[dict]:
    pool = [
        w for w in db_all_words()
        if w["id"] != word["id"] and w["ozbekcha_tarjima"] != word["ozbekcha_tarjima"]
    ]
    distractors = random.sample(pool, k=min(TEST_OPTIONS - 1, len(pool)))
    options = [word, *distractors]
    random.shuffle(options)
    return options


def _short_uz(text: str, limit: int = 40) -> str:
    first = text.split(",")[0].strip()
    return first if len(first) <= limit else first[: limit - 1] + "…"


# --------------------------------------------------------------------------- #
#  Sessiya boshqaruvi
# --------------------------------------------------------------------------- #
def _start_session(context: ContextTypes.DEFAULT_TYPE, mavzu: str, mode: str) -> dict | None:
    words = db.get_words_by_category(mavzu)
    if not words:
        return None
    random.shuffle(words)
    words = words[:SESSION_SIZE]
    session = {
        "mode": mode,
        "mavzu": mavzu,
        "queue": words,
        "pos": 0,
        "revealed": False,
        "correct": 0,
        "wrong": 0,
        "options": [],
    }
    context.user_data["session"] = session
    return session


def _current_word(session: dict) -> dict | None:
    if session["pos"] >= len(session["queue"]):
        return None
    return session["queue"][session["pos"]]


async def _render_current(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = context.user_data["session"]
    word = _current_word(session)
    total = len(session["queue"])
    idx = session["pos"] + 1

    send = _make_sender(update_or_query)

    if word is None:
        await send(_summary_text(session), reply_markup=None)
        context.user_data.pop("session", None)
        return

    if session["mode"] == "flashcard":
        text = _card_text(word, idx, total, session["revealed"])
        if session["revealed"]:
            kb = [[
                InlineKeyboardButton("✅ Bildim", callback_data="ans:1"),
                InlineKeyboardButton("❌ Bilmadim", callback_data="ans:0"),
            ]]
        else:
            kb = [[InlineKeyboardButton("👁 Javobni ko'rish", callback_data="reveal")]]
        await send(text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if not session["options"]:
        session["options"] = _build_test_options(word)
    text = (
        f"🧩 Test {idx}/{total}  <i>({word['mavzu'].title()})</i>\n\n"
        f"Bu so'z nima degani?\n🇦🇪 <b>{word['arabcha_soz']}</b>"
    )
    kb = [
        [InlineKeyboardButton(_short_uz(opt["ozbekcha_tarjima"]), callback_data=f"opt:{opt['id']}")]
        for opt in session["options"]
    ]
    await send(text, reply_markup=InlineKeyboardMarkup(kb))


def _make_sender(update_or_query):
    if isinstance(update_or_query, Update):
        chat = update_or_query.effective_chat

        async def send(text, reply_markup):
            await chat.send_message(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        return send

    query = update_or_query

    async def send(text, reply_markup):
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return send


def _topics_keyboard(mode: str) -> InlineKeyboardMarkup:
    cats = db.get_categories()
    rows = [
        [InlineKeyboardButton(f"{c['mavzu'].title()} ({c['count']})", callback_data=f"cat:{mode}:{i}")]
        for i, c in enumerate(cats)
    ]
    return InlineKeyboardMarkup(rows)


# --------------------------------------------------------------------------- #
#  Buyruq handler'lari
# --------------------------------------------------------------------------- #
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    name = user.first_name or "do'stim"
    await update.effective_chat.send_message(
        f"Salom, {name}! 👋\n\n{HELP_TEXT}",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_KB,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_message(HELP_TEXT, parse_mode=ParseMode.HTML, reply_markup=MAIN_KB)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    route = {
        BTN_FLASHCARD: cmd_flashcard,
        BTN_TEST: cmd_test,
        BTN_STATS: cmd_stats,
    }
    handler = route.get((update.message.text or "").strip())
    if handler:
        await handler(update, context)


async def cmd_flashcard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    await update.effective_chat.send_message(
        "📇 Mavzuni tanlang:", reply_markup=_topics_keyboard("flashcard")
    )


async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    await update.effective_chat.send_message(
        "🧩 Mavzuni tanlang:", reply_markup=_topics_keyboard("test")
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.ensure_user(user.id, user.username, user.first_name)
    s = db.get_stats(user.id)
    lines = [
        f"📊 <b>Statistika</b>\n",
        f"Jami so'zlar: {s['total_words']}",
        f"✅ Bilaman: {s['known']}",
        f"❌ Bilmayman: {s['unknown']}",
        f"⚪ Boshlanmagan: {s['not_started']}\n",
        "<b>Mavzular bo'yicha (bilaman/jami)</b>",
    ]
    for c in s["by_category"]:
        lines.append(f"  {c['mavzu'].title()}: {c['known']}/{c['total']}")
    await update.effective_chat.send_message("\n".join(lines), parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------------- #
#  Tugma (callback) handler'lari
# --------------------------------------------------------------------------- #
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("cat:"):
        _, mode, idx_str = data.split(":", 2)
        cats = db.get_categories()
        idx = int(idx_str)
        if idx >= len(cats):
            await query.edit_message_text("Mavzu topilmadi. /flashcard yoki /test bilan qayta urinib ko'ring.")
            return
        mavzu = cats[idx]["mavzu"]
        session = _start_session(context, mavzu, mode)
        if session is None:
            await query.edit_message_text("Bu mavzuda so'z topilmadi.")
            return
        await _render_current(query, context)
        return

    session = context.user_data.get("session")
    if session is None:
        await query.edit_message_text("Sessiya tugagan. Yangi mashq: /flashcard yoki /test")
        return

    word = _current_word(session)
    if word is None:
        await query.edit_message_text(_summary_text(session), parse_mode=ParseMode.HTML)
        context.user_data.pop("session", None)
        return

    user_id = query.from_user.id

    if data == "reveal":
        session["revealed"] = True
        await _render_current(query, context)
        return

    if data.startswith("ans:"):
        correct = data == "ans:1"
        db.set_status(user_id, word["id"], "known" if correct else "unknown")
        session["correct" if correct else "wrong"] += 1
        session["pos"] += 1
        session["revealed"] = False
        await _render_current(query, context)
        return

    if data.startswith("opt:"):
        chosen_id = int(data.split(":", 1)[1])
        correct = chosen_id == word["id"]
        db.set_status(user_id, word["id"], "known" if correct else "unknown")
        session["correct" if correct else "wrong"] += 1
        await query.answer(
            "To'g'ri!" if correct else f"Noto'g'ri — {word['ozbekcha_tarjima']}",
            show_alert=not correct,
        )
        session["pos"] += 1
        session["options"] = []
        await _render_current(query, context)
        return


# --------------------------------------------------------------------------- #
#  Ishga tushirish
# --------------------------------------------------------------------------- #
async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Buyruqlar menyusi o'rnatildi (%d ta).", len(BOT_COMMANDS))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Handler xatosi", exc_info=context.error)
    chat = getattr(update, "effective_chat", None) if isinstance(update, Update) else None
    if chat is None:
        return
    try:
        await chat.send_message(
            "⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring — /flashcard yoki /test.",
            reply_markup=MAIN_KB,
        )
    except Exception:
        logger.exception("Xato haqida xabar yuborib bo'lmadi")


def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN topilmadi. .env.example ni .env deb nusxalab, tokeningizni yozing."
        )

    db.init_db()
    if db.count_words() == 0:
        raise SystemExit(
            "Baza bo'sh. Avval `python parse_pdf.py` ni ishga tushiring."
        )
    logger.info("Baza tayyor, so'zlar: %d, mavzular: %d", db.count_words(), len(db.get_categories()))

    app = Application.builder().token(token).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("flashcard", cmd_flashcard))
    app.add_handler(CommandHandler("test", cmd_test))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)

    logger.info("Bot ishga tushdi (polling).")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
