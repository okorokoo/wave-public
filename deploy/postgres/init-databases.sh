#!/bin/sh
# Создаёт по отдельной базе на каждый сервис (database-per-service).
# Выполняется Postgres один раз — при первой инициализации пустого тома.
set -e

for db in $(echo "$POSTGRES_MULTIPLE_DATABASES" | tr "," " "); do
  echo "Creating database: $db"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE \"$db\";"
done
