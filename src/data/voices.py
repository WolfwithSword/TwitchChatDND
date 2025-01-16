from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column
from sqlalchemy import String, Integer, asc, CheckConstraint
from sqlalchemy.future import select

from data.base import Base

from sqlalchemy.future import select
from db import async_session

from custom_logger.logger import logger 
from helpers.constants import SOURCES, SOURCE_11L, SOURCE_LOCAL

class Voice(Base):
    __tablename__ = "voices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False) # Unique? May need to request them to rename voice?
    uid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String, default=SOURCE_LOCAL, nullable=False)

    __table_args__ = (
        CheckConstraint(
            f"source IN ({', '.join(repr(value) for value in SOURCES)})",
            name="chk_source_valid_val"
        ),
    )

    def __init__(self, name: str, uid: str, source: str):
        if source not in SOURCES:
            return None
        self.name: str = name
        self.uid: str = uid
        self.source: str = source

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


async def _upsert_voice(name: str, uid: str, source: str) -> Voice | None:
    if source not in SOURCES:
        return None
    async with async_session() as session:
        async with session.begin():
            query = select(Voice).where(Voice.name == name).where(Voice.uid == uid).where(Voice.source == source)
            result = await session.execute(query)
            voice = result.scalars().first()

            if voice:
                return voice
            else:
                # Create new voice
                new_voice = Voice(name=name, uid=uid, source=source)
                session.add(new_voice)
                return new_voice


async def delete_voice(uid: str = None, source: str = None) -> bool:
    if not uid:
        return False
    async with async_session() as session:
        voice = await fetch_voice(uid=uid, source=source)
        if voice:
            await session.delete(voice)
            await session.commit()
            return True
        return False


async def fetch_voice(name: str = None, uid: str = None, source: str = None) -> Voice | None:
    if not any([name, uid]):
        return None
    async with async_session() as session:
        query = select(Voice)
        if uid:
            query = query.where(Voice.uid == uid)
        if name:
            query = query.where(Voice.name == name)
        if source:
            query = query.where(Voice.source == source)
        result = await session.execute(query)
        return result.scalars().first()


async def fetch_voices(source: str = None, limit: int = 100) -> list[Voice]:

    async with async_session() as session:
        query = select(Voice)
        if source:
            query = query.where(Voice.source == source)
        query = query.limit(limit)
        result = await session.execute(query)
        res =  result.scalars().all()
        if not res and source == 'elevenlabs':
            logger.info("Adding default ElevenLabs voice 'Will'")
            v = await _upsert_voice(name="Will", uid="bIHbv24MWmeRgasZH58o", source=SOURCE_11L)
            return [v]
        return res


async def fetch_paginated_voices(page: int, per_page: int=20, 
                                 name_filter: str = None, filter_source: str = None) -> list[Voice]:
    if not exclude_names:
        exclude_names = []
    
    async with async_session() as session:
        query = select(Voice).order_by(asc(Voice.name))

        if name_filter:
            query = query.where(Voice.name.like(f"%{name_filter.lower()}%"))
        
        if filter_source:
            query = query.where(Voice.source == source)
        
        offset = (page -1) * per_page
        query = query.offset(offset).limit(per_page)

        result = await session.execute(query)
        return result.scalars().all()
