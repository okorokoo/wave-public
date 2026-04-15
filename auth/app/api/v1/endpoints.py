from datetime import datetime, timezone, timedelta

from common.config import settings
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.security import hash_password, create_refresh_token
from app.core.security import verify_password, create_access_token
from app.models import User, RefreshToken
from app.schemas import UserAuthRead, UserRegister, RefreshRequest
from common.database import get_db

router = APIRouter(prefix="/v1")

# Указываем FastAPI, где искать токен.
# tokenUrl должен совпадать с путем к твоему эндпоинту логина.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/login")


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось валидировать учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # 1. Декодируем токен
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 2. Ищем пользователя в базе
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


@router.post("/register", response_model=UserAuthRead, status_code=status.HTTP_201_CREATED)
async def register_user(
        user_in: UserRegister,
        db: AsyncSession = Depends(get_db)
):
    # 1. Проверяем, не занят ли email
    query = select(User).where(User.email == user_in.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует"
        )

    # 2. Создаем объект пользователя
    new_user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password)
    )

    # 3. Сохраняем в базу
    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка при сохранении в базу")

    return new_user


@router.post("/login")
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_db)
):
    # 1. Ищем юзера по email (в OAuth2PasswordRequestForm email лежит в поле username)
    query = select(User).where(User.email == form_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    # 2. Проверяем существование и пароль
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Генерируем токен
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token_str = create_refresh_token(data={"sub": str(user.id)})

    # Сохраняем refresh_token в БД
    new_refresh_token = RefreshToken(
        token=refresh_token_str,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_refresh_token)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "bearer"
    }


@router.post("/refresh")
async def refresh_token_endpoint(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    # 1. Декодируем и проверяем тип токена
    try:
        payload = jwt.decode(data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Неверный тип токена")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Токен просрочен или неверен")

    # 2. Ищем токен в БД (проверка на отзыв)
    query = select(RefreshToken).where(RefreshToken.token == data.refresh_token)
    result = await db.execute(query)
    db_token = result.scalar_one_or_none()

    if not db_token or db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh токен недействителен")

    # 3. Удаляем старый токен (Rotation policy) и создаем новые
    await db.delete(db_token)

    new_access = create_access_token(data={"sub": user_id})
    new_refresh = create_refresh_token(data={"sub": user_id})

    new_refresh_token = RefreshToken(
        token=new_refresh,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    await db.delete(db_token)
    db.add(new_refresh_token)
    await db.commit()

    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
        data: RefreshRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Удаляет refresh-токен из базы данных, завершая сессию.
    """
    # 1. Ищем токен в базе
    query = select(RefreshToken).where(RefreshToken.token == data.refresh_token)
    result = await db.execute(query)
    db_token = result.scalar_one_or_none()

    # 2. Если нашли — удаляем
    if db_token:
        await db.delete(db_token)
        await db.commit()

    # Мы возвращаем 204 No Content, даже если токена не было (идемпотентность)
    return None


@router.get("/me", response_model=UserAuthRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
