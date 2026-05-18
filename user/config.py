import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


class Settings(BaseSettings):
    # Настройки базы данных
    USER: str
    PASSWORD: str
    USER_DB_NAME: str
    USER_DB_HOST: str
    DB_PORT_INSIDE: int

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.USER_DB_HOST}:{self.DB_PORT_INSIDE}/{self.USER_DB_NAME}"

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

    # Конфигурация загрузки из .env
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"  # Игнорировать лишние переменные в .env
    )


# Создаем синглтон (один экземпляр на все приложение)
settings = Settings()
