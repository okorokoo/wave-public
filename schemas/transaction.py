from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict
from models.payment import TransactionStatus


class TransactionRead(BaseModel):
    id: int
    item_id: int
    total_amount: float
    status: TransactionStatus
    created_at: datetime

    # Ссылка на контракт появится только после оплаты
    license_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
