FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python init_db.py && python seed_october.py

EXPOSE 5006

CMD ["python", "app.py"]
