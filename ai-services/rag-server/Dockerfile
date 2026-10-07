FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py corpus.py retrieval.py ./
COPY prompts ./prompts
COPY documents ./documents

EXPOSE 5200

CMD ["python", "app.py"]
