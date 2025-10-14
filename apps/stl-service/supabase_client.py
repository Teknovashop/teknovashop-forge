# apps/stl-service/supabase_client.py
import os
from typing import IO, Optional

# Usamos el cliente oficial; él construye bien el storage endpoint
from supabase import create_client, Client


def _get_supabase() -> Client:
    """
    Crea el cliente oficial de Supabase con la SERVICE ROLE KEY.
    - Normaliza la URL (sin doble slash).
    - Evita construir manualmente el endpoint de storage (no aparece el warning del trailing slash).
    """
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_ANON_KEY")  # último fallback; mejor evitarlo para escribir
    )
    if not url or not key:
        raise RuntimeError("Faltan SUPABASE_URL o SERVICE ROLE KEY en el entorno.")
    return create_client(url, key)


def _guess_content_type(object_key: str) -> str:
    k = object_key.lower()
    if k.endswith(".stl"):
        return "model/stl"
    if k.endswith(".png"):
        return "image/png"
    if k.endswith(".svg"):
        return "image/svg+xml"
    if k.endswith(".jpg") or k.endswith(".jpeg"):
        return "image/jpeg"
    return "application/octet-stream"


def upload_and_get_url(
    file_obj: IO[bytes],
    object_key: str,
    bucket: str = "forge-stl",
    public: bool = False,
    expires_in: int = 300,  # segundos, si no es público
) -> str:
    """
    Sube un fichero a Supabase Storage y devuelve URL:
      - Si 'public' → public_url
      - Si no, signed_url con expiración.

    ¡OJO! No uses headers booleanos. Usa 'file_options={"upsert": True}'.
    """
    sb = _get_supabase()

    # Normaliza la ruta y el content-type
    path = object_key.lstrip("/")
    content_type = _guess_content_type(path)

    # SUBIR (sin tocar headers; dejamos que la lib convierta 'upsert' correctamente)
    sb.storage.from_(bucket).upload(
        path=path,
        file=file_obj,
        file_options={
            "contentType": content_type,
            "upsert": True,              # ← correcto (NO meter "x-upsert": True en headers)
            # "cacheControl": "3600",    # opcional
        },
    )

    # URL
    if public:
        return sb.storage.from_(bucket).get_public_url(path)
    else:
        signed = sb.storage.from_(bucket).create_signed_url(path, expires_in)
        # compat: algunas versiones devuelven 'signedURL' y otras 'signedUrl'
        return signed.get("signedURL") or signed.get("signedUrl") or ""
