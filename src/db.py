from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = "sqlite+aiosqlite:///tcdnd_data.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

from custom_logger.logger import logger 
import logging
from data.base import Base


debug_mode = os.environ['TCDND_DEBUG_MODE'] == '1'
logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG if debug_mode else logging.INFO)
logging.getLogger("sqlalchemy.engine").handlers = logger.handlers

async def initialize_database():
    #Initialize the database and create tables.#
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
