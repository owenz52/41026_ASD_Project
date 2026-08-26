FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY prompts ./prompts

WORKDIR /app/backend

EXPOSE 5003

CMD ["python", "app.py"]
