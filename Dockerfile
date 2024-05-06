FROM python:3.12.1-alpine

RUN pip install --upgrade pip

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host","0.0.0.0", "--port", "8000", "--reload"]