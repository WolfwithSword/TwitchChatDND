from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column
from sqlalchemy import String, Integer, JSON, asc
from sqlalchemy.future import select

from data.base import Base

from sqlalchemy.future import select
from db import async_session

# We don't need to pass the DB object around after it's been initialized by main
# Simply import async_session from it, or objects made from it around

class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    pfp_url: Mapped[str] = mapped_column(String, default="")
    num_sessions: Mapped[int] = mapped_column(Integer, default=0) # increment on end/complete session
    preferred_tts: Mapped[str] = mapped_column(String, default="") # local vs cloud, and what name for tts voice

    data: Mapped[dict] = mapped_column(JSON, default=dict) # We can store arbitrary data in here if we need extra columns and stuff later, just need to be safe with checking
    # elsewise, we will need to setup alembic and migrations with an updater script/function/exe


    def __init__(self, name: str, pfp_url: str = ""):
        self.name: str = name.lower()
        self.pfp_url: str = pfp_url


    def __eq__(self, other):
        return self.name == other.name
    

    def __hash__(self):
        return hash(self.name)


    def __repr__(self):
        return f"Member(name='{self.name}')"


async def create_or_get_member(name: str, pfp_url: str = "") -> Member:
    member = await _upsert_member(name, pfp_url)
    return member

async def _upsert_member(name: str, pfp_url: str, preferred_tts: str = "") -> Member:
    name = name.lower()
    async with async_session() as session:
        async with session.begin():
            query = select(Member).where(Member.name == name)
            result = await session.execute(query)
            member = result.scalars().first()

            if member:
                # Update existing member
                if member.pfp_url != pfp_url:
                    member.pfp_url = pfp_url
                if member.preferred_tts != preferred_tts:
                    member.preferred_tts = preferred_tts
                await session.commit()
                return member
            else:
                # Create new member
                new_member = Member(name=name, pfp_url=pfp_url)
                session.add(new_member)
                return new_member

async def update_tts(member: Member, preferred_tts: str = ""):
    async with async_session() as session:
        async with session.begin():
            member_in_db = await session.get(Member, member.id)
            if member_in_db:
                member_in_db.preferred_tts = preferred_tts
                await session.commit()


async def fetch_member(name: str) -> Member | None:
    name = name.lower()
    async with async_session() as session:
        query = select(Member).where(Member.name == name)
        result = await session.execute(query)
        return result.scalars().first()


async def fetch_paginated_members(page: int, per_page: int=20, 
                                  exclude_names: list[str] = None,
                                  name_filter: str = None) -> list[Member]:
    if not exclude_names:
        exclude_names = []
    
    async with async_session() as session:
        query = select(Member).order_by(asc(Member.name))

        if exclude_names:
            query = query.where(Member.name.notin_([name.lower()] for name in exclude_names))
        
        if name_filter:
            query = query.where(Member.name.like(f"%{name_filter.lower()}%"))
        
        offset = (page -1) * per_page
        query = query.offset(offset).limit(per_page)

        result = await session.execute(query)
        return result.scalars().all()