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

# Названия листов (кириллица — как в таблице)
SHEET_TRANSACTIONS = "Транзакции"
SHEET_CLIENTS      = "Клиенты"
SHEET_LOG          = "Лог"


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
        logger.info(f"Created sheet: {sheet_name}")
        return sh.add_worksheet(title=sheet_name, rows=1000, cols=20)


def init_spreadsheet(spreadsheet_id: str = None):
    """Инициализирует все нужные листы в таблице."""
    gc = get_client()
    sid = spreadsheet_id or SPREADSHEET_ID
    sh = gc.open_by_key(sid)
    existing = [ws.title for ws in sh.worksheets()]
    for name in [SHEET_TRANSACTIONS, SHEET_CLIENTS, SHEET_LOG]:
        if name not in existing:
            sh.add_worksheet(title=name, rows=1000, cols=20)
            logger.info(f"Spreadsheet initialized: created sheet {name}")
    logger.info("Spreadsheet initialized successfully")


# ── Транзакции ────────────────────────────────────────────────────────────────

def get_all_transactions():
    ws = get_sheet(SHEET_TRANSACTIONS)
    try:
        return ws.get_all_records(expected_headers=[])
    except Exception as e:
        logger.error(f"get_all_transactions error: {e}")
        return []


def add_transaction(row: dict):
    ws = get_sheet(SHEET_TRANSACTIONS)
    headers = ws.row_values(1)
    if not headers:
        headers = ["Дата", "Тип", "Сумма", "Валюта", "От", "Кому", "Комментарий", "Проект", "Пользователь", "Документ", "Аудио"]
        ws.append_row(headers)
        logger.info("add_transaction: wrote headers")
    row_num = len(ws.get_all_values()) + 1
    values = [row.get(h, "") for h in headers]
    ws.append_row(values)
    logger.info(f"add_transaction: row={row_num}")


def delete_transaction(row_index: int):
    """Удаляет транзакцию по индексу (0-based, без учёта заголовка)."""
    ws = get_sheet(SHEET_TRANSACTIONS)
    ws.delete_rows(row_index + 2)  # +1 header, +1 1-based


# ── Клиенты / Контрагенты ─────────────────────────────────────────────────────

def get_all_clients():
    ws = get_sheet(SHEET_CLIENTS)
    try:
        return ws.get_all_records(expected_headers=[])
    except Exception as e:
        logger.error(f"get_all_clients error: {e}")
        return []


def add_client(row: dict):
    ws = get_sheet(SHEET_CLIENTS)
    headers = ws.row_values(1)
    if not headers:
        headers = ["Имя", "User_ID", "Алиас", "Адрес", "Страна", "Активен"]
        ws.append_row(headers)
    values = [row.get(h, "") for h in headers]
    ws.append_row(values)


def delete_client(alias: str) -> bool:
    """Удаляет клиента по алиасу. Возвращает True если найден и удалён."""
    ws = get_sheet(SHEET_CLIENTS)
    try:
        records = ws.get_all_records(expected_headers=[])
    except Exception:
        records = []
    for i, rec in enumerate(records):
        if str(rec.get("Алиас", "") or rec.get("Имя", "")).lower() == alias.lower():
            ws.delete_rows(i + 2)  # +1 header, +1 1-based
            return True
    return False


# ── Лог действий ─────────────────────────────────────────────────────────────

def log_action(user_id: int, action: str, details: str = ""):
    """Записывает действие пользователя в лист Лог."""
    ws = get_sheet(SHEET_LOG)
    from datetime import datetime
    ws.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        str(user_id),
        action,
        details,
    ])
