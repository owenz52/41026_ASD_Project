FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# prompts/ is copied as a sibling of backend/, matching how ai_mode.py
# resolves prompt files at runtime.
COPY backend ./backend
COPY prompts ./prompts

WORKDIR /app/backend

EXPOSE 5007

CMD ["python", "app.py"]
