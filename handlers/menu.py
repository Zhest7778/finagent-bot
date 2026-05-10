import html as html_module
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("➕ Новая запись"), KeyboardButton("📊 Таблица")],
        [KeyboardButton("🏢 Контрагенты"), KeyboardButton("⚙️ Настройки")],
    ],
    resize_keyboard=True,
)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=MAIN_MENU,
    )


async def show_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает последние 20 транзакций из Google Sheets."""
    from services.sheets import get_all_transactions

    await update.message.reply_text("⏳ Загружаю данные...")

    try:
        records = get_all_transactions()
    except Exception as e:
        logger.error(f"show_table error: {e}")
        await update.message.reply_text(f"❌ Ошибка получения данных:\n<code>{html_module.escape(str(e))}</code>", parse_mode="HTML")
        return

    if not records:
        await update.message.reply_text("📭 Записей пока нет.")
        return

    lines = []
    for idx, rec in enumerate(records[-20:], 1):
        parts = [f"<b>#{idx}</b>"]
        for k, v in rec.items():
            if v == "" or v is None:
                continue
            safe_k = html_module.escape(str(k))
            safe_v = html_module.escape(str(v))
            parts.append(f"<b>{safe_k}:</b> {safe_v}")
        lines.append("\n".join(parts))

    text = "\n\n".join(lines)

    # Telegram лимит 4096 символов
    if len(text) > 4000:
        text = text[:4000] + "\n\n<i>...список обрезан, показаны последние записи</i>"

    await update.message.reply_text(text, parse_mode="HTML")


async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Роутер для кнопок главного меню."""
    text = update.message.text

    if text == "📊 Таблица":
        await show_table(update, context)
    elif text == "➕ Новая запись":
        from handlers.transaction import start_transaction
        await start_transaction(update, context)
    elif text == "🏢 Контрагенты":
        from handlers.clients import show_clients
        await show_clients(update, context)
    elif text == "⚙️ Настройки":
        await update.message.reply_text("⚙️ Настройки в разработке.")
    else:
        await show_main_menu(update, context)
