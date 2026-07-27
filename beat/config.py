import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


class Settings(BaseSettings):
    # Настройки базы данных
    USER: str
    PASSWORD: str
    BEAT_DB_NAME: str
    BEAT_DB_HOST: str
    DB_PORT_INSIDE: int

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.BEAT_DB_HOST}:{self.DB_PORT_INSIDE}/{self.BEAT_DB_NAME}"

    DEBUG: bool = False

    # Секреты приложения
    SECRET_KEY: str = Field(..., description="Ключ для подписи JWT токенов")
    ALGORITHM: str = "HS256"

    # Настройки брокера
    RABBITMQ_PORT: int
    RABBITMQ_PORT_ADMIN: int
    RABBITMQ_LOGIN: str
    RABBITMQ_PASSWORD: str

    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.RABBITMQ_LOGIN}:{self.RABBITMQ_PASSWORD}@rabbitmq:{self.RABBITMQ_PORT}/"

    # S3 / MinIO
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadminpassword"
    S3_BUCKET_NAME: str = "wave-beats"
    S3_PRESIGNED_URL_EXPIRE_SECONDS: int = 3600
    S3_DOWNLOAD_URL_EXPIRE_SECONDS: int = 3600
    MAX_AUDIO_UPLOAD_BYTES: int = 104_857_600  # 100 MB

    # Конфигурация загрузки из .env
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"  # Игнорировать лишние переменные в .env
    )


# Создаем синглтон (один экземпляр на все приложение)
settings = Settings()
