# 1. Выбираем базовый образ. slim-версия Python весит мало и содержит всё нужное.
FROM python:3.12-slim

# 2. Устанавливаем переменные окружения:
# Не создавать .pyc файлы (экономим место)
ENV PYTHONDONTWRITEBYTECODE=1
# Выводить логи сразу в консоль, не буферизируя (важно для Docker)
ENV PYTHONUNBUFFERED=1

# 3. Устанавливаем системные зависимости и Poetry
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && pip install poetry \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 4. Создаем рабочую директорию внутри контейнера
WORKDIR /auth
ENV PYTHONPATH=/auth

# 5. КЭШИРОВАНИЕ ЗАВИСИМОСТЕЙ (Самый важный этап!)
# Сначала копируем только файлы с зависимостями.
# Если ты изменишь код, но не добавишь библиотек, Docker пропустит установку pip/poetry.
COPY auth/pyproject.toml auth/poetry.lock* /auth/

# Настраиваем Poetry: не создавать venv внутри контейнера (он там не нужен)
# И устанавливаем зависимости только для auth-service
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# 6. Копируем остальной код сервиса
COPY auth/app/ /auth/app/
COPY common/ /auth/common/
COPY auth/config.py /auth/common/config.py

# 7. Команда для запуска. Используем uvicorn.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]