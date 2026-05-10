import os
import logging
import json
import traceback
from dotenv import load_dotenv

load_dotenv()

# ====================== ДИАГНОСТИКА GOOGLE CREDENTIALS ======================
print("\n[DEBUG] === GOOGLE CREDENTIALS CHECK START ===", flush=True)

_raw = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
print(f"[DEBUG] GOOGLE_CREDENTIALS_JSON length: {len(_raw)}", flush=True)

if _raw:
    try:
        _parsed = json.loads(_raw)
        print(f"[DEBUG] JSON OK, client_email: {_parsed.get('client_email')}", flush=True)
        print(f"[DEBUG] project_id: {_parsed.get('project_id')}", flush=True)
        _pk = _parsed.get("private_key", "")
        print(f"[DEBUG] private_key length={len(_pk)} newlines={_pk.count(chr(10))}", flush=True)
        if not _pk.startswith("-----BEGIN PRIVATE KEY-----"):
            print("[WARNING] private_key имеет неправильный формат!", flush=True)
    except json.JSONDecodeError as e:
        print(f"[ERROR] GOOGLE_CREDENTIALS_JSON — невалидный JSON: {e}", flush=True)
    except Exception as e:
        print(f"[ERROR] Credentials check failed: {e}", flush=True)
else:
    print("[ERROR] GOOGLE_CREDENTIALS_JSON is empty or not set!", flush=True)

print("[DEBUG] === GOOGLE CREDENTIALS CHECK END ===\n", flush=True)
# ============================================================================

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from config import TELEGRAM_BOT_TOKEN, SPREADSHEET_ID
from handlers.start import start, help_command
from handlers.voice import handle_voice, process_text_command
from handlers.transaction import handle_callback
from handlers.menu import handle_menu_button, ALL_BUTTONS
from handlers.documents import handle_incoming_file, attach_last_command, done_command
from services.sheets import init_spreadsheet

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ── Системный промпт для LLM ──────────────────────────────────────────────────
# Импортируется handlers/voice.py и handlers/transaction.py — передаётся в Gemini.
# Если у тебя промпт задаётся в другом файле, перенеси туда эту константу.
SYSTEM_PROMPT = (
    "Ты — финансовый помощник. Твоя единственная задача: распознавать финансовые операции "
    "из сообщений пользователя и фиксировать их в таблице. "
    "Не давай никаких оценок, предупреждений, советов и комментариев по поводу "
    "названий проектов, контрагентов, характера сделок или финансовых рисков. "
    "Не предупреждай о мошенничестве, схемах, пирамидах или рисках потери средств. "
    "Просто записывай данные так, как их передаёт пользователь, без интерпретации."
)


async def post_init(application):
    if SPREADSHEET_ID:
        application.bot_data["spreadsheet_id"] = SPREADSHEET_ID.strip()
        application.bot_data["system_prompt"] = SYSTEM_PROMPT
        print(f"✅ Таблица подключена: {SPREADSHEET_ID}", flush=True)
    else:
        print("⚠️ SPREADSHEET_ID не задан в .env — используйте /settable", flush=True)


async def set_table(update: Update, context):
    if not context.args:
        await update.message.reply_text(
            "Использование: `/settable <ID таблицы>`\n\n"
            "ID находится в URL Google таблицы между `/d/` и `/edit`",
            parse_mode="Markdown"
        )
        return

    sheet_id = context.args[0].strip()
    context.user_data["spreadsheet_id"] = sheet_id
    context.bot_data["spreadsheet_id"] = sheet_id
    await update.message.reply_text(f"✅ Таблица подключена: `{sheet_id}`", parse_mode="Markdown")


async def init_sheet(update: Update, context):
    sheet_id = context.user_data.get("spreadsheet_id") or context.bot_data.get("spreadsheet_id")
    if not sheet_id:
        await update.message.reply_text("⚠️ Сначала подключите таблицу: /settable <ID>")
        return

    msg = await update.message.reply_text("⏳ Инициализирую таблицу...")
    try:
        init_spreadsheet(sheet_id)
        await msg.edit_text("✅ Таблица успешно инициализирована!")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[ERROR] init_sheet: {tb}", flush=True)
        await msg.edit_text(f"❌ Ошибка:\n```{str(e)[:500]}```", parse_mode="Markdown")


def _sync_spreadsheet_id(context):
    if not context.user_data.get("spreadsheet_id"):
        sid = context.bot_data.get("spreadsheet_id") or SPREADSHEET_ID
        if sid:
            context.user_data["spreadsheet_id"] = sid


async def handle_text(update: Update, context):
    _sync_spreadsheet_id(context)
    text = update.message.text

    if text in ALL_BUTTONS:
        await handle_menu_button(update, context)
    else:
        await process_text_command(update, context, text)


async def handle_voice_wrapper(update: Update, context):
    _sync_spreadsheet_id(context)
    await handle_voice(update, context)


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("settable", set_table))
    app.add_handler(CommandHandler("initsheet", init_sheet))
    app.add_handler(CommandHandler("attachlast", attach_last_command))
    app.add_handler(CommandHandler("done", done_command))

    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_wrapper))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_incoming_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🚀 FinAgent Bot запущен!", flush=True)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
