import os
from supabase import create_client, Client
from typing import Optional

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def upload_to_supabase(
    local_path: str,
    bucket: str,
    key: str,
    content_type: str = "application/octet-stream",
    expires_sec: int = 3600,
) -> Optional[str]:
    """
    Sube un fichero a Supabase Storage y devuelve una signed URL.

    NOTA: Evitamos 'upsert=True' porque algunas versiones del client python
    no lo aceptan como kwarg en Storage. Para sobrescribir, primero intentamos
    borrar si existe.
    """
    # Intento de borrado preventivo (si no existe, ignora)
    try:
        supabase.storage.from_(bucket).remove([key])
    except Exception:
        pass

    # Subida
    with open(local_path, "rb") as f:
        # La API python acepta path=file y file=f, más file_options.
        supabase.storage.from_(bucket).upload(
            file=f,
            path=key,
            file_options={"content-type": content_type},
        )

    # Signed URL
    signed = supabase.storage.from_(bucket).create_signed_url(path=key, expires_in=expires_sec)
    # El SDK devuelve dict con 'signedURL' o 'signed_url' según versión:
    return signed.get("signedURL") or signed.get("signed_url")
