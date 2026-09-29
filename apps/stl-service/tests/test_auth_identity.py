from fastapi import HTTPException
from starlette.requests import Request

import app as forge_app


def _request(headers=None):
    raw = []
    for key, value in (headers or {}).items():
        raw.append((key.lower().encode("latin-1"), value.encode("latin-1")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/generate",
            "headers": raw,
        }
    )


def test_forged_user_headers_are_ignored_without_bearer_token():
    request = _request({"x-user-id": "attacker-chosen-user"})
    assert forge_app._authenticated_user_id(request) is None


def test_verified_bearer_token_returns_supabase_user_id(monkeypatch):
    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "11111111-2222-3333-4444-555555555555"}

    monkeypatch.setattr(forge_app, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(forge_app, "SUPABASE_SERVICE_KEY", "server-only-key")

    import httpx

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: Response())

    request = _request(
        {
            "authorization": "Bearer valid-user-token",
            "x-user-id": "attacker-chosen-user",
        }
    )

    assert (
        forge_app._authenticated_user_id(request)
        == "11111111-2222-3333-4444-555555555555"
    )


def test_invalid_bearer_token_is_rejected(monkeypatch):
    class Response:
        status_code = 401

        @staticmethod
        def json():
            return {}

    monkeypatch.setattr(forge_app, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(forge_app, "SUPABASE_SERVICE_KEY", "server-only-key")

    import httpx

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: Response())

    request = _request({"authorization": "Bearer expired-token"})

    try:
        forge_app._authenticated_user_id(request)
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("Invalid bearer token should be rejected")
