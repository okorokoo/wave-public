import os

# Set required env vars before any app imports so pydantic-settings resolves them
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("PASSWORD", "test")
os.environ.setdefault("AUTH_DB_NAME", "test_auth")
os.environ.setdefault("AUTH_DB_HOST", "localhost")
os.environ.setdefault("DB_PORT_INSIDE", "5432")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "30")
os.environ.setdefault("RABBITMQ_PORT", "5672")
os.environ.setdefault("RABBITMQ_PORT_ADMIN", "15672")
os.environ.setdefault("RABBITMQ_LOGIN", "guest")
os.environ.setdefault("RABBITMQ_PASSWORD", "guest")
