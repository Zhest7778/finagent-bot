from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from services.sheets import get_all_transactions, get_all_clients
from config import ADMIN_TELEGRAM_ID

MAIN_MENU = ReplyKeyboardMarkup([
    [KeyboardButton("🎤 Голосовой ввод"), KeyboardButton("📝 Текстовый ввод")],
    [KeyboardButton("📊 Таблица"), KeyboardButton("🏢 Контрагенты")],
    [KeyboardButton("📈 Отчёт"), KeyboardButton("📎 Добавить документ")],
    [KeyboardButton("🗂 Проекты"), KeyboardButton("ℹ️ Помощь")],
], resize_keyboard=True)

ADMIN_MENU = ReplyKeyboardMarkup([
    [KeyboardButton("🎤 Голосовой ввод"), KeyboardButton("📝 Текстовый ввод")],
    [KeyboardButton("📊 Таблица"), KeyboardButton("🏢 Контрагенты")],
    [KeyboardButton("📈 Отчёт"), KeyboardButton("📎 Добавить документ")],
    [KeyboardButton("🗂 Проекты"), KeyboardButton("🔐 Админ-панель")],
    [KeyboardButton("ℹ️ Помощь")],
], resize_keyboard=True)

ALL_BUTTONS = [
    "🎤 Голосовой ввод", "📝 Текстовый ввод", "📊 Таблица",
    "🏢 Контрагенты", "📈 Отчёт", "📎 Добавить документ",
    "🗂 Проекты", "🔐 Админ-панель", "ℹ️ Помощь"
]

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    spreadsheet_id = context.user_data.get("spreadsheet_id")

    if text == "📊 Таблица":
        await show_table(update, context, spreadsheet_id)
    elif text == "🏢 Контрагенты":
        from handlers.clients import show_clients_list
        await show_clients_list(update, context, page=0)
    elif text == "📈 Отчёт":
        await update.message.reply_text(
            "📈 Задайте вопрос голосом или текстом:\n\n"
            "• Сколько потратили на аренду в этом месяце?\n"
            "• Покажи все платежи свыше 1000 евро\n"
            "• Каков баланс за апрель?"
        )
    elif text == "📎 Добавить документ":
        from handlers.attach_doc import show_transactions_for_attach
        await show_transactions_for_attach(update, context, page=0)
    elif text == "🗂 Проекты":
        sid = spreadsheet_id or "не подключена"
        await update.message.reply_text(
            f"🗂 *Рабочие пространства*\n\nТекущая таблица: `{sid}`\n\n"
            f"/settable `ID` — подключить таблицу\n"
            f"/initsheet — инициализировать листы",
            parse_mode="Markdown"
        )
    elif text == "🔐 Админ-панель":
        if update.effective_user.id != ADMIN_TELEGRAM_ID:
            await update.message.reply_text("❌ Нет доступа.")
            return
        await update.message.reply_text(
            f"🔐 *Админ-панель*\n\n"
            f"Таблица: `{spreadsheet_id or 'не подключена'}`\n\n"
            f"/settable `ID`\n/initsheet",
            parse_mode="Markdown"
        )
    elif text in ("🎤 Голосовой ввод", "📝 Текстовый ввод"):
        await update.message.reply_text(
            "🎤 Говорите или пишите команду.\n\nПример:\n"
            "_Запиши платёж 1650 евро Viza Rent за аренду генератора_",
            parse_mode="Markdown"
        )
    elif text == "ℹ️ Помощь":
        from handlers.start import help_command
        await help_command(update, context)


async def show_table(update, context, spreadsheet_id):
    if not spreadsheet_id:
        await update.message.reply_text("⚠️ Таблица не подключена.\n/settable <ID>")
        return
    try:
        records = get_all_transactions(spreadsheet_id)
        if not records:
            await update.message.reply_text("📭 Таблица пуста.")
            return
        lines = ["📊 *Последние записи:*\n"]
        for r in reversed(records[-10:]):
            doc_icon = "📎" if r.get("Документ") else ""
            lines.append(
                f"#{r.get('№','')} | {r.get('Дата','')} | "
                f"{r.get('Сумма','')} {r.get('Валюта','EUR')} {doc_icon}\n"
                f"   _{str(r.get('Комментарий',''))[:35]}_"
            )
        lines.append(f"\n_Всего: {len(records)} записей_")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        await update.message.reply_text(
            f"❌ Ошибка: {type(e).__name__}: {e}\n\n<pre>{err[-800:]}</pre>",
            parse_mode="HTML"
        )
