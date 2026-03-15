import random
import string
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select, insert, update, delete

from auth.db import User
from auth.users import current_active_user, optional_current_user
from database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

from .models import links
from .schemas import LinkCreate, LinkUpdate, LinkSearchResponseSchema


router = APIRouter(
    prefix="/links",
    tags=["Links"],
)


def generate_short_code(length: int = 6) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=length))


async def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def stats_cache_key(short_code: str) -> str:
    return f"link_stats:{short_code}"


def url_cache_key(short_code: str) -> str:
    return f"link_url:{short_code}"


async def clear_link_cache(redis: Redis, short_code: str):
    await redis.delete(stats_cache_key(short_code))
    await redis.delete(url_cache_key(short_code))


@router.post("/shorten")
async def create_short_link(new_link: LinkCreate, request: Request, session: AsyncSession = Depends(get_async_session), user: Optional[User] = Depends(optional_current_user)):
    now = datetime.now(timezone.utc)

    if new_link.expires_at is not None and new_link.expires_at <= now:
        raise HTTPException(status_code=400, detail="expires_at must be in the future")

    short_code = new_link.custom_alias

    if short_code:
        existing_alias_query = select(links).where(links.c.short_code == short_code)
        existing_alias_result = await session.execute(existing_alias_query)
        existing_alias = existing_alias_result.mappings().first()

        if existing_alias:
            raise HTTPException(status_code=400, detail="custom alias already exists")
    else:
        while True:
            candidate = generate_short_code()
            check_query = select(links).where(links.c.short_code == candidate)
            check_result = await session.execute(check_query)
            exists = check_result.mappings().first()

            if not exists:
                short_code = candidate
                break

    statement = insert(links).values(
        original_url=str(new_link.original_url),
        short_code=short_code,
        owner_id=user.id if user else None,
        click_count=0,
        created_at=now,
        last_used_at=None,
        expires_at=new_link.expires_at,
    )

    await session.execute(statement)
    await session.commit()

    base_url = str(request.base_url).rstrip("/")

    return {
        "data": {
            "short_code": short_code,
            "short_url": f"{base_url}/links/{short_code}",
            "original_url": str(new_link.original_url),
            "expires_at": new_link.expires_at,
        },
    }


@router.get("/search", response_model=LinkSearchResponseSchema)
async def search_link_by_original_url(original_url: str, session: AsyncSession = Depends(get_async_session)):
    query = select(links).where(links.c.original_url == original_url)
    result = await session.execute(query)
    found_links = result.mappings().all()

    return LinkSearchResponseSchema(data=found_links)


@router.get("/{short_code}/stats")
async def get_link_stats(
    short_code: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    redis: Redis = await get_redis(request)

    cached_stats = await redis.get(stats_cache_key(short_code))
    if cached_stats:
        return {
            "data": json.loads(cached_stats),
        }


    query = select(links).where(links.c.short_code == short_code)
    result = await session.execute(query)
    link = result.mappings().first()

    if not link:
        raise HTTPException(status_code=404, detail="not found")

    if link["expires_at"] and link["expires_at"] <= datetime.now(timezone.utc):
        delete_query = delete(links).where(links.c.short_code == short_code)
        await session.execute(delete_query)
        await session.commit()
        await clear_link_cache(redis, short_code)
        raise HTTPException(status_code=404, detail="link has expired or been deleted")

    data = {
        "original_url": link["original_url"],
        "short_code": link["short_code"],
        "created_at": link["created_at"].isoformat(),
        "click_count": link["click_count"],
        "last_used_at": link["last_used_at"].isoformat() if link["last_used_at"] else None,
        "expires_at": link["expires_at"].isoformat() if link["expires_at"] else None,
    }

    await redis.set(stats_cache_key(short_code), json.dumps(data), ex=300)

    return {
        "data": data,
    }


@router.get("/{short_code}")
async def redirect_to_original_url(
    short_code: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    redis: Redis = await get_redis(request)
    now = datetime.now(timezone.utc)

    cached_url = await redis.get(url_cache_key(short_code))
    if cached_url:
        update_stmt = (update(links).where(links.c.short_code == short_code).values(click_count=links.c.click_count + 1, last_used_at=now))
        await session.execute(update_stmt)
        await session.commit()
        await redis.delete(stats_cache_key(short_code))
        return RedirectResponse(url=cached_url)

    query = select(links).where(links.c.short_code == short_code)
    result = await session.execute(query)
    link = result.mappings().first()

    if not link:
        raise HTTPException(status_code=404, detail="not found")

    if link["expires_at"] and link["expires_at"] <= now:
        delete_query = delete(links).where(links.c.short_code == short_code)
        await session.execute(delete_query)
        await session.commit()
        await clear_link_cache(redis, short_code)
        raise HTTPException(status_code=404, detail="link has expired or been deleted")

    update_stmt = (update(links).where(links.c.short_code == short_code).values(click_count=links.c.click_count + 1,last_used_at=now))
    await session.execute(update_stmt)
    await session.commit()
    await redis.set(url_cache_key(short_code), link["original_url"], ex=300)
    await redis.delete(stats_cache_key(short_code))

    # print(f"Redirecting to {link['original_url']}")
    return RedirectResponse(url=link["original_url"])


@router.put("/{short_code}")
async def update_link(
    short_code: str,
    link_update: LinkUpdate,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    query = select(links).where(links.c.short_code == short_code)
    result = await session.execute(query)
    link = result.mappings().first()

    if not link:
        raise HTTPException(status_code=404, detail="not found")

    if link["owner_id"] != user.id:
        raise HTTPException(status_code=403,detail="can only modify your own links")

    stmt = (update(links).where(links.c.short_code == short_code).values(original_url=str(link_update.original_url)))

    await session.execute(stmt)
    await session.commit()

    redis: Redis = await get_redis(request)
    await clear_link_cache(redis, short_code)

    return {
        "data": {
            "short_code": short_code,
            "new_original_url": str(link_update.original_url),
        },
    }


@router.delete("/{short_code}")
async def delete_link(
    short_code: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    query = select(links).where(links.c.short_code == short_code)
    result = await session.execute(query)
    link = result.mappings().first()

    if not link:
        raise HTTPException(status_code=404, detail="not found")

    if link["owner_id"] != user.id:
        raise HTTPException(status_code=403, detail="can only delete your own links")

    stmt = delete(links).where(links.c.short_code == short_code)
    await session.execute(stmt)
    await session.commit()

    redis: Redis = await get_redis(request)
    await clear_link_cache(redis, short_code)

    return {
        "data": f"Link {short_code} deleted",
    }