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
    AUTH_DB_PORT: int

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.AUTH_DB_HOST}:5432/{self.AUTH_DB_NAME}"

    # Секреты приложения
    SECRET_KEY: str = Field(..., description="Ключ для подписи JWT токенов")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    # Конфигурация загрузки из .env
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"  # Игнорировать лишние переменные в .env
    )


# Создаем синглтон (один экземпляр на все приложение)
settings = Settings()
