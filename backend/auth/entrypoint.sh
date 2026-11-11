#!/bin/sh
set -e

echo "Waiting for PostgreSQL at ${AUTH_DB_HOST}:${DB_PORT_INSIDE:-5432}..."
while ! nc -z "${AUTH_DB_HOST}" "${DB_PORT_INSIDE:-5432}"; do
  sleep 0.5
done

echo "Running migrations..."
alembic upgrade head

echo "Starting: $*"
exec "$@"
