import os

# Must be set before any app imports so pydantic-settings resolves them
os.environ.setdefault("USER", "test")
os.environ.setdefault("PASSWORD", "test")
os.environ.setdefault("USER_DB_NAME", "test_user")
os.environ.setdefault("USER_DB_HOST", "localhost")
os.environ.setdefault("DB_PORT_INSIDE", "5432")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("RABBITMQ_PORT", "5672")
os.environ.setdefault("RABBITMQ_PORT_ADMIN", "15672")
os.environ.setdefault("RABBITMQ_LOGIN", "guest")
os.environ.setdefault("RABBITMQ_PASSWORD", "guest")
