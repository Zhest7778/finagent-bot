import os
import json
import base64
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.5-flash"
DEFAULT_COMPANY = "SVOY SPETS SL"

def transcribe_voice(audio_path: str) -> str:
    try:
        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part(inline_data=types.Blob(mime_type="audio/ogg", data=audio_b64)),
                types.Part(text="Транскрибируй это аудио дословно. Верни только текст.")
            ]
        )
        return response.text.strip()
    except Exception as e:
        return f"Ошибка транскрипции: {e}"

def parse_transaction(text: str) -> dict:
    from datetime import datetime
    today = datetime.now().strftime("%d.%m.%Y")
    prompt = (
        "Разбери финансовую команду и верни JSON.\n\n"
        "Правила:\n"
        "- Если дата не указана — используй " + today + "\n"
        "- Если не указан отправитель — используй " + DEFAULT_COMPANY + "\n"
        "- currency по умолчанию: EUR\n"
        "- type: expense если мы платим, income если получаем\n\n"
        'Формат: {"date":"дд.мм.гггг","amount":0,"currency":"EUR","from_party":"","to_party":"","comment":"","type":"expense","missing_fields":[]}\n\n'
        "Только JSON без markdown.\n\nКоманда: " + text
    )
    try:
        raw = client.models.generate_content(model=MODEL, contents=prompt).text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        data = json.loads(raw.strip())
        if not data.get("date"): data["date"] = today
        if not data.get("from_party"): data["from_party"] = DEFAULT_COMPANY
        mf = data.get("missing_fields", [])
        if "date" in mf: mf.remove("date")
        data["missing_fields"] = mf
        return data
    except Exception as e:
        return {"error": str(e)}

def parse_client(text: str) -> dict:
    prompt = (
        "Разбери данные о компании и верни JSON:\n"
        '{"alias":"","company_name":"","reg_number":"","vat":"","address":"","director":"","contacts":"","country":"","is_eu":"Да"}\n'
        "Только JSON без markdown.\nТекст: " + text
    )
    try:
        raw = client.models.generate_content(model=MODEL, contents=prompt).text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        return {"error": str(e)}

def parse_document_for_client(text: str) -> dict:
    prompt = (
        "Из текста документа извлеки данные компании-контрагента:\n"
        '{"alias":"","company_name":"","reg_number":"","vat":"","address":"","director":"","contacts":"","country":"Spain","is_eu":"Да"}\n'
        "Только JSON без markdown.\nДокумент: " + text
    )
    try:
        raw = client.models.generate_content(model=MODEL, contents=prompt).text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        return {"error": str(e)}

def analyze_report_query(question: str, transactions: list) -> str:
    sample = transactions[-200:] if len(transactions) > 200 else transactions
    prompt = (
        "Ты финансовый аналитик " + DEFAULT_COMPANY + ".\n"
        "Данные: " + json.dumps(sample, ensure_ascii=False) + "\n\n"
        "Вопрос: " + question + "\n\nОтветь кратко на русском с эмодзи."
    )
    try:
        return client.models.generate_content(model=MODEL, contents=prompt).text.strip()
    except Exception as e:
        return "Ошибка анализа: " + str(e)

def smart_reply(text: str) -> str:
    prompt = (
        "Ты финансовый ассистент " + DEFAULT_COMPANY + " (Испания).\n"
        "Пользователь: " + text + "\nОтветь кратко на русском."
    )
    try:
        return client.models.generate_content(model=MODEL, contents=prompt).text.strip()
    except Exception as e:
        return "Ошибка: " + str(e)
