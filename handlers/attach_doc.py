from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from services.sheets import get_all_transactions, attach_document_to_row, log_action

PAGE_SIZE = 8

async def show_transactions_for_attach(update_or_query, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    spreadsheet_id = context.user_data.get("spreadsheet_id")
    if not spreadsheet_id:
        text = "⚠️ Таблица не подключена. /settable"
        if hasattr(update_or_query, "edit_message_text"):
            await update_or_query.edit_message_text(text)
        else:
            await update_or_query.message.reply_text(text)
        return

    try:
        records = get_all_transactions(spreadsheet_id)
    except Exception as e:
        text = f"❌ Ошибка: {e}"
        if hasattr(update_or_query, "edit_message_text"):
            await update_or_query.edit_message_text(text)
        else:
            await update_or_query.message.reply_text(text)
        return

    if not records:
        text = "📭 Нет записей."
        if hasattr(update_or_query, "edit_message_text"):
            await update_or_query.edit_message_text(text)
        else:
            await update_or_query.message.reply_text(text)
        return

    # Показываем последние записи первыми
    reversed_records = list(reversed(records))
    total = len(reversed_records)
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    page_records = reversed_records[start:end]

    context.user_data["attach_page"] = page
    context.user_data["attach_records"] = records  # оригинальный порядок

    lines = [f"📎 *Выберите запись для документа* (стр. {page+1}):\n"]
    buttons = []
    for r in page_records:
        num = r.get("№", "")
        date = r.get("Дата", "")
        amount = r.get("Сумма", "")
        currency = r.get("Валюта", "EUR")
        comment = str(r.get("Комментарий", ""))[:25]
        has_doc = "📎" if r.get("Документ") else ""
        label = f"#{num} {date} | {amount} {currency} {has_doc}"
        lines.append(f"• {label} — {comment}")
        buttons.append([InlineKeyboardButton(label, callback_data=f"attach_to_{num}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"attach_page_{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("➡️ Вперёд", callback_data=f"attach_page_{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("✖️ Закрыть", callback_data="cancel")])

    keyboard = InlineKeyboardMarkup(buttons)
    text = "\n".join(lines)

    if hasattr(update_or_query, "edit_message_text"):
        await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def handle_attach_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data = query.data

    if data.startswith("attach_page_"):
        page = int(data.split("_")[-1])
        await query.answer()
        await show_transactions_for_attach(query, context, page)
        return True

    if data.startswith("attach_to_"):
        num = int(data.split("_")[-1])
        await query.answer()
        context.user_data["doc_upload_active"] = True
        context.user_data["doc_purpose"] = "attach"
        context.user_data["awaiting_doc_for"] = num
        await query.edit_message_text(
            f"📤 *Отправьте документ для записи #{num}*\n\n"
            f"Можно отправить несколько файлов по очереди.\n"
            f"• 📷 Фото чека\n"
            f"• 📄 PDF фактуры или договора\n\n"
            f"Когда закончите — нажмите /done",
            parse_mode="Markdown"
        )
        return True

    return False
