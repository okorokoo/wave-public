FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update && apt-get install -y --no-install-recommends \
        netcat-openbsd \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install "poetry==2.3.3"

WORKDIR /beat
ENV PYTHONPATH=/beat

# Сначала только зависимости — слой кэшируется, пока не меняется lock-файл
COPY beat/pyproject.toml beat/poetry.lock /beat/
RUN poetry install --only main --no-interaction --no-ansi --no-root

COPY beat/app/ /beat/app/
COPY beat/config.py beat/alembic.ini beat/worker.py /beat/
COPY beat/migrations/ /beat/migrations/
COPY beat/assets/ /beat/assets/
COPY beat/entrypoint.sh /beat/entrypoint.sh
RUN chmod +x /beat/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/beat/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
