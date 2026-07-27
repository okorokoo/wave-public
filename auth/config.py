import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


class Settings(BaseSettings):
    # Настройки базы данных
    USER: str
    PASSWORD: str
    AUTH_DB_NAME: str
    AUTH_DB_HOST: str
    DB_PORT_INSIDE: int

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.AUTH_DB_HOST}:{self.DB_PORT_INSIDE}/{self.AUTH_DB_NAME}"

    # Секреты приложения
    SECRET_KEY: str = Field(..., description="Ключ для подписи JWT токенов")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    # Настройки брокера
    RABBITMQ_PORT: int
    RABBITMQ_PORT_ADMIN: int
    RABBITMQ_LOGIN: str
    RABBITMQ_PASSWORD: str

    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.RABBITMQ_LOGIN}:{self.RABBITMQ_PASSWORD}@rabbitmq:{self.RABBITMQ_PORT}/"

    DEBUG: bool = False

    # Настройки email
    SMTP_HOST: str = "mailhog"
    SMTP_PORT: int = 1025
    EMAIL_FROM: str = "noreply@wave.local"
    BASE_URL: str = "http://localhost/auth"
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24

    # Конфигурация загрузки из .env
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"  # Игнорировать лишние переменные в .env
    )


# Создаем синглтон (один экземпляр на все приложение)
settings = Settings()
