import os
import mimetypes
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import GOOGLE_CREDENTIALS_FILE

SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]

def get_drive_service():
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

def get_or_create_folder(folder_name, parent_id=None):
    service = get_drive_service()
    query = f"name=\'{folder_name}\' and mimeType=\'application/vnd.google-apps.folder\' and trashed=false"
    if parent_id:
        query += f" and \'{parent_id}\' in parents"
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]

def upload_file_to_drive(local_path, file_name, folder_name="FinAgent_Docs", transaction_num=None):
    service = get_drive_service()
    root_id = get_or_create_folder("FinAgent_Docs")
    parent_id = get_or_create_folder(f"Транзакция_{transaction_num}", root_id) if transaction_num else root_id
    mime_type, _ = mimetypes.guess_type(local_path)
    if not mime_type:
        mime_type = "application/octet-stream"
    meta = {"name": file_name, "parents": [parent_id]}
    media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
    uploaded = service.files().create(body=meta, media_body=media, fields="id,webViewLink,name").execute()
    service.permissions().create(fileId=uploaded["id"], body={"type":"anyone","role":"reader"}).execute()
    return {"file_id": uploaded["id"], "name": uploaded["name"], "view_link": uploaded.get("webViewLink","")}

def attach_doc_to_transaction(spreadsheet_id, row_num, file_link):
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build as gbuild
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
    sheets = gbuild("sheets", "v4", credentials=creds)
    range_name = f"Транзакции!H{row_num + 1}"
    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption="RAW", body={"values": [[file_link]]}
    ).execute()
