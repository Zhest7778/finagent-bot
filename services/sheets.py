import logging
import gspread
from config import GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID as DEFAULT_SPREADSHEET_ID
from config import SHEET_TRANSACTIONS, SHEET_CLIENTS, DEFAULT_HEADERS, CLIENT_HEADERS

logger = logging.getLogger(__name__)

SHEET_LOG = "_logs"

TRANSACTION_HEADERS = DEFAULT_HEADERS + ["Тип", "Аудио"]
# CLIENT_HEADERS уже импортирован из config


def get_client():
    return gspread.service_account(filename=GOOGLE_CREDENTIALS_FILE)


def _open(spreadsheet_id: str = None):
    return get_client().open_by_key(spreadsheet_id or DEFAULT_SPREADSHEET_ID)


def init_spreadsheet(spreadsheet_id: str = None):
    sid = spreadsheet_id or DEFAULT_SPREADSHEET_ID
    gc = get_client()
    sh = gc.open_by_key(sid)
    existing = [ws.title for ws in sh.worksheets()]
    for name, headers in [
        (SHEET_TRANSACTIONS, TRANSACTION_HEADERS),
        (SHEET_CLIENTS, CLIENT_HEADERS),
        (SHEET_LOG, ["Дата", "Пользователь", "Действие", "Детали"]),
    ]:
        if name not in existing:
            ws = sh.add_worksheet(title=name, rows=1000, cols=len(headers))
            ws.append_row(headers)
            logger.info(f"Created sheet: {name}")
        else:
            ws = sh.worksheet(name)
            if not ws.row_values(1):
                ws.append_row(headers)


def get_all_transactions(spreadsheet_id: str = None) -> list:
    try:
        ws = _open(spreadsheet_id).worksheet(SHEET_TRANSACTIONS)
        return ws.get_all_records(expected_headers=[])
    except Exception as e:
        logger.error(f"get_all_transactions: {e}")
        return []


def add_transaction(spreadsheet_id: str, data: dict) -> int:
    sh = _open(spreadsheet_id)
    ws = sh.worksheet(SHEET_TRANSACTIONS)
    headers = ws.row_values(1)
    if not headers:
        ws.append_row(TRANSACTION_HEADERS)
        headers = TRANSACTION_HEADERS
    records = ws.get_all_records(expected_headers=[])
    num = len(records) + 1
    mapping = {
        "№": num,
        "Дата": data.get("date", ""),
        "Сумма": data.get("amount", ""),
        "Валюта": data.get("currency", "EUR"),
        "Комментарий": data.get("comment", ""),
        "Откуда": data.get("from_party", ""),
        "Куда": data.get("to_party", ""),
        "Документ": "",
        "Проект": data.get("project", ""),
        "Тип": data.get("type", "expense"),
        "Аудио": "",
    }
    row = [mapping.get(h, "") for h in headers]
    ws.append_row(row)
    logger.info(f"add_transaction: #{num}")
    return num


def delete_transaction(spreadsheet_id: str, row_index: int):
    ws = _open(spreadsheet_id).worksheet(SHEET_TRANSACTIONS)
    ws.delete_rows(row_index + 2)


def get_all_clients(spreadsheet_id: str = None) -> list:
    try:
        ws = _open(spreadsheet_id).worksheet(SHEET_CLIENTS)
        return ws.get_all_records(expected_headers=[])
    except Exception as e:
        logger.error(f"get_all_clients: {e}")
        return []


def add_client(spreadsheet_id: str, data: dict):
    sh = _open(spreadsheet_id)
    ws = sh.worksheet(SHEET_CLIENTS)
    headers = ws.row_values(1)
    if not headers:
        ws.append_row(CLIENT_HEADERS)
        headers = CLIENT_HEADERS
    mapping = {
        "Алиас": data.get("alias", ""),
        "Название компании": data.get("company_name", ""),
        "Рег. номер": data.get("reg_number", ""),
        "VAT": data.get("vat", ""),
        "Адрес": data.get("address", ""),
        "Руководитель": data.get("director", ""),
        "Контакты": data.get("contacts", ""),
        "Страна": data.get("country", ""),
        "ЕС": data.get("is_eu", "Да"),
    }
    row = [mapping.get(h, "") for h in headers]
    ws.append_row(row)
    logger.info(f"add_client: {data.get('company_name')}")


def delete_client(spreadsheet_id: str, alias: str) -> bool:
    ws = _open(spreadsheet_id).worksheet(SHEET_CLIENTS)
    records = ws.get_all_records(expected_headers=[])
    for i, r in enumerate(records):
        if r.get("Алиас") == alias or r.get("Название компании") == alias:
            ws.delete_rows(i + 2)
            return True
    return False


def log_action(spreadsheet_id: str, user_id: int, action: str, details: str = ""):
    try:
        from datetime import datetime
        ws = _open(spreadsheet_id).worksheet(SHEET_LOG)
        ws.append_row([datetime.now().strftime("%d.%m.%Y %H:%M"), str(user_id), action, details])
    except Exception as e:
        logger.warning(f"log_action failed: {e}")


def attach_document_to_row(spreadsheet_id: str, transaction_num: int, file_link: str):
    ws = _open(spreadsheet_id).worksheet(SHEET_TRANSACTIONS)
    headers = ws.row_values(1)
    if "Документ" not in headers:
        logger.warning("attach_document_to_row: column Документ not found")
        return
    doc_col = headers.index("Документ") + 1
    all_nums = ws.col_values(1)
    for i, val in enumerate(all_nums):
        if str(val) == str(transaction_num):
            row_num = i + 1
            existing = ws.cell(row_num, doc_col).value or ""
            new_val = (existing + " | " + file_link).strip(" | ") if existing else file_link
            ws.update_cell(row_num, doc_col, new_val)
            return
    logger.warning(f"attach_document_to_row: #{transaction_num} not found")


def attach_audio_to_row(spreadsheet_id: str, transaction_num: int, audio_link: str):
    ws = _open(spreadsheet_id).worksheet(SHEET_TRANSACTIONS)
    headers = ws.row_values(1)
    if "Аудио" not in headers:
        logger.warning("attach_audio_to_row: column Аудио not found")
        return
    audio_col = headers.index("Аудио") + 1
    all_nums = ws.col_values(1)
    for i, val in enumerate(all_nums):
        if str(val) == str(transaction_num):
            ws.update_cell(i + 1, audio_col, audio_link)
            return
    logger.warning(f"attach_audio_to_row: #{transaction_num} not found")
