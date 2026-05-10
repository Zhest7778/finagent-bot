import os
import base64
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
SPREADSHEET_ID = (os.environ.get("SPREADSHEET_ID") or "").strip()

SHEET_TRANSACTIONS = "Транзакции"
SHEET_CLIENTS = "Контрагенты"
SHEET_TEMPLATES_META = "_meta"
SHEET_LOGS = "_logs"

DEFAULT_HEADERS = ["№", "Дата", "Сумма", "Валюта", "Комментарий", "Откуда", "Куда", "Документ", "Проект"]
CLIENT_HEADERS = ["Алиас", "Название компании", "Рег. номер", "VAT", "Адрес", "Руководитель", "Контакты", "Страна", "ЕС"]

# --- Google Credentials ---
_creds_b64 = (os.getenv("GOOGLE_CREDENTIALS_B64") or "").strip()
_creds_json = (os.getenv("GOOGLE_CREDENTIALS_JSON") or "").strip()

if _creds_b64:
    try:
        decoded = base64.b64decode(_creds_b64).decode("utf-8")
        with open("credentials.json", "w") as f:
            f.write(decoded)
        print(f"DEBUG: credentials.json written from B64 (len={len(decoded)})", flush=True)
    except Exception as e:
        print(f"ERROR writing credentials from B64: {e}", flush=True)
elif _creds_json:
    try:
        with open("credentials.json", "w") as f:
            f.write(_creds_json)
        print(f"DEBUG: credentials.json written from JSON (len={len(_creds_json)})", flush=True)
    except Exception as e:
        print(f"ERROR writing credentials from JSON: {e}", flush=True)
else:
    print("ERROR: No Google credentials found (B64 and JSON both empty)!", flush=True)
