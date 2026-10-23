FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py init_db.py ./

RUN mkdir -p /app/data

EXPOSE 5004

CMD ["sh", "-c", "python init_db.py && exec python app.py"]