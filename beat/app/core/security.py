from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel
import uuid
from config import settings

security = HTTPBearer()


class TokenData(BaseModel):
    user_id: uuid.UUID


async def get_current_user_id(auth: HTTPAuthorizationCredentials = Depends(security)) -> uuid.UUID:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось валидировать токен",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = auth.credentials
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")  # В Auth мы обычно кладем ID в 'sub'
        if user_id is None:
            raise credentials_exception
        return uuid.UUID(user_id)
    except (JWTError, ValueError):
        raise credentials_exception
