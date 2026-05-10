import os
import tempfile
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from services.ai import transcribe_voice, parse_transaction, parse_client, analyze_report_query, smart_reply, extract_project
from services.sheets import get_all_transactions
from handlers.transaction import confirm_transaction_keyboard

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        await update.message.reply_text("❌ Не удалось получить аудиофайл.")
        return
    msg = await update.message.reply_text("🎧 Распознаю речь...")

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        tg_file = await context.bot.get_file(voice.file_id)
        await tg_file.download_to_drive(tmp_path)

        context.user_data["pending_audio_file_id"] = voice.file_id

        await msg.edit_text("🤖 Обрабатываю...")
        text = transcribe_voice(tmp_path)
        if not text or text.startswith("Ошибка"):
            await msg.edit_text(f"❌ {text}\nПопробуйте написать текстом.")
            return

        context.user_data["last_text"] = text
        await msg.edit_text(f"📝 Распознано: _{text}_", parse_mode="Markdown")
        await process_text_command(update, context, text)

    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


async def process_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = None):
    if text is None:
        text = update.message.text
    spreadsheet_id = context.user_data.get("spreadsheet_id")

    # ── Ручной ввод контрагента ──────────────────────────────────────
    if context.user_data.get("manual_client_mode"):
        context.user_data.pop("manual_client_mode", None)
        data = parse_client(text)
        if "error" in data:
            await update.message.reply_text("❌ Не удалось разобрать данные компании. Попробуйте ещё раз.")
            return
        context.user_data["pending_client"] = data
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Сохранить", callback_data="save_client"),
            InlineKeyboardButton("❌ Отменить", callback_data="cancel")
        ]])
        await update.message.reply_text(
            f"🏢 *Новый контрагент:*\n"
            f"• Алиас: {data.get('alias','—')}\n"
            f"• Название: {data.get('company_name','—')}\n"
            f"• VAT: {data.get('vat','—')}\n"
            f"• Страна: {data.get('country','—')}\n\nСохранить?",
            parse_mode="Markdown", reply_markup=keyboard
        )
        return
    # ────────────────────────────────────────────────────────────────

    lower = text.lower()

    is_transaction = any(w in lower for w in [
        "запиши", "плат", "получил", "заплатил", "перевод", "расход", "доход",
        "занял", "одолжил", "долг", "займ", "заём", "выдал", "взял в долг",
        "дал в долг", "дал мне", "я дал", "я занял",
        "registro", "pago", "cobro", "transferencia", "factura", "gasto",
        "prestamo", "préstamo", "deuda",
    ])
    is_client = any(w in lower for w in [
        "добавь контрагента", "новая компания", "добавь компанию",
        "nueva empresa", "agregar empresa"
    ])
    is_report = any(w in lower for w in [
        "отчёт", "отчет", "сколько", "покажи", "анализ", "итого",
        "informe", "total", "reporte"
    ])

    if is_transaction:
        data = parse_transaction(text)
        if "error" in data:
            await update.message.reply_text("❌ Не удалось разобрать команду. Напишите подробнее.")
            return
        data["project"] = data.get("project") or extract_project(text)
        context.user_data["pending_transaction"] = data
        await confirm_transaction_keyboard(update, context, data)

    elif is_client:
        data = parse_client(text)
        if "error" in data:
            await update.message.reply_text("❌ Не удалось разобрать данные компании.")
            return
        context.user_data["pending_client"] = data
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Сохранить", callback_data="save_client"),
            InlineKeyboardButton("❌ Отменить", callback_data="cancel")
        ]])
        await update.message.reply_text(
            f"🏢 *Новый контрагент:*\n"
            f"• Алиас: {data.get('alias','—')}\n"
            f"• Название: {data.get('company_name','—')}\n"
            f"• VAT: {data.get('vat','—')}\n"
            f"• Страна: {data.get('country','—')}\n\nСохранить?",
            parse_mode="Markdown", reply_markup=keyboard
        )

    elif is_report:
        if not spreadsheet_id:
            await update.message.reply_text("⚠️ Укажите ID таблицы: /settable")
            return
        msg = await update.message.reply_text("📊 Анализирую данные...")
        transactions = get_all_transactions(spreadsheet_id)
        if not transactions:
            await msg.edit_text("📭 Таблица пуста.")
            return
        result = analyze_report_query(text, transactions)
        await msg.edit_text(f"📈 *Отчёт:*\n\n{result}", parse_mode="Markdown")

    else:
        context.user_data.pop("pending_audio_file_id", None)
        reply = smart_reply(text)
        await update.message.reply_text(reply)
