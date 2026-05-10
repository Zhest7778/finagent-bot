import os
import logging
import json
import base64
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")


def get_client():
    b64 = os.environ.get("GOOGLE_CREDENTIALS_B64", "")
    if b64:
        logger.info("DEBUG Using GOOGLE_CREDENTIALS_B64")
        creds_json = base64.b64decode(b64).decode("utf-8")
        creds_dict = json.loads(creds_json)
    else:
        raw = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
        creds_dict = json.loads(raw)

    logger.info(f"DEBUG client_email: {creds_dict.get('client_email')}")
    pk = creds_dict.get("private_key", "")
    logger.info(f"DEBUG private_key length={len(pk)} newlines={pk.count(chr(10))}")

    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet(sheet_name: str):
    gc = get_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        return sh.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=sheet_name, rows=1000, cols=20)


# ── Транзакции ────────────────────────────────────────────────────────────────

def get_all_transactions():
    ws = get_sheet("Transactions")
    try:
        return ws.get_all_records(expected_headers=[])
    except Exception as e:
        logger.error(f"get_all_transactions error: {e}")
        return []


def add_transaction(row: dict):
    ws = get_sheet("Transactions")
    headers = ws.row_values(1)
    if not headers:
        headers = ["Дата", "Сумма", "Контрагент", "Проект", "Категория", "Описание", "Тип", "Файл"]
        ws.append_row(headers)
    values = [row.get(h, "") for h in headers]
    ws.append_row(values)


def delete_transaction(row_index: int):
    """Удаляет транзакцию по индексу (0-based, без учёта заголовка)."""
    ws = get_sheet("Transactions")
    ws.delete_rows(row_index + 2)  # +1 header, +1 1-based


# ── Клиенты / Контрагенты ─────────────────────────────────────────────────────

def get_all_clients():
    ws = get_sheet("Clients")
    try:
        return ws.get_all_records(expected_headers=[])
    except Exception as e:
        logger.error(f"get_all_clients error: {e}")
        return []


def add_client(row: dict):
    ws = get_sheet("Clients")
    headers = ws.row_values(1)
    if not headers:
        headers = ["Алиас", "Название", "Реквизиты"]
        ws.append_row(headers)
    values = [row.get(h, "") for h in headers]
    ws.append_row(values)


def delete_client(alias: str) -> bool:
    """Удаляет клиента по алиасу. Возвращает True если найден и удалён."""
    ws = get_sheet("Clients")
    try:
        records = ws.get_all_records(expected_headers=[])
    except Exception:
        records = []
    for i, rec in enumerate(records):
        if str(rec.get("Алиас", "")).lower() == alias.lower():
            ws.delete_rows(i + 2)  # +1 header, +1 1-based
            return True
    return False


# ── Лог действий ─────────────────────────────────────────────────────────────

def log_action(user_id: int, action: str, details: str = ""):
    """Записывает действие пользователя в лист Log."""
    ws = get_sheet("Log")
    from datetime import datetime
    ws.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        str(user_id),
        action,
        details,
    ])
