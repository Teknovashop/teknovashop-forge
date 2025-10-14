# apps/stl-service/supabase_client.py
from __future__ import annotations

import io
import os
import mimetypes
from typing import Optional

try:
    # supabase-py v2
    from supabase import create_client, Client  # type: ignore
except Exception as e:
    raise RuntimeError("Supabase client not installed in the image") from e


def _ensure_trailing_slash(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    return url if url.endswith("/") else url + "/"


# Config
_SUPABASE_URL = _ensure_trailing_slash(os.getenv("SUPABASE_URL", ""))
# service key (server-side). En tus envs puede llamarse SERVICE_ROLE_KEY o SERVICE_KEY
_SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_SECRET_KEY")
    or os.getenv("SUPABASE_ANON_KEY")  # último recurso (no recomendado para servidor)
    or ""
)

if not _SUPABASE_URL or not _SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL o SUPABASE_SERVICE_* no configurado. "
        "Revisa variables en Render: SUPABASE_URL (con barra final opcional) y SUPABASE_SERVICE_ROLE_KEY."
    )

# Crear cliente (el SDK ya compone storage/v1 internamente)
_client: Client = create_client(_SUPABASE_URL, _SUPABASE_KEY)


def _guess_content_type(object_key: str) -> str:
    ctype, _ = mimetypes.guess_type(object_key)
    if ctype:
        return ctype
    # Mapas comunes del proyecto
    if object_key.lower().endswith(".stl"):
        return "model/stl"
    if object_key.lower().endswith(".png"):
        return "image/png"
    if object_key.lower().endswith(".svg"):
        return "image/svg+xml"
    return "application/octet-stream"


def upload_and_get_url(
    fileobj: io.BytesIO,
    object_key: str,
    bucket: str = "forge-stl",
    public: bool = False,
    content_type: Optional[str] = None,
) -> str:
    """
    Sube el buffer a Supabase Storage (upsert=True) y devuelve URL pública o firmada.
    - Asegura barra final en SUPABASE_URL (evita 'Storage endpoint URL should have a trailing slash').
    - Fija content-type correcto (model/stl, image/png, image/svg+xml, ...).
    """
    if not object_key:
        raise ValueError("object_key vacío")

    path = object_key.lstrip("/")
    fileobj.seek(0)
    data = fileobj.read()
    fileobj.seek(0)

    ctype = content_type or _guess_content_type(object_key)

    # Subir con upsert para no romper flujos si repetimos nombre
    _client.storage.from_(bucket).upload(
        path=path,
        file=data,
        file_options={"content-type": ctype, "upsert": True},
    )

    if public:
        # URL pública directa
        pub = _client.storage.from_(bucket).get_public_url(path)
        if isinstance(pub, dict):
            # algunas versiones devuelven {"publicUrl": "..."}
            return pub.get("publicUrl") or pub.get("public_url") or ""
        return pub  # string en otras versiones
    else:
        # URL firmada (7 días)
        signed = _client.storage.from_(bucket).create_signed_url(path, 60 * 60 * 24 * 7)
        if isinstance(signed, dict):
            # distintas claves según versión
            return signed.get("signedURL") or signed.get("signed_url") or signed.get("data", {}).get("signedURL", "")
        return signed  # string en otras versiones
