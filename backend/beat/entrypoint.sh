#!/bin/sh

# Ждем, пока база станет доступна (используем nc - netcat)
echo "Waiting for postgres..."
while ! nc -z $BEAT_DB_HOST $DB_PORT_INSIDE; do
  sleep 0.1
done
echo "PostgreSQL started"

# Прогоняем миграции до последней версии
echo "Running migrations..."
alembic upgrade head

# Запускаем переданную команду (или дефолтную из CMD)
echo "Starting app..."
exec "$@"