from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from jose import JWTError, jwt

EXPIRE_SECONDS = 900  # 15 минут


def create_download_token(beat_id: str, buyer_id: str, file_type: str = "wav") -> str:
    from config import settings

    expire = datetime.now(timezone.utc) + timedelta(seconds=EXPIRE_SECONDS)
    return jwt.encode(
        {
            "type": "download",
            "beat_id": str(beat_id),
            "buyer_id": str(buyer_id),
            "file": file_type,
            "exp": expire,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def verify_download_token(token: str) -> dict:
    from config import settings

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "download":
            raise ValueError("wrong token type")
        return payload
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная или истёкшая ссылка для скачивания",
        )
