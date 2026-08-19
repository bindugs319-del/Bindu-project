"""
Database connection and session management
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    future=True,
    pool_size=10,
    max_overflow=20,
    # pool_pre_ping=True was disabled: on this SQLAlchemy/asyncpg combo it can
    # trigger "MissingGreenlet: greenlet_spawn has not been called" during
    # the pool's connection health-check ping, which happens outside the
    # normal async request context. pool_recycle achieves a similar goal
    # (avoid using stale/dead connections) without that bug, by proactively
    # discarding connections older than 30 minutes instead of pinging them.
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()