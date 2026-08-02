from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime


# Данные для создания пользователя
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Пароль минимум 8 символов")
    username: str = Field(..., min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_]+$', description="Псевдоним: латиница, цифры, подчёркивание")


# То, что мы отдаем после успешной регистрации
class UserAuthRead(BaseModel):
    id: UUID
    email: EmailStr
    username: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Структура JWT токена, которую получит клиент после логина
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, description="Новый пароль минимум 8 символов")
