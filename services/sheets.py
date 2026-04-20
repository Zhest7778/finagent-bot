import gspread
import json
from google.oauth2.service_account import Credentials
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import GOOGLE_CREDENTIALS_FILE, DEFAULT_HEADERS, CLIENT_HEADERS
from config import SHEET_TRANSACTIONS, SHEET_CLIENTS, SHEET_TEMPLATES_META, SHEET_LOGS

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_gspread_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)

def get_or_create_sheet(spreadsheet_id, sheet_name, headers=None):
    gc = get_gspread_client()
    sh = gc.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
        if headers:
            ws.append_row(headers)
    return ws

def init_spreadsheet(spreadsheet_id):
    get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    get_or_create_sheet(spreadsheet_id, SHEET_CLIENTS, CLIENT_HEADERS)
    get_or_create_sheet(spreadsheet_id, SHEET_TEMPLATES_META, ["Шаблон", "Последний номер"])
    get_or_create_sheet(spreadsheet_id, SHEET_LOGS, ["Время", "User ID", "Username", "Действие", "Детали"])

def add_transaction(spreadsheet_id, data):
    ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    all_rows = ws.get_all_values()
    next_num = len(all_rows)
    row = [
        next_num,
        data.get("date", datetime.now().strftime("%d.%m.%Y")),
        data.get("amount", ""),
        data.get("currency", "EUR"),
        data.get("comment", ""),
        data.get("from_party", ""),
        data.get("to_party", ""),
        data.get("document", "")
    ]
    ws.append_row(row)
    return next_num

def add_client(spreadsheet_id, data):
    ws = get_or_create_sheet(spreadsheet_id, SHEET_CLIENTS, CLIENT_HEADERS)
    ws.append_row([
        data.get("alias", ""), data.get("company_name", ""),
        data.get("reg_number", ""), data.get("vat", ""),
        data.get("address", ""), data.get("director", ""),
        data.get("contacts", ""), data.get("country", ""),
        data.get("is_eu", "Нет")
    ])

def delete_client(spreadsheet_id, record_index):
    """Удаляет контрагента. record_index — 0-based индекс в списке записей (без заголовка).
    Строка в таблице = record_index + 2 (1 — заголовок, +1 т.к. gspread 1-based).
    """
    ws = get_or_create_sheet(spreadsheet_id, SHEET_CLIENTS, CLIENT_HEADERS)
    sheet_row = record_index + 2  # строка 1 = заголовок, данные с строки 2
    ws.delete_rows(sheet_row)

def get_all_transactions(spreadsheet_id):
    ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    all_values = ws.get_all_values()
    if not all_values or len(all_values) < 2:
        return []
    headers = all_values[0]
    result = []
    for row in all_values[1:]:
        if not any(row) or row == headers:
            continue
        padded = row + [""] * (len(headers) - len(row))
        result.append(dict(zip(headers, padded)))
    return result

def get_all_clients(spreadsheet_id):
    ws = get_or_create_sheet(spreadsheet_id, SHEET_CLIENTS, CLIENT_HEADERS)
    all_values = ws.get_all_values()
    if not all_values:
        return []
    result = []
    for row in all_values:
        # Пропускаем полностью пустые строки и строку-заголовок если она есть
        if not any(row):
            continue
        if row == CLIENT_HEADERS:
            continue
        padded = row + [""] * max(0, len(CLIENT_HEADERS) - len(row))
        result.append(dict(zip(CLIENT_HEADERS, padded)))
    return result

def attach_document_to_row(spreadsheet_id, row_num, file_link):
    """row_num — номер транзакции (значение в колонке №).
    Ищем строку по значению в колонке А.
    """
    ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    all_rows = ws.get_all_values()
    sheet_row = None
    for i, row in enumerate(all_rows):
        if str(row[0]) == str(row_num):
            sheet_row = i + 1  # 1-based
            break
    if sheet_row is None:
        sheet_row = row_num + 1  # fallback
    cell = ws.cell(sheet_row, 8).value or ""
    new_val = (cell + "\n" + file_link).strip() if cell else file_link
    ws.update_cell(sheet_row, 8, new_val)

def attach_audio_to_row(spreadsheet_id, row_num, audio_link):
    ws = get_or_create_sheet(spreadsheet_id, SHEET_TRANSACTIONS, DEFAULT_HEADERS)
    headers = ws.row_values(1)
    if len(headers) < 9:
        ws.update_cell(1, 9, "Аудио")
    all_rows = ws.get_all_values()
    sheet_row = None
    for i, row in enumerate(all_rows):
        if str(row[0]) == str(row_num):
            sheet_row = i + 1
            break
    if sheet_row is None:
        sheet_row = row_num + 1
    ws.update_cell(sheet_row, 9, audio_link)

def log_action(spreadsheet_id, user_id, username, action, details=""):
    try:
        ws = get_or_create_sheet(spreadsheet_id, SHEET_LOGS)
        ws.append_row([
            datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            str(user_id), username, action, details
        ])
    except Exception:
        pass

def search_transactions(spreadsheet_id, query):
    records = get_all_transactions(spreadsheet_id)
    q = query.lower()
    return [r for r in records if any(q in str(v).lower() for v in r.values())]

def search_clients(spreadsheet_id, query):
    records = get_all_clients(spreadsheet_id)
    q = query.lower()
    return [r for r in records if any(q in str(v).lower() for v in r.values())]
