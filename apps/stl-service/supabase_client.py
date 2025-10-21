# apps/stl-service/supabase_client.py
from __future__ import annotations

import io
import os
from typing import Any, Dict, Optional

from supabase import create_client
try:
    from supabase.lib.client import Client  # type: ignore
except Exception:
    Client = Any  # type: ignore

SUPABASE_URL = (os.getenv("SUPABASE_URL", "") or "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")

_client: Optional[Client] = None


def _ensure_storage_trailing_slash(sb: Client) -> None:
    try:
        if hasattr(sb.storage, "url"):
            u = getattr(sb.storage, "url")
            if isinstance(u, str) and not u.endswith("/"):
                setattr(sb.storage, "url", u + "/")
        if hasattr(sb.storage, "storage_url"):
            su = getattr(sb.storage, "storage_url")
            if isinstance(su, str) and not su.endswith("/"):
                setattr(sb.storage, "storage_url", su + "/")
    except Exception:
        pass


def _get() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError("Supabase ENV vars missing (SUPABASE_URL / SERVICE_KEY)")
        cli = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        _ensure_storage_trailing_slash(cli)
        _client = cli
    return _client


def upload_and_get_url(
    data: bytes | bytearray | io.BytesIO,
    object_path: str,
    *,
    content_type: str = "model/stl",
    cache_control: str = "public, max-age=31536000, immutable",
    expires_in: int = 3600,
) -> Dict[str, Optional[str]]:
    path = (object_path or "").lstrip("/")
    if not path or "/" not in path:
        raise ValueError("object_path must be '<slug>/forge-output.stl'")

    cli = _get()
    store = cli.storage.from_(SUPABASE_BUCKET)

    # Emula upsert sin enviar cabecera booleana x-upsert
    try:
        store.remove([path])
    except Exception:
        pass

    opts = {
        "content-type": content_type,
        "contentType": content_type,
        "cache-control": cache_control,
        "cacheControl": cache_control,
    }
    payload = data.getvalue() if hasattr(data, "getvalue") else bytes(data)  # type: ignore
    store.upload(path, payload, opts)

    signed = store.create_signed_url(path, expires_in)
    signed_url = None
    if isinstance(signed, dict):
        signed_url = signed.get("signedURL") or signed.get("signed_url")
    return {"path": path, "signed_url": signed_url}
