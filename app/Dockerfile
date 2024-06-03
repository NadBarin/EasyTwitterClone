FROM python:3.10-slim

WORKDIR /app

COPY /app/models.py /app/api/models.py

COPY /app/shemas.py /app/api/shemas.py

COPY /app/routes.py /app/api/routes.py

COPY /static /app/static

COPY /app/requirements.txt /app/requirements.txt

RUN pip install --upgrade pip

RUN pip install --no-cache-dir -r /app/requirements.txt

