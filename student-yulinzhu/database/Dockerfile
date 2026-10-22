FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py init_db.py start.py ./
ENV DATA_DIR=/app/data

EXPOSE 5002

CMD ["python", "start.py"]