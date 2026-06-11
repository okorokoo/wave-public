import uuid
from typing import Optional, Sequence

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Beat, Purchase


class BeatRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, beat_data: dict) -> Beat:
        """Сохранение нового бита в базу данных"""
        new_beat = Beat(**beat_data)
        self.db.add(new_beat)
        await self.db.commit()
        await self.db.refresh(new_beat)
        return new_beat

    async def update(self, beat: Beat, update_data: dict) -> Beat:
        """Динамическое обновление полей бита"""
        for key, value in update_data.items():
            setattr(beat, key, value)

        self.db.add(beat)
        await self.db.commit()
        await self.db.refresh(beat)
        return beat

    async def get_by_id(self, beat_id: uuid.UUID) -> Optional[Beat]:
        """Поиск конкретного бита по его ID"""
        query = select(Beat).where(Beat.id == beat_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_beats(
            self,
            search: Optional[str] = None,
            genre: Optional[str] = None,
            instrument: Optional[str] = None,
            min_bpm: Optional[int] = None,
            max_bpm: Optional[int] = None
    ) -> Sequence[Beat]:
        query = select(Beat)
        filters = []

        if search:
            filters.append(Beat.title.ilike(f"%{search}%"))
        if genre:
            filters.append(Beat.genre == genre)
        if instrument:
            filters.append(Beat.primary_instrument == instrument)
        if min_bpm:
            filters.append(Beat.bpm >= min_bpm)
        if max_bpm:
            filters.append(Beat.bpm <= max_bpm)

        if filters:
            query = query.where(and_(*filters))

        query = query.order_by(Beat.id.desc())

        result = await self.db.execute(query)
        return result.scalars().all()

    async def delete(self, beat: Beat) -> None:
        """Удаление бита из базы"""
        await self.db.delete(beat)
        await self.db.commit()


class PurchaseRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, beat_id: uuid.UUID, buyer_id: uuid.UUID, license_type: str = "basic") -> Purchase:
        purchase = Purchase(beat_id=beat_id, buyer_id=buyer_id, license_type=license_type)
        self.db.add(purchase)
        await self.db.commit()
        await self.db.refresh(purchase)
        return purchase

    async def get_by_beat_and_buyer(self, beat_id: uuid.UUID, buyer_id: uuid.UUID) -> Optional[Purchase]:
        query = select(Purchase).where(
            and_(Purchase.beat_id == beat_id, Purchase.buyer_id == buyer_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
