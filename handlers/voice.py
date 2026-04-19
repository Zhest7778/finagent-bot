import os
import shutil
import tempfile
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from services.ai import transcribe_voice, parse_transaction, parse_client, analyze_report_query, smart_reply
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

    # Сохраняем копию аудио для последующей привязки к транзакции
    audio_backup_path = tmp_path + "_backup.ogg"

    try:
        tg_file = await context.bot.get_file(voice.file_id)
        await tg_file.download_to_drive(tmp_path)
        shutil.copy2(tmp_path, audio_backup_path)

        await msg.edit_text("🤖 Обрабатываю...")
        text = transcribe_voice(tmp_path)
        if not text or text.startswith("Ошибка"):
            await msg.edit_text(f"❌ {text}\nПопробуйте написать текстом.")
            return

        context.user_data["last_text"] = text
        context.user_data["pending_audio_path"] = audio_backup_path
        await msg.edit_text(f"📝 Распознано: _{text}_", parse_mode="Markdown")
        await process_text_command(update, context, text)

    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")
        try: os.remove(audio_backup_path)
        except: pass
    finally:
        try: os.remove(tmp_path)
        except: pass


async def process_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = None):
    if text is None:
        text = update.message.text
    spreadsheet_id = context.user_data.get("spreadsheet_id")
    lower = text.lower()

    is_transaction = any(w in lower for w in [
        "запиши", "плат", "получил", "заплатил", "перевод", "расход", "доход",
        "registro", "pago", "cobro", "transferencia", "factura", "gasto"
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
        reply = smart_reply(text)
        await update.message.reply_text(reply)
        # Если не транзакция — удаляем сохранённое аудио
        try:
            audio_path = context.user_data.pop("pending_audio_path", None)
            if audio_path:
                os.remove(audio_path)
        except: pass
