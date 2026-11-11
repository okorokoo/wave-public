import os

# Must be set before any app imports so pydantic-settings resolves them
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("PASSWORD", "test")
os.environ.setdefault("BEAT_DB_NAME", "test_beat")
os.environ.setdefault("BEAT_DB_HOST", "localhost")
os.environ.setdefault("DB_PORT_INSIDE", "5432")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("RABBITMQ_PORT", "5672")
os.environ.setdefault("RABBITMQ_LOGIN", "guest")
os.environ.setdefault("RABBITMQ_PASSWORD", "guest")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")
