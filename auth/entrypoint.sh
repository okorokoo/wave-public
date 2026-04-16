#!/bin/sh

# Ждем, пока база станет доступна (используем nc - netcat)
echo "Waiting for postgres..."
while ! nc -z $AUTH_DB_HOST $DB_PORT_INSIDE; do
  sleep 0.1
done
echo "PostgreSQL started"

# Прогоняем миграции до последней версии
echo "Running migrations..."
alembic upgrade head

# Запускаем основное приложение
echo "Starting app..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000