from typing import List, Tuple
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, and_, asc, CheckConstraint
from sqlalchemy.future import select

from data.base import Base

from db import async_session

from custom_logger.logger import logger
from helpers.constants import TTS_SOURCE


class Voice(Base):
    __tablename__ = "voices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    # Unique? May need to request them to rename voice?
    uid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String, default=TTS_SOURCE.SOURCE_LOCAL.value, nullable=False)

    __table_args__ = (
        CheckConstraint(
            f"source IN ({', '.join(repr(value) for value in [source.value for source in TTS_SOURCE])})",
            name="chk_source_valid_val",
        ),
    )

    def __init__(self, name: str, uid: str, source: TTS_SOURCE):
        self.name: str = name
        self.uid: str = uid
        if isinstance(source, str):
            self.source = source
        elif isinstance(source, TTS_SOURCE):
            self.source: str = source.value

    def __eq__(self, other):
        return self.name == other.name and self.uid == other.uid and self.source == other.source

    def __hash__(self):
        return hash(f"{self.name}{self.uid}{self.source}")

    def __repr__(self):
        return f"Voice(name='{self.name}', uid='{self.uid}', source='{self.source}')"

    def __lt__(self, other):
        return self.name < other.name

    def __gt__(self, other):
        return self.name > other.name


async def _upsert_voice(name: str, uid: str, source: TTS_SOURCE) -> Voice | None:
    async with async_session() as session:
        async with session.begin():
            query = select(Voice).where(and_(Voice.name == name, Voice.uid == uid, Voice.source == source.value))
            result = await session.execute(query)
            voice = result.scalars().first()

            if voice:
                return voice
            else:
                # Create new voice
                new_voice = Voice(name=name, uid=uid, source=source.value)
                session.add(new_voice)
                return new_voice


async def bulk_insert_voices(values: List[Tuple[str, str]], source: TTS_SOURCE):
    async with async_session() as session:
        async with session.begin():
            session.add_all([Voice(name=v[0], uid=v[1], source=source.value) for v in values])


async def get_all_voice_ids(source: TTS_SOURCE) -> list:
    async with async_session() as session:
        query = select(Voice.uid)
        if source:
            query = query.where(Voice.source == source.value)
        result = await session.execute(query)
        return result.scalars().all()


async def delete_voice(uid: str | list = None, source: TTS_SOURCE = None) -> bool:
    if not uid:
        return False
    async with async_session() as session:
        if isinstance(uid, str):
            voice = await fetch_voice(uid=uid, source=source)
            if voice:
                await session.delete(voice)
                await session.commit()
                return True
        elif isinstance(uid, list):
            query = select(Voice).where(Voice.uid.in_(uid))
            result = await session.execute(query)
            voices = result.scalars().all()
            for voice in voices:
                await session.delete(voice)
            await session.commit()
            return True
        return False


async def fetch_voice(name: str = None, uid: str = None, source: TTS_SOURCE = None) -> Voice | None:
    if not any([name, uid]):
        return None
    async with async_session() as session:
        query = select(Voice)
        if uid:
            query = query.where(Voice.uid == uid)
        if name:
            query = query.where(Voice.name == name)
        if source:
            query = query.where(Voice.source == source.value)
        result = await session.execute(query)
        return result.scalars().first()


async def fetch_voices(source: TTS_SOURCE = None, limit: int = 100) -> list[Voice]:

    async with async_session() as session:
        query = select(Voice)
        if source:
            query = query.where(Voice.source == source.value)
        query = query.limit(limit)
        result = await session.execute(query)
        res = result.scalars().all()
        if not res and source == TTS_SOURCE.SOURCE_11L.value:
            logger.info("Adding default ElevenLabs voice 'Will'")
            v = await _upsert_voice(name="Will", uid="bIHbv24MWmeRgasZH58o", source=TTS_SOURCE.SOURCE_11L.value)
            return [v]
        return res


# fmt: off
async def fetch_paginated_voices(page: int, per_page: int = 20, name_filter: str = None,
                                 filter_source: TTS_SOURCE = None) -> list[Voice]:
# fmt: on
    if not exclude_names:
        exclude_names = []

    async with async_session() as session:
        query = select(Voice).order_by(asc(Voice.name))

        if name_filter:
            query = query.where(Voice.name.like(f"%{name_filter.lower()}%"))

        if filter_source:
            query = query.where(Voice.source == filter_source.value)

        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        result = await session.execute(query)
        return result.scalars().all()
