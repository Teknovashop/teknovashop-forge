# apps/stl-service/supabase_client.py
from __future__ import annotations

import io
import os
from typing import Any, Dict, Optional

from supabase import create_client
try:
    # Algunas versiones exponen Client aquí
    from supabase.lib.client import Client  # type: ignore
except Exception:  # compatibilidad
    Client = Any  # type: ignore

# ---------------- Config ----------------
SUPABASE_URL = (os.getenv("SUPABASE_URL", "") or "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")

_client: Optional[Client] = None


def _ensure_storage_trailing_slash(sb: Client) -> None:
    """
    Algunas builds del SDK esperan que el storage endpoint termine en '/'.
    Forzamos el trailing slash sin fallar si el atributo no existe.
    """
    try:
        if hasattr(sb.storage, "url"):
            url = getattr(sb.storage, "url")
            if isinstance(url, str) and not url.endswith("/"):
                setattr(sb.storage, "url", url + "/")
        if hasattr(sb.storage, "storage_url"):
            s_url = getattr(sb.storage, "storage_url")
            if isinstance(s_url, str) and not s_url.endswith("/"):
                setattr(sb.storage, "storage_url", s_url + "/")
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
    """
    Sube el STL y devuelve { path, signed_url }.
    - Evita usar 'upsert' (que dispara el error de la cabecera booleana).
    - Si el objeto ya existe, se elimina antes (equivalente a upsert).
    - 'object_path' debe ser relativo al bucket, p.ej. 'vesa-adapter/forge-output.stl'
    """
    path = (object_path or "").lstrip("/")
    if not path or "/" not in path:
        raise ValueError("object_path must be '<slug>/forge-output.stl'")

    cli = _get()
    store = cli.storage.from_(SUPABASE_BUCKET)

    # 1) Borrar si existe (emula upsert)
    try:
        store.remove([path])
    except Exception:
        # Si no existe, ignoramos
        pass

    # 2) Subir sin 'upsert'
    #   El SDK acepta varias claves; cubrimos ambas para compat:
    #   - "content-type" / "contentType"
    #   - "cache-control" / "cacheControl"
    file_opts = {
        "content-type": content_type,
        "contentType": content_type,
        "cache-control": cache_control,
        "cacheControl": cache_control,
        # NO poner 'upsert': True  <- causa la cabecera booleana y el 500
    }

    payload = data.getvalue() if hasattr(data, "getvalue") else bytes(data)  # type: ignore
    store.upload(path, payload, file_opts)

    # 3) Firmar URL
    signed = store.create_signed_url(path, expires_in)
    signed_url = None
    if isinstance(signed, dict):
        signed_url = signed.get("signedURL") or signed.get("signed_url")

    return {"path": path, "signed_url": signed_url}
