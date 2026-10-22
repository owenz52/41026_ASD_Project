FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY init_db.py .

RUN mkdir -p /app/data

EXPOSE 5003

CMD ["sh", "-c", "python init_db.py && exec python app.py"]