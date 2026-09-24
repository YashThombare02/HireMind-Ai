import uuid
from collections.abc import AsyncGenerator

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.config import settings
from app.db.models import Base
from app.db.session import get_async_session
from app.main import app
from app.rate_limit import limiter

# Same Postgres server as the dev DB, separate database — avoids the dev
# database being wiped/polluted by test runs. Auto-created if missing so
# there's no manual setup step blocking `pytest` from working.
TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/hireminds_test"


def _ensure_test_database_exists() -> None:
    sync_url = TEST_DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    db_name = sync_url.rsplit("/", 1)[1]
    maintenance_url = sync_url.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(maintenance_url, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{db_name}"')


@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    _ensure_test_database_exists()
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """One test = one outer transaction that's always rolled back, so tests
    never leak state into each other even when the app code under test calls
    session.commit() (that only commits an inner savepoint)."""
    connection = await test_engine.connect()
    outer_transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")

    yield session

    await session.close()
    await outer_transaction.rollback()
    await connection.close()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_async_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_async_session
    # Explicit client address so slowapi's get_remote_address (used for rate
    # limiting) has something to key on under ASGITransport.
    transport = ASGITransport(app=app, client=("127.0.0.1", 12345))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Every test shares the same fake client IP (127.0.0.1), so without a
    reset the in-memory rate limiter would leak hit-counts across unrelated
    tests and cause flaky, order-dependent 429s."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture
def sample_skills() -> list[str]:
    return ["python", "fastapi", "sql", "react", "docker"]
