import json, pytest
from datetime import timezone
from auth.users import current_active_user, optional_current_user
from links.router import stats_cache_key, url_cache_key


@pytest.mark.asyncio
async def test_create_short_link_anonymous(client, future_dt):
    response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/",
            "expires_at": future_dt.isoformat(),
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["original_url"] == "https://example.com/"
    assert data["short_code"]
    assert data["short_url"].endswith(f"/links/{data['short_code']}")
    assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_create_short_link_with_custom_alias(client, future_dt):
    response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/custom",
            "custom_alias": "string123",
            "expires_at": future_dt.isoformat(),
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["short_code"] == "string123"
    assert data["short_url"].endswith("/links/string123")


@pytest.mark.asyncio
async def test_create_short_link_duplicate_alias(client, create_link, future_dt):
    await create_link(short_code="string123", original_url="https://example.com/already")

    response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/new",
            "custom_alias": "string123",
            "expires_at": future_dt.isoformat(),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "custom alias already exists"


@pytest.mark.asyncio
async def test_create_short_link_expired_at_less_than_current(client, past_dt):
    response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/",
            "expires_at": past_dt.isoformat(),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "expires_at must be in the future"


@pytest.mark.asyncio
async def test_create_short_link_invalid_url(client):
    response = await client.post(
        "/links/shorten",
        json={
            "original_url": "hf2g3f-vghgh",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_short_link_invalid_alias(client):
    response = await client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com/",
            "custom_alias": "!!sdcs123___!!",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_short_link_retries_on_generated_code_collision(client, create_link, monkeypatch):
    await create_link(short_code="dup123", original_url="https://example.com/existing")

    generated = iter(["dup123", "fresh9z"])

    import links.router as router_module

    monkeypatch.setattr(router_module, "generate_short_code", lambda: next(generated))

    response = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/new"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["short_code"] == "fresh9z"


@pytest.mark.asyncio
async def test_create_short_link_generates_code_without_collision(client, monkeypatch):
    import links.router as router_module

    monkeypatch.setattr(router_module, "generate_short_code", lambda: "abc123")

    response = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/plain-generate"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["short_code"] == "abc123"
    assert payload["short_url"].endswith("/links/abc123")


@pytest.mark.asyncio
async def test_search_link_by_original_url_returns_compact_schema(client, create_link):
    await create_link(short_code="s11111", original_url="https://example.com")
    await create_link(short_code="s22222", original_url="https://example.com")

    response = await client.get("/links/search", params={"original_url": "https://example.com"})

    assert response.status_code == 200
    data = response.json()["data"]

    assert len(data) == 2
    assert {item["short_code"] for item in data} == {"s11111", "s22222"}


@pytest.mark.asyncio
async def test_search_unknown_original_url(client):
    response = await client.get("/links/search", params={"original_url": "https://no-such-url.com"})

    assert response.status_code == 200
    assert response.json() == {"data": []}


@pytest.mark.asyncio
async def test_get_link_stats_from_db(client, create_link, fake_redis, future_dt):
    await create_link(
        short_code="stats01",
        original_url="https://example.com/stats",
        click_count=3,
        expires_at=future_dt,
    )

    response = await client.get("/links/stats01/stats")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["short_code"] == "stats01"
    assert data["original_url"] == "https://example.com/stats"
    assert data["click_count"] == 3

    cached = await fake_redis.get(stats_cache_key("stats01"))
    assert cached is not None
    parsed = json.loads(cached)
    assert parsed["short_code"] == "stats01"


@pytest.mark.asyncio
async def test_get_link_stats_cached(client, create_link, fake_redis, future_dt):
    await create_link(
        short_code="stats02",
        original_url="https://example.com/real",
        click_count=1,
        expires_at=future_dt,
    )

    await fake_redis.set(
        stats_cache_key("stats02"),
        json.dumps(
            {
                "short_code": "stats02",
                "original_url": "https://example.com/cached",
                "click_count": 99,
                "created_at": None,
                "last_used_at": None,
                "expires_at": None,
            }
        ),
    )

    response = await client.get("/links/stats02/stats")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["short_code"] == "stats02"
    assert data["original_url"] == "https://example.com/cached"
    assert data["click_count"] == 99


@pytest.mark.asyncio
async def test_get_link_stats_expired_link(client, create_link, fetch_link, past_dt):
    await create_link(short_code="expired1", expires_at=past_dt)

    response = await client.get("/links/expired1/stats")

    assert response.status_code == 404
    assert fetch_link is not None
    link = await fetch_link("expired1")
    assert link is None


@pytest.mark.asyncio
async def test_get_link_stats_cached_expired(
    client, create_link, fake_redis, past_dt
):
    await create_link(
        short_code="expired-cache",
        original_url="https://expired.com",
        expires_at=past_dt,
    )

    await fake_redis.set(
        stats_cache_key("expired-cache"),
        json.dumps(
            {
                "short_code": "expired-cache",
                "original_url": "https://expired.com",
                "click_count": 99,
            }
        ),
    )

    response = await client.get("/links/expired-cache/stats")

    assert response.status_code == 200
    assert response.json()["data"]["short_code"] == "expired-cache"
    assert response.json()["data"]["click_count"] == 99


@pytest.mark.asyncio
async def test_stats_not_found(client):
    response = await client.get("/links/not-exists/stats")

    assert response.status_code == 404
    assert response.json()["detail"] == "not found"


@pytest.mark.asyncio
async def test_redirect_to_original_url_cached(client, create_link, fake_redis, future_dt):
    await create_link(
        short_code="redir01",
        original_url="https://example.com/cached-redirect",
        click_count=10,
        expires_at=future_dt,
    )
    await fake_redis.set(url_cache_key("redir01"), "https://example.com/cached-redirect")
    await fake_redis.set(stats_cache_key("redir01"), json.dumps({"short_code": "redir01"}))

    response = await client.get("/links/redir01", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "https://example.com/cached-redirect"
    assert await fake_redis.get(stats_cache_key("redir01")) is None


@pytest.mark.asyncio
async def test_redirect_to_original_url_db(client, create_link, fake_redis, future_dt, fetch_link):
    await create_link(
        short_code="redir02",
        original_url="https://example.com/db-redirect",
        click_count=1,
        expires_at=future_dt,
    )

    response = await client.get("/links/redir02", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "https://example.com/db-redirect"

    cached = await fake_redis.get(url_cache_key("redir02"))
    assert cached == "https://example.com/db-redirect"

    link = await fetch_link("redir02")
    assert link["click_count"] == 2
    assert link["last_used_at"] is not None


@pytest.mark.asyncio
async def test_redirect_expired_link(client, create_link, fetch_link, past_dt):
    await create_link(short_code="expired2", expires_at=past_dt)

    response = await client.get("/links/expired2", follow_redirects=False)

    assert response.status_code == 404
    link = await fetch_link("expired2")
    assert link is None


@pytest.mark.asyncio
async def test_redirect_not_found(client):
    response = await client.get("/links/not-exists", follow_redirects=False)

    assert response.status_code == 404
    assert response.json()["detail"] == "not found"


@pytest.mark.asyncio
async def test_update_link_owner(app, client, create_link, fetch_link, fake_redis, user_factory):
    owner = user_factory("owner@example.com")
    app.dependency_overrides[current_active_user] = lambda: owner

    await create_link(
        short_code="upd001",
        original_url="https://example.com/old",
        owner_id=owner.id,
    )
    await fake_redis.set(stats_cache_key("upd001"), "stats")
    await fake_redis.set(url_cache_key("upd001"), "url")

    response = await client.put(
        "/links/upd001",
        json={"original_url": "https://example.com/new"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["short_code"] == "upd001"
    assert data["new_original_url"] == "https://example.com/new"

    link = await fetch_link("upd001")
    assert link["original_url"] == "https://example.com/new"
    assert await fake_redis.get(stats_cache_key("upd001")) is None
    assert await fake_redis.get(url_cache_key("upd001")) is None


@pytest.mark.asyncio
async def test_update_link_non_owner(app, client, create_link, user_factory):
    owner = user_factory("owner@example.com")
    stranger = user_factory("stranger@example.com")
    app.dependency_overrides[current_active_user] = lambda: stranger

    await create_link(
        short_code="upd002",
        original_url="https://example.com/old",
        owner_id=owner.id,
    )

    response = await client.put(
        "/links/upd002",
        json={"original_url": "https://example.com/new"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_link_not_found(app, client, user_factory):
    owner = user_factory("owner@example.com")
    app.dependency_overrides[current_active_user] = lambda: owner

    response = await client.put(
        "/links/not-exists",
        json={"original_url": "https://example.com/new"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "not found"


@pytest.mark.asyncio
async def test_delete_link_owner(app, client, create_link, fetch_link, fake_redis, user_factory):
    owner = user_factory("owner@example.com")
    app.dependency_overrides[current_active_user] = lambda: owner

    await create_link(
        short_code="del001",
        original_url="https://example.com/delete",
        owner_id=owner.id,
    )
    await fake_redis.set(stats_cache_key("del001"), "stats")
    await fake_redis.set(url_cache_key("del001"), "url")

    response = await client.delete("/links/del001")

    assert response.status_code == 200
    assert "deleted" in response.json()["data"].lower()

    link = await fetch_link("del001")
    assert link is None
    assert await fake_redis.get(stats_cache_key("del001")) is None
    assert await fake_redis.get(url_cache_key("del001")) is None


@pytest.mark.asyncio
async def test_delete_link_non_owner(app, client, create_link, user_factory):
    owner = user_factory("owner@example.com")
    stranger = user_factory("stranger@example.com")
    app.dependency_overrides[current_active_user] = lambda: stranger

    await create_link(
        short_code="del002",
        original_url="https://example.com/delete",
        owner_id=owner.id,
    )

    response = await client.delete("/links/del002")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_link_not_found(app, client, user_factory):
    owner = user_factory("owner@example.com")
    app.dependency_overrides[current_active_user] = lambda: owner

    response = await client.delete("/links/not-exists")

    assert response.status_code == 404
    assert response.json()["detail"] == "not found"


@pytest.mark.asyncio
async def test_create_short_link_saves_owner(app, client, fetch_link, user_factory):
    owner = user_factory("owner@example.com")
    app.dependency_overrides[optional_current_user] = lambda: owner

    response = await client.post(
        "/links/shorten",
        json={"original_url": "https://example.com/private"},
    )

    assert response.status_code == 200
    short_code = response.json()["data"]["short_code"]

    link = await fetch_link(short_code)
    assert link["owner_id"] == owner.id