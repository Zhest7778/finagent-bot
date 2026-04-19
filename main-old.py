import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)
from config import TELEGRAM_BOT_TOKEN, SPREADSHEET_ID
from handlers.start import start, help_command
from handlers.voice import handle_voice, process_text_command
from handlers.transaction import handle_callback
from handlers.menu import handle_menu_button
from handlers.documents import handle_incoming_file, attach_last_command
from services.sheets import init_spreadsheet

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

async def post_init(application):
    """Загружаем spreadsheet_id из .env при каждом старте."""
    if SPREADSHEET_ID:
        application.bot_data["spreadsheet_id"] = SPREADSHEET_ID
        print(f"✅ Таблица подключена автоматически: {SPREADSHEET_ID}")
    else:
        print("⚠️  SPREADSHEET_ID не задан в .env — используйте /settable")

async def set_table(update: Update, context):
    if not context.args:
        await update.message.reply_text(
            "Использование: /settable <ID таблицы>\n\n"
            "ID находится в URL таблицы между /d/ и /edit"
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
    context.user_data["spreadsheet_id"] = sheet_id
    msg = await update.message.reply_text("⏳ Инициализирую таблицу...")
    try:
        init_spreadsheet(sheet_id)
        await msg.edit_text(
            "✅ Готово! Листы созданы:\n"
            "• Транзакции\n• Контрагенты\n• _meta\n• _logs"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")

async def handle_text(update: Update, context):
    # Восстанавливаем spreadsheet_id если потерялся
    if not context.user_data.get("spreadsheet_id"):
        sid = context.bot_data.get("spreadsheet_id") or SPREADSHEET_ID
        if sid:
            context.user_data["spreadsheet_id"] = sid

    text = update.message.text
    menu_buttons = [
        "📊 Таблица", "🏢 Контрагенты", "📈 Отчёт",
        "🗂 Проекты", "🔐 Админ-панель", "ℹ️ Помощь",
        "🎤 Голосовой ввод", "📝 Текстовый ввод"
    ]
    if text in menu_buttons:
        await handle_menu_button(update, context)
    else:
        if context.user_data.get("manual_client_mode"):
            context.user_data.pop("manual_client_mode", None)
            from services.ai import parse_client
            data = parse_client(text)
            if "error" in data:
                await update.message.reply_text("❌ Не удалось разобрать данные. Попробуйте ещё раз.")
                return
            context.user_data["pending_client"] = data
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Сохранить", callback_data="save_client"),
                InlineKeyboardButton("❌ Отменить", callback_data="cancel")
            ]])
            await update.message.reply_text(
                f"🏢 *Контрагент:*\n"
                f"• Название: {data.get('company_name','—')}\n"
                f"• CIF/NIF: {data.get('reg_number','—')}\n"
                f"• Адрес: {data.get('address','—')}\n\nСохранить?",
                parse_mode="Markdown", reply_markup=keyboard
            )
        else:
            await process_text_command(update, context, text)

async def handle_voice_wrapper(update: Update, context):
    if not context.user_data.get("spreadsheet_id"):
        sid = context.bot_data.get("spreadsheet_id") or SPREADSHEET_ID
        if sid:
            context.user_data["spreadsheet_id"] = sid
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
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_wrapper))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_incoming_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("🚀 FinAgent Bot запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
