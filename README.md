# Wave — маркетплейс битов

Платформа для продажи и покупки музыкальных битов. Продюсеры загружают биты, покупатели приобретают лицензии и скачивают треки.

## Стек

| Слой | Технологии |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand, React Query, Radix UI |
| Backend | FastAPI, SQLAlchemy (async), Pydantic v2, Poetry |
| Базы данных | PostgreSQL 17 (по одной на сервис) |
| Очередь | RabbitMQ |
| Хранилище | MinIO (S3-совместимое) |
| Платежи | YooKassa |
| Gateway | Nginx |
| Мониторинг | Prometheus, Loki, Promtail, Grafana |

## Архитектура

```
Browser
  └── Nginx :80
        ├── /          → Frontend SPA
        ├── /auth/*    → auth-service :8000
        ├── /users/*   → user-service :8000
        └── /beats/*   → beat-service :8000

auth-service  ──┐
user-service  ──┼── RabbitMQ (события: user_created, user_deleted)
beat-service  ──┘

beat-service  ── MinIO (аудио, обложки, стемы, войстеги)
user-service  ── MinIO (аватары)

beat-worker   ── фоновая конвертация WAV → MP3
```

**Лицензии:** basic (только MP3) / premium (MP3 + стемы проекта ZIP)

## Быстрый старт

### Требования
- Docker Desktop
- Node.js 20+ (для локальной разработки фронтенда)

### 1. Переменные окружения

Скопируй `.env.example` в `.env` и заполни:

```bash
cp .env.example .env
```

### 2. Запуск

```bash
docker compose up -d --build
```

Первый запуск займёт несколько минут (сборка образов + `poetry lock`).

### 3. Открой в браузере

| Сервис | URL |
|---|---|
| Приложение | http://localhost |
| API документация (auth) | http://localhost/auth/docs |
| API документация (users) | http://localhost/users/docs |
| API документация (beats) | http://localhost/beats/docs |
| Grafana (мониторинг) | http://localhost:4000 — admin / admin |
| Prometheus | http://localhost:9090 |
| MinIO консоль | http://localhost:9001 — minioadmin / minioadminpassword |
| MailHog (email) | http://localhost:8025 |
| RabbitMQ | http://localhost:15672 — guest / guest |

> Swagger доступен только при `DEBUG=true` в `.env`

## Переменные окружения

Все сервисы читают один общий `.env` из корня проекта.

```env
# --- Пользователь БД (общий для всех баз) ---
USER=wave
PASSWORD=your_password

# --- Auth service ---
AUTH_DB_NAME=auth_db
AUTH_DB_HOST=auth-db
AUTH_DB_PORT_OUTSIDE=5433      # порт на хосте для прямого подключения

# --- User service ---
USER_DB_NAME=user_db
USER_DB_HOST=user-db
USER_DB_PORT_OUTSIDE=5434

# --- Beat service ---
BEAT_DB_NAME=beat_db
BEAT_DB_HOST=beat-db
BEAT_DB_PORT_OUTSIDE=5435

# --- Общее ---
DB_PORT_INSIDE=5432             # порт внутри контейнера (не менять)
SECRET_KEY=your_jwt_secret      # минимум 32 символа
DEBUG=false                     # true — включает Swagger UI

# --- RabbitMQ ---
RABBITMQ_PORT=5672
RABBITMQ_PORT_ADMIN=15672
RABBITMQ_LOGIN=guest
RABBITMQ_PASSWORD=guest

# --- YooKassa ---
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret
YOOKASSA_RETURN_URL=http://localhost/payment-result

# --- MinIO / S3 (значения по умолчанию для локальной разработки) ---
S3_ENDPOINT_URL=http://minio:9000
S3_PUBLIC_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadminpassword
S3_BUCKET_NAME=wave-beats
```

## Сервисы

### auth-service
Регистрация, вход, JWT-токены, восстановление пароля по email.  
События в RabbitMQ: `user_created`, `user_deleted`.  
Паттерн outbox — события публикуются надёжно даже при перезапуске.

### user-service
Профили пользователей, подписки (follow/unfollow), аватары.  
Слушает `user_created` (создаёт пустой профиль) и `user_deleted` (удаляет профиль).

### beat-service
Биты, покупки, платежи YooKassa, лайки, счётчики прослушиваний, стемы, войстеги.  
Webhook от YooKassa → статус платежа → создание покупки.

### beat-worker
Конвертация загруженного WAV в MP3 через ffmpeg.  
Читает задачи из RabbitMQ-очереди, результат пишет в MinIO.

## Тесты

```bash
# auth-service
cd backend/auth && python -m pytest tests/ -v

# beat-service
cd backend/beat && python -m pytest tests/ -v

# user-service
cd backend/user && python -m pytest tests/ -v

# frontend (утилиты)
cd frontend && npm run test
```

## Мониторинг

Grafana автоматически загружает дашборд **Wave — Мониторинг** при старте.  
Метрики собирает `prometheus-fastapi-instrumentator` (эндпоинт `/metrics` на каждом сервисе).  
Логи — Promtail через Docker socket → Loki.

Порядок старта: Loki → Promtail → бизнес-сервисы (гарантирует что стартовые логи не теряются).

## Ограничения на загрузку файлов

| Тип | Лимит |
|---|---|
| Аудио (WAV/MP3) | 200 МБ |
| Обложка (JPEG/PNG/WebP) | 5 МБ |
| Аватар | 5 МБ |
| Стемы (ZIP) | 500 МБ |
| Nginx (client_max_body_size) | 100 МБ |
