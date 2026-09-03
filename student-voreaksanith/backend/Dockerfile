FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# prompts/ must land as a SIBLING of backend/, because prompt_loader.py
# resolves it as <parent of backend>/prompts. Flattening backend into /app
# (COPY backend/ .) breaks this: the loader then looks in /prompts.
COPY backend ./backend
COPY prompts ./prompts

WORKDIR /app/backend

EXPOSE 5005

CMD ["python", "app.py"]
