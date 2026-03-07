FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Migrar BD (añade columnas nuevas + upsert datos) y arrancar servidor
CMD python migrate_from_excel.py && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
