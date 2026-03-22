import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASS", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")

from auth.db import Base
from auth.users import current_active_user, optional_current_user
from database import get_async_session
from links.models import links
from links.router import router as links_router


class FakeResult:
    def __init__(self, first_value=None, all_value=None):
        self._first_value = first_value
        self._all_value = all_value if all_value is not None else []

    def mappings(self):
        return self

    def first(self):
        return self._first_value

    def all(self):
        return self._all_value


class FakeSession:
    def __init__(self, execute_results=None):
        self.execute_results = list(execute_results or [])
        self.executed = []
        self.commits = 0

    async def execute(self, stmt):
        self.executed.append(stmt)
        if self.execute_results:
            return self.execute_results.pop(0)
        return FakeResult()

    async def commit(self):
        self.commits += 1


class FakeRedis:
    def __init__(self):
        self.storage: dict[str, str] = {}
        self.ttl: dict[str, int | None] = {}

    async def get(self, key: str):
        return self.storage.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.storage[key] = value
        self.ttl[key] = ex
        return True

    async def delete(self, *keys: str):
        deleted = 0
        for key in keys:
            if key in self.storage:
                deleted += 1
                self.storage.pop(key, None)
                self.ttl.pop(key, None)
        return deleted

    async def close(self):
        return None


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture
def session_maker(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_maker):
    async with session_maker() as session:
        yield session


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def app(session_maker, fake_redis):
    app = FastAPI()
    app.include_router(links_router)
    app.state.redis = fake_redis

    async def override_get_async_session():
        async with session_maker() as session:
            yield session

    async def override_optional_current_user():
        return None

    async def override_current_active_user():
        return SimpleNamespace(id=uuid4(), email="user@example.com")

    app.dependency_overrides[get_async_session] = override_get_async_session
    app.dependency_overrides[optional_current_user] = override_optional_current_user
    app.dependency_overrides[current_active_user] = override_current_active_user

    return app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def user_factory():
    def _make_user(email: str = "user@example.com"):
        return SimpleNamespace(id=uuid4(), email=email)

    return _make_user


@pytest_asyncio.fixture
async def create_link(session_maker):
    async def _create_link(
        *,
        original_url: str = "https://example.com/",
        short_code: str = "abc123",
        owner_id=None,
        click_count: int = 0,
        created_at: datetime | None = None,
        last_used_at: datetime | None = None,
        expires_at: datetime | None = None,
    ):
        created_at = created_at or datetime.now(timezone.utc)
        async with session_maker() as session:
            await session.execute(
                insert(links).values(
                    original_url=original_url,
                    short_code=short_code,
                    owner_id=owner_id,
                    click_count=click_count,
                    created_at=created_at,
                    last_used_at=last_used_at,
                    expires_at=expires_at,
                )
            )
            await session.commit()
        return short_code

    return _create_link


@pytest_asyncio.fixture
async def fetch_link(session_maker):
    async def _fetch_link(short_code: str):
        async with session_maker() as session:
            result = await session.execute(select(links).where(links.c.short_code == short_code))
            return result.mappings().first()

    return _fetch_link


@pytest.fixture
def future_dt():
    return datetime.now(timezone.utc) + timedelta(days=1)


@pytest.fixture
def past_dt():
    return datetime.now(timezone.utc) - timedelta(days=1)
