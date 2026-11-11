FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update && apt-get install -y --no-install-recommends \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && pip install "poetry==2.3.3"

WORKDIR /user
ENV PYTHONPATH=/user

# Сначала только зависимости — слой кэшируется, пока не меняется lock-файл
COPY user/pyproject.toml user/poetry.lock /user/
RUN poetry install --only main --no-interaction --no-ansi --no-root

COPY user/app/ /user/app/
COPY user/config.py user/alembic.ini /user/
COPY user/migrations/ /user/migrations/
COPY user/entrypoint.sh /user/entrypoint.sh
RUN chmod +x /user/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/user/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
