from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///tcdnd_data.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

from custom_logger.logger import logger 
import logging
from data.base import Base

logging.getLogger("sqlalchemy.engine").handlers = logger.handlers
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

async def initialize_database():
    #Initialize the database and create tables.#
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
