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

DEFAULT_HEADERS = ["Дата", "Тип", "Сумма", "Валюта", "От", "Кому", "Комментарий", "Проект", "Пользователь", "Документ", "Аудио"]
CLIENT_HEADERS = ["Алиас", "Название компании", "Рег.номер", "VAT", "Адрес", "Руководитель", "Контакты", "Страна", "ЕС"]
LOG_HEADERS = ["Дата", "User_ID", "Действие", "Детали"]

b64 = os.environ.get("GOOGLE_CREDENTIALS_B64", "")
print(f"[DEBUG] B64 length: {len(b64)}")
print(f"[DEBUG] B64 first 20 chars: {repr(b64[:20])}")
print(f"[DEBUG] B64 has newlines: {chr(10) in b64}")


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
    sh = gc.open_by_key(spreadsheet_id)
    try:
        worksheet = sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=sheet_name, rows=1000, cols=max(len(headers), 10))
        worksheet.append_row(headers)
        logger.info(f"Created sheet: {sheet_name}")
    return worksheet


def init_spreadsheet(spreadsheet_id: str):
    get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    get_or_create_sheet(spreadsheet_id, SHEET_BUDGETS, ["Категория", "Лимит", "Период"])
    get_or_create_sheet(spreadsheet_id, SHEET_CLIENTS, CLIENT_HEADERS)
    get_or_create_sheet(spreadsheet_id, SHEET_LOG, LOG_HEADERS)
    logger.info("Spreadsheet initialized successfully")


# ─── Транзакции ───────────────────────────────────────────────────────────────

def add_transaction(spreadsheet_id: str, data: dict) -> int:
    """Добавляет транзакцию и возвращает номер строки (1-based, включая заголовок)."""
    try:
        ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
        row = [
            data.get("date", datetime.utcnow().strftime("%d.%m.%Y")),
            data.get("type", ""),
            data.get("amount", ""),
            data.get("currency", "EUR"),
            data.get("from_party", ""),
            data.get("to_party", ""),
            data.get("comment", ""),
            data.get("project", ""),
            str(data.get("user_id", "")),
            data.get("document", ""),
            data.get("audio", ""),
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
        # Возвращаем номер добавленной строки
        row_num = len(ws.col_values(1))
        logger.info(f"add_transaction: row={row_num}")
        return row_num
    except Exception as e:
        logger.error(f"add_transaction error: {e}")
        return 0


def get_all_transactions(spreadsheet_id: str) -> list:
    ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    return ws.get_all_records()


def _find_last_row(spreadsheet_id: str) -> int:
    ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    values = ws.col_values(1)
    return len(values)


def attach_document_to_row(spreadsheet_id: str, row_index: int, file_url: str) -> bool:
    try:
        ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
        # Колонка "Документ" — 10-я
        ws.update_cell(row_index, 10, file_url)
        logger.info(f"attach_document_to_row: row={row_index} url={file_url}")
        return True
    except Exception as e:
        logger.error(f"attach_document_to_row error: {e}")
        return False


def attach_audio_to_row(spreadsheet_id: str, row_index: int, file_url: str) -> bool:
    try:
        ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
        # Колонка "Аудио" — 11-я
        ws.update_cell(row_index, 11, file_url)
        logger.info(f"attach_audio_to_row: row={row_index} url={file_url}")
        return True
    except Exception as e:
        logger.error(f"attach_audio_to_row error: {e}")
        return False


# ─── Клиенты ──────────────────────────────────────────────────────────────────

def add_client(spreadsheet_id: str, data: dict) -> bool:
    """Добавляет контрагента из словаря в лист Клиенты."""
    try:
        ws = get_or_create_sheet(spreadsheet_id, SHEET_CLIENTS, CLIENT_HEADERS)
        existing = ws.col_values(2)  # Колонка "Название компании"
        name = data.get("company_name", "")
        if name and name in existing:
            return True
        row = [
            data.get("alias", ""),
            data.get("company_name", ""),
            data.get("reg_number", ""),
            data.get("vat", ""),
            data.get("address", ""),
            data.get("director", ""),
            data.get("contacts", ""),
            data.get("country", ""),
            data.get("is_eu", ""),
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        logger.error(f"add_client error: {e}")
        return False


def get_all_clients(spreadsheet_id: str) -> list:
    """Возвращает список словарей контрагентов из листа Клиенты."""
    try:
        ws = get_or_create_sheet(spreadsheet_id, SHEET_CLIENTS, CLIENT_HEADERS)
        return ws.get_all_records()
    except Exception as e:
        logger.error(f"get_all_clients error: {e}")
        return []


def delete_client(spreadsheet_id: str, client_idx: int) -> bool:
    """Удаляет строку клиента по индексу (0-based) из листа Клиенты."""
    try:
        ws = get_or_create_sheet(spreadsheet_id, SHEET_CLIENTS, CLIENT_HEADERS)
        ws.delete_rows(client_idx + 2)
        return True
    except Exception as e:
        logger.error(f"delete_client error: {e}")
        return False


# ─── Лог ──────────────────────────────────────────────────────────────────────

def log_action(spreadsheet_id: str, user_id: int, action: str, detail: str = "") -> None:
    try:
        ws = get_or_create_sheet(spreadsheet_id, SHEET_LOG, LOG_HEADERS)
        ws.append_row(
            [datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), str(user_id), action, detail],
            value_input_option="USER_ENTERED"
        )
    except Exception as e:
        logger.error(f"log_action error: {e}")


# ─── Бюджеты ──────────────────────────────────────────────────────────────────

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
