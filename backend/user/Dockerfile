# 1. Выбираем базовый образ. slim-версия Python весит мало и содержит всё нужное.
FROM python:3.12-slim

# 2. Устанавливаем переменные окружения:
# Не создавать .pyc файлы (экономим место)
ENV PYTHONDONTWRITEBYTECODE=1
# Выводить логи сразу в консоль, не буферизируя (важно для Docker)
ENV PYTHONUNBUFFERED=1

# 3. Устанавливаем системные зависимости и Poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    netcat-openbsd \
    && pip install poetry \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. Создаем рабочую директорию внутри контейнера
WORKDIR /user
ENV PYTHONPATH=/user

# 5. КЭШИРОВАНИЕ ЗАВИСИМОСТЕЙ (Самый важный этап!)
# Сначала копируем только файлы с зависимостями.
# Если ты изменишь код, но не добавишь библиотек, Docker пропустит установку pip/poetry.
COPY user/pyproject.toml user/poetry.lock* /user/

# Настраиваем Poetry: не создавать venv внутри контейнера (он там не нужен)
# И устанавливаем зависимости только для user-service
RUN poetry config virtualenvs.create false \
    && poetry lock \
    && poetry install --no-interaction --no-ansi --no-root

# 6. Копируем остальной код сервиса
COPY user/app/ /user/app/
COPY user/config.py /user/config.py

COPY user/alembic.ini /user/alembic.ini
COPY user/migrations/ /user/migrations/

COPY user/entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/user/entrypoint.sh"]