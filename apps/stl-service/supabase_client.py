# apps/stl-service/supabase_client.py
import os
import time
from typing import Optional, Union

try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = None  # type: ignore[assignment]


def _env(name: str, fallback: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None or f"{v}".strip() == "":
        return fallback
    return f"{v}".strip()


def _ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else url + "/"


def get_client() -> "Client":
    """
    Crea el cliente de Supabase usando credenciales de servidor.
    Prioriza variables privadas si existen; si no, usa las públicas.
    """
    url = _env("SUPABASE_URL") or _env("NEXT_PUBLIC_SUPABASE_URL")
    key = _env("SUPABASE_SERVICE_ROLE_KEY") or _env("SUPABASE_ANON_KEY") or _env("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    if not url or not key:
        raise RuntimeError("SUPABASE_URL o SUPABASE_*_KEY no configurados")

    url = _ensure_trailing_slash(url)

    if create_client is None:
        raise RuntimeError("Paquete 'supabase' no disponible en el runtime")

    return create_client(url, key)


def upload_and_get_url(
    fileobj_or_bytes: Union[bytes, "io.BytesIO", "memoryview", any],
    *,
    filename: str,
    folder: str = "stl",
    bucket: Optional[str] = None,
    sign_seconds: int = 7 * 24 * 3600,
) -> dict:
    """
    Sube bytes o file-like a Supabase Storage y devuelve una URL firmada.
    - Acepta directamente `bytes` o cualquier objeto con `.read()`.
    - Usa `bucket` de env si no se pasa (NEXT_PUBLIC_SUPABASE_BUCKET o SUPABASE_BUCKET).
    """
    # --- datos ---
    if isinstance(fileobj_or_bytes, (bytes, memoryview)):
        data = bytes(fileobj_or_bytes)
    elif hasattr(fileobj_or_bytes, "read"):
        data = fileobj_or_bytes.read()  # type: ignore[attr-defined]
    else:
        raise TypeError("upload_and_get_url: se esperaban bytes o un objeto con .read()")

    if not data:
        raise ValueError("upload_and_get_url: no hay datos para subir")

    bucket = bucket or _env("SUPABASE_BUCKET") or _env("NEXT_PUBLIC_SUPABASE_BUCKET") or "forge-stl"
    client = get_client()
    storage = client.storage.from_(bucket)

    # ruta única por carpeta
    # (evita colisiones cuando se repite el nombre)
    epoch = int(time.time())
    path = f"{folder.strip('/')}/{epoch}-{filename}".replace("//", "/")

    # sube con upsert para no fallar por nombres repetidos
    storage.upload(path, data, {"contentType": "application/sla", "upsert": "true"})

    # URL firmada (fallback: pública)
    try:
        signed = storage.create_signed_url(path, sign_seconds)
        url = signed.get("signedURL") or signed.get("signed_url") or signed.get("signedUrl")
    except Exception:
        url = storage.get_public_url(path)

    return {"path": path, "url": url}
