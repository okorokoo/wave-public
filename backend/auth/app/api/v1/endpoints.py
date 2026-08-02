import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.database import get_db
from app.core.email import send_verification_email
from app.core.security import hash_password, create_refresh_token
from app.core.security import verify_password, create_access_token
from app.models.models import User, RefreshToken, EmailVerification, OutboxEvent
from schemas.schemas import UserAuthRead, UserRegister, RefreshRequest, ResendVerificationRequest, ChangePasswordRequest
from config import settings

router = APIRouter(prefix="/v1")

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
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

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
    query = select(User).where(User.email == user_in.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует"
        )

    new_user = User(
        email=user_in.email,
        username=user_in.username,
        hashed_password=hash_password(user_in.password)
    )

    verification_token = str(uuid.uuid4())

    db.add(new_user)
    try:
        await db.flush()

        verification = EmailVerification(
            token=verification_token,
            user_id=new_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS),
        )
        outbox_event = OutboxEvent(
            event_type="user_created",
            routing_key="user_created",
            payload={"user_id": str(new_user.id), "username": user_in.username},
        )
        db.add(verification)
        db.add(outbox_event)
        await db.commit()
        await db.refresh(new_user)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Ошибка при сохранении в базу")

    try:
        await send_verification_email(new_user.email, verification_token)
    except Exception as e:
        logger.warning("Failed to send verification email: %s", e)

    return new_user


@router.post("/login")
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.email == form_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт деактивирован",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Подтвердите email перед входом",
        )

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email, "username": user.username})
    refresh_token_str = create_refresh_token(data={"sub": str(user.id)})

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
    try:
        payload = jwt.decode(data.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Неверный тип токена")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Токен просрочен или неверен")

    query = select(RefreshToken).where(RefreshToken.token == data.refresh_token)
    result = await db.execute(query)
    db_token = result.scalar_one_or_none()

    if not db_token or db_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh токен недействителен")

    user = await db.get(User, db_token.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Аккаунт недоступен")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Подтвердите email перед входом")

    await db.delete(db_token)

    new_access = create_access_token(data={"sub": user_id})
    new_refresh = create_refresh_token(data={"sub": user_id})

    new_refresh_token = RefreshToken(
        token=new_refresh,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_refresh_token)
    await db.commit()

    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    query = select(RefreshToken).where(RefreshToken.token == data.refresh_token)
    result = await db.execute(query)
    db_token = result.scalar_one_or_none()

    if db_token:
        await db.delete(db_token)
        await db.commit()

    return None


@router.get("/me", response_model=UserAuthRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
        token: str = Query(...),
        db: AsyncSession = Depends(get_db)
):
    query = select(EmailVerification).where(EmailVerification.token == token)
    result = await db.execute(query)
    verification = result.scalar_one_or_none()

    if not verification:
        raise HTTPException(status_code=400, detail="Неверный токен")

    if verification.used_at is not None:
        raise HTTPException(status_code=400, detail="Токен уже использован")

    if verification.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Токен просрочен")

    verification.used_at = datetime.now(timezone.utc)

    user = await db.get(User, verification.user_id)
    user.is_verified = True

    await db.commit()

    return {"message": "Email успешно подтверждён"}


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
        data: ChangePasswordRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный текущий пароль")

    current_user.hashed_password = hash_password(data.new_password)
    db.add(current_user)
    await db.commit()
    return None


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
        data: ResendVerificationRequest,
        db: AsyncSession = Depends(get_db)
):
    generic_response = {"message": "Если аккаунт существует и не подтверждён, письмо отправлено"}

    query = select(User).where(User.email == data.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or user.is_verified:
        return generic_response

    query = select(EmailVerification).where(
        EmailVerification.user_id == user.id,
        EmailVerification.used_at == None  # noqa: E711
    )
    result = await db.execute(query)
    for old_token in result.scalars().all():
        old_token.used_at = datetime.now(timezone.utc)

    verification_token = str(uuid.uuid4())
    verification = EmailVerification(
        token=verification_token,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS)
    )
    db.add(verification)
    await db.commit()

    try:
        await send_verification_email(user.email, verification_token)
    except Exception as e:
        logger.warning("Failed to send verification email: %s", e)

    return generic_response
