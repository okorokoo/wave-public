FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update && apt-get install -y --no-install-recommends \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && pip install "poetry==2.3.3"

WORKDIR /auth
ENV PYTHONPATH=/auth

# Сначала только зависимости — слой кэшируется, пока не меняется lock-файл
COPY auth/pyproject.toml auth/poetry.lock /auth/
RUN poetry install --only main --no-interaction --no-ansi --no-root

COPY auth/app/ /auth/app/
COPY auth/schemas/ /auth/schemas/
COPY auth/config.py auth/alembic.ini /auth/
COPY auth/migrations/ /auth/migrations/
COPY auth/entrypoint.sh /auth/entrypoint.sh
RUN chmod +x /auth/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/auth/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
