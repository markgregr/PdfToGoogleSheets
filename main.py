import os
import re
import tempfile
import PyPDF2
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from starlette.templating import Jinja2Templates
from googleapiclient.discovery import build
from google.oauth2 import service_account  

# Функция извлечения текста из PDF
def extract_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
    return text

# Функция извлечения данных из текста
def extract_data_from_text(text):
    pattern = r'(\d{3}-\d{3}-\d{3})\s+.*?net:\s*(\d+)\s+gr.*?(\d+)\s+(PAC|PC)\s+(\d+,\d+)\s+EUR/(PAC|PC)\s+(\d+,\d+)'
    matches = re.finditer(pattern, text, re.DOTALL)
    extracted_data = []
    for match in matches:
        number, net_value, count, pac_or_pc, price, wallet, total_price = match.groups()
        extracted_data.append({
            'Number': number,
            'Net': net_value,
            'Count': count,
            'PAC or PC': pac_or_pc,
            'Price': price,
            'Price Type': f'EUR/{wallet}',
            'Total Price': total_price
        })
    return extracted_data

def check_empty(sheet_values):
    # Проверяем, содержит ли первая строка только пустые значения
    first_row = sheet_values[0] if sheet_values else []
    return all(cell == '' for cell in first_row)

# Функция загрузки данных в Google Таблицы
def upload_to_google_sheets(data, credentials_path, sheet_id, sheet_name):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = None
    if os.path.exists(credentials_path):
        creds = service_account.Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    else:
        print("The credentials file does not exist.")
        return
    
    service = build('sheets', 'v4', credentials=creds)
    spreadsheet_id = sheet_id
    range_name = sheet_name  # Указываем имя листа
    
    # Получаем существующие данные из листа
    sheet_values = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute().get('values', [])
    
    # Проверяем, есть ли уже данные в листе
    if check_empty(sheet_values):
        # Если первая строка пуста, вставляем заголовки
        values = [
            ['Number', 'Net', 'Count', 'PAC or PC', 'Price', 'Price Type', 'Total Price']
        ]
    else:
        # Иначе добавляем новые данные ниже существующих строк
        values = []
        
    for item in data:
        values.append([
            item['Number'], item['Net'], item['Count'],
            item['PAC or PC'], item['Price'], item['Price Type'],
            item['Total Price']
        ])
    
    body = {
        'values': values
    }
    
    try:
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, 
            range=range_name,
            valueInputOption='RAW', 
            body=body,
            insertDataOption='INSERT_ROWS',  # Вставлять новые строки
        ).execute()
        print("Data uploaded successfully.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


app = FastAPI()

# Создаем экземпляр класса Jinja2Templates и указываем путь к папке с шаблонами
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", context={"request": request})

@app.post("/uploadfile/")
async def upload_file(file: UploadFile = File(...), sheet_id: str = "", sheet_name: str = ""):
    try:
        # Создаем временный файл для сохранения загруженного PDF
        with tempfile.NamedTemporaryFile(delete=False) as temp_pdf:
            temp_pdf.write(await file.read())
            temp_pdf_path = temp_pdf.name
        # Извлекаем текст из PDF
        text = extract_text_from_pdf(temp_pdf_path)
        # Извлекаем данные из текста
        extracted_data = extract_data_from_text(text)
        # Загружаем данные в Google Таблицы, указывая идентификатор и имя листа
        upload_to_google_sheets(extracted_data, "/app/credentionals.json", sheet_id=sheet_id, sheet_name=sheet_name)
        return JSONResponse(status_code=200, content={"message": "Data uploaded successfully"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"An error occurred: {str(e)}"})
