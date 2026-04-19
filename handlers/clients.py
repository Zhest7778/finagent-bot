from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from services.sheets import get_all_clients, delete_client, log_action

PAGE_SIZE = 8

# Колонки: Алиас(0), Название компании(1), Рег.номер(2), VAT(3), Адрес(4), Руководитель(5), Контакты(6), Страна(7), ЕС(8)

def _client_display(c: dict, num: int) -> str:
    alias   = (c.get("Алиас") or "").strip()
    name    = (c.get("Название компании") or "").strip()
    country = (c.get("Страна") or "").strip()

    if alias and name:
        display = f"{alias} — {name}"
    elif alias:
        display = alias
    elif name:
        display = name
    else:
        display = f"#{num}"

    if country:
        display += f" ({country})"
    return display


async def show_clients_list(update_or_query, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    spreadsheet_id = context.user_data.get("spreadsheet_id")
    if not spreadsheet_id:
        text = "⚠️ Таблица не подключена. /settable"
        if hasattr(update_or_query, "edit_message_text"):
            await update_or_query.edit_message_text(text)
        else:
            await update_or_query.message.reply_text(text)
        return

    try:
        clients = get_all_clients(spreadsheet_id)
    except Exception as e:
        text = f"❌ Ошибка получения данных: {e}"
        if hasattr(update_or_query, "edit_message_text"):
            await update_or_query.edit_message_text(text)
        else:
            await update_or_query.message.reply_text(text)
        return

    if not clients:
        text = "📭 База контрагентов пуста."
        if hasattr(update_or_query, "edit_message_text"):
            await update_or_query.edit_message_text(text)
        else:
            await update_or_query.message.reply_text(text)
        return

    total = len(clients)
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    page_clients = clients[start:end]

    context.user_data["clients_page"] = page
    context.user_data["clients_list"] = clients

    lines = [f"🏢 *Контрагенты* ({total} всего), стр. {page+1}:\n"]
    buttons = []
    for i, c in enumerate(page_clients):
        idx = start + i
        display = _client_display(c, idx + 1)
        lines.append(f"{idx+1}. {display}")
        short = display[:25]
        buttons.append([InlineKeyboardButton(
            f"🗑 Удалить {short}",
            callback_data=f"del_client_{idx}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"clients_page_{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("➡️ Вперёд", callback_data=f"clients_page_{page+1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("✖️ Закрыть", callback_data="cancel")])

    keyboard = InlineKeyboardMarkup(buttons)
    text = "\n".join(lines)

    if hasattr(update_or_query, "edit_message_text"):
        try:
            await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        except Exception:
            pass
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def handle_clients_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data = query.data

    if data.startswith("clients_page_"):
        page = int(data.split("_")[-1])
        await query.answer()
        await show_clients_list(query, context, page)
        return True

    if data.startswith("del_client_"):
        idx = int(data.split("_")[-1])
        clients = context.user_data.get("clients_list", [])
        if idx >= len(clients):
            await query.answer("❌ Запись не найдена")
            return True
        client = clients[idx]
        name = _client_display(client, idx + 1)
        context.user_data["del_client_idx"] = idx
        context.user_data["del_client_name"] = name
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_del_client_{idx}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"clients_page_{context.user_data.get('clients_page',0)}")
        ]])
        await query.answer()
        try:
            await query.edit_message_text(
                f"⚠️ Удалить контрагента?\n\n*{name}*",
                parse_mode="Markdown", reply_markup=keyboard
            )
        except Exception:
            pass
        return True

    if data.startswith("confirm_del_client_"):
        idx = int(data.split("_")[-1])
        spreadsheet_id = context.user_data.get("spreadsheet_id")
        name = context.user_data.get("del_client_name", "")
        await query.answer()
        try:
            delete_client(spreadsheet_id, idx)
            log_action(spreadsheet_id, query.from_user.id,
                      query.from_user.username or "", "delete_client", name)
            context.user_data.pop("clients_list", None)
            await query.message.reply_text(f"✅ Контрагент *{name}* удалён.", parse_mode="Markdown")
            await show_clients_list(query.message, context, page=0)
        except Exception as e:
            try:
                await query.edit_message_text(f"❌ Ошибка удаления: {e}")
            except Exception:
                await query.message.reply_text(f"❌ Ошибка удаления: {e}")
        return True

    return False
