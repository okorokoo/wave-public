import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from config import settings

security = HTTPBearer()

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось валидировать учетные данные",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user_id(
    auth: HTTPAuthorizationCredentials = Depends(security),
) -> uuid.UUID:
    try:
        payload = jwt.decode(
            auth.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise CREDENTIALS_EXCEPTION
        return uuid.UUID(user_id)
    except (JWTError, ValueError):
        raise CREDENTIALS_EXCEPTION
