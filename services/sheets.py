import os
import json
import base64
import logging
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_TRANSACTIONS = "Транзакции"
SHEET_BUDGETS = "Бюджеты"
SHEET_CLIENTS = "Клиенты"
SHEET_LOG = "Лог"

DEFAULT_HEADERS = ["Дата", "Тип", "Сумма", "Категория", "Описание", "Пользователь"]
CLIENT_HEADERS = ["Имя", "User_ID"]
LOG_HEADERS = ["Дата", "User_ID", "Действие", "Детали"]


def get_gspread_client() -> gspread.Client:
    b64 = os.environ.get("GOOGLE_CREDENTIALS_B64", "")
    if b64:
        creds_json = base64.b64decode(b64).decode("utf-8")
        creds_data = json.loads(creds_json)
        logger.info("DEBUG Using GOOGLE_CREDENTIALS_B64")
    else:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
        creds_data = json.loads(creds_json)
        logger.info("DEBUG Using GOOGLE_CREDENTIALS_JSON (fallback)")

    pk = creds_data.get("private_key", "")
    logger.info(f"DEBUG client_email: {creds_data.get('client_email')}")
    logger.info(f"DEBUG private_key length={len(pk)} newlines={pk.count(chr(10))}")

    creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
    return gspread.authorize(creds)


def get_or_create_sheet(spreadsheet_id: str, sheet_name: str, headers: list) -> gspread.Worksheet:
    gc = get_gspread_client()
    logger.info(f"DEBUG opening spreadsheet {spreadsheet_id}")
    sh = gc.open_by_key(spreadsheet_id)
    try:
        worksheet = sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=sheet_name, rows=1000, cols=len(headers))
        worksheet.append_row(headers)
        logger.info(f"Created sheet: {sheet_name}")
    return worksheet


def init_spreadsheet(spreadsheet_id: str):
    get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    get_or_create_sheet(spreadsheet_id, SHEET_BUDGETS, ["Категория", "Лимит", "Период"])
    get_or_create_sheet(spreadsheet_id, SHEET_CLIENTS, CLIENT_HEADERS)
    get_or_create_sheet(spreadsheet_id, SHEET_LOG, LOG_HEADERS)
    logger.info("Spreadsheet initialized successfully")


def append_transaction(spreadsheet_id: str, row: list):
    ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    ws.append_row(row, value_input_option="USER_ENTERED")


def add_transaction(spreadsheet_id: str, data: dict) -> bool:
    """Добавляет транзакцию из словаря в лист Транзакции."""
    try:
        row = [
            data.get("date", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
            data.get("type", ""),
            data.get("amount", ""),
            data.get("category", ""),
            data.get("description", ""),
            str(data.get("user_id", "")),
        ]
        append_transaction(spreadsheet_id, row)
        return True
    except Exception as e:
        logger.error(f"add_transaction error: {e}")
        return False


def get_all_transactions(spreadsheet_id: str) -> list:
    ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    records = ws.get_all_records()
    return records


def add_client(spreadsheet_id: str, name: str, user_id: int = None) -> bool:
    """Добавляет клиента в лист Клиенты (без дублей)."""
    try:
        existing = get_all_clients(spreadsheet_id)
        if name in existing:
            return True  # уже есть
        ws = get_or_create_sheet(spreadsheet_id, SHEET_CLIENTS, CLIENT_HEADERS)
        ws.append_row([name, str(user_id or "")], value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        logger.error(f"add_client error: {e}")
        return False


def get_all_clients(spreadsheet_id: str) -> list:
    """Возвращает список клиентов из листа Клиенты."""
    try:
        ws = get_or_create_sheet(spreadsheet_id, SHEET_CLIENTS, CLIENT_HEADERS)
        records = ws.get_all_records()
        return sorted([r.get("Имя", "") for r in records if r.get("Имя")])
    except Exception as e:
        logger.error(f"get_all_clients error: {e}")
        return []


def log_action(spreadsheet_id: str, user_id: int, action: str, detail: str = "") -> None:
    """Логирует действие в лист Лог."""
    try:
        ws = get_or_create_sheet(spreadsheet_id, SHEET_LOG, LOG_HEADERS)
        ws.append_row(
            [datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), str(user_id), action, detail],
            value_input_option="USER_ENTERED"
        )
    except Exception as e:
        logger.error(f"log_action error: {e}")


def get_budgets(spreadsheet_id: str) -> list:
    ws = get_or_create_sheet(spreadsheet_id, SHEET_BUDGETS, ["Категория", "Лимит", "Период"])
    return ws.get_all_records()


def set_budget(spreadsheet_id: str, category: str, limit: float, period: str = "месяц"):
    ws = get_or_create_sheet(spreadsheet_id, SHEET_BUDGETS, ["Категория", "Лимит", "Период"])
    records = ws.get_all_records()
    for i, rec in enumerate(records, start=2):
        if rec.get("Категория") == category:
            ws.update(f"A{i}:C{i}", [[category, limit, period]])
            return
    ws.append_row([category, limit, period])
