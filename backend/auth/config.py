import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


class Settings(BaseSettings):
    """Конфигурация auth-service. Всё читается из переменных окружения (или .env)."""

    # База данных
    DB_USER: str
    PASSWORD: str
    AUTH_DB_NAME: str
    AUTH_DB_HOST: str
    DB_PORT_INSIDE: int = 5432

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.PASSWORD}"
            f"@{self.AUTH_DB_HOST}:{self.DB_PORT_INSIDE}/{self.AUTH_DB_NAME}"
        )

    # JWT
    SECRET_KEY: str = Field(..., description="Ключ для подписи JWT токенов")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # RabbitMQ
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_LOGIN: str
    RABBITMQ_PASSWORD: str

    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.RABBITMQ_LOGIN}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

    DEBUG: bool = False

    # Инвайт-коды (закрытая бета): если список непустой — регистрация только по коду
    INVITE_CODES: str = ""

    @field_validator("INVITE_CODES", mode="before")
    @classmethod
    def _parse_codes(cls, v: object) -> str:
        return str(v) if v is not None else ""

    @property
    def invite_codes_list(self) -> list[str]:
        return [c.strip() for c in self.INVITE_CODES.split(",") if c.strip()]

    # Email
    SMTP_HOST: str = "mailpit"
    SMTP_PORT: int = 1025
    EMAIL_FROM: str = "noreply@wave.local"
    BASE_URL: str = "http://localhost"
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24

    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
