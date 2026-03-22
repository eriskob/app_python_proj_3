import json, string, pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from fastapi import HTTPException

from auth.users import get_jwt_strategy
from database import get_async_session
from links.router import generate_short_code, stats_cache_key, url_cache_key
from links.schemas import LinkCreate, LinkUpdate


@pytest.mark.parametrize("length", [4, 6, 12])
def test_generate_short_code_length(length):
    code = generate_short_code(length)
    alphabet = set(string.ascii_letters + string.digits)

    assert len(code) == length
    assert set(code).issubset(alphabet)


def test_generate_short_code_is_not_constant():
    first = generate_short_code(8)
    second = generate_short_code(8)

    assert first != second


def test_generate_short_code_default_length():
    code = generate_short_code()
    assert len(code) == 6


def test_stats_cache_key_format():
    assert stats_cache_key("abc123") == "link_stats:abc123"


def test_url_cache_key_format():
    assert url_cache_key("abc123") == "link_url:abc123"