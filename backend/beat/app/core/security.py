from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel
import uuid
from config import settings

security = HTTPBearer()


class TokenData(BaseModel):
    user_id: uuid.UUID


def _decode_payload(auth: HTTPAuthorizationCredentials) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось валидировать учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(auth.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("sub") is None:
            raise credentials_exception
        return payload
    except (JWTError, ValueError):
        raise credentials_exception


async def get_current_user_id(auth: HTTPAuthorizationCredentials = Depends(security)) -> uuid.UUID:
    payload = _decode_payload(auth)
    return uuid.UUID(payload["sub"])


async def get_current_user_email(auth: HTTPAuthorizationCredentials = Depends(security)) -> str:
    payload = _decode_payload(auth)
    return payload.get("email", "")


async def get_current_user_username(auth: HTTPAuthorizationCredentials = Depends(security)) -> str:
    payload = _decode_payload(auth)
    # Fallback to email prefix for tokens issued before username was added
    username = payload.get("username")
    if username:
        return username
    email = payload.get("email", "")
    return email.split("@")[0]
