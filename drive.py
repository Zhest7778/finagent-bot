# drive.py — Google Drive ОТКЛЮЧЁН
# Документы сохраняются как Telegram file links напрямую в таблицу.
# Этот файл оставлен для совместимости импортов.

def upload_file_to_drive(local_path, file_name, folder_name="FinAgent_Docs", transaction_num=None):
    raise NotImplementedError(
        "Google Drive загрузка отключена. "
        "Используйте Telegram file_path напрямую через handle_incoming_file."
    )
