from uuid import UUID

from pydantic import BaseModel


class TokenPayload(BaseModel):
    """Данные, зашитые внутри токена (Payload)"""
    sub: str = None  # Здесь будет лежать UUID пользователя в формате строки
    exp: int = None  # Время истечения
    type: str


class UserVerifyResponse(BaseModel):
    """Схема ответа для других микросервисов при проверке токена"""
    user_id: UUID
    is_active: bool
    is_superuser: bool
