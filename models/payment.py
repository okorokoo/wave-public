import enum
from typing import Optional
from datetime import datetime
from sqlalchemy import String, ForeignKey, Float, Enum, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.item import Item
from models.user import User


class TransactionStatus(enum.Enum):
    PENDING = "pending"  # Ожидание оплаты
    COMPLETED = "completed"  # Успешно проведено
    FAILED = "failed"  # Ошибка оплаты
    REFUNDED = "refunded"  # Возврат средств


class LicenseType(enum.Enum):
    NON_EXCLUSIVE = "non_exclusive"  # Аренда (можно продать много раз)
    EXCLUSIVE = "exclusive"  # Полный выкуп (продается один раз)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Кто, кому и за что
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"), index=True)

    # Финансовые детали
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)  # Полная цена
    platform_fee: Mapped[float] = mapped_column(Float, nullable=False)  # Твоя комиссия
    seller_revenue: Mapped[float] = mapped_column(Float, nullable=False)  # Чистый доход автора

    # Статус и внешние ID
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus), default=TransactionStatus.PENDING
    )
    stripe_session_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Связи
    buyer: Mapped[User] = relationship(foreign_keys=[buyer_id])
    seller: Mapped[User] = relationship(foreign_keys=[seller_id])
    item: Mapped[Item] = relationship()
    license: Mapped["License"] = relationship(back_populates="transaction", uselist=False)

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, amount={self.total_amount}, status={self.status})>"


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), unique=True
    )

    # Тип лицензии на момент покупки (чтобы не изменился, если автор поменяет условия позже)
    license_type: Mapped[LicenseType] = mapped_column(Enum(LicenseType), nullable=False)

    # Ссылка на сгенерированный PDF в S3
    s3_contract_key: Mapped[str] = mapped_column(String(500), nullable=False)

    # Снапшот юридических данных (важно для истории)
    buyer_legal_name: Mapped[str] = mapped_column(String(255))  # ФИО покупателя
    seller_legal_name: Mapped[str] = mapped_column(String(255))  # ФИО/Псевдоним продавца

    # Условия лицензии (текст контракта в момент покупки)
    terms_snapshot: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Связь обратно к транзакции
    transaction: Mapped["Transaction"] = relationship(back_populates="license")

    def __repr__(self) -> str:
        return f"<License(id={self.id}, type={self.license_type})>"
