import os
import tempfile
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from services.drive import upload_file_to_drive
from services.sheets import (
    log_action, add_client, attach_document_to_row, attach_audio_to_row
)

async def offer_document_upload(update_or_query, context: ContextTypes.DEFAULT_TYPE, transaction_num: int):
    context.user_data["awaiting_doc_for"] = transaction_num
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📎 Прикрепить документ", callback_data="upload_doc"),
        InlineKeyboardButton("⏩ Пропустить", callback_data="skip_doc"),
    ]])
    text = (
        f"✅ Запись #{transaction_num} сохранена.\n\n"
        f"📎 Прикрепить документ к записи?\n"
        f"_Фото чека, PDF фактуры, скан договора_"
    )
    if hasattr(update_or_query, "edit_message_text"):
        await update_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await update_or_query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def save_voice_for_transaction(context: ContextTypes.DEFAULT_TYPE, audio_path: str, transaction_num: int, user_id: int):
    """Сохраняет аудио на Drive и прикрепляет к транзакции (только для админа)."""
    try:
        spreadsheet_id = context.bot_data.get("spreadsheet_id") or context.user_data.get("spreadsheet_id")
        if not spreadsheet_id:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_name = f"audio_{transaction_num}_{ts}.ogg"
        result = upload_file_to_drive(
            local_path=audio_path,
            file_name=audio_name,
            folder_name="FinAgent_Audio",
            transaction_num=str(transaction_num)
        )
        attach_audio_to_row(spreadsheet_id, transaction_num, result["view_link"])
        log_action(spreadsheet_id, user_id, "", "save_audio", f"#{transaction_num} → {audio_name}")
    except Exception:
        pass  # Тихая ошибка — не мешаем основному потоку


async def handle_doc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    if query.data not in ("upload_doc", "skip_doc"):
        return False
    await query.answer()
    if query.data == "skip_doc":
        context.user_data.pop("awaiting_doc_for", None)
        await query.edit_message_text("⏩ Документ не прикреплён.")
        return True
    if query.data == "upload_doc":
        num = context.user_data.get("awaiting_doc_for", "—")
        context.user_data["doc_upload_active"] = True
        context.user_data["doc_purpose"] = "attach"
        await query.edit_message_text(
            f"📤 *Отправьте файл для записи #{num}*\n\n"
            f"Можно отправить несколько файлов по очереди.\n"
            f"Когда закончите — /done",
            parse_mode="Markdown"
        )
        return True
    return False


async def handle_incoming_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("doc_upload_active"):
        await update.message.reply_text(
            "📎 Получен файл. Нажмите *📎 Добавить документ* в меню или /attachlast",
            parse_mode="Markdown"
        )
        return

    spreadsheet_id = context.user_data.get("spreadsheet_id")
    transaction_num = context.user_data.get("awaiting_doc_for")
    purpose = context.user_data.get("doc_purpose", "attach")
    user = update.effective_user
    msg = await update.message.reply_text("⏳ Загружаю файл...")

    with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        if update.message.photo:
            photo = update.message.photo[-1]
            file_obj = await context.bot.get_file(photo.file_id)
            suffix = ".jpg"
            original_name = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            mime = "image/jpeg"
        elif update.message.document:
            doc = update.message.document
            file_obj = await context.bot.get_file(doc.file_id)
            original_name = doc.file_name or "document.pdf"
            suffix = os.path.splitext(original_name)[1] or ".pdf"
            mime = doc.mime_type or "application/pdf"
        else:
            await msg.edit_text("❌ Неподдерживаемый тип. Отправьте фото или PDF.")
            return

        os.remove(tmp_path)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp2:
            tmp_path = tmp2.name
        await file_obj.download_to_drive(tmp_path)

        # Извлечение данных контрагента
        if purpose == "extract_client":
            await msg.edit_text("🤖 Извлекаю данные...")
            client_data = await _extract_client_from_file(tmp_path, mime)
            if "error" in client_data:
                await msg.edit_text(f"❌ Не удалось извлечь: {client_data['error']}")
                return
            context.user_data["pending_client"] = client_data
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Сохранить", callback_data="save_client"),
                InlineKeyboardButton("❌ Отменить", callback_data="cancel")
            ]])
            await msg.edit_text(
                f"🏢 *Данные из документа:*\n\n"
                f"• Название: {client_data.get('company_name','—')}\n"
                f"• CIF/NIF: {client_data.get('reg_number','—')}\n"
                f"• VAT: {client_data.get('vat','—')}\n"
                f"• Адрес: {client_data.get('address','—')}\n"
                f"• Контакты: {client_data.get('contacts','—')}\n\nСохранить?",
                parse_mode="Markdown", reply_markup=keyboard
            )
            context.user_data.pop("doc_upload_active", None)
            context.user_data.pop("doc_purpose", None)
            return

        # Загрузка на Drive
        await msg.edit_text("☁️ Загружаю на Google Drive...")
        result = upload_file_to_drive(
            local_path=tmp_path,
            file_name=original_name,
            transaction_num=str(transaction_num) if transaction_num else None
        )

        if spreadsheet_id and transaction_num:
            attach_document_to_row(spreadsheet_id, transaction_num, result["view_link"])
            log_action(spreadsheet_id, user.id, user.username or "",
                      "attach_document", f"#{transaction_num} → {original_name}")

        await msg.edit_text(
            f"✅ *Документ загружен!*\n\n"
            f"📄 {result['name']}\n"
            f"🔗 [Открыть]({result['view_link']})" +
            (f"\n📌 Привязан к записи #{transaction_num}" if transaction_num else "") +
            f"\n\n_Можете отправить ещё файл или нажмите /done_",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        # НЕ сбрасываем doc_upload_active — можно добавить ещё файлы

    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {e}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершает сессию загрузки документов."""
    num = context.user_data.get("awaiting_doc_for")
    for key in ["doc_upload_active", "awaiting_doc_for", "doc_purpose"]:
        context.user_data.pop(key, None)
    if num:
        await update.message.reply_text(f"✅ Документы к записи #{num} сохранены.")
    else:
        await update.message.reply_text("✅ Готово.")


async def _extract_client_from_file(file_path: str, mime: str) -> dict:
    import base64
    from google import genai
    from google.genai import types
    from config import GEMINI_API_KEY
    from services.ai import MODEL, parse_document_for_client
    try:
        with open(file_path, "rb") as f:
            file_b64 = base64.b64encode(f.read()).decode()
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part(inline_data=types.Blob(mime_type=mime, data=file_b64)),
                types.Part(text="Извлеки весь текст из документа. Верни только текст.")
            ]
        )
        return parse_document_for_client(response.text.strip())
    except Exception as e:
        return {"error": str(e)}


async def attach_last_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    spreadsheet_id = context.user_data.get("spreadsheet_id")
    if not spreadsheet_id:
        await update.message.reply_text("⚠️ Таблица не подключена. /settable")
        return
    from services.sheets import get_all_transactions
    records = get_all_transactions(spreadsheet_id)
    if not records:
        await update.message.reply_text("📭 Таблица пуста.")
        return
    last = records[-1]
    last_num = last.get("№", len(records))
    context.user_data["awaiting_doc_for"] = last_num
    context.user_data["doc_upload_active"] = True
    context.user_data["doc_purpose"] = "attach"
    await update.message.reply_text(
        f"📎 *Прикрепление к записи #{last_num}*\n\n"
        f"📅 {last.get('Дата','—')} | {last.get('Сумма','—')} {last.get('Валюта','EUR')}\n"
        f"📝 {last.get('Комментарий','—')}\n\n"
        f"Отправьте фото или PDF. Несколько файлов — по очереди.\nЗавершить: /done",
        parse_mode="Markdown"
    )
