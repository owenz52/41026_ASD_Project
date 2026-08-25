FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py .
COPY app.py init_db.py ./

RUN python init_db.py

EXPOSE 5004

CMD ["python", "app.py"]
