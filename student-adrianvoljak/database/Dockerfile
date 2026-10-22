FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 5008

CMD ["sh", "-c", "python init_db.py && exec python app.py"]