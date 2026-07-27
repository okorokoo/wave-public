import uuid
from typing import Optional, Sequence, List

from sqlalchemy import select, and_, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Beat, Purchase, BeatTag


def _normalize_tags(tags: List[str]) -> List[str]:
    seen = set()
    result = []
    for t in tags:
        t = t.strip().lower()
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


class BeatRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, beat_data: dict) -> Beat:
        """Сохранение нового бита в базу данных"""
        tags = beat_data.pop("tags", [])
        new_beat = Beat(**beat_data)
        self.db.add(new_beat)
        await self.db.flush()
        for tag in _normalize_tags(tags):
            self.db.add(BeatTag(beat_id=new_beat.id, tag=tag))
        await self.db.commit()
        await self.db.refresh(new_beat)
        return new_beat

    async def update(self, beat: Beat, update_data: dict) -> Beat:
        """Динамическое обновление полей бита"""
        tags = update_data.pop("tags", None)
        for key, value in update_data.items():
            setattr(beat, key, value)

        if tags is not None:
            await self.db.execute(delete(BeatTag).where(BeatTag.beat_id == beat.id))
            for tag in _normalize_tags(tags):
                self.db.add(BeatTag(beat_id=beat.id, tag=tag))

        self.db.add(beat)
        await self.db.commit()
        await self.db.refresh(beat)
        return beat

    async def get_by_id(self, beat_id: uuid.UUID) -> Optional[Beat]:
        """Поиск конкретного бита по его ID"""
        query = select(Beat).where(Beat.id == beat_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    def _build_filters(
            self,
            search: Optional[str],
            genre: Optional[str],
            instrument: Optional[str],
            min_bpm: Optional[int],
            max_bpm: Optional[int],
            tag: Optional[str] = None,
    ) -> list:
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
        if tag:
            filters.append(Beat.id.in_(
                select(BeatTag.beat_id).where(BeatTag.tag == tag.strip().lower())
            ))
        return filters

    async def count_beats(
            self,
            search: Optional[str] = None,
            genre: Optional[str] = None,
            instrument: Optional[str] = None,
            min_bpm: Optional[int] = None,
            max_bpm: Optional[int] = None,
            tag: Optional[str] = None,
    ) -> int:
        filters = self._build_filters(search, genre, instrument, min_bpm, max_bpm, tag=tag)
        query = select(func.count()).select_from(Beat)
        if filters:
            query = query.where(and_(*filters))
        result = await self.db.execute(query)
        return result.scalar_one()

    async def list_beats(
            self,
            search: Optional[str] = None,
            genre: Optional[str] = None,
            instrument: Optional[str] = None,
            min_bpm: Optional[int] = None,
            max_bpm: Optional[int] = None,
            tag: Optional[str] = None,
            limit: int = 20,
            offset: int = 0,
    ) -> Sequence[Beat]:
        filters = self._build_filters(search, genre, instrument, min_bpm, max_bpm, tag=tag)
        query = select(Beat)
        if filters:
            query = query.where(and_(*filters))
        query = query.order_by(Beat.id.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count_by_author(self, author_id: uuid.UUID) -> int:
        query = select(func.count()).select_from(Beat).where(Beat.author_id == author_id)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def list_by_author(self, author_id: uuid.UUID, limit: int = 20, offset: int = 0):
        query = (
            select(Beat, func.count(Purchase.id).label("sales_count"))
            .outerjoin(Purchase, Purchase.beat_id == Beat.id)
            .where(Beat.author_id == author_id)
            .group_by(Beat.id)
            .order_by(Beat.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)
        return result.all()

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

    async def get_by_buyer(self, buyer_id: uuid.UUID):
        query = (
            select(Purchase, Beat)
            .join(Beat, Purchase.beat_id == Beat.id)
            .where(Purchase.buyer_id == buyer_id)
            .order_by(Purchase.purchased_at.desc())
        )
        result = await self.db.execute(query)
        return result.all()
