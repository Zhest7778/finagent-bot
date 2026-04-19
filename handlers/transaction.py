from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from services.sheets import add_transaction, add_client, get_all_clients, log_action

async def confirm_transaction_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict):
    missing = [f for f in data.get("missing_fields", []) if f != "date"]
    type_emoji = "📥" if data.get("type") == "income" else "📤"
    text = (
        f"{type_emoji} *Проект записи:*\n\n"
        f"📅 Дата: {data.get('date', '—')}\n"
        f"💶 Сумма: {data.get('amount', '—')} {data.get('currency', 'EUR')}\n"
        f"🔄 От: {data.get('from_party', '—')}\n"
        f"🔄 Кому: {data.get('to_party', '—')}\n"
        f"📝 Комментарий: {data.get('comment', '—')}"
    )
    if missing:
        fields_ru = {"amount": "сумма", "from_party": "от кого", "to_party": "кому", "comment": "назначение"}
        text += f"\n\n⚠️ _Не указано: {', '.join(fields_ru.get(f,f) for f in missing)}_"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Записать", callback_data="save_transaction"),
        InlineKeyboardButton("❌ Отменить", callback_data="cancel")
    ]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

    # Проверка контрагента в базе
    spreadsheet_id = context.user_data.get("spreadsheet_id")
    if spreadsheet_id:
        counterparty = data.get("to_party") or data.get("from_party")
        from services.ai import DEFAULT_COMPANY
        if counterparty and counterparty != DEFAULT_COMPANY:
            await check_counterparty(update, context, counterparty, spreadsheet_id)


async def check_counterparty(update, context, name: str, spreadsheet_id: str):
    try:
        clients = get_all_clients(spreadsheet_id)
        name_lower = name.lower()
        found = any(
            name_lower in str(c.get("Название компании", "")).lower() or
            name_lower in str(c.get("Алиас", "")).lower()
            for c in clients
        )
        if not found:
            context.user_data["unknown_counterparty"] = name
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📄 Загрузить документ", callback_data="add_client_doc"),
                    InlineKeyboardButton("✏️ Ввести вручную", callback_data="add_client_manual"),
                ],
                [InlineKeyboardButton("⏩ Пропустить", callback_data="skip_counterparty")]
            ])
            await update.message.reply_text(
                f"🔍 Контрагент *{name}* не найден в базе.\n\n"
                f"Создать карточку компании?\n\n"
                f"📄 *Загрузить документ* — фактура, договор, presupuesto\n"
                f"✏️ *Ввести вручную* — текстом или голосом",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    except Exception:
        pass


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    # Делегируем специализированным обработчикам
    from handlers.documents import handle_doc_callback
    from handlers.clients import handle_clients_callback
    from handlers.attach_doc import handle_attach_callback

    if await handle_doc_callback(update, context):
        return
    if await handle_clients_callback(update, context):
        return
    if await handle_attach_callback(update, context):
        return

    await query.answer()
    user = query.from_user
    spreadsheet_id = context.user_data.get("spreadsheet_id")

    if query.data == "save_transaction":
        if not spreadsheet_id:
            await query.edit_message_text("⚠️ Таблица не подключена. /settable")
            return
        data = context.user_data.get("pending_transaction", {})
        if not data:
            await query.edit_message_text("❌ Данные не найдены.")
            return
        try:
            num = add_transaction(spreadsheet_id, data)
            log_action(spreadsheet_id, user.id, user.username or "",
                      "add_transaction",
                      f"#{num} {data.get('amount')} {data.get('currency')} {str(data.get('comment',''))[:30]}")
            context.user_data.pop("pending_transaction", None)

            # Автосохранение аудио (только если была голосовая команда)
            audio_path = context.user_data.pop("pending_audio_path", None)
            if audio_path:
                from handlers.documents import save_voice_for_transaction
                await save_voice_for_transaction(context, audio_path, num, user.id)
                import os
                try: os.remove(audio_path)
                except: pass

            from handlers.documents import offer_document_upload
            await offer_document_upload(query, context, num)
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка записи: {e}")

    elif query.data == "save_client":
        if not spreadsheet_id:
            await query.edit_message_text("⚠️ Таблица не подключена.")
            return
        data = context.user_data.get("pending_client", {})
        if not data:
            await query.edit_message_text("❌ Данные не найдены.")
            return
        try:
            add_client(spreadsheet_id, data)
            log_action(spreadsheet_id, user.id, user.username or "",
                      "add_client", data.get("company_name", ""))
            await query.edit_message_text(
                f"✅ *Контрагент сохранён!*\n🏢 {data.get('company_name','—')}\n🔑 Алиас: {data.get('alias','—')}",
                parse_mode="Markdown"
            )
            context.user_data.pop("pending_client", None)
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {e}")

    elif query.data == "add_client_doc":
        name = context.user_data.get("unknown_counterparty", "контрагент")
        context.user_data["doc_upload_active"] = True
        context.user_data["doc_purpose"] = "extract_client"
        await query.edit_message_text(
            f"📤 *Отправьте документ для {name}*\n\n"
            f"• 📄 Фактура (factura)\n• 📋 Договор\n• 💰 Presupuesto\n\n"
            f"_Данные заполнятся автоматически_",
            parse_mode="Markdown"
        )

    elif query.data == "add_client_manual":
        context.user_data["manual_client_mode"] = True
        name = context.user_data.get("unknown_counterparty", "")
        await query.edit_message_text(
            f"✏️ Напишите данные компании *{name}*:\n\n"
            f"Пример: _Viza Rent S.L., CIF B12345678, Calle Mayor 5 Valencia_",
            parse_mode="Markdown"
        )

    elif query.data == "skip_counterparty":
        await query.edit_message_text("⏩ Контрагент пропущен.")
        context.user_data.pop("unknown_counterparty", None)

    elif query.data == "cancel":
        await query.edit_message_text("❌ Отменено.")
        for key in ["pending_transaction", "pending_client", "awaiting_doc_for",
                    "doc_upload_active", "unknown_counterparty", "manual_client_mode",
                    "pending_audio_path"]:
            context.user_data.pop(key, None)
