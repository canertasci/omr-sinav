FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY omr_app/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY omr_app/backend/ .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
