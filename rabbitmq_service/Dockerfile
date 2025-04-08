FROM python:3.11-slim

WORKDIR /app

COPY rabbitmq_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lib /app/lib/
RUN pip install -e /app/lib/

COPY rabbitmq_service /app/

CMD ["python", "main.py"] 