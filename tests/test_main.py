from types import SimpleNamespace
import pytest
from fastapi import FastAPI


def test_main_app_exists():
    import main

    assert main.app is not None
    assert isinstance(main.app, FastAPI)


def test_main_routes():
    from main import app

    routes = {route.path for route in app.routes}

    assert "/links/shorten" in routes
    assert "/links/search" in routes
    assert "/links/{short_code}" in routes
    assert "/links/{short_code}/stats" in routes
    assert "/protected-route" in routes
    assert "/unprotected-route" in routes
    assert "/auth/jwt/login" in routes


def test_unprotected_route_returns_expected_string():
    from main import unprotected_route

    assert unprotected_route() == "Hello, anonym"


def test_protected_route_returns_expected_string():
    from main import protected_route

    user = SimpleNamespace(email="user@example.com")

    assert protected_route(user) == "Hello, user@example.com"