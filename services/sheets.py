import os
import json
import base64
import logging
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_TRANSACTIONS = "Транзакции"
SHEET_BUDGETS = "Бюджеты"
DEFAULT_HEADERS = ["Дата", "Тип", "Сумма", "Категория", "Описание", "Пользователь"]


def get_gspread_client() -> gspread.Client:
    b64 = os.environ.get("GOOGLE_CREDENTIALS_B64", "")
    if b64:
        creds_json = base64.b64decode(b64).decode("utf-8")
        creds_data = json.loads(creds_json)
        logger.info("DEBUG Using GOOGLE_CREDENTIALS_B64")
    else:
        # fallback на старую переменную
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
    logger.info("Spreadsheet initialized successfully")


def append_transaction(spreadsheet_id: str, row: list):
    ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    ws.append_row(row, value_input_option="USER_ENTERED")


def get_all_transactions(spreadsheet_id: str) -> list:
    ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    records = ws.get_all_records()
    return records


def get_budgets(spreadsheet_id: str) -> list:
    ws = get_or_create_sheet(spreadsheet_id, SHEET_BUDGETS, ["Категория", "Лимит", "Период"])
    return ws.get_all_records()
    
def get_all_clients(spreadsheet_id: str) -> list:
    """Возвращает список уникальных клиентов из транзакций."""
    transactions = get_all_transactions(spreadsheet_id)
    clients = list({t.get("client", "") for t in transactions if t.get("client")})
    return sorted(clients)


def set_budget(spreadsheet_id: str, category: str, limit: float, period: str = "месяц"):
    ws = get_or_create_sheet(spreadsheet_id, SHEET_BUDGETS, ["Категория", "Лимит", "Период"])
    records = ws.get_all_records()
    for i, rec in enumerate(records, start=2):
        if rec.get("Категория") == category:
            ws.update(f"A{i}:C{i}", [[category, limit, period]])
            return
    ws.append_row([category, limit, period])
