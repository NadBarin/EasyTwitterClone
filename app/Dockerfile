FROM python:3.10-slim

WORKDIR /app

COPY models.py /app/api/models.py

COPY shemas.py /app/api/shemas.py

COPY routes.py /app/api/routes.py

COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip

RUN pip install --no-cache-dir -r /app/requirements.txt

