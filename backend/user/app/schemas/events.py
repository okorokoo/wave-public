import uuid

from pydantic import BaseModel


class UserCreatedEvent(BaseModel):
    user_id: uuid.UUID
