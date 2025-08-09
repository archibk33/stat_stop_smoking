# syntax=docker/dockerfile:1
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Установим зависимости
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Копируем исходники
COPY . .

# По умолчанию запускаем бота
CMD ["python", "main.py"]
