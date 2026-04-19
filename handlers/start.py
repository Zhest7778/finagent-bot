from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_TELEGRAM_ID
from handlers.menu import MAIN_MENU, ADMIN_MENU

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = user.id == ADMIN_TELEGRAM_ID
    menu = ADMIN_MENU if is_admin else MAIN_MENU
    context.user_data["user_id"] = user.id
    context.user_data["username"] = user.username or user.first_name
    context.user_data["is_admin"] = is_admin
    if not context.user_data.get("spreadsheet_id") and context.bot_data.get("spreadsheet_id"):
        context.user_data["spreadsheet_id"] = context.bot_data["spreadsheet_id"]
    role = "Администратор 🔐" if is_admin else "Пользователь"
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n\n"
        f"Я *FinAgent* — финансовый AI-ассистент.\n"
        f"Роль: {role}\n\nОтправьте голосовое или выберите действие в меню.",
        parse_mode="Markdown",
        reply_markup=menu
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*FinAgent — команды:*\n\n"
        "🎤 *Голос* — диктуйте транзакцию или вопрос\n"
        "📊 *Таблица* — последние 10 записей\n"
        "🏢 *Контрагенты* — список с возможностью удаления\n"
        "📎 *Добавить документ* — к любой записи\n"
        "📈 *Отчёт* — анализ данных\n\n"
        "*Примеры команд:*\n"
        "• Запиши платёж 1650 евро Viza Rent за аренду генератора\n"
        "• Добавь контрагента Viza Rent\n"
        "• Сколько потратили на аренду этот месяц?\n\n"
        "/settable — подключить таблицу\n"
        "/initsheet — создать листы\n"
        "/attachlast — прикрепить к последней записи\n"
        "/done — завершить загрузку файлов",
        parse_mode="Markdown"
    )
