# apps/stl-service/_helpers.py
from __future__ import annotations

import os
import io
import typing as t

from supabase import create_client, Client  # supabase-py v2

# -------------------------------------------------------------------
#  Supabase client (Service Role) – se crea una única vez por proceso
# -------------------------------------------------------------------

_SUPABASE: Client | None = None


def get_supabase() -> Client:
    global _SUPABASE
    if _SUPABASE is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")  # SERVICE ROLE KEY (no la anon)
        if not url or not key:
            raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en el entorno")
        _SUPABASE = create_client(url, key)
    return _SUPABASE


def get_bucket_name() -> str:
    return os.environ.get("SUPABASE_BUCKET", "forge-stl")


# -------------------------------------------------------------------
#  Subida y firma de STL
# -------------------------------------------------------------------

def upload_and_sign_stl(
    *,
    path: str,
    data: bytes | io.BytesIO | memoryview,
    content_type: str = "model/stl",
    expires_seconds: int = 60 * 60,
) -> str:
    """
    Sube el binario a Storage y devuelve una URL firmada temporal.
    - path: 'modelo_underscored/uuid.stl' (SIN barra inicial)
    - data: bytes del STL
    """
    sb = get_supabase()
    bucket = get_bucket_name()
    storage = sb.storage

    # normalizamos la ruta (sin barra inicial)
    path = path.lstrip("/")

    # convertimos stream a bytes si hace falta
    if hasattr(data, "getvalue"):
        data = t.cast(io.BytesIO, data).getvalue()
    elif isinstance(data, memoryview):
        data = data.tobytes()

    print(f"[upload] bucket='{bucket}' put path='{path}'")
    # IMPORTANTE: upsert=True y contentType
    storage.from_(bucket).upload(
        path,
        data,  # bytes
        {"contentType": content_type, "upsert": True},
    )

    print(f"[upload] sign path='{path}'")
    signed = storage.from_(bucket).create_signed_url(path, expires_seconds)

    # la librería puede devolver distintas formas según versión
    # intentamos obtener la URL de manera robusta:
    url: str | None = None
    if isinstance(signed, dict):
        url = (
            signed.get("signedURL")
            or signed.get("signed_url")
            or (signed.get("data") or {}).get("signedURL")
            or (signed.get("data") or {}).get("signed_url")
        )
    if not url:
        # algunas versiones devuelven str directamente
        if isinstance(signed, str):
            url = signed

    if not url:
        raise RuntimeError(f"No se pudo obtener URL firmada para '{path}' (respuesta: {signed!r})")

    print(f"[upload] signed URL -> {url}")
    return url
