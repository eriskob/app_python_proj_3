from celery import Celery
from datetime import datetime, timezone
import asyncio
from sqlalchemy import delete
from config import REDIS_HOST, REDIS_PORT
from database import async_session_maker
from links.models import links


celery = Celery(
    "tasks",
    broker=f"redis://{REDIS_HOST}:{REDIS_PORT}",
    backend=f"redis://{REDIS_HOST}:{REDIS_PORT}",
)

celery.conf.beat_schedule = {
    "cleanup-expired-links-every-10-minutes": {
        "task": "tasks.tasks.cleanup_expired_links",
        "schedule": 600.0,
    },
}
celery.conf.timezone = "UTC"

@celery.task(name="tasks.tasks.cleanup_expired_links")
def cleanup_expired_links():
    asyncio.run(_cleanup_expired_links())


async def _cleanup_expired_links():
    async with async_session_maker() as session:
        now = datetime.now(timezone.utc)
        stmt = delete(links).where(links.c.expires_at.is_not(None), links.c.expires_at < now)
        result = await session.execute(stmt)
        await session.commit()

        return result.rowcount or 0