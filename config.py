import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
SPREADSHEET_ID = (os.environ.get("SPREADSHEET_ID") or "").strip()
TELEGRAM_BOT_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()

SHEET_TRANSACTIONS = "Транзакции"
SHEET_CLIENTS = "Контрагенты"
SHEET_TEMPLATES_META = "_meta"
SHEET_LOGS = "_logs"

DEFAULT_HEADERS = ["№", "Дата", "Сумма", "Валюта", "Комментарий", "Откуда", "Куда", "Документ", "Проект"]
CLIENT_HEADERS = ["Алиас", "Название компании", "Рег. номер", "VAT", "Адрес", "Руководитель", "Контакты", "Страна", "ЕС"]

import json
_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if _creds_json:
    # ВСЕГДА перезаписываем — иначе старый кэш мешает
    try:
        with open("credentials.json", "w") as f:
            f.write(_creds_json)
    except Exception:
        pass
